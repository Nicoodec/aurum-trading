"""
AURUM Signal Engine v2 — Intraday H1 + D1 Filter
==================================================
- D1: filtro de tendencia (direccion principal)
- H1: señal de entrada (timing preciso)
- ATR H1 ~$19 -> SL ~$29, TP ~$58
- Trades duran 2-8 horas tipicamente
"""

import MetaTrader5 as mt5
from datetime import datetime
import statistics

# ═══════════════════════════════════════════════════════════════
# PARAMETROS
# ═══════════════════════════════════════════════════════════════

SIGNAL_PARAMS = {
    # Timeframes
    "tf_trend":     mt5.TIMEFRAME_D1,   # tendencia principal
    "tf_entry":     mt5.TIMEFRAME_H1,   # entrada

    # Candles a cargar
    "d1_candles":   50,
    "h1_candles":   100,                # ultimas 100h ~4 dias de datos

    # Indicadores D1 (tendencia)
    "d1_ema_fast":  9,
    "d1_ema_slow":  21,

    # Indicadores H1 (entrada)
    "h1_ema_fast":  9,
    "h1_ema_mid":   21,
    "h1_ema_slow":  50,
    "h1_rsi_period":14,
    "h1_atr_period":14,
    "h1_adx_period":14,
    "h1_bb_period": 20,

    # Filtros RSI H1
    "rsi_long_min":  35,
    "rsi_long_max":  68,
    "rsi_short_min": 35,
    "rsi_short_max": 65,
    "rsi_oversold":  30,
    "rsi_overbought":70,

    # ADX
    "adx_min":    18,
    "adx_strong": 25,

    # Distancias EMA (en ATR H1)
    "pullback_ema21_dist": 0.4,
    "pullback_ema9_dist":  0.25,
    "trend_ema9_dist":     0.6,
    "extension_limit":     1.8,

    # Risk
    "sl_atr_mult": 1.5,
    "tp_atr_mult": 3.0,
    "min_rr":      2.0,

    # Señales activas
    "use_pullback_ema21": True,
    "use_pullback_ema9":  True,
    "use_bb_reversal":    True,
    "use_trend":          True,
    "use_short":          True,

    # Filtro horario (UTC) - evitar primeras y ultimas horas de sesion
    "session_start_utc": 7,    # 07:00 UTC = 09:00 Madrid
    "session_end_utc":   20,   # 20:00 UTC = 22:00 Madrid
}


# ═══════════════════════════════════════════════════════════════
# INDICADORES
# ═══════════════════════════════════════════════════════════════

def _rsi(closes, period):
    if len(closes) < period + 1: return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    if al == 0: return 100.0
    return round(100 - 100 / (1 + ag/al), 1)

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
        h=candles[i]["high"]; l=candles[i]["low"]; pc=candles[i-1]["close"]
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
    if len(trs) < period: return None
    return round(sum(trs[-period:]) / period, 2)

def _adx(candles, period):
    if len(candles) < period + 2: return None
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, len(candles)):
        h=candles[i]["high"]; l=candles[i]["low"]
        ph=candles[i-1]["high"]; pl=candles[i-1]["low"]; pc=candles[i-1]["close"]
        up=h-ph; down=pl-l
        plus_dm.append(up   if up>down   and up>0   else 0)
        minus_dm.append(down if down>up  and down>0 else 0)
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
    def smooth(arr):
        s=sum(arr[:period]); result=[s]
        for v in arr[period:]: s=s-s/period+v; result.append(s)
        return result
    s=smooth(trs); pd=smooth(plus_dm); md=smooth(minus_dm)
    adx_v=[]
    for i in range(len(s)):
        if s[i]==0: continue
        pdi=100*pd[i]/s[i]; mdi=100*md[i]/s[i]
        dx=100*abs(pdi-mdi)/(pdi+mdi) if (pdi+mdi)>0 else 0
        adx_v.append(dx)
    if len(adx_v)<period: return None
    return round(sum(adx_v[-period:])/period, 1)

def _bb(closes, period):
    if len(closes) < period: return None, None, None
    sma = sum(closes[-period:])/period
    std = statistics.stdev(closes[-period:])
    return round(sma+2*std,2), round(sma,2), round(sma-2*std,2)


# ═══════════════════════════════════════════════════════════════
# CARGA DE DATOS DESDE MT5
# ═══════════════════════════════════════════════════════════════

def _load_candles(timeframe, count):
    rates = mt5.copy_rates_from_pos("XAUUSD", timeframe, 0, count)
    if rates is None or len(rates) == 0:
        return []
    return [{
        "time":  datetime.fromtimestamp(r["time"]),
        "open":  float(r["open"]),
        "high":  float(r["high"]),
        "low":   float(r["low"]),
        "close": float(r["close"]),
        "vol":   int(r["tick_volume"]),
    } for r in rates]


# ═══════════════════════════════════════════════════════════════
# SEÑAL DE TENDENCIA D1
# ═══════════════════════════════════════════════════════════════

def _get_d1_trend(p):
    candles = _load_candles(p["tf_trend"], p["d1_candles"])
    if len(candles) < 25:
        return "UNKNOWN", None, None

    closes = [c["close"] for c in candles]
    ema9   = _ema(closes, p["d1_ema_fast"])
    ema21  = _ema(closes, p["d1_ema_slow"])
    rsi_d1 = _rsi(closes, 14)
    price  = closes[-1]

    if ema9 and ema21:
        if ema9 > ema21 and price > ema21:
            trend = "UP"
        elif ema9 < ema21 and price < ema21:
            trend = "DOWN"
        else:
            trend = "SIDEWAYS"
    else:
        trend = "UNKNOWN"

    return trend, rsi_d1, price


# ═══════════════════════════════════════════════════════════════
# SEÑAL DE ENTRADA H1
# ═══════════════════════════════════════════════════════════════

def _get_h1_signal(d1_trend, p):
    candles = _load_candles(p["tf_entry"], p["h1_candles"])
    if len(candles) < 55:
        return None

    closes = [c["close"] for c in candles]
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]

    rsi   = _rsi(closes, p["h1_rsi_period"])
    ema9  = _ema(closes, p["h1_ema_fast"])
    ema21 = _ema(closes, p["h1_ema_mid"])
    ema50 = _ema(closes, p["h1_ema_slow"])
    atr   = _atr(candles, p["h1_atr_period"])
    adx   = _adx(candles, p["h1_adx_period"])
    bb_up, bb_mid, bb_lo = _bb(closes, p["h1_bb_period"])

    if any(v is None for v in [rsi, ema9, ema21, ema50, atr]):
        return None

    price = closes[-1]
    c     = candles[-1]
    chg   = round((c["close"] - c["open"]) / c["open"] * 100, 2)

    # Filtro horario — solo operar en sesion activa
    hour_utc = c["time"].hour
    if hour_utc < p["session_start_utc"] or hour_utc >= p["session_end_utc"]:
        return None

    # Tendencia H1
    h1_fast = "UP"   if ema9  > ema21  else "DOWN"
    h1_mid  = "UP"   if ema21 > ema50  else "DOWN"
    h1_slow = "UP"   if price > ema50  else "DOWN"

    # Distancias en ATR
    dist_ema9  = abs(price - ema9)  / atr
    dist_ema21 = abs(price - ema21) / atr
    dist_sma20 = (price - (ema21)) / atr

    trending     = adx is None or adx > p["adx_min"]
    strong_trend = adx is not None and adx > p["adx_strong"]
    ext_up       = dist_sma20 >  p["extension_limit"]
    ext_dn       = dist_sma20 < -p["extension_limit"]

    # Alineacion con D1
    d1_allows_long  = d1_trend in ("UP", "SIDEWAYS", "UNKNOWN")
    d1_allows_short = d1_trend in ("DOWN", "SIDEWAYS", "UNKNOWN")
    d1_confirms_long  = d1_trend == "UP"
    d1_confirms_short = d1_trend == "DOWN"

    signal=None; reason=""; confidence=60; sig_type=""

    # ── A: Pullback EMA21 H1 LONG (D1 uptrend) ─────────────
    if (p["use_pullback_ema21"] and d1_allows_long
        and h1_fast=="UP" and (h1_mid=="UP" or h1_slow=="UP")
        and dist_ema21 <= p["pullback_ema21_dist"]
        and p["rsi_long_min"] <= rsi <= p["rsi_long_max"]-8
        and trending and not ext_up and chg > -1.5):
        signal="LONG"; sig_type="PULLBACK_EMA21"; confidence=75
        if d1_confirms_long: confidence += 6
        if strong_trend:     confidence += 4
        if rsi < 48:         confidence += 3
        reason = f"H1 pullback EMA21 | D1={d1_trend} | RSI={rsi} ADX={adx}"

    # ── B: Pullback EMA9 H1 LONG ────────────────────────────
    elif (p["use_pullback_ema9"] and d1_allows_long
          and h1_fast=="UP" and h1_mid=="UP" and h1_slow=="UP"
          and dist_ema9 <= p["pullback_ema9_dist"]
          and p["rsi_long_min"]+5 <= rsi <= p["rsi_long_max"]-5
          and strong_trend and not ext_up):
        signal="LONG"; sig_type="PULLBACK_EMA9"; confidence=72
        if d1_confirms_long: confidence += 6
        if adx > 30:         confidence += 4
        reason = f"H1 pullback EMA9 | D1={d1_trend} | RSI={rsi} ADX={adx}"

    # ── C: Pullback EMA21 H1 SHORT (D1 downtrend) ──────────
    elif (p["use_pullback_ema21"] and p["use_short"] and d1_allows_short
          and h1_fast=="DOWN" and (h1_mid=="DOWN" or h1_slow=="DOWN")
          and dist_ema21 <= p["pullback_ema21_dist"]
          and p["rsi_short_min"]+8 <= rsi <= p["rsi_short_max"]
          and trending and not ext_dn and chg < 1.5):
        signal="SHORT"; sig_type="PULLBACK_EMA21"; confidence=75
        if d1_confirms_short: confidence += 6
        if strong_trend:      confidence += 4
        if rsi > 52:          confidence += 3
        reason = f"H1 pullback EMA21 | D1={d1_trend} | RSI={rsi} ADX={adx}"

    # ── D: Pullback EMA9 H1 SHORT ───────────────────────────
    elif (p["use_pullback_ema9"] and p["use_short"] and d1_allows_short
          and h1_fast=="DOWN" and h1_mid=="DOWN" and h1_slow=="DOWN"
          and dist_ema9 <= p["pullback_ema9_dist"]
          and p["rsi_short_min"]+5 <= rsi <= p["rsi_short_max"]-5
          and strong_trend and not ext_dn):
        signal="SHORT"; sig_type="PULLBACK_EMA9"; confidence=72
        if d1_confirms_short: confidence += 6
        if adx > 30:          confidence += 4
        reason = f"H1 pullback EMA9 | D1={d1_trend} | RSI={rsi} ADX={adx}"

    # ── E: BB Oversold H1 (D1 uptrend) ─────────────────────
    elif (p["use_bb_reversal"] and d1_allows_long
          and bb_lo and price < bb_lo
          and rsi < p["rsi_oversold"]
          and not ext_dn and chg > -2.0):
        signal="LONG"; sig_type="BB_REVERSAL"; confidence=70
        if d1_confirms_long: confidence += 5
        reason = f"H1 BB oversold bounce | D1={d1_trend} | RSI={rsi}"

    # ── F: BB Overbought H1 (D1 downtrend) ─────────────────
    elif (p["use_bb_reversal"] and p["use_short"] and d1_allows_short
          and bb_up and price > bb_up
          and rsi > p["rsi_overbought"]
          and not ext_up and chg < 2.0):
        signal="SHORT"; sig_type="BB_REVERSAL"; confidence=70
        if d1_confirms_short: confidence += 5
        reason = f"H1 BB overbought | D1={d1_trend} | RSI={rsi}"

    # ── G: Trend LONG H1 (conservador) ──────────────────────
    elif (p["use_trend"] and d1_confirms_long
          and h1_fast=="UP" and h1_mid=="UP" and h1_slow=="UP"
          and p["rsi_long_min"]+10 <= rsi <= p["rsi_long_max"]
          and strong_trend and not ext_up
          and dist_ema9 < p["trend_ema9_dist"] and chg > -0.8):
        signal="LONG"; sig_type="TREND"; confidence=68
        if adx > 30: confidence += 4
        reason = f"H1 trend LONG near EMA9 | D1={d1_trend} | RSI={rsi} ADX={adx}"

    # ── H: Trend SHORT H1 (conservador) ─────────────────────
    elif (p["use_trend"] and p["use_short"] and d1_confirms_short
          and h1_fast=="DOWN" and h1_mid=="DOWN" and h1_slow=="DOWN"
          and p["rsi_short_min"] <= rsi <= p["rsi_short_max"]-10
          and strong_trend and not ext_dn
          and dist_ema9 < p["trend_ema9_dist"] and chg < 0.8):
        signal="SHORT"; sig_type="TREND"; confidence=68
        if adx > 30: confidence += 4
        reason = f"H1 trend SHORT near EMA9 | D1={d1_trend} | RSI={rsi} ADX={adx}"

    if signal is None:
        return None

    sl_dist = round(atr * p["sl_atr_mult"], 2)
    tp_dist = round(atr * p["tp_atr_mult"], 2)
    rr      = round(tp_dist / sl_dist, 1)

    if rr < p["min_rr"]:
        return None

    return {
        "signal":      signal,
        "sig_type":    sig_type,
        "confidence":  confidence,
        "reason":      reason,
        "price":       price,
        "rsi":         rsi,
        "ema9":        ema9,
        "ema21":       ema21,
        "ema50":       ema50,
        "atr":         atr,
        "adx":         adx,
        "bb_up":       bb_up,
        "bb_lo":       bb_lo,
        "sl_dist":     sl_dist,
        "tp_dist":     tp_dist,
        "rr":          rr,
        "d1_trend":    d1_trend,
        "h1_fast":     h1_fast,
        "h1_mid":      h1_mid,
        "h1_slow":     h1_slow,
        "dist_ema9":   round(dist_ema9, 2),
        "dist_ema21":  round(dist_ema21, 2),
        "ext_up":      ext_up,
        "ext_dn":      ext_dn,
        "hour_utc":    hour_utc,
        "chg_h1":      chg,
    }


# ═══════════════════════════════════════════════════════════════
# API PUBLICA
# ═══════════════════════════════════════════════════════════════

def get_signal(candles=None, p=None, verbose=False):
    """Compatibilidad con backtest — usa candles H1 directamente."""
    if p is None: p = SIGNAL_PARAMS
    if candles is None:
        return get_signal_from_mt5(p=p, verbose=verbose)[0]
    # Para backtest: asumir candles son H1, D1 trend desconocido
    return _get_h1_signal_from_candles(candles, "UNKNOWN", p)

def _get_h1_signal_from_candles(candles, d1_trend, p):
    """Version para backtest sin MT5."""
    if len(candles) < 55: return None
    closes=[c["close"] for c in candles]
    rsi  =_rsi(closes, p["h1_rsi_period"])
    ema9 =_ema(closes, p["h1_ema_fast"])
    ema21=_ema(closes, p["h1_ema_mid"])
    ema50=_ema(closes, p["h1_ema_slow"])
    atr  =_atr(candles, p["h1_atr_period"])
    adx  =_adx(candles, p["h1_adx_period"])
    bb_up,_,bb_lo=_bb(closes, p["h1_bb_period"])
    if any(v is None for v in [rsi,ema9,ema21,ema50,atr]): return None
    price=closes[-1]; c=candles[-1]
    chg=round((c["close"]-c["open"])/c["open"]*100,2)
    h1_fast="UP" if ema9>ema21 else "DOWN"
    h1_mid ="UP" if ema21>ema50 else "DOWN"
    h1_slow="UP" if price>ema50 else "DOWN"
    dist_ema9=abs(price-ema9)/atr; dist_ema21=abs(price-ema21)/atr
    dist_sma20=(price-ema21)/atr
    trending=adx is None or adx>p["adx_min"]
    strong_trend=adx is not None and adx>p["adx_strong"]
    ext_up=dist_sma20>p["extension_limit"]; ext_dn=dist_sma20<-p["extension_limit"]
    signal=None; reason=""; confidence=60; sig_type=""
    if (p["use_pullback_ema21"] and h1_fast=="UP" and h1_mid=="UP"
        and dist_ema21<=p["pullback_ema21_dist"]
        and p["rsi_long_min"]<=rsi<=p["rsi_long_max"]-8
        and trending and not ext_up and chg>-1.5):
        signal="LONG"; sig_type="PULLBACK_EMA21"; confidence=75
        if strong_trend: confidence+=4
        reason=f"Pullback EMA21 H1 | D1={d1_trend} | RSI={rsi} ADX={adx}"
    elif (p["use_pullback_ema21"] and p["use_short"] and h1_fast=="DOWN" and h1_mid=="DOWN"
          and dist_ema21<=p["pullback_ema21_dist"]
          and p["rsi_short_min"]+8<=rsi<=p["rsi_short_max"]
          and trending and not ext_dn and chg<1.5):
        signal="SHORT"; sig_type="PULLBACK_EMA21"; confidence=75
        if strong_trend: confidence+=4
        reason=f"Pullback EMA21 H1 | D1={d1_trend} | RSI={rsi} ADX={adx}"
    elif (p["use_trend"] and h1_fast=="UP" and h1_mid=="UP" and h1_slow=="UP"
          and p["rsi_long_min"]+10<=rsi<=p["rsi_long_max"]
          and strong_trend and not ext_up
          and dist_ema9<p["trend_ema9_dist"] and chg>-0.8):
        signal="LONG"; sig_type="TREND"; confidence=65
        reason=f"Trend LONG H1 | RSI={rsi} ADX={adx}"
    elif (p["use_trend"] and p["use_short"] and h1_fast=="DOWN" and h1_mid=="DOWN" and h1_slow=="DOWN"
          and p["rsi_short_min"]<=rsi<=p["rsi_short_max"]-10
          and strong_trend and not ext_dn
          and dist_ema9<p["trend_ema9_dist"] and chg<0.8):
        signal="SHORT"; sig_type="TREND"; confidence=65
        reason=f"Trend SHORT H1 | RSI={rsi} ADX={adx}"
    if signal is None: return None
    sl_dist=round(atr*p["sl_atr_mult"],2)
    tp_dist=round(atr*p["tp_atr_mult"],2)
    rr=round(tp_dist/sl_dist,1)
    if rr<p["min_rr"]: return None
    return {"signal":signal,"sig_type":sig_type,"confidence":confidence,"reason":reason,
            "price":price,"rsi":rsi,"ema9":ema9,"ema21":ema21,"ema50":ema50,
            "atr":atr,"adx":adx,"sl_dist":sl_dist,"tp_dist":tp_dist,"rr":rr,
            "d1_trend":d1_trend,"h1_fast":h1_fast,"h1_mid":h1_mid,"h1_slow":h1_slow,
            "dist_ema9":round(dist_ema9,2),"dist_ema21":round(dist_ema21,2)}

def get_signal_from_mt5(p=None, verbose=False):
    """API principal para main.py"""
    if p is None: p = SIGNAL_PARAMS
    try:
        if not mt5.initialize():
            if verbose: print("[signal] MT5 not available")
            return None, None
        d1_trend, d1_rsi, d1_price = _get_d1_trend(p)
        if verbose:
            print(f"[signal] D1 trend: {d1_trend} | D1 RSI: {d1_rsi} | D1 price: {d1_price}")
        sig = _get_h1_signal(d1_trend, p)
        h1_candles = _load_candles(p["tf_entry"], p["h1_candles"])
        mt5.shutdown()
        if verbose and sig:
            print(f"[signal] H1 signal: {sig['signal']} {sig['sig_type']} conf={sig['confidence']}%")
        elif verbose:
            print("[signal] No H1 setup found")
        return sig, h1_candles
    except Exception as e:
        if verbose: print(f"[signal] error: {e}")
        try: mt5.shutdown()
        except: pass
        return None, None

def format_signal_summary(sig):
    if sig is None: return "No technical setup"
    return (
        f"{sig['signal']} {sig['sig_type']} | conf={sig['confidence']}% | "
        f"D1={sig.get('d1_trend','?')} | "
        f"H1={sig.get('h1_fast','?')}/{sig.get('h1_mid','?')}/{sig.get('h1_slow','?')} | "
        f"RSI={sig['rsi']} ADX={sig['adx']} | "
        f"SL=${sig['sl_dist']} TP=${sig['tp_dist']} RR={sig['rr']} | "
        f"{sig['reason']}"
    )
