from datetime import datetime, timezone

# XAU/USD opera 24 horas de lunes a viernes
# Abre domingo 22:00 UTC, cierra viernes 22:00 UTC
# Pausa de mantenimiento diaria: 23:00-23:05 UTC (depende del broker)
# NO cierra por las noches entre semana

def is_market_open():
    now = datetime.now(timezone.utc)
    wd  = now.weekday()  # 0=Lun 4=Vie 5=Sab 6=Dom
    h   = now.hour
    m   = now.minute

    if wd == 5:
        return False, "Weekend closed (Saturday)"

    if wd == 6 and h < 22:
        mins = (22 - h) * 60 - m
        return False, "Opens in " + str(mins) + " min (Sunday 22:00 UTC)"

    if wd == 4 and h >= 22:
        return False, "Weekend closed (Friday 22:00+ UTC)"

    # Pausa mantenimiento FTMO 23:00-23:05 UTC
    if h == 23 and m < 6:
        return False, "Broker maintenance break (23:00-23:05 UTC)"

    return True, "Market open (XAU/USD 24/5)"

def get_market_status():
    open_flag, reason = is_market_open()
    now = datetime.now(timezone.utc)
    return {
        "is_open":  open_flag,
        "reason":   reason,
        "utc_time": now.strftime("%Y-%m-%d %H:%M UTC"),
        "local_note": "XAU/USD trades 24h Mon-Fri. Does NOT close at night.",
        "weekday":  now.strftime("%A"),
    }

def minutes_until_open():
    open_flag, _ = is_market_open()
    if open_flag:
        return 0
    now = datetime.now(timezone.utc)
    wd, h, m = now.weekday(), now.hour, now.minute
    if wd == 5:
        return (24 - h) * 60 - m + 22 * 60
    if wd == 6 and h < 22:
        return (22 - h) * 60 - m
    if wd == 4 and h >= 22:
        return (24 - h) * 60 - m + 24 * 60 + 22 * 60
    return 5  # maintenance break
