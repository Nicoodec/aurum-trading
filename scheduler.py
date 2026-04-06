# scheduler.py — corre ciclos automaticamente cada X horas
import schedule, time, traceback
from main import run_cycle

INTERVAL_HOURS = 4  # ciclo cada 4 horas

def safe_cycle():
    try:
        run_cycle()
    except Exception as e:
        print(f'[scheduler] cycle error: {e}')
        traceback.print_exc()

print(f'[AURUM scheduler] Running every {INTERVAL_HOURS}h. First cycle now.')
safe_cycle()
schedule.every(INTERVAL_HOURS).hours.do(safe_cycle)

while True:
    schedule.run_pending()
    time.sleep(60)
