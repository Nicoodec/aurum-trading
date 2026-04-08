import requests, os
from dotenv import load_dotenv
load_dotenv()
GOLDAPI_KEY = os.getenv("GOLDAPI_KEY", "")

FALLBACK_PRICE = None

def get_xauusd():
    global FALLBACK_PRICE
    if GOLDAPI_KEY:
        try:
            r = requests.get("https://www.goldapi.io/api/XAU/USD",
                headers={"x-access-token": GOLDAPI_KEY, "Content-Type": "application/json"},
                timeout=10)
            if r.status_code == 200:
                d = r.json()
                price = d.get("price")
                if price:
                    FALLBACK_PRICE = price
                    return {
                        "price":      float(price),
                        "open":       d.get("open_price"),
                        "high":       d.get("high_price"),
                        "low":        d.get("low_price"),
                        "change":     d.get("ch"),
                        "change_pct": d.get("chp"),
                        "prev_close": d.get("prev_close_price"),
                        "ask":        d.get("ask"),
                        "bid":        d.get("bid"),
                        "timestamp":  d.get("timestamp"),
                        "source":     "goldapi.io"
                    }
            print("[price_feed] goldapi status:", r.status_code)
        except Exception as e:
            print("[price_feed] goldapi error:", e)

    # Fallback: MT5 real-time price
    try:
        import MetaTrader5 as mt5
        if mt5.initialize():
            tick = mt5.symbol_info_tick("XAUUSD")
            if tick and tick.bid > 0:
                price = (tick.bid + tick.ask) / 2
                FALLBACK_PRICE = price
                mt5.shutdown()
                return {"price": round(price,2), "open": None, "high": None, "low": None,
                        "change": None, "change_pct": None, "source": "MT5"}
    except Exception as e:
        print("[price_feed] MT5 tick error:", e)

    if FALLBACK_PRICE:
        print("[price_feed] Using last known price:", FALLBACK_PRICE)
        return {"price": FALLBACK_PRICE, "open": None, "high": None, "low": None,
                "change": None, "change_pct": None, "source": "cached"}

    return {"price": None, "open": None, "high": None, "low": None,
            "change": None, "change_pct": None, "source": "unavailable"}

def get_technical_data():
    return get_xauusd()
