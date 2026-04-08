import time, traceback, os, sys
from datetime import datetime, timezone

NEWS_CHECK_INTERVAL     = 300    # 5 min
FULL_CYCLE_INTERVAL     = 14400  # 4 horas
MONITOR_INTERVAL        = 60     # 1 min

last_full_cycle = 0
last_news_check = 0
seen_headlines  = set()

def is_market_open():
    now = datetime.now(timezone.utc)
    wd, h = now.weekday(), now.hour
    if wd == 5: return False
    if wd == 6 and h < 22: return False
    if wd == 4 and h >= 22: return False
    return True

def check_breaking_news():
    from agents.news_collector import collect
    from utils.telegram_alerts import alert_news_flash
    HIGH_IMPACT = [
        "trump", "fed ", "rate decision", "cpi", "nfp", "war",
        "attack", "strike", "iran", "israel", "ukraine", "russia",
        "emergency", "crisis", "crash", "collapse", "default",
        "tariff", "sanctions", "nuclear", "invasion", "explosion"
    ]
    try:
        news = collect()
        items     = news.get("news_items", [])
        sentiment = news.get("sentiment", "NEUTRAL")
        breaking  = []
        for item in items:
            title = item.get("title", "")
            tl    = title.lower()
            if title not in seen_headlines and any(kw in tl for kw in HIGH_IMPACT):
                breaking.append(title)
                seen_headlines.add(title)
        if len(seen_headlines) > 500:
            seen_headlines.clear()
        if breaking:
            print("[daemon] BREAKING:", breaking[0][:80])
            if sentiment in ("BULLISH_GOLD", "BEARISH_GOLD"):
                alert_news_flash(breaking[0][:120], sentiment)
            return True, news
        return False, news
    except Exception as e:
        print("[daemon] news error:", e)
        return False, {}

def monitor_positions():
    try:
        from agents.mt5_broker import connect, get_open_positions, get_account_summary, disconnect
        from agents.ftmo_validator import get_ftmo_status
        from utils.telegram_alerts import alert_ftmo
        from portfolio import load_positions, close_position
        if connect(1513020113, "FH2dXFt7?", "FTMO-Demo"):
            account   = get_account_summary()
            ftmo      = get_ftmo_status(account)
            mt5_pos   = get_open_positions()
            mt5_ticks = {p["ticket"] for p in mt5_pos}
            ts = datetime.now().strftime("%H:%M:%S")
            eq = account.get("equity", 0)
            pr = account.get("profit", 0)
            dr = ftmo.get("daily_remaining", 0)
            print("[" + ts + "] Equity: " + str(round(eq,2)) + " | Profit: " + str(round(pr,2)) + " | Open: " + str(len(mt5_pos)) + " | Daily left: " + str(round(dr,2)))
            if not ftmo["can_trade"]:
                reason = " | ".join(ftmo.get("reasons", ["FTMO limit hit"]))
                print("[daemon] FTMO LIMIT:", reason)
                alert_ftmo(reason)
            local = load_positions()
            for pos in local:
                if pos["status"] == "OPEN" and pos.get("ticket") and pos["ticket"] not in mt5_ticks:
                    print("[daemon] Position " + str(pos["ticket"]) + " closed by MT5 (SL/TP)")
                    try:
                        import MetaTrader5 as mt5
                        from datetime import timedelta
                        deals = mt5.history_deals_get(
                            datetime.now() - timedelta(hours=48), datetime.now()
                        )
                        if deals:
                            deal = next((d for d in deals if d.position_id == pos["ticket"]), None)
                            if deal:
                                close_position(pos["id"], deal.price, deal.profit)
                                from utils.telegram_alerts import alert_closed
                                alert_closed(pos, deal.price)
                    except Exception as e2:
                        print("[daemon] deal history error:", e2)
                        close_position(pos["id"], pos.get("take_profit", 0))
            disconnect()
    except Exception as e:
        print("[daemon] monitor error:", e)

def run_full_cycle():
    try:
        from main import run_cycle
        print("[daemon] Starting full cycle...")
        run_cycle()
    except Exception as e:
        print("[daemon] cycle error:", e)
        traceback.print_exc()

print("[AURUM DAEMON] Starting")
print("[AURUM DAEMON] Monitor: 1min | News: 5min | Cycle: 4h")

from utils.telegram_alerts import send
send("AURUM DAEMON started\nMonitor: 1min | News: 5min | Cycle: 4h\nMarket open: " + str(is_market_open()))

# Primer ciclo inmediato
run_full_cycle()
last_full_cycle = time.time()
last_news_check = time.time()

while True:
    now = time.time()
    try:
        monitor_positions()

        if now - last_news_check >= NEWS_CHECK_INTERVAL:
            last_news_check = now
            if is_market_open():
                breaking, _ = check_breaking_news()
                if breaking:
                    print("[daemon] Breaking news -- immediate cycle")
                    run_full_cycle()
                    last_full_cycle = now

        if now - last_full_cycle >= FULL_CYCLE_INTERVAL:
            last_full_cycle = now
            if is_market_open():
                print("[daemon] Scheduled cycle")
                run_full_cycle()
            else:
                print("[daemon] Market closed -- skip")

        time.sleep(MONITOR_INTERVAL)

    except KeyboardInterrupt:
        print("[daemon] Stopped")
        send("AURUM DAEMON stopped by user")
        break
    except Exception as e:
        print("[daemon] loop error:", e)
        time.sleep(30)
