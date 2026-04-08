import requests, os, json
from datetime import datetime, timedelta
from config import STATE_DIR, GOLDAPI_KEY

HISTORY_FILE = os.path.join(STATE_DIR, "price_history.json")

def fetch_recent_prices(days=30):
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            cached = json.load(f)
        prices = cached.get("prices", [])
        last   = cached.get("last_update", "")
        if prices and len(prices) >= 10 and last[:10] == datetime.now().strftime("%Y-%m-%d"):
            return prices

    prices = []
    if GOLDAPI_KEY:
        for d in range(days, 0, -1):
            date = (datetime.now() - timedelta(days=d)).strftime("%Y%m%d")
            try:
                import requests as req
                r = req.get(
                    f"https://www.goldapi.io/api/XAU/USD/{date}",
                    headers={"x-access-token": GOLDAPI_KEY},
                    timeout=8
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
            except Exception as e:
                pass

    if prices:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"prices": prices, "last_update": datetime.now().isoformat()}, f)

    return prices

def calculate_rsi(prices, period=14):
    closes = [p["close"] for p in prices if p.get("close") and isinstance(p["close"], (int, float))]
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs  = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 1)

def calculate_sma(prices, period):
    closes = [p["close"] for p in prices if p.get("close") and isinstance(p["close"], (int, float))]
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)

def find_support_resistance(prices):
    closes = [p["close"] for p in prices if p.get("close") and isinstance(p["close"], (int, float))]
    highs  = [p.get("high") or p["close"] for p in prices if p.get("close")]
    lows   = [p.get("low")  or p["close"] for p in prices if p.get("close")]
    highs  = [h for h in highs if isinstance(h, (int, float))]
    lows   = [l for l in lows  if isinstance(l, (int, float))]
    if not closes:
        return None, None
    current    = closes[-1]
    candidates_s = sorted([l for l in lows   if l < current], reverse=True)
    candidates_r = sorted([h for h in highs  if h > current])
    support    = round(candidates_s[0], 2) if candidates_s else None
    resistance = round(candidates_r[0], 2) if candidates_r else None
    return support, resistance

def get_full_technical_context(current_price):
    prices = fetch_recent_prices(days=25)
    if current_price and isinstance(current_price, (int, float)):
        prices.append({"close": current_price, "high": current_price, "low": current_price, "open": current_price})
    if not prices:
        return {
            "rsi": None, "sma20": None, "sma50": None,
            "support": round(current_price * 0.985, 2) if current_price else None,
            "resistance": round(current_price * 1.015, 2) if current_price else None,
            "trend_20d": "UNKNOWN", "price_vs_sma": "UNKNOWN", "history_days": 0
        }
    rsi   = calculate_rsi(prices)
    sma20 = calculate_sma(prices, 20)
    sma50 = calculate_sma(prices, 50)
    support, resistance = find_support_resistance(prices)
    closes = [p["close"] for p in prices if p.get("close") and isinstance(p["close"], (int, float))]
    trend_20d = "UP" if len(closes) >= 20 and closes[-1] > closes[-20] else ("DOWN" if len(closes) >= 20 else "UNKNOWN")
    price_vs_sma = "ABOVE" if (sma20 and current_price and current_price > sma20) else "BELOW"
    return {
        "rsi": rsi, "sma20": sma20, "sma50": sma50,
        "support": support, "resistance": resistance,
        "trend_20d": trend_20d, "price_vs_sma": price_vs_sma,
        "history_days": len(prices)
    }
