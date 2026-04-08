from datetime import datetime, timezone

# XAU/USD trading hours (UTC):
# Opens: Sunday 22:00 UTC
# Closes: Friday 22:00 UTC
# Daily maintenance break: 23:00-23:05 UTC (some brokers)

def is_market_open():
    now = datetime.now(timezone.utc)
    wd  = now.weekday()  # 0=Mon 4=Fri 5=Sat 6=Sun
    h   = now.hour
    m   = now.minute

    # Saturday: always closed
    if wd == 5:
        return False, "Weekend - market closed (Saturday)"

    # Sunday before 22:00 UTC: closed
    if wd == 6 and (h < 22):
        opens_in = (22 - h) * 60 - m
        return False, "Market opens in " + str(opens_in) + " min (Sunday 22:00 UTC)"

    # Friday after 22:00 UTC: closed
    if wd == 4 and h >= 22:
        return False, "Weekend - market closed (Friday 22:00+ UTC)"

    # Daily maintenance break 23:00-23:05 UTC
    if h == 23 and m < 6:
        return False, "Daily maintenance break (23:00-23:05 UTC)"

    return True, "Market open"

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
    now = datetime.now(timezone.utc)
    wd  = now.weekday()
    h   = now.hour
    m   = now.minute

    if wd == 5:  # Saturday - opens Sunday 22:00
        mins_to_midnight = (24 - h) * 60 - m
        mins_sunday      = 22 * 60
        return mins_to_midnight + mins_sunday

    if wd == 6 and h < 22:  # Sunday before open
        return (22 - h) * 60 - m

    if wd == 4 and h >= 22:  # Friday closed - opens Sunday
        mins_to_midnight = (24 - h) * 60 - m
        mins_saturday    = 24 * 60
        mins_sunday      = 22 * 60
        return mins_to_midnight + mins_saturday + mins_sunday

    return 0  # already open
