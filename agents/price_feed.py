import requests, os
from dotenv import load_dotenv
load_dotenv()
GOLDAPI_KEY = os.getenv("GOLDAPI_KEY", "")

_last_price = None

def get_xauusd():
    global _last_price

    # Fuente 1: MT5 tick en tiempo real (instantaneo)
    try:
        import MetaTrader5 as mt5
        if mt5.initialize():
            tick = mt5.symbol_info_tick("XAUUSD")
            if tick and tick.bid > 0:
                price  = round((tick.bid + tick.ask) / 2, 2)
                spread = round(tick.ask - tick.bid, 2)
                mt5.shutdown()
                _last_price = price
                return {
                    "price":      price,
                    "bid":        tick.bid,
                    "ask":        tick.ask,
                    "spread":     spread,
                    "open":       None,
                    "high":       None,
                    "low":        None,
                    "change":     None,
                    "change_pct": None,
                    "source":     "MT5_realtime"
                }
        mt5.shutdown()
    except Exception as e:
        print("[price_feed] MT5 error:", e)

    # Fuente 2: GoldAPI (puede tener delay)
    if GOLDAPI_KEY:
        try:
            r = requests.get(
                "https://www.goldapi.io/api/XAU/USD",
                headers={"x-access-token": GOLDAPI_KEY},
                timeout=10
            )
            if r.status_code == 200:
                d = r.json()
                price = d.get("price")
                if price:
                    _last_price = float(price)
                    return {
                        "price":      float(price),
                        "open":       d.get("open_price"),
                        "high":       d.get("high_price"),
                        "low":        d.get("low_price"),
                        "change":     d.get("ch"),
                        "change_pct": d.get("chp"),
                        "bid":        d.get("bid"),
                        "ask":        d.get("ask"),
                        "source":     "goldapi"
                    }
        except Exception as e:
            print("[price_feed] goldapi error:", e)

    if _last_price:
        print("[price_feed] Using cached price:", _last_price)
        return {"price": _last_price, "open": None, "high": None, "low": None,
                "change": None, "change_pct": None, "source": "cached"}

    return {"price": None, "open": None, "high": None, "low": None,
            "change": None, "change_pct": None, "source": "unavailable"}

def get_technical_data():
    d = get_xauusd()
    # Si MT5 da precio pero no high/low, calcular desde historial MT5
    if d["source"] == "MT5_realtime" and not d.get("high"):
        try:
            import MetaTrader5 as mt5
            from datetime import datetime
            if mt5.initialize():
                rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_D1, 0, 1)
                if rates is not None and len(rates) > 0:
                    d["open"]  = float(rates[0]["open"])
                    d["high"]  = float(rates[0]["high"])
                    d["low"]   = float(rates[0]["low"])
                    p = d["price"]
                    op = d["open"]
                    if op and op > 0:
                        d["change"]     = round(p - op, 2)
                        d["change_pct"] = round((p - op) / op * 100, 2)
                mt5.shutdown()
        except Exception as e:
            print("[price_feed] MT5 OHLC error:", e)
    return d
