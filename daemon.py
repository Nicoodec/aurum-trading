import time, json, os, traceback
from datetime import datetime, timezone

MT5_LOGIN    = 1513020113
MT5_PASSWORD = "FH2dXFt7?"
MT5_SERVER   = "FTMO-Demo"
CAPITAL_BASE = 25000.0
RISK_PCT     = 0.01
MAX_DAILY_LOSS_PCT = 0.05
MAX_TOTAL_LOSS_PCT = 0.10
MAX_CONSEC_LOSSES  = 2
SCAN_INTERVAL    = 600
MONITOR_INTERVAL = 120
STATE_FILE = "state/daemon_state.json"

def load_state():
    try:
        if os.path.exists(STATE_FILE):
            return json.load(open(STATE_FILE, encoding="utf-8"))
    except: pass
    return {"consec_losses_today":0,"daily_pnl":0.0,
            "last_trade_date":"","total_trades":0,"total_wins":0}

def save_state(s):
    os.makedirs("state", exist_ok=True)
    json.dump(s, open(STATE_FILE,"w",encoding="utf-8"), indent=2)

def send_tg(msg):
    try:
        from utils.telegram_alerts import send
        send(msg)
    except Exception as e: print("[tg]", e)

def get_account():
    try:
        import MetaTrader5 as mt5
        mt5.initialize()
        i = mt5.account_info()
        bal = i.balance if i else CAPITAL_BASE
        eq  = i.equity  if i else CAPITAL_BASE
        mt5.shutdown()
        return bal, eq
    except: return CAPITAL_BASE, CAPITAL_BASE

def get_positions():
    try:
        import MetaTrader5 as mt5
        mt5.initialize()
        pos = mt5.positions_get(symbol="XAUUSD")
        mt5.shutdown()
        return list(pos) if pos else []
    except: return []

def run_scan(state):
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    hour_utc = now.hour

    if state["last_trade_date"] != date_str:
        state["consec_losses_today"] = 0
        state["daily_pnl"] = 0.0
        state["last_trade_date"] = date_str
        save_state(state)

    print()
    print("=" * 50)
    print("AURUM SCAN -- " + now.strftime("%Y-%m-%d %H:%M UTC"))
    print("=" * 50)

    bal, eq = get_account()
    total_dd = CAPITAL_BASE - eq
    print("[account] Balance:" + str(round(bal,2)) + " Equity:" + str(round(eq,2)) + " DD:" + str(round(total_dd,2)))

    if total_dd >= CAPITAL_BASE * MAX_TOTAL_LOSS_PCT:
        msg = "AURUM STOP total DD " + str(round(total_dd,2)) + " hit FTMO limit"
        print("[STOP] " + msg)
        send_tg(msg)
        return state

    if state["daily_pnl"] <= -(CAPITAL_BASE * MAX_DAILY_LOSS_PCT):
        print("[STOP] Daily loss limit hit")
        return state

    if state["consec_losses_today"] >= MAX_CONSEC_LOSSES:
        print("[STOP] " + str(MAX_CONSEC_LOSSES) + " consecutive losses today")
        return state

    in_session = (7 <= hour_utc < 10) or (12 <= hour_utc < 16)
    if not in_session:
        print("[scan] Outside session hour=" + str(hour_utc) + " waiting")
        return state

    positions = get_positions()
    if positions:
        p = positions[0]
        dir_str = "LONG" if p.type == 0 else "SHORT"
        print("[position] " + dir_str + " entry=" + str(p.price_open) + " PnL=" + str(round(p.profit,2)))
        print("[scan] Position open -- skipping")
        return state

    print("[scan] In session, no position -- scanning...")
    from agents.signal_engine import get_signal_from_mt5, format_signal_summary
    sig, _ = get_signal_from_mt5(verbose=True)

    if sig is None:
        print("[scan] No setup found")
        return state

    print("[scan] SETUP FOUND: " + format_signal_summary(sig))

    news_verdict = {"verdict":"NEUTRAL","confidence":50,"reason":""}
    try:
        from agents.delta_one import fetch_deltaone
        from agents.news_collector import collect
        from utils.fred_data import get_all as fred_get
        from agents.news_filter import analyze as nf
        delta = fetch_deltaone()
        rss   = collect()
        fred  = fred_get()
        all_items = rss.get("news_items",[]) + (delta or [])
        news_verdict = nf(sig["signal"], all_items, fred, delta or [])
        print("[news] " + news_verdict["verdict"] + " -- " + news_verdict["reason"][:80])
    except Exception as e:
        print("[news] error: " + str(e))

    if news_verdict["verdict"] == "VETO":
        print("[scan] News VETO -- skip")
        send_tg("AURUM: " + sig["signal"] + " setup VETOED by news")
        return state

    try:
        from utils.fred_data import get_all as fred_get
        from agents.macro_filter import check as mc
        fred = fred_get()
        macro = mc(sig["signal"], fred, {"balance":bal,"equity":eq}, state["daily_pnl"])
        print("[macro] " + macro["verdict"])
        if not macro["approved"]:
            for r in macro.get("reasons",[]): print("[macro] VETO: " + r)
            print("[scan] Macro VETO -- skip")
            return state
    except Exception as e:
        print("[macro] error: " + str(e))

    sl_dist  = sig["sl_dist"]
    risk_usd = round(eq * RISK_PCT, 2)
    lots     = risk_usd / (sl_dist * 100)
    lots     = round(max(0.01, min(lots, 2.0)), 2)
    print("[risk] risk=" + str(risk_usd) + " sl=" + str(sl_dist) + " lots=" + str(lots) + " rr=" + str(sig["rr"]))

    try:
        import MetaTrader5 as mt5
        mt5.initialize()
        mt5.login(MT5_LOGIN, MT5_PASSWORD, MT5_SERVER)
        tick = mt5.symbol_info_tick("XAUUSD")
        if sig["signal"] == "LONG":
            entry = tick.ask
            sl    = round(entry - sl_dist, 2)
            tp    = round(entry + sig["tp_dist"], 2)
            otype = mt5.ORDER_TYPE_BUY
        else:
            entry = tick.bid
            sl    = round(entry + sl_dist, 2)
            tp    = round(entry - sig["tp_dist"], 2)
            otype = mt5.ORDER_TYPE_SELL
        req = {
            "action":       mt5.TRADE_ACTION_DEAL,
            "symbol":       "XAUUSD",
            "volume":       lots,
            "type":         otype,
            "price":        entry,
            "sl":           sl,
            "tp":           tp,
            "deviation":    20,
            "magic":        123456,
            "comment":      "AURUM_v3",
            "type_time":    mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(req)
        mt5.shutdown()
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            ticket = result.order
            state["total_trades"] += 1
            save_state(state)
            print("[exec] ORDER PLACED ticket=" + str(ticket))
            print("[exec] " + sig["signal"] + " entry=" + str(round(entry,2)) + " SL=" + str(sl) + " TP=" + str(tp) + " lots=" + str(lots))
            emoji = "UP" if sig["signal"] == "LONG" else "DN"
            msg = ("AURUM ORDER PLACED " + emoji + "\n"
                   + sig["signal"] + " entry=" + str(round(entry,2)) + "\n"
                   + "SL=" + str(sl) + " TP=" + str(tp) + "\n"
                   + "Lots=" + str(lots) + " Risk=" + str(risk_usd) + "\n"
                   + "RR=" + str(sig["rr"]) + " ADX=" + str(sig["adx"]) + " RSI=" + str(sig["rsi"]) + "\n"
                   + "News: " + news_verdict["verdict"] + "\n"
                   + sig["reason"])
            send_tg(msg)
        else:
            err = result.comment if result else "unknown"
            print("[exec] FAILED: " + str(err))
            send_tg("AURUM order FAILED: " + str(err))
    except Exception as e:
        print("[exec] error: " + str(e))
        traceback.print_exc()

    return state

def run():
    print("AURUM DAEMON v3")
    print("EMA200 trend + EMA50 pullback")
    print("Sessions: London 07-10 UTC, NY overlap 12-16 UTC")
    print("Risk: 1pct per trade, stop after 2 consecutive losses")
    send_tg("AURUM DAEMON v3 started -- EMA50 pullback -- 1pct risk -- Auto-execute")
    state = load_state()
    last_scan = 0
    last_mon  = 0
    while True:
        try:
            now = time.time()
            if now - last_mon >= MONITOR_INTERVAL:
                pos = get_positions()
                if pos:
                    p = pos[0]
                    dir_str = "LONG" if p.type == 0 else "SHORT"
                    print("[monitor] " + dir_str + " PnL=" + str(round(p.profit,2)))
                last_mon = now
            if now - last_scan >= SCAN_INTERVAL:
                state = run_scan(state)
                last_scan = now
            time.sleep(30)
        except KeyboardInterrupt:
            print("[daemon] Stopped by user")
            send_tg("AURUM DAEMON stopped")
            break
        except Exception as e:
            print("[daemon] Error: " + str(e))
            traceback.print_exc()
            time.sleep(60)

if __name__ == "__main__":
    run()
