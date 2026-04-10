from agents.signal_engine import (
    get_signal, get_signal_from_mt5, format_signal_summary,
    SIGNAL_PARAMS, _ema, _rsi, _atr, _adx, _bb, _sma
)

KEY_LEVELS = [
    3000,3100,3200,3300,3400,3500,3600,3700,3800,3900,
    4000,4100,4200,4300,4400,4500,4600,4700,4750,4800,
    4850,4900,4950,5000,5100,5200,5300,5400,5500
]

def nearest_levels(price, n=3):
    below = sorted([l for l in KEY_LEVELS if l < price], reverse=True)[:n]
    above = sorted([l for l in KEY_LEVELS if l > price])[:n]
    return (below[0] if below else round(price*0.985,2),
            above[0] if above else round(price*1.015,2))

def analyze(price_data, d1_candles=None):
    price = price_data.get("price", 0)
    sig, _ = get_signal_from_mt5(verbose=False)
    sup, res = nearest_levels(price)
    if sig:
        return {
            "trend":      sig.get("d1_trend", "UNKNOWN"),
            "trend_fast": sig.get("h1_fast", "UNKNOWN"),
            "trend_mid":  sig.get("h1_mid",  "UNKNOWN"),
            "trend_slow": sig.get("h1_slow", "UNKNOWN"),
            "rsi_zone":   ("OVERBOUGHT" if sig["rsi"] and sig["rsi"]>70
                           else "OVERSOLD" if sig["rsi"] and sig["rsi"]<30
                           else "NEUTRAL"),
            "rsi_value":  sig.get("rsi"),
            "sma20":      sig.get("ema21"),
            "ema9":       sig.get("ema9"),
            "ema21":      sig.get("ema21"),
            "ema50":      sig.get("ema50"),
            "atr":        sig.get("atr"),
            "adx":        sig.get("adx"),
            "support":    sup,
            "resistance": res,
            "bias":       "BULLISH" if sig["signal"]=="LONG" else "BEARISH",
            "confidence": sig.get("confidence", 60),
            "analysis":   sig.get("reason",""),
        }
    else:
        try:
            import MetaTrader5 as mt5
            from datetime import datetime
            mt5.initialize()
            rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, 60)
            mt5.shutdown()
            if rates is not None and len(rates) >= 20:
                closes = [float(r["close"]) for r in rates]
                candles = [{"high":float(r["high"]),"low":float(r["low"]),"close":float(r["close"])} for r in rates]
                rsi  = _rsi(closes, 14)
                ema9 = _ema(closes, 9)
                ema21= _ema(closes, 21)
                ema50= _ema(closes, 50)
                atr  = _atr(candles, 14)
                adx  = _adx(candles, 14)
                trend_slow = "UP" if price > (ema50 or price) else "DOWN"
                return {
                    "trend":      trend_slow,
                    "trend_fast": "UP" if (ema9 and ema21 and ema9>ema21) else "DOWN",
                    "trend_mid":  "UP" if (ema21 and ema50 and ema21>ema50) else "DOWN",
                    "trend_slow": trend_slow,
                    "rsi_zone":   "OVERBOUGHT" if rsi and rsi>70 else ("OVERSOLD" if rsi and rsi<30 else "NEUTRAL"),
                    "rsi_value":  rsi,
                    "sma20":      ema21,
                    "ema9":       ema9,
                    "ema21":      ema21,
                    "ema50":      ema50,
                    "atr":        atr,
                    "adx":        adx,
                    "support":    sup,
                    "resistance": res,
                    "bias":       "BULLISH" if trend_slow=="UP" else "BEARISH",
                    "confidence": 50,
                    "analysis":   f"No signal | RSI={rsi} ADX={adx}",
                }
        except Exception as e:
            print("[tech] error:", e)
        return {
            "trend":"UNKNOWN","trend_fast":"UNKNOWN","trend_mid":"UNKNOWN",
            "trend_slow":"UNKNOWN","rsi_zone":"NEUTRAL","rsi_value":None,
            "sma20":None,"ema9":None,"ema21":None,"ema50":None,
            "atr":None,"adx":None,"support":sup,"resistance":res,
            "bias":"NEUTRAL","confidence":40,"analysis":"No data",
        }
