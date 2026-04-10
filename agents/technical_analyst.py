from agents.signal_engine import get_signal_from_mt5, format_signal_summary

def analyze(price_data, d1_candles=None):
    price = price_data.get("price", 0)
    sig, _ = get_signal_from_mt5(verbose=False)

    KEY_LEVELS = [3000,3200,3400,3500,3600,3700,3800,3900,4000,4100,
                  4200,4300,4400,4500,4600,4700,4750,4800,4850,4900,
                  4950,5000,5100,5200,5300,5400,5500]
    below = sorted([l for l in KEY_LEVELS if l < price], reverse=True)
    above = sorted([l for l in KEY_LEVELS if l > price])
    sup = below[0] if below else round(price*0.985, 2)
    res = above[0] if above else round(price*1.015, 2)

    if sig:
        return {
            "trend":      "UP" if sig["signal"]=="LONG" else "DOWN",
            "trend_fast": "UP" if sig["signal"]=="LONG" else "DOWN",
            "trend_mid":  "UP" if sig["signal"]=="LONG" else "DOWN",
            "trend_slow": "UP" if sig["signal"]=="LONG" else "DOWN",
            "rsi_zone":   "NEUTRAL",
            "rsi_value":  sig.get("rsi"),
            "sma20":      sig.get("ema50"),
            "ema9":       sig.get("ema50"),
            "ema21":      sig.get("ema50"),
            "ema50":      sig.get("ema50"),
            "atr":        sig.get("atr"),
            "adx":        sig.get("adx"),
            "support":    sup,
            "resistance": res,
            "bias":       "BULLISH" if sig["signal"]=="LONG" else "BEARISH",
            "confidence": sig.get("confidence", 60),
            "analysis":   sig.get("reason", ""),
        }

    # Sin señal — calcular indicadores basicos desde MT5
    try:
        import MetaTrader5 as mt5
        from datetime import datetime
        from agents.signal_engine import _ema, _rsi, _atr, _adx
        mt5.initialize()
        rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, 60)
        mt5.shutdown()
        if rates is not None and len(rates) >= 20:
            closes  = [float(r["close"]) for r in rates]
            candles = [{"high":float(r["high"]),"low":float(r["low"]),"close":float(r["close"])} for r in rates]
            rsi_v   = _rsi(closes, 14)
            ema50_v = _ema(closes, 50)
            atr_v   = _atr(candles, 14)
            adx_v   = _adx(candles, 14)
            trend   = "UP" if price > (ema50_v or price) else "DOWN"
            return {
                "trend": trend, "trend_fast": trend, "trend_mid": trend, "trend_slow": trend,
                "rsi_zone": "OVERBOUGHT" if rsi_v and rsi_v>70 else ("OVERSOLD" if rsi_v and rsi_v<30 else "NEUTRAL"),
                "rsi_value": rsi_v, "sma20": ema50_v, "ema9": ema50_v,
                "ema21": ema50_v, "ema50": ema50_v, "atr": atr_v, "adx": adx_v,
                "support": sup, "resistance": res,
                "bias": "BULLISH" if trend=="UP" else "BEARISH",
                "confidence": 50, "analysis": "No setup | RSI="+str(rsi_v)+" ADX="+str(adx_v),
            }
    except Exception as e:
        print("[tech] error:", e)

    return {
        "trend":"UNKNOWN","trend_fast":"UNKNOWN","trend_mid":"UNKNOWN","trend_slow":"UNKNOWN",
        "rsi_zone":"NEUTRAL","rsi_value":None,"sma20":None,"ema9":None,"ema21":None,
        "ema50":None,"atr":None,"adx":None,"support":sup,"resistance":res,
        "bias":"NEUTRAL","confidence":40,"analysis":"No data",
    }
