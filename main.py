import json, os
from datetime import datetime
from agents.news_collector import collect as collect_rss
from agents.news_api import fetch_newsapi
from agents.news_gpt import analyze_news_gpt
from agents.delta_one import fetch_deltaone
from agents.price_feed import get_technical_data
from agents.price_history_av import fetch_ohlcv
from agents.signal_engine import get_signal_from_mt5, format_signal_summary
from agents.technical_analyst import analyze as tech_analyze
from agents.risk_manager import calculate as risk_calc  # tech_signal based
from agents.news_filter import analyze as news_filter_analyze
from agents.macro_filter import check as macro_filter_check
from agents.arbitrator import decide as arbitrate
from agents.ftmo_validator import validate_before_trade
from utils.fred_data import get_all as fred_get_all
from utils.state_manager import save_cycle, load_history
from utils.github_sync import sync
from utils.position_sync import sync_mt5_positions, get_mt5_account
from utils.market_hours import is_market_open
from gen_dashboard import generate as gen_html
from portfolio import add_position, get_stats
from config import MAX_POSITIONS

MT5_ENABLED  = True
MT5_LOGIN    = 1513020113
MT5_PASSWORD = "FH2dXFt7?"
MT5_SERVER   = "FTMO-Demo"

def run_cycle():
    print()
    print("=" * 52)
    print("AURUM CYCLE --", datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 52)

    # ── Sync MT5 positions ─────────────────────────────────
    try:
        synced  = sync_mt5_positions()
        mt5_acc = get_mt5_account()
        if synced:
            for s in synced:
                print("[sync] ticket=" + str(s["ticket"]) + " PnL=$" + str(s["pnl"]) + " " + s["result"])
        if mt5_acc:
            print("[MT5] Balance:$" + str(mt5_acc.get("balance","--")) +
                  " Equity:$"  + str(mt5_acc.get("equity","--")) +
                  " Profit:$"  + str(mt5_acc.get("profit","--")))
    except Exception as e:
        print("[sync] error:", e)

    stats = get_stats()
    print("[portfolio] Equity:$" + str(stats["equity"]) +
          " Open:" + str(stats["open_positions"]) + "/" + str(MAX_POSITIONS))
    if stats["open_positions"] >= MAX_POSITIONS:
        print("[portfolio] MAX positions reached")
        return None

    # ── 1. Technical signal ────────────────────────────────
    print("[1/7] Technical signal (EMA+RSI+ADX)...")
    tech_signal, d1_candles = get_signal_from_mt5(verbose=False)
    if tech_signal:
        print("      Signal: " + format_signal_summary(tech_signal))
    else:
        print("      No technical setup right now")

    # Cache D1 history
    try:
        fetch_ohlcv()
    except Exception as e:
        print("      [history]", e)

    # ── 2. News ────────────────────────────────────────────
    print("[2/7] Collecting news...")
    rss   = collect_rss()
    api   = fetch_newsapi()
    try:
        delta = fetch_deltaone()
        if delta:
            print("      [DeltaOne] " + str(len(delta)) + " items:")
            for d in delta[:6]:
                tag = "BREAK" if d.get("breaking") else ("GOLD" if d.get("relevant") else "----")
                print("      [" + tag + "] " + d["title"][:80])
    except Exception as e:
        delta = []
        print("      [DeltaOne] unavailable:", e)

    all_items = list({
        i["title"]: i
        for i in rss.get("news_items", []) + api + delta
    }.values())[:30]

    gpt = analyze_news_gpt(all_items)
    if gpt:
        news = gpt
        news["news_items"] = all_items
        print("      [GPT] Sentiment:" + str(gpt.get("sentiment")) +
              " conf:" + str(gpt.get("confidence")) + "%")
    else:
        news = rss
        news["news_items"] = all_items

    print("      Total:" + str(len(all_items)) +
          " Sentiment:" + str(news.get("sentiment")))
    for i in all_items[:5]:
        print("      >> [" + i["source"] + "] " + i["title"][:70])

    # ── 3. FRED macro data ─────────────────────────────────
    print("[3/7] FRED macro data...")
    fred = fred_get_all()
    print("      " + str(fred.get("summary", "unavailable")))

    # ── 4. Price feed ──────────────────────────────────────
    print("[4/7] Price feed...")
    price = get_technical_data()
    print("      XAU/USD:" + str(price.get("price")) +
          " Chg:" + str(price.get("change_pct")) + "%" +
          " H:" + str(price.get("high")) +
          " L:" + str(price.get("low")) +
          " [" + str(price.get("source","")) + "]")

    # ── 5. Technical analysis (indicators) ─────────────────
    print("[5/7] Technical analysis...")
    tech = tech_analyze(price, d1_candles)
    print("      Trend:" + str(tech.get("trend")) +
          " RSI:" + str(tech.get("rsi_value")) +
          " ADX:" + str(tech.get("adx")) +
          " S:" + str(tech.get("support")) +
          " R:" + str(tech.get("resistance")))

    # ── 6. News filter + Macro filter ──────────────────────
    print("[6/7] News filter + Macro filter...")

    # News filter
    if tech_signal:
        direction   = tech_signal["signal"]
        delta_items = [i for i in all_items if i.get("source") == "DeltaOne"]
        other_items = [i for i in all_items if i.get("source") != "DeltaOne"]
        news_verdict = news_filter_analyze(direction, other_items, fred, delta_items)
        print("      [News] " + news_verdict["verdict"] +
              " (" + str(news_verdict["confidence"]) + "%) — " +
              news_verdict["reason"][:80])
    else:
        direction    = "LONG"
        news_verdict = {"verdict": "NEUTRAL", "confidence": 50,
                        "reason": "No technical signal to evaluate"}
        print("      [News] NEUTRAL — no technical signal")

    # ── 7. Risk + Arbitrator ───────────────────────────────
    print("[7/7] Risk + Arbitrator...")
    account_info = None
    if MT5_ENABLED:
        try:
            from agents.mt5_broker import connect, get_account_summary, disconnect
            if connect(MT5_LOGIN, MT5_PASSWORD, MT5_SERVER):
                account_info = get_account_summary()
                disconnect()
        except Exception as e:
            print("      [MT5]", e)

    # Macro filter (needs account_info for FTMO checks)
    macro_verdict = macro_filter_check(direction, fred, account_info, daily_pnl=0.0)
    print("      [Macro] " + macro_verdict["verdict"] +
          " | size_mult=" + str(macro_verdict["size_multiplier"]))
    for w in macro_verdict.get("warnings", []):
        print("      [Macro] WARN: " + w)
    for r in macro_verdict.get("reasons", []):
        print("      [Macro] VETO: " + r)

    # Risk management
    risk = risk_calc(
        tech_signal,
        price,
        account_info.get("balance") if account_info else None
    )
    if risk.get("valid"):
        print("      Risk:" + str(risk.get("direction")) +
              " RR=" + str(risk.get("risk_reward")) +
              " $" + str(risk.get("risk_usd")) +
              " Lots=" + str(risk.get("contracts")))
    else:
        print("      Risk INVALID:" + str(risk.get("reason")))

    # Apply size multiplier from macro filter
    if macro_verdict.get("size_multiplier", 1.0) < 1.0 and risk.get("valid"):
        mult = macro_verdict["size_multiplier"]
        risk["contracts"] = round(risk.get("contracts", 0.01) * mult, 2)
        risk["risk_usd"]  = round(risk.get("risk_usd", 0) * mult, 2)
        print("      [Macro] Size reduced to " + str(mult*100) + "% — lots=" + str(risk["contracts"]))

    # Arbitrator
    final    = arbitrate(tech_signal, news_verdict, macro_verdict, risk)
    decision = final.get("decision")

    print()
    print(">>> DECISION: " + decision + " conf:" + str(final.get("confidence")) + "%")
    print("    " + str(final.get("reason", "")))

    # ── Execute order ──────────────────────────────────────
    ticket = None
    if risk.get("valid") and decision in ("LONG", "SHORT"):
        from utils.market_hours import is_market_open
        mkt_open, mkt_reason = is_market_open()
        print("    [Market] " + mkt_reason)
        if not mkt_open:
            print("    [MT5] Market closed — order skipped")
            try:
                from utils.telegram_alerts import send
                send("AURUM: " + decision + " signal @ $" + str(price.get("price")) +
                     " — market closed\n" + mkt_reason)
            except: pass
        elif MT5_ENABLED:
            print("    Entry:$" + str(risk.get("entry")) +
                  " SL:$" + str(risk.get("stop_loss")) +
                  " TP:$" + str(risk.get("take_profit")) +
                  " Lots:" + str(risk.get("contracts")))
            try:
                from agents.mt5_broker import connect, open_trade, disconnect
                if connect(MT5_LOGIN, MT5_PASSWORD, MT5_SERVER):
                    r = open_trade(
                        decision,
                        max(0.01, round(risk["contracts"], 2)),
                        risk["stop_loss"],
                        risk["take_profit"]
                    )
                    if r:
                        ticket = r["ticket"]
                        print("    [MT5] ORDER PLACED ticket=" + str(ticket))
                    disconnect()
            except Exception as e:
                print("    [MT5] Error:", e)

    # ── Save cycle ─────────────────────────────────────────
    cycle_data = {
        "ts":           datetime.now().isoformat(),
        "price":        price.get("price"),
        "change_pct":   price.get("change_pct"),
        "decision":     decision,
        "confidence":   final.get("confidence"),
        "reason":       final.get("reason"),
        "risk_plan":    risk,
        "mt5_ticket":   ticket,
        "news_items":   all_items[:10],
        "fred":         fred,
        "ftmo_status":  macro_verdict.get("ftmo", {}),
        "tech_signal":  tech_signal,
        "news_verdict": news_verdict,
        "macro_verdict":{"verdict": macro_verdict["verdict"],
                         "size_multiplier": macro_verdict["size_multiplier"]},
        "technical": {
            "trend":      tech.get("trend"),
            "rsi_value":  tech.get("rsi_value"),
            "rsi_zone":   tech.get("rsi_zone"),
            "adx":        tech.get("adx"),
            "support":    tech.get("support"),
            "resistance": tech.get("resistance"),
            "sma20":      tech.get("sma20"),
            "ema9":       tech.get("ema9"),
            "ema21":      tech.get("ema21"),
            "ema50":      tech.get("ema50"),
            "bias":       tech.get("bias"),
        },
        "debate_summary": {
            "winner":    tech_signal["signal"] if tech_signal else "NONE",
            "bull_conf": tech_signal["confidence"] if tech_signal else 0,
            "bear_conf": 0,
            "margin":    100 if tech_signal else 0,
            "is_tie":    tech_signal is None,
        },
        "macro": {
            "bias":       fred.get("macro_bias", "NEUTRAL"),
            "confidence": 65,
            "drivers":    [],
        },
        "portfolio": stats,
    }

    if decision in ("LONG", "SHORT") and risk.get("valid"):
        add_position(cycle_data, ticket=ticket)
        print("    [portfolio] Position recorded")

    folder = save_cycle(cycle_data)
    gen_html(latest=cycle_data, history=load_history(), stats=stats)
    print("[SAVED]", folder)

    try:
        from utils.telegram_alerts import alert_decision
        alert_decision(cycle_data)
    except Exception as e:
        print("[telegram]", e)

    try:
        from training.feedback import sync_closed_positions
        insights, patterns = sync_closed_positions()
        if insights:
            print("[training]", insights[0])
    except Exception as e:
        print("[training]", e)

    sync("AURUM: " + decision + " @ " + str(price.get("price")))
    return cycle_data

if __name__ == "__main__":
    run_cycle()
