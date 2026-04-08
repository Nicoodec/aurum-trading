from datetime import datetime, timezone

def is_market_open():
    # Use MT5 as source of truth for market status
    try:
        import MetaTrader5 as mt5
        if mt5.initialize():
            info = mt5.symbol_info("XAUUSD")
            if info is None:
                mt5.shutdown()
                return False, "XAUUSD symbol not found"
            # trade_mode: 0=disabled 1=longonly 2=shortonly 3=closeonly 4=full
            mode = info.trade_mode
            mt5.shutdown()
            if mode == 4:
                return True, "Market open (MT5 full access)"
            elif mode == 3:
                return False, "Market close-only mode"
            elif mode == 0:
                return False, "Market disabled by broker"
            else:
                return True, "Market partial (" + str(mode) + ")"
    except Exception as e:
        print("[market_hours] MT5 check error:", e)

    # Fallback: time-based calculation
    now = datetime.now(timezone.utc)
    wd, h, m = now.weekday(), now.hour, now.minute
    if wd == 5: return False, "Saturday - market closed"
    if wd == 6 and h < 22: return False, "Sunday before 22:00 UTC"
    if wd == 4 and h >= 22: return False, "Friday after 22:00 UTC"
    if h == 23 and m < 6: return False, "Maintenance break 23:00-23:05 UTC"
    return True, "Market open (time-based)"

def get_market_status():
    open_flag, reason = is_market_open()
    now = datetime.now(timezone.utc)
    return {
        "is_open":  open_flag,
        "reason":   reason,
        "utc_time": now.strftime("%Y-%m-%d %H:%M UTC"),
        "weekday":  now.strftime("%A"),
    }

def minutes_until_open():
    open_flag, _ = is_market_open()
    if open_flag: return 0
    now = datetime.now(timezone.utc)
    wd, h, m = now.weekday(), now.hour, now.minute
    if wd == 5: return (24-h)*60-m + 22*60
    if wd == 6 and h < 22: return (22-h)*60-m
    if wd == 4 and h >= 22: return (24-h)*60-m + 24*60 + 22*60
    return 5
