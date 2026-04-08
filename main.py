import json, os
from datetime import datetime
from agents.news_collector import collect as collect_rss
from agents.news_api import fetch_newsapi
from agents.news_gpt import analyze_news_gpt
from agents.price_feed import get_technical_data
from agents.price_history_av import fetch_ohlcv
from agents.macro_analyst import analyze as macro_analyze
from agents.technical_analyst import analyze as tech_analyze
from agents.debate import run_debate
from agents.risk_manager import calculate as risk_calc
from agents.arbitrator import decide
from agents.ftmo_validator import validate_before_trade
from utils.fred_data import get_all as fred_get_all
from utils.state_manager import save_cycle, load_history
from utils.github_sync import sync
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

    # Sync MT5 positions first
    try:
        from utils.position_sync import sync_mt5_positions, get_mt5_account
        synced = sync_mt5_positions()
        if synced:
            print("[sync] Synced " + str(len(synced)) + " closed position(s)")
            for s in synced:
                print("[sync]   ticket=" + str(s["ticket"]) + " PnL=$" + str(s["pnl"]) + " " + s["result"])
        mt5_acc = get_mt5_account()
        if mt5_acc:
            print("[MT5 account] Balance:$" + str(mt5_acc.get("balance","--")) + " Equity:$" + str(mt5_acc.get("equity","--")) + " Profit:$" + str(mt5_acc.get("profit","--")))
    except Exception as e:
        print("[sync] error:", e)

    stats = get_stats()
    print("[portfolio] Equity:$" + str(stats["equity"]) + " Open:" + str(stats["open_positions"]) + "/" + str(MAX_POSITIONS))
    if stats["open_positions"] >= MAX_POSITIONS:
        print("[portfolio] MAX positions reached")
        return None

    print("[1/8] Alpha Vantage OHLCV...")
    try:
        fetch_ohlcv()
    except Exception as e:
        print("      AV:", e)

    print("[2/8] Collecting news...")
    rss   = collect_rss()
    try:
        from agents.delta_one import fetch_deltaone
        delta = fetch_deltaone()
        if delta:
            print('      [DeltaOne] ' + str(len(delta)) + ' items:')
            for _d in delta[:6]:
                _tag = 'BREAK' if _d.get('breaking') else ('GOLD' if _d.get('relevant') else '----')
                print('      ['+_tag+'] ' + _d['title'][:80])
    except Exception as e:
        delta = []
        print('      [DeltaOne] unavailable:', e)
    api   = fetch_newsapi()
    items = list({i["title"]: i for i in rss.get("news_items", []) + api + delta}.values())[:30]
    gpt   = analyze_news_gpt(items)
    if gpt:
        news = gpt
        news["news_items"] = items
        print("      [GPT] Sentiment:" + str(gpt.get("sentiment")) + " conf:" + str(gpt.get("confidence")) + "%")
    else:
        news = rss
        news["news_items"] = items
    print("      Total:" + str(len(items)) + " Sentiment:" + str(news.get("sentiment")))
    for i in items[:5]:
        print("      >> [" + i["source"] + "] " + i["title"][:70])

    print("[3/8] FRED macro data...")
    fred = fred_get_all()
    print("      " + str(fred.get("summary", "unavailable")))

    print("[4/8] Price feed...")
    price = get_technical_data()
    print("      XAU/USD:" + str(price.get("price")) + " Chg:" + str(price.get("change_pct")) + "% H:" + str(price.get("high")) + " L:" + str(price.get("low")))

    print("[5/8] Macro analysis...")
    news["fred"] = fred
    macro = macro_analyze(news, price)
    print("      Bias:" + str(macro.get("macro_bias")) + " (" + str(macro.get("confidence")) + "%) DXY=" + str(fred.get("dxy")) + " 10Y=" + str(fred.get("t10y")) + "%")

    print("[6/8] Technical analysis...")
    tech = tech_analyze(price)
    print("      Trend:" + str(tech.get("trend")) + " RSI:" + str(tech.get("rsi_value")) + " S:" + str(tech.get("support")) + " R:" + str(tech.get("resistance")))

    print("[7/8] Debate 3 rounds...")
    debate = run_debate(macro, tech, price, news)
    print("      Winner:" + str(debate.get("winner")) + " Bull:" + str(debate.get("avg_bull_confidence")) + "% Bear:" + str(debate.get("avg_bear_confidence")) + "% Margin:" + str(debate.get("margin")) + "pts")

    print("[8/8] Risk + Arbitrator...")
    account_info = None
    if MT5_ENABLED:
        try:
            from agents.mt5_broker import connect, get_account_summary, disconnect
            if connect(MT5_LOGIN, MT5_PASSWORD, MT5_SERVER):
                account_info = get_account_summary()
                disconnect()
        except Exception as e:
            print("      [MT5]", e)

    risk = risk_calc(debate, tech, price, account_info.get("balance") if account_info else None)
    if risk.get("valid"):
        print("      Risk:" + str(risk.get("direction")) + " RR=" + str(risk.get("risk_reward")) + " $" + str(risk.get("risk_usd")) + " Lots=" + str(risk.get("contracts")))
    else:
        print("      Risk INVALID:" + str(risk.get("reason")))

    ftmo_check = validate_before_trade(risk, account_info)
    if not ftmo_check["approved"]:
        print("      [FTMO] BLOCKED:" + str(ftmo_check["reason"]))
        risk["valid"] = False
        risk["reason"] = ftmo_check["reason"]
    else:
        fs = ftmo_check["ftmo_status"]
        print("      [FTMO] OK Daily:$" + str(fs["daily_remaining"]) + " Total:$" + str(fs["total_remaining"]))
        for w in ftmo_check.get("warnings", []):
            print("      " + w)

    final    = decide(debate, risk, macro, news)
    decision = final.get("decision")
    print()
    print(">>> DECISION: " + decision + " conf:" + str(final.get("confidence")) + "%")
    print("    " + str(final.get("reason")))

    ticket = None
    if risk.get("valid") and decision in ("LONG", "SHORT"):
        print("    Entry:" + str(risk["entry"]) + " SL:" + str(risk["stop_loss"]) + " TP:" + str(risk["take_profit"]) + " Lots:" + str(risk["contracts"]))
        from utils.market_hours import is_market_open, get_market_status
        mkt_open, mkt_reason = is_market_open()
        mkt_status = get_market_status()
        print("    [Market] " + mkt_status["utc_time"] + " | " + mkt_reason)
        if not mkt_open:
            print("    [MT5] SKIPPING ORDER -- " + mkt_reason)
            print("    [MT5] Order will execute at next cycle when market reopens")
            try:
                from utils.telegram_alerts import send
                send("AURUM: " + decision + " signal @ $" + str(risk["entry"]) + " -- Market closed, waiting to execute\n" + mkt_reason)
            except: pass
        elif MT5_ENABLED:
            try:
                from agents.mt5_broker import connect, open_trade, disconnect
                if connect(MT5_LOGIN, MT5_PASSWORD, MT5_SERVER):
                    r = open_trade(decision, max(0.01, round(risk["contracts"], 2)), risk["stop_loss"], risk["take_profit"])
                    if r:
                        ticket = r["ticket"]
                        print("    [MT5] ORDER PLACED ticket=" + str(ticket))
                    disconnect()
            except Exception as e:
                print("    [MT5] Error:", e)

    cycle_data = {
        "ts":         datetime.now().isoformat(),
        "price":      price.get("price"),
        "change_pct": price.get("change_pct"),
        "decision":   decision,
        "confidence": final.get("confidence"),
        "reason":     final.get("reason"),
        "risk_plan":  risk,
        "mt5_ticket": ticket,
        "news_items": items[:10],
        "fred":       fred,
        "debate_summary": {
            "winner":    debate.get("winner"),
            "bull_conf": debate.get("avg_bull_confidence"),
            "bear_conf": debate.get("avg_bear_confidence"),
            "margin":    debate.get("margin"),
            "is_tie":    debate.get("is_tie"),
        },
        "macro": {
            "bias":       macro.get("macro_bias"),
            "confidence": macro.get("confidence"),
            "drivers":    macro.get("key_drivers"),
            "analysis":   macro.get("analysis"),
        },
        "technical": {
            "trend":      tech.get("trend"),
            "rsi_value":  tech.get("rsi_value"),
            "rsi_zone":   tech.get("rsi_zone"),
            "support":    tech.get("support"),
            "resistance": tech.get("resistance"),
            "sma20":      tech.get("sma20"),
            "bias":       tech.get("bias"),
        },
        "portfolio": stats,
        "ftmo_status": ftmo_check.get("ftmo_status", {}) if ftmo_check else {},
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
            print("[training] Insights:", insights[0])
    except Exception as e:
        print("[training] error:", e)

    sync("AURUM: " + decision + " @ " + str(price.get("price")))
    return cycle_data

if __name__ == "__main__":
    run_cycle()
