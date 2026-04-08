import requests, os, json
from datetime import datetime, timedelta
from dotenv import load_dotenv
from config import STATE_DIR, GOLDAPI_KEY
load_dotenv()

def fetch_ohlcv():
    # Intentar cargar desde cache si es de hoy
    cache = os.path.join(STATE_DIR, "price_history.json")
    if os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("last_update","")[:10] == datetime.now().strftime("%Y-%m-%d"):
            prices = data.get("prices",[])
            if len(prices) >= 10:
                print("[history] Using cached", len(prices), "candles")
                return prices

    # Intentar MT5 historial
    try:
        import MetaTrader5 as mt5
        if mt5.initialize():
            rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_D1, 0, 60)
            if rates is not None and len(rates) > 5:
                prices = []
                for r in rates:
                    prices.append({
                        "date":  datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d"),
                        "open":  float(r["open"]),
                        "high":  float(r["high"]),
                        "low":   float(r["low"]),
                        "close": float(r["close"]),
                    })
                os.makedirs(STATE_DIR, exist_ok=True)
                with open(cache, "w", encoding="utf-8") as f:
                    json.dump({"prices":prices,"last_update":datetime.now().isoformat(),"source":"MT5"}, f)
                print("[history] Saved", len(prices), "candles from MT5")
                mt5.shutdown()
                return prices
        mt5.shutdown()
    except Exception as e:
        print("[history] MT5 error:", e)

    # Fallback goldapi historico
    if GOLDAPI_KEY:
        prices = []
        for d in range(30, 0, -1):
            date = (datetime.now() - timedelta(days=d)).strftime("%Y%m%d")
            try:
                r = requests.get(
                    f"https://www.goldapi.io/api/XAU/USD/{date}",
                    headers={"x-access-token": GOLDAPI_KEY},
                    timeout=6
                )
                if r.status_code == 200:
                    data = r.json()
                    p = data.get("price")
                    if p and isinstance(p, (int, float)):
                        prices.append({
                            "date":  date,
                            "close": float(p),
                            "open":  float(data.get("open_price") or p),
                            "high":  float(data.get("high_price") or p),
                            "low":   float(data.get("low_price")  or p),
                        })
            except: pass
        if prices:
            os.makedirs(STATE_DIR, exist_ok=True)
            with open(cache, "w", encoding="utf-8") as f:
                json.dump({"prices":prices,"last_update":datetime.now().isoformat(),"source":"goldapi"}, f)
            print("[history] Saved", len(prices), "candles from goldapi")
            return prices
    return []
