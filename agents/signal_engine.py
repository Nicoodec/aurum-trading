"""
AURUM Signal Engine — Technical Core
=====================================
Fuente de verdad para señales de entrada.
Usado tanto en live trading como en backtest.
Parametros calibrados con walk-forward en 500 dias D1.
"""

# ═══════════════════════════════════════════════════════════
# PARAMETROS CALIBRADOS (walk-forward optimizados)
# ═══════════════════════════════════════════════════════════

SIGNAL_PARAMS = {
    # Indicadores
    "rsi_period":           14,
    "ema_fast":              9,
    "ema_mid":              21,
    "ema_slow":             50,
    "sma_period":           20,
    "atr_period":           14,
    "adx_period":           14,
    "bb_period":            20,

    # Filtros de tendencia
    "adx_min":              20,     # ADX minimo para considerar tendencia
    "adx_strong":           25,     # ADX para boost de confianza

    # Zonas RSI
    "rsi_long_min":         35,
    "rsi_long_max":         62,
    "rsi_short_min":        38,
    "rsi_short_max":        65,
    "rsi_oversold":         32,
    "rsi_overbought":       68,

    # Proximidad EMA (en unidades ATR)
    "pullback_ema21_dist":  0.5,
    "pullback_ema9_dist":   0.3,
    "trend_ema9_dist":      0.8,

    # Filtro de extension (ATR desde SMA20)
    "extension_limit":      2.0,

    # Risk management
    "sl_atr_mult":          1.5,
    "tp_atr_mult":          3.0,
    "min_rr":               2.0,

    # Tipos de señal activos
    "use_pullback_ema21":   True,
    "use_pullback_ema9":    True,
    "use_bb_reversal":      True,
    "use_trend":            True,
    "use_short":            True,
}


# ═══════════════════════════════════════════════════════════
# INDICADORES
# ═══════════════════════════════════════════════════════════

def _rsi(closes, period):
    if len(closes) < period + 1: return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    if al == 0: return 100.0
    return round(100 - 100 / (1 + ag / al), 1)

def _ema(closes, period):
    if len(closes) < period: return None
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for c in closes[period:]: ema = c * k + ema * (1 - k)
    return round(ema, 2)

def _sma(closes, period):
    if len(closes) < period: return None
    return round(sum(closes[-period:]) / period, 2)

def _atr(candles, period):
    trs = []
    for i in range(1, len(candles)):
        h  = candles[i]["high"]
        l  = candles[i]["low"]
        pc = candles[i-1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period: return None
    return round(sum(trs[-period:]) / period, 2)

def _adx(candles, period):
    if len(candles) < period + 2: return None
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, len(candles)):
        h  = candles[i]["high"];   l  = candles[i]["low"]
        ph = candles[i-1]["high"]; pl = candles[i-1]["low"]
        pc = candles[i-1]["close"]
        up = h - ph; down = pl - l
        plus_dm.append(up   if up > down   and up > 0   else 0)
        minus_dm.append(down if down > up  and down > 0 else 0)
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    def smooth(arr):
        s = sum(arr[:period]); result = [s]
        for v in arr[period:]: s = s - s / period + v; result.append(s)
        return result
    s14 = smooth(trs); pd14 = smooth(plus_dm); md14 = smooth(minus_dm)
    adx_v = []
    for i in range(len(s14)):
        if s14[i] == 0: continue
        pdi = 100 * pd14[i] / s14[i]
        mdi = 100 * md14[i] / s14[i]
        dx  = 100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) > 0 else 0
        adx_v.append(dx)
    if len(adx_v) < period: return None
    return round(sum(adx_v[-period:]) / period, 1)

def _bb(closes, period):
    import statistics
    if len(closes) < period: return None, None, None
    sma = sum(closes[-period:]) / period
    std = statistics.stdev(closes[-period:])
    return round(sma + 2*std, 2), round(sma, 2), round(sma - 2*std, 2)

def compute_all_indicators(candles, p=None):
    """Calcula todos los indicadores. Retorna dict con valores."""
    if p is None: p = SIGNAL_PARAMS
    closes = [c["close"] for c in candles]
    return {
        "rsi":   _rsi(closes, p["rsi_period"]),
        "ema9":  _ema(closes, p["ema_fast"]),
        "ema21": _ema(closes, p["ema_mid"]),
        "ema50": _ema(closes, p["ema_slow"]),
        "sma20": _sma(closes, p["sma_period"]),
        "atr":   _atr(candles, p["atr_period"]),
        "adx":   _adx(candles, p["adx_period"]),
        "bb":    _bb(closes, p["bb_period"]),
    }


# ═══════════════════════════════════════════════════════════
# GENERADOR DE SEÑALES
# ═══════════════════════════════════════════════════════════

def get_signal(candles, p=None, verbose=False):
    """
    Genera señal tecnica pura basada en EMA + ADX + RSI + BB.

    Args:
        candles: lista de dicts con open/high/low/close/date
        p: parametros (usa SIGNAL_PARAMS por defecto)
        verbose: si True, imprime razonamiento

    Returns:
        dict con signal, sig_type, confidence, sl_dist, tp_dist, etc.
        None si no hay setup valido.
    """
    if p is None: p = SIGNAL_PARAMS

    min_needed = max(p["ema_slow"], p["adx_period"], p["bb_period"]) + 5
    if len(candles) < min_needed:
        if verbose: print(f"[signal] Not enough candles ({len(candles)}/{min_needed})")
        return None

    ind = compute_all_indicators(candles, p)
    rsi   = ind["rsi"]
    ema9  = ind["ema9"]
    ema21 = ind["ema21"]
    ema50 = ind["ema50"]
    sma20 = ind["sma20"]
    atr   = ind["atr"]
    adx   = ind["adx"]
    bb_up, _, bb_lo = ind["bb"]

    if any(v is None for v in [rsi, ema9, ema21, ema50, atr, sma20]):
        if verbose: print("[signal] Missing indicators")
        return None

    price  = candles[-1]["close"]
    c      = candles[-1]
    chg    = round((c["close"] - c["open"]) / c["open"] * 100, 2)

    # Estructura de tendencia
    trend_fast = "UP"   if ema9  > ema21  else "DOWN"
    trend_mid  = "UP"   if ema21 > ema50  else "DOWN"
    trend_slow = "UP"   if price > ema50  else "DOWN"

    # Distancias en unidades ATR
    dist_ema9  = abs(price - ema9)  / atr
    dist_ema21 = abs(price - ema21) / atr
    dist_sma20 = (price - sma20)    / atr   # positivo = por encima

    # Flags de tendencia
    trending     = adx is None or adx > p["adx_min"]
    strong_trend = adx is not None and adx > p["adx_strong"]
    ext_up       = dist_sma20 >  p["extension_limit"]   # precio muy extendido arriba
    ext_dn       = dist_sma20 < -p["extension_limit"]   # precio muy extendido abajo

    if verbose:
        print(f"[signal] Price={price} RSI={rsi} ADX={adx}")
        print(f"[signal] EMA9={ema9} EMA21={ema21} EMA50={ema50}")
        print(f"[signal] Trend: fast={trend_fast} mid={trend_mid} slow={trend_slow}")
        print(f"[signal] Dist EMA9={round(dist_ema9,2)} EMA21={round(dist_ema21,2)} SMA20={round(dist_sma20,2)}")
        print(f"[signal] Extended up={ext_up} dn={ext_dn} Trending={trending}")

    signal     = None
    reason     = ""
    confidence = 60
    sig_type   = ""

    # ── A: Pullback a EMA21 LONG (mejor señal) ──────────────
    if (p["use_pullback_ema21"]
        and trend_fast == "UP" and trend_mid == "UP" and trend_slow == "UP"
        and dist_ema21 <= p["pullback_ema21_dist"]
        and p["rsi_long_min"] <= rsi <= (p["rsi_long_max"] - 10)
        and trending and not ext_up and chg > -2.0):
        signal="LONG"; sig_type="PULLBACK_EMA21"; confidence=78
        if strong_trend: confidence += 4
        if rsi < 48:     confidence += 3
        reason = f"Pullback EMA21 uptrend | RSI={rsi} ADX={adx}"

    # ── B: Pullback a EMA9 LONG ─────────────────────────────
    elif (p["use_pullback_ema9"]
          and trend_fast == "UP" and trend_mid == "UP" and trend_slow == "UP"
          and dist_ema9 <= p["pullback_ema9_dist"]
          and (p["rsi_long_min"]+5) <= rsi <= (p["rsi_long_max"]-7)
          and strong_trend and not ext_up):
        signal="LONG"; sig_type="PULLBACK_EMA9"; confidence=74
        if adx > 30: confidence += 4
        reason = f"Pullback EMA9 strong uptrend | RSI={rsi} ADX={adx}"

    # ── C: Pullback a EMA21 SHORT ───────────────────────────
    elif (p["use_pullback_ema21"] and p["use_short"]
          and trend_fast == "DOWN" and trend_mid == "DOWN" and trend_slow == "DOWN"
          and dist_ema21 <= p["pullback_ema21_dist"]
          and (p["rsi_short_min"]+10) <= rsi <= p["rsi_short_max"]
          and trending and not ext_dn and chg < 2.0):
        signal="SHORT"; sig_type="PULLBACK_EMA21"; confidence=78
        if strong_trend: confidence += 4
        if rsi > 52:     confidence += 3
        reason = f"Pullback EMA21 downtrend | RSI={rsi} ADX={adx}"

    # ── D: Pullback a EMA9 SHORT ────────────────────────────
    elif (p["use_pullback_ema9"] and p["use_short"]
          and trend_fast == "DOWN" and trend_mid == "DOWN" and trend_slow == "DOWN"
          and dist_ema9 <= p["pullback_ema9_dist"]
          and (p["rsi_short_min"]+7) <= rsi <= (p["rsi_short_max"]-5)
          and strong_trend and not ext_dn):
        signal="SHORT"; sig_type="PULLBACK_EMA9"; confidence=74
        if adx > 30: confidence += 4
        reason = f"Pullback EMA9 strong downtrend | RSI={rsi} ADX={adx}"

    # ── E: BB Oversold en uptrend ───────────────────────────
    elif (p["use_bb_reversal"]
          and bb_lo and price < bb_lo
          and rsi < p["rsi_oversold"]
          and trend_slow == "UP"
          and not ext_dn and chg > -3.0):
        signal="LONG"; sig_type="BB_REVERSAL"; confidence=72
        reason = f"BB lower breach oversold | RSI={rsi}"

    # ── F: BB Overbought en downtrend ───────────────────────
    elif (p["use_bb_reversal"] and p["use_short"]
          and bb_up and price > bb_up
          and rsi > p["rsi_overbought"]
          and trend_slow == "DOWN"
          and not ext_up and chg < 3.0):
        signal="SHORT"; sig_type="BB_REVERSAL"; confidence=72
        reason = f"BB upper breach overbought | RSI={rsi}"

    # ── G: Trend LONG (conservador, no extendido) ───────────
    elif (p["use_trend"]
          and trend_fast == "UP" and trend_mid == "UP" and trend_slow == "UP"
          and (p["rsi_long_min"]+10) <= rsi <= p["rsi_long_max"]
          and trending and not ext_up
          and dist_ema9 < p["trend_ema9_dist"]
          and chg > -1.0):
        signal="LONG"; sig_type="TREND"; confidence=65
        if strong_trend: confidence += 4
        reason = f"Trend LONG near EMA9 | RSI={rsi} ADX={adx}"

    # ── H: Trend SHORT (conservador, no extendido) ──────────
    elif (p["use_trend"] and p["use_short"]
          and trend_fast == "DOWN" and trend_mid == "DOWN" and trend_slow == "DOWN"
          and p["rsi_short_min"] <= rsi <= (p["rsi_short_max"]-10)
          and trending and not ext_dn
          and dist_ema9 < p["trend_ema9_dist"]
          and chg < 1.0):
        signal="SHORT"; sig_type="TREND"; confidence=65
        if strong_trend: confidence += 4
        reason = f"Trend SHORT near EMA9 | RSI={rsi} ADX={adx}"

    if signal is None:
        if verbose: print("[signal] No valid setup found")
        return None

    sl_dist = round(atr * p["sl_atr_mult"], 2)
    tp_dist = round(atr * p["tp_atr_mult"], 2)
    rr      = round(tp_dist / sl_dist, 1)

    if rr < p["min_rr"]:
        if verbose: print(f"[signal] RR={rr} below minimum {p['min_rr']}")
        return None

    result = {
        # Señal
        "signal":      signal,
        "sig_type":    sig_type,
        "confidence":  confidence,
        "reason":      reason,

        # Precio y niveles
        "price":       price,
        "sl_dist":     sl_dist,
        "tp_dist":     tp_dist,
        "rr":          rr,

        # Indicadores (para logging y análisis)
        "rsi":         rsi,
        "ema9":        ema9,
        "ema21":       ema21,
        "ema50":       ema50,
        "sma20":       sma20,
        "atr":         atr,
        "adx":         adx,
        "bb_up":       bb_up,
        "bb_lo":       bb_lo,

        # Contexto
        "trend_fast":  trend_fast,
        "trend_mid":   trend_mid,
        "trend_slow":  trend_slow,
        "dist_ema9":   round(dist_ema9, 2),
        "dist_ema21":  round(dist_ema21, 2),
        "dist_sma20":  round(dist_sma20, 2),
        "ext_up":      ext_up,
        "ext_dn":      ext_dn,
        "trending":    trending,
        "strong_trend":strong_trend,
        "chg":         chg,
    }

    if verbose:
        print(f"[signal] ✓ {signal} {sig_type} conf={confidence}% | {reason}")

    return result


def get_signal_from_mt5(p=None, verbose=False):
    """
    Obtiene candles D1 de MT5 y genera señal tecnica.
    Conveniencia para uso en main.py.
    """
    try:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            if verbose: print("[signal] MT5 not available")
            return None, None
        rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_D1, 0, 100)
        mt5.shutdown()
        if rates is None or len(rates) == 0:
            return None, None
        from datetime import datetime
        candles = [{
            "date":  datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d"),
            "open":  float(r["open"]),
            "high":  float(r["high"]),
            "low":   float(r["low"]),
            "close": float(r["close"]),
        } for r in rates]
        sig = get_signal(candles, p, verbose=verbose)
        return sig, candles
    except Exception as e:
        if verbose: print(f"[signal] MT5 error: {e}")
        return None, None


def format_signal_summary(sig):
    """Formato legible para logs."""
    if sig is None:
        return "No technical setup"
    return (
        f"{sig['signal']} {sig['sig_type']} | "
        f"conf={sig['confidence']}% | "
        f"RSI={sig['rsi']} ADX={sig['adx']} | "
        f"Trend: {sig['trend_fast']}/{sig['trend_mid']}/{sig['trend_slow']} | "
        f"SL={sig['sl_dist']} TP={sig['tp_dist']} RR={sig['rr']} | "
        f"{sig['reason']}"
    )
