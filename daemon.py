import json, os, time, traceback
from datetime import datetime, timezone

MT5_LOGIN    = 1513020113
MT5_PASSWORD = "FH2dXFt7?"
MT5_SERVER   = "FTMO-Demo"
CAPITAL_BASE = 25000.0
RISK_PCT     = 0.01
MAX_DAILY_LOSS_PCT = 0.05
MAX_TOTAL_LOSS_PCT = 0.10
MAX_CONSEC_LOSSES  = 2
MAX_TRADE_HOURS    = 8
SCAN_INTERVAL      = 600
MONITOR_INTERVAL   = 60
STATE_FILE         = "state/daemon_state.json"

def load_state():
    try:
        if os.path.exists(STATE_FILE):
            return json.load(open(STATE_FILE, encoding="utf-8"))
    except: pass
    return {
        "consec_losses_today": 0, "daily_pnl": 0.0,
        "last_trade_date": "", "total_trades": 0,
        "total_wins": 0, "total_losses": 0,
        "open_ticket": None, "open_dir": None,
        "open_entry": None, "open_sl": None,
        "open_tp": None, "open_lots": None,
        "open_time": None, "be_done": False,
        "daily_pnl_before_trade": 0.0,
    }

def save_state(s):
    os.makedirs("state", exist_ok=True)
    json.dump(s, open(STATE_FILE, "w", encoding="utf-8"), indent=2)

def send_tg(msg):
    try:
        from utils.telegram_alerts import send
        send(msg)
    except Exception as e:
        print("[tg]", e)

def get_account():
    try:
        import MetaTrader5 as mt5
        mt5.initialize()
        i = mt5.account_info()
        bal = i.balance if i else CAPITAL_BASE
        eq  = i.equity  if i else CAPITAL_BASE
        mt5.shutdown()
        return bal, eq
    except:
        return CAPITAL_BASE, CAPITAL_BASE

def get_positions():
    try:
        import MetaTrader5 as mt5
        mt5.initialize()
        pos = mt5.positions_get(symbol="XAUUSD")
        mt5.shutdown()
        return list(pos) if pos else []
    except:
        return []

def get_daily_pnl():
    """P&L real de deals cerrados hoy segun MT5."""
    try:
        import MetaTrader5 as mt5
        mt5.initialize()
        now   = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        deals = mt5.history_deals_get(start, now)
        mt5.shutdown()
        if deals is None:
            return 0.0
        pnl = sum(d.profit for d in deals if d.symbol == "XAUUSD" and d.entry == 1)
        return round(pnl, 2)
    except:
        return 0.0

def move_to_breakeven(ticket, entry, direction, sl_dist):
    """Mueve SL a breakeven cuando el precio va +1R a favor."""
    try:
        import MetaTrader5 as mt5
        mt5.initialize()
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            mt5.shutdown()
            return False
        pos     = positions[0]
        current = pos.price_current
        moved   = False
        if direction == "LONG" and current >= entry + sl_dist:
            new_sl = round(entry + 0.10, 2)
            req = {"action": mt5.TRADE_ACTION_SLTP, "symbol": "XAUUSD",
                   "position": ticket, "sl": new_sl, "tp": pos.tp}
            r = mt5.order_send(req)
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                print("[BE] Moved SL to breakeven " + str(new_sl))
                send_tg("AURUM: SL moved to breakeven $" + str(new_sl))
                moved = True
        elif direction == "SHORT" and current <= entry - sl_dist:
            new_sl = round(entry - 0.10, 2)
            req = {"action": mt5.TRADE_ACTION_SLTP, "symbol": "XAUUSD",
                   "position": ticket, "sl": new_sl, "tp": pos.tp}
            r = mt5.order_send(req)
            if r and r.retcode == mt5.TRADE_RETCODE_DONE:
                print("[BE] Moved SL to breakeven " + str(new_sl))
                send_tg("AURUM: SL moved to breakeven $" + str(new_sl))
                moved = True
        mt5.shutdown()
        return moved
    except Exception as e:
        print("[BE] error:", e)
        return False

def close_position(ticket, reason="time_exit"):
    """Cierra una posicion abierta por ticket."""
    try:
        import MetaTrader5 as mt5
        mt5.initialize()
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            mt5.shutdown()
            return None
        pos   = positions[0]
        otype = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
        tick  = mt5.symbol_info_tick("XAUUSD")
        price = tick.bid if pos.type == 0 else tick.ask
        pnl   = pos.profit
        req   = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": "XAUUSD",
            "volume": pos.volume, "type": otype, "position": ticket,
            "price": price, "deviation": 20, "magic": 123456,
            "comment": "AURUM_" + reason,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(req)
        mt5.shutdown()
        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            print("[close] ticket=" + str(ticket) + " reason=" + reason + " PnL=" + str(round(pnl,2)))
            return round(pnl, 2)
        return None
    except Exception as e:
        print("[close] error:", e)
        return None

def monitor(state):
    """
    Monitoriza posicion abierta cada 60s:
    1. Detecta cierre por SL/TP y actualiza estado
    2. Mueve SL a breakeven cuando precio va +1R
    3. Cierra por tiempo si lleva mas de MAX_TRADE_HOURS
    """
    ticket = state.get("open_ticket")
    if not ticket:
        return state

    positions    = get_positions()
    open_tickets = [p.ticket for p in positions]

    # Posicion cerrada (SL o TP tocado)
    if ticket not in open_tickets:
        real_pnl   = get_daily_pnl()
        prev_pnl   = state.get("daily_pnl_before_trade", 0.0)
        trade_pnl  = round(real_pnl - prev_pnl, 2)

        state["daily_pnl"]   = real_pnl
        state["total_trades"] += 1

        if trade_pnl > 0:
            state["total_wins"]          += 1
            state["consec_losses_today"]  = 0
            result_str = "WIN"
            emoji      = "✅"
        else:
            state["total_losses"]        += 1
            state["consec_losses_today"] += 1
            result_str = "LOSS"
            emoji      = "❌"

        for k in ["open_ticket","open_dir","open_entry","open_sl","open_tp","open_lots","open_time"]:
            state[k] = None
        state["be_done"] = False
        save_state(state)

        msg = (emoji + " AURUM TRADE CLOSED " + result_str + "\n"
               + "Trade P&L: $" + str(trade_pnl) + "\n"
               + "Daily P&L: $" + str(real_pnl) + "\n"
               + "Consec losses today: " + str(state["consec_losses_today"]) + "\n"
               + "Total: " + str(state["total_wins"]) + "W / " + str(state["total_losses"]) + "L")
        print("[monitor] CLOSED " + result_str + " PnL=" + str(trade_pnl))
        send_tg(msg)
        return state

    # Posicion sigue abierta
    pos       = next(p for p in positions if p.ticket == ticket)
    entry     = state.get("open_entry", pos.price_open)
    direction = state.get("open_dir", "LONG")
    sl_dist   = abs(entry - state.get("open_sl", entry))

    print("[monitor] " + direction + " ticket=" + str(ticket)
          + " entry=" + str(round(entry,2))
          + " current=" + str(round(pos.price_current,2))
          + " PnL=$" + str(round(pos.profit,2)))

    # Breakeven: mover SL cuando el precio va +1R
    if not state.get("be_done", False) and sl_dist > 0:
        if move_to_breakeven(ticket, entry, direction, sl_dist):
            state["be_done"] = True
            save_state(state)

    # Time exit: cerrar si lleva mas de MAX_TRADE_HOURS horas
    open_time_str = state.get("open_time", "")
    if open_time_str:
        try:
            open_dt    = datetime.fromisoformat(open_time_str)
            hours_open = (datetime.now(timezone.utc) - open_dt).total_seconds() / 3600
            if hours_open >= MAX_TRADE_HOURS:
                print("[monitor] Time exit after " + str(round(hours_open,1)) + "h")
                send_tg("AURUM: closing after " + str(MAX_TRADE_HOURS) + "h time limit")
                pnl = close_position(ticket, reason="time_exit")
                if pnl is not None:
                    state["daily_pnl"] = get_daily_pnl()
                    state["total_trades"] += 1
                    if pnl > 0:
                        state["total_wins"] += 1
                        state["consec_losses_today"] = 0
                    else:
                        state["total_losses"] += 1
                        state["consec_losses_today"] += 1
                    for k in ["open_ticket","open_dir","open_entry","open_sl","open_tp","open_lots","open_time"]:
                        state[k] = None
                    state["be_done"] = False
                    save_state(state)
                    emoji = "✅" if pnl > 0 else "❌"
                    result_str = "WIN" if pnl > 0 else "LOSS"
                    send_tg(emoji + " AURUM TIME EXIT " + result_str + " PnL=$" + str(round(pnl,2)))
        except Exception as e:
            print("[monitor] time check error:", e)

    return state

def run_scan(state):
    now      = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    hour_utc = now.hour

    # Reset diario
    if state["last_trade_date"] != date_str:
        state["consec_losses_today"]    = 0
        state["daily_pnl"]              = 0.0
        state["daily_pnl_before_trade"] = 0.0
        state["last_trade_date"]        = date_str
        save_state(state)

    print()
    print("=" * 50)
    print("AURUM SCAN -- " + now.strftime("%Y-%m-%d %H:%M UTC"))
    print("=" * 50)

    bal, eq        = get_account()
    total_dd       = CAPITAL_BASE - eq
    real_daily_pnl = get_daily_pnl()
    state["daily_pnl"] = real_daily_pnl

    print("[account] Balance:" + str(round(bal,2))
          + " Equity:" + str(round(eq,2))
          + " DD:" + str(round(total_dd,2))
          + " DailyPnL:" + str(real_daily_pnl))

    # FTMO hard stops
    if total_dd >= CAPITAL_BASE * MAX_TOTAL_LOSS_PCT:
        msg = "AURUM STOP total DD $" + str(round(total_dd,2)) + " hit FTMO 10% limit"
        print("[STOP] " + msg)
        send_tg("🔴 " + msg)
        return state

    if real_daily_pnl <= -(CAPITAL_BASE * MAX_DAILY_LOSS_PCT):
        msg = "AURUM STOP daily loss $" + str(real_daily_pnl) + " hit FTMO 5% limit"
        print("[STOP] " + msg)
        send_tg("🔴 " + msg)
        return state

    if state["consec_losses_today"] >= MAX_CONSEC_LOSSES:
        print("[STOP] " + str(MAX_CONSEC_LOSSES) + " consecutive losses today -- stopped")
        return state

    # Session check
    in_session = (7 <= hour_utc < 10) or (12 <= hour_utc < 16)
    if not in_session:
        print("[scan] Outside session hour=" + str(hour_utc) + " waiting")
        return state

    # Position check
    positions = get_positions()
    if positions:
        p = positions[0]
        dir_str = "LONG" if p.type == 0 else "SHORT"
        print("[position] " + dir_str + " entry=" + str(p.price_open) + " PnL=$" + str(round(p.profit,2)))
        print("[scan] Position open -- skipping")
        return state

    # Signal
    print("[scan] In session, no position -- scanning...")
    from agents.signal_engine import get_signal_from_mt5, format_signal_summary
    sig, _ = get_signal_from_mt5(verbose=True)

    if sig is None:
        print("[scan] No setup found")
        return state

    print("[scan] SETUP FOUND: " + format_signal_summary(sig))

    # News filter
    news_verdict = {"verdict": "NEUTRAL", "confidence": 50, "reason": ""}
    try:
        from agents.delta_one import fetch_deltaone
        from agents.news_collector import collect
        from utils.fred_data import get_all as fred_get
        from agents.news_filter import analyze as nf
        delta        = fetch_deltaone()
        rss          = collect()
        fred         = fred_get()
        all_items    = rss.get("news_items", []) + (delta or [])
        news_verdict = nf(sig["signal"], all_items, fred, delta or [])
        print("[news] " + news_verdict["verdict"] + " -- " + news_verdict["reason"][:80])
    except Exception as e:
        print("[news] error:", e)

    if news_verdict["verdict"] == "VETO":
        print("[scan] News VETO -- skip")
        send_tg("⚠️ AURUM: " + sig["signal"] + " setup VETOED by news\n" + news_verdict["reason"][:100])
        return state

    # Macro filter
    try:
        from utils.fred_data import get_all as fred_get
        from agents.macro_filter import check as mc
        fred  = fred_get()
        macro = mc(sig["signal"], fred, {"balance": bal, "equity": eq}, real_daily_pnl)
        print("[macro] " + macro["verdict"])
        if not macro["approved"]:
            for r in macro.get("reasons", []):
                print("[macro] VETO: " + r)
            print("[scan] Macro VETO -- skip")
            return state
    except Exception as e:
        print("[macro] error:", e)

    # Sizing 1% riesgo
    sl_dist  = sig["sl_dist"]
    risk_usd = round(eq * RISK_PCT, 2)
    lots     = risk_usd / (sl_dist * 100)
    lots     = round(max(0.01, min(lots, 2.0)), 2)
    print("[risk] risk=$" + str(risk_usd) + " sl=$" + str(sl_dist) + " lots=" + str(lots) + " rr=" + str(sig["rr"]))

    # Execute order
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
            "action": mt5.TRADE_ACTION_DEAL, "symbol": "XAUUSD",
            "volume": lots, "type": otype, "price": entry,
            "sl": sl, "tp": tp, "deviation": 20, "magic": 123456,
            "comment": "AURUM_v3",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(req)
        mt5.shutdown()

        if result and result.retcode == mt5.TRADE_RETCODE_DONE:
            ticket    = result.order
            open_time = datetime.now(timezone.utc).isoformat()
            state.update({
                "open_ticket": ticket, "open_dir": sig["signal"],
                "open_entry": entry, "open_sl": sl, "open_tp": tp,
                "open_lots": lots, "open_time": open_time,
                "be_done": False,
                "daily_pnl_before_trade": real_daily_pnl,
            })
            save_state(state)

            print("[exec] ORDER PLACED ticket=" + str(ticket))
            print("[exec] " + sig["signal"] + " entry=" + str(round(entry,2))
                  + " SL=" + str(sl) + " TP=" + str(tp) + " lots=" + str(lots))

            emoji = "📈" if sig["signal"] == "LONG" else "📉"
            msg = (emoji + " AURUM ORDER PLACED\n"
                   + "Direction: " + sig["signal"] + "\n"
                   + "Entry: $" + str(round(entry,2)) + "\n"
                   + "SL: $" + str(sl) + " (risk $" + str(round(sl_dist,2)) + ")\n"
                   + "TP: $" + str(tp) + "\n"
                   + "Lots: " + str(lots) + " | Risk: $" + str(risk_usd) + " (1%)\n"
                   + "RR: " + str(sig["rr"]) + ":1 | ADX: " + str(sig["adx"]) + " | RSI: " + str(sig["rsi"]) + "\n"
                   + "News: " + news_verdict["verdict"] + "\n"
                   + sig["reason"])
            send_tg(msg)
        else:
            err = result.comment if result else "unknown"
            print("[exec] FAILED: " + str(err))
            send_tg("❌ AURUM order FAILED: " + str(err))

    except Exception as e:
        print("[exec] error:", e)
        traceback.print_exc()

    return state

def run():
    print("AURUM DAEMON v3 -- complete edition")
    print("Strategy : EMA200 trend + EMA50 pullback")
    print("Sessions : London 07-10 UTC, NY overlap 12-16 UTC")
    print("Risk     : 1% per trade")
    print("Breakeven: +1R")
    print("Time exit: " + str(MAX_TRADE_HOURS) + "h max")
    print("Daily stop: " + str(MAX_CONSEC_LOSSES) + " consecutive losses")
    send_tg("🤖 AURUM DAEMON v3 started\nEMA50 pullback | 1% risk | BE at +1R | " + str(MAX_TRADE_HOURS) + "h time exit")

    state     = load_state()
    last_scan = 0
    last_mon  = 0

    while True:
        try:
            now = time.time()
            if now - last_mon >= MONITOR_INTERVAL:
                state    = monitor(state)
                last_mon = now
            if now - last_scan >= SCAN_INTERVAL:
                state     = run_scan(state)
                last_scan = now
            time.sleep(30)
        except KeyboardInterrupt:
            print("\n[daemon] Stopped by user")
            send_tg("🛑 AURUM DAEMON stopped")
            break
        except Exception as e:
            print("[daemon] Error:", e)
            traceback.print_exc()
            time.sleep(60)

if __name__ == "__main__":
    run()
