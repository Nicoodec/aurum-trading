from agents.signal_engine import get_signal, compute_all_indicators, SIGNAL_PARAMS, format_signal_summary

KEY_LEVELS = [3000,3100,3200,3300,3400,3500,3600,3700,3800,3900,
              4000,4100,4200,4300,4400,4500,4600,4700,4750,4800,
              4850,4900,4950,5000,5100,5200,5300,5400,5500]

def nearest_levels(price, n=3):
    below = sorted([l for l in KEY_LEVELS if l < price], reverse=True)[:n]
    above = sorted([l for l in KEY_LEVELS if l > price])[:n]
    sup   = below[0] if below else round(price * 0.985, 2)
    res   = above[0] if above else round(price * 1.015, 2)
    return sup, res

def analyze(price_data, d1_candles=None):
    """
    Analisis tecnico usando signal_engine como fuente de verdad.
    Si d1_candles disponible (de MT5), usa datos reales.
    Si no, usa price_data como fallback.
    """
    price  = price_data.get("price", 0)
    high   = price_data.get("high", price)
    low    = price_data.get("low", price)
    chg    = price_data.get("change_pct", 0)

    # Intentar usar candles D1 de MT5
    if d1_candles and len(d1_candles) >= 30:
        candles = d1_candles
    else:
        try:
            import MetaTrader5 as mt5
            from datetime import datetime
            if mt5.initialize():
                rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_D1, 0, 100)
                if rates is not None and len(rates) >= 30:
                    candles = [{"date": datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d"),
                                "open": float(r["open"]), "high": float(r["high"]),
                                "low": float(r["low"]), "close": float(r["close"])}
                               for r in rates]
                else:
                    candles = None
                mt5.shutdown()
            else:
                candles = None
        except:
            candles = None

    if candles:
        ind = compute_all_indicators(candles, SIGNAL_PARAMS)
        rsi   = ind["rsi"]
        ema9  = ind["ema9"]
        ema21 = ind["ema21"]
        ema50 = ind["ema50"]
        sma20 = ind["sma20"]
        atr   = ind["atr"]
        adx   = ind["adx"]
        closes = [c["close"] for c in candles]
        trend_fast = "UP"  if ema9  and ema21 and ema9>ema21   else "DOWN"
        trend_mid  = "UP"  if ema21 and ema50 and ema21>ema50  else "DOWN"
        trend_slow = "UP"  if price and ema50 and price>ema50  else "DOWN"
        trend = trend_slow
        rsi_zone = ("OVERBOUGHT" if rsi and rsi>70
                    else "OVERSOLD" if rsi and rsi<30 else "NEUTRAL")
    else:
        rsi=None; ema9=None; ema21=None; ema50=None
        sma20=None; atr=None; adx=None
        trend="UNKNOWN"; rsi_zone="UNKNOWN"
        trend_fast=trend_mid=trend_slow="UNKNOWN"

    sup, res = nearest_levels(price)

    return {
        "trend":      trend,
        "trend_fast": trend_fast,
        "trend_mid":  trend_mid,
        "trend_slow": trend_slow,
        "rsi_zone":   rsi_zone,
        "rsi_value":  rsi,
        "sma20":      sma20,
        "ema9":       ema9,
        "ema21":      ema21,
        "ema50":      ema50,
        "atr":        atr,
        "adx":        adx,
        "support":    sup,
        "resistance": res,
        "bias":       ("BULLISH" if trend_slow=="UP"
                       else "BEARISH" if trend_slow=="DOWN" else "NEUTRAL"),
        "confidence": 65 if candles else 40,
        "analysis":   (f"EMA9={ema9} EMA21={ema21} EMA50={ema50} "
                       f"RSI={rsi} ADX={adx} Trend={trend_slow}")
    }
