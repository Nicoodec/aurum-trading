"""
AURUM main.py -- US30 + GPT Arbitrator
========================================
Flujo:
1. Sync MT5 posiciones y cuenta
2. Signal engine US30 (H4 EMA200 + H1 EMA50 pullback)
3. Si hay setup: noticias + macro + GPT decide
4. Si GPT dice LONG/SHORT: ejecuta en MT5
5. Guarda estado y push a GitHub
"""
import json, os
from datetime import datetime
from agents.news_collector import collect as collect_rss
from agents.delta_one import fetch_deltaone
from agents.news_gpt import analyze_news_gpt
from agents.signal_engine import get_signal_from_mt5, format_signal_summary
from agents.news_filter import analyze as news_filter_analyze
from agents.macro_filter import check as macro_filter_check
from utils.fred_data import get_all as fred_get_all
from utils.state_manager import save_cycle, load_history
from utils.github_sync import sync
from utils.position_sync import sync_mt5_positions, get_mt5_account
from gen_dashboard import generate as gen_html
from portfolio import add_position, get_stats
from config import MAX_POSITIONS

MT5_LOGIN    = 1513020113
MT5_PASSWORD = "FH2dXFt7?"
MT5_SERVER   = "FTMO-Demo"
MT5_ENABLED  = True
SYMBOL       = "US30.cash"

# US30 sizing: 1 lot = $1 por punto
LOT_SIZE     = 1.0
RISK_PCT     = 0.01
COMMISSION   = 0.50

def gpt_arbitrator(signal, news_items, fred, account_info, daily_pnl=0.0):
    """
    GPT-4o decide si ejecutar la señal técnica basándose en:
    - Setup técnico completo
    - Noticias en tiempo real
    - Datos macro (DXY, yields)
    - Estado FTMO actual
    
    Returns: {"decision": "LONG"|"SHORT"|"STAY OUT", "confidence": int, "reason": str}
    """
    import os, requests, json
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        return {"decision": "STAY OUT", "confidence": 0, "reason": "No OpenAI key"}

    # Noticias recientes
    news_str = "\n".join([
        "  [" + i.get("source","") + "] " + i.get("title","")[:100]
        for i in (news_items or [])[:15]
    ]) or "  No news available"

    # Macro
    dxy  = fred.get("dxy", "N/A")
    t10  = fred.get("t10y", "N/A")
    fed  = fred.get("fedfunds", "N/A")

    # Estado FTMO
    bal  = account_info.get("balance", 25000) if account_info else 25000
    eq   = account_info.get("equity",  25000) if account_info else 25000
    dd   = round(25000 - eq, 2)
    dd_pct = round(dd / 25000 * 100, 1)

    # Signal info
    sig_dir  = signal["signal"]
    sig_conf = signal["confidence"]
    price    = signal["price"]
    e50      = signal["e50"]
    t_ema    = signal["trend_ema"]
    adx      = signal["adx"]
    rsi_v    = signal["rsi"]
    atr      = signal["atr"]
    sl_pts   = signal["sl_dist"]
    tp_pts   = signal["tp_dist"]
    rr       = signal["rr"]

    system = """You are an expert prop firm trader specializing in US30 (Dow Jones) intraday trading.
Your goal is to help pass an FTMO $25k challenge with strict risk rules:
- Daily loss limit: 5% ($1,250)
- Total loss limit: 10% ($2,500) 
- Target: +10% ($2,500)

You will receive a technical setup and must decide whether to execute it based on:
1. Technical quality (EMA alignment, ADX momentum, RSI levels)
2. News context (is there any macro risk that contradicts the setup?)
3. Current FTMO status (are we close to any limits?)

Be decisive. When in doubt with good technicals and neutral news: EXECUTE.
Only STAY OUT if there is a clear reason (bad news, near FTMO limits, contradicting macro).
Respond ONLY in valid JSON."""

    prompt = f"""TECHNICAL SETUP DETECTED on US30 (Dow Jones):
Direction: {sig_dir}
Price: {price:.0f} | EMA50 H1: {e50:.0f} | EMA200 H4: {t_ema:.0f}
ADX: {adx} | RSI: {rsi_v} | ATR: {atr:.1f} pts
SL: {sl_pts} pts | TP: {tp_pts} pts | RR: {rr}:1
Technical confidence: {sig_conf}%

FTMO STATUS:
Balance: ${bal:.2f} | Equity: ${eq:.2f}
Total DD: ${dd:.2f} ({dd_pct}%) -- limit is 10% ($2,500)
Daily P&L: ${daily_pnl:.2f} -- limit is -5% (-$1,250)

MACRO DATA (FRED):
DXY: {dxy} | 10Y Yield: {t10}% | Fed Funds: {fed}%

RECENT NEWS (real-time):
{news_str}

QUESTION: Should I execute this {sig_dir} trade on US30?

Consider:
- Is the technical setup valid? (H4 uptrend/downtrend confirmed by EMA200, H1 pullback to EMA50, ADX confirms momentum)
- Do the news support or contradict this direction?
- Is the macro environment favorable?
- Are we safe within FTMO limits?

Respond ONLY in JSON:
{{"decision": "LONG" or "SHORT" or "STAY OUT", "confidence": 0-100, "reason": "specific reason max 150 chars"}}"""

    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            json={
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user",   "content": prompt},
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
            timeout=25,
        )
        data = r.json()
        if "error" in data:
            print("      [GPT] API error:", data["error"].get("message","")[:80])
            return {"decision": "STAY OUT", "confidence": 0, "reason": "API error"}
        content = data["choices"][0]["message"]["content"]
        result  = json.loads(content)
        dec     = result.get("decision", "STAY OUT").upper()
        if dec not in ("LONG", "SHORT", "STAY OUT"):
            dec = "STAY OUT"
        return {
            "decision":   dec,
            "confidence": int(result.get("confidence", 50)),
            "reason":     str(result.get("reason", ""))[:200],
        }
    except Exception as e:
        print("      [GPT] error:", e)
        return {"decision": "STAY OUT", "confidence": 0, "reason": str(e)[:100]}


def run_cycle():
    print()
    print("=" * 52)
    print("AURUM US30 CYCLE --", datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 52)

    # Sync MT5
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
        mt5_acc = None

    stats = get_stats()
    print("[portfolio] Equity:$" + str(stats["equity"]) +
          " Open:" + str(stats["open_positions"]) + "/" + str(MAX_POSITIONS))
    if stats["open_positions"] >= MAX_POSITIONS:
        print("[portfolio] MAX positions reached")
        return None

    # 1. Signal engine US30
    print("[1/5] Signal engine US30 (H4 EMA200 + H1 EMA50)...")
    sig, h1_candles = get_signal_from_mt5(verbose=False)
    if sig:
        print("      " + format_signal_summary(sig))
    else:
        print("      No technical setup right now")
        # Guardar ciclo sin decision y salir
        cycle_data = {
            "ts": datetime.now().isoformat(), "symbol": SYMBOL,
            "decision": "STAY OUT", "confidence": 0,
            "reason": "No technical setup",
        }
        save_cycle(cycle_data)
        sync("AURUM US30: no setup")
        return None

    # 2. Noticias
    print("[2/5] Collecting news...")
    try:
        rss   = collect_rss()
        delta = fetch_deltaone()
        all_items = list({
            i["title"]: i
            for i in rss.get("news_items", []) + (delta or [])
        }.values())[:25]
        gpt_sent = analyze_news_gpt(all_items)
        sentiment = gpt_sent.get("sentiment","NEUTRAL") if gpt_sent else "NEUTRAL"
        print("      Items:" + str(len(all_items)) +
              " Sentiment:" + str(sentiment))
        for i in all_items[:4]:
            print("      >> [" + i.get("source","") + "] " + i["title"][:70])
    except Exception as e:
        print("      [news] error:", e)
        all_items = []

    # 3. FRED macro
    print("[3/5] FRED macro data...")
    fred = fred_get_all()
    print("      " + str(fred.get("summary","unavailable")))

    # 4. GPT arbitrator
    print("[4/5] GPT-4o arbitrator...")
    account_info = mt5_acc

    # Daily P&L from state
    daily_pnl = 0.0
    try:
        history = load_history()
        today = datetime.now().strftime("%Y-%m-%d")
        today_trades = [c for c in history if c.get("ts","")[:10] == today]
        daily_pnl = sum(
            c.get("risk_plan",{}).get("pnl_realized",0)
            for c in today_trades
        )
    except: pass

    gpt_result = gpt_arbitrator(sig, all_items, fred, account_info, daily_pnl)
    decision   = gpt_result["decision"]
    confidence = gpt_result["confidence"]
    reason     = gpt_result["reason"]

    print()
    print(">>> GPT DECISION: " + decision + " (" + str(confidence) + "%)")
    print("    " + reason)
    print()

    # 5. Execute
    ticket = None
    price  = sig["price"]
    sl_pts = sig["sl_dist"]
    tp_pts = sig["tp_dist"]

    if decision in ("LONG", "SHORT"):
        # Sizing: 1% riesgo
        bal      = account_info.get("balance", 25000) if account_info else 25000
        risk_usd = round(bal * RISK_PCT, 2)
        lots     = round(max(0.01, min(risk_usd / (sl_pts * LOT_SIZE), 50.0)), 2)
        print("[5/5] Executing order...")
        print("      Direction: " + decision)
        print("      Entry: ~" + str(round(price,0)) +
              " | SL: " + str(sl_pts) + "pts | TP: " + str(tp_pts) + "pts")
        print("      Lots: " + str(lots) + " | Risk: $" + str(risk_usd))

        if MT5_ENABLED:
            try:
                import MetaTrader5 as mt5
                if mt5.initialize() and mt5.login(MT5_LOGIN, MT5_PASSWORD, MT5_SERVER):
                    tick  = mt5.symbol_info_tick(SYMBOL)
                    if decision == "LONG":
                        entry = tick.ask
                        sl    = round(entry - sl_pts, 2)
                        tp    = round(entry + tp_pts, 2)
                        otype = mt5.ORDER_TYPE_BUY
                    else:
                        entry = tick.bid
                        sl    = round(entry + sl_pts, 2)
                        tp    = round(entry - tp_pts, 2)
                        otype = mt5.ORDER_TYPE_SELL

                    req = {
                        "action":       mt5.TRADE_ACTION_DEAL,
                        "symbol":       SYMBOL,
                        "volume":       lots,
                        "type":         otype,
                        "price":        entry,
                        "sl":           sl,
                        "tp":           tp,
                        "deviation":    30,
                        "magic":        123456,
                        "comment":      "AURUM_US30",
                        "type_time":    mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    result = mt5.order_send(req)
                    mt5.shutdown()
                    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                        ticket = result.order
                        print("      [MT5] ORDER PLACED ticket=" + str(ticket))
                    else:
                        err = result.comment if result else "unknown"
                        print("      [MT5] FAILED: " + str(err))
            except Exception as e:
                print("      [MT5] error:", e)
    else:
        print("[5/5] STAY OUT -- no order placed")

    # Save cycle
    cycle_data = {
        "ts":         datetime.now().isoformat(),
        "symbol":     SYMBOL,
        "price":      price,
        "decision":   decision,
        "confidence": confidence,
        "reason":     reason,
        "signal":     sig,
        "gpt_result": gpt_result,
        "fred":       fred,
        "mt5_ticket": ticket,
        "portfolio":  stats,
    }
    if decision in ("LONG","SHORT") and ticket:
        add_position(cycle_data, ticket=ticket)

    save_cycle(cycle_data)

    try:
        gen_html(latest=cycle_data, history=load_history(), stats=stats)
    except Exception as e:
        print("[dashboard] error:", e)

    try:
        from utils.telegram_alerts import alert_decision
        alert_decision(cycle_data)
    except Exception as e:
        print("[telegram] error:", e)

    sync("AURUM US30: " + decision + " @ " + str(round(price,0)))
    return cycle_data


if __name__ == "__main__":
    run_cycle()
