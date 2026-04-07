# scheduler.py
import schedule, time, traceback
from datetime import datetime

INTERVAL_HOURS = 4

def is_market_open():
    now = datetime.utcnow()
    # XAU/USD cierra vierens 22:00 UTC, abre domingo 22:00 UTC
    weekday = now.weekday()  # 0=lunes, 6=domingo
    hour    = now.hour
    if weekday == 5:  # sabado — cerrado todo el dia
        return False
    if weekday == 6 and hour < 22:  # domingo antes de las 22 UTC
        return False
    if weekday == 4 and hour >= 22:  # viernes despues de las 22 UTC
        return False
    return True

def safe_cycle():
    if not is_market_open():
        print(f'[scheduler] Market closed — skipping ({datetime.utcnow().strftime("%a %H:%M UTC")})')
        return
    try:
        from main import run_cycle
        run_cycle()
    except Exception as e:
        print(f'[scheduler] cycle error: {e}')
        traceback.print_exc()

print(f'[AURUM scheduler] Every {INTERVAL_HOURS}h. Market hours only.')
safe_cycle()
schedule.every(INTERVAL_HOURS).hours.do(safe_cycle)

while True:
    schedule.run_pending()
    time.sleep(60)
