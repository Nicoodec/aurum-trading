"""
AURUM Signal Engine - US30 (Dow Jones)
========================================
Estrategia: NY Session Momentum + EMA trend
- H4 EMA200 como filtro de tendencia principal
- H1 EMA50 como nivel de entrada en pullback
- Entrada solo en apertura NY (14:30-16:30 UTC) y continuacion (16:30-20:00 UTC)
- ADX H1 > 20 para confirmar momentum
- Confirmacion de vela: cierre de vuelta en direccion de tendencia
- SL: 1.5x ATR H1
- TP: 3.0x ATR H1 (RR = 2.0 minimo)
- Sizing: 1% riesgo por trade

US30 specs:
- 1 lot = $1 por punto
- Spread tipico: 2-3 puntos
- ATR H1 tipico: 50-130 puntos segun año
"""

import MetaTrader5 as mt5
from datetime import datetime, timezone

SYMBOL = "US30.cash"

# Parametros de la estrategia
PARAMS = {
    "symbol":        "US30.cash",
    "trend_tf":      mt5.TIMEFRAME_H4,   # H4 para tendencia
    "entry_tf":      mt5.TIMEFRAME_H1,   # H1 para entrada
    "trend_ema":     200,                 # EMA tendencia H4
    "entry_ema":     50,                  # EMA entrada H1
    "atr_period":    14,
    "adx_period":    14,
    "adx_min":       20,                  # ADX minimo para operar
    "rsi_period":    14,
    "rsi_long_min":  35,                  # RSI minimo para LONG
    "rsi_long_max":  70,                  # RSI maximo para LONG
    "rsi_short_min": 30,                  # RSI minimo para SHORT
    "rsi_short_max": 65,                  # RSI maximo para SHORT
    "sl_mult":       1.5,                 # SL = 1.5 x ATR
    "tp_mult":       3.0,                 # TP = 3.0 x ATR
    "min_rr":        2.0,
    "dist_min_atr":  1.5,                 # Distancia minima previa a EMA (ATR units)
    "lookback_dist": 20,                  # Barras para calcular distancia previa
    # Sesiones UTC
    "sess_ny_open":  (14, 17),            # NY open: 14:30-17:00 UTC
    "sess_ny_cont":  (17, 20),            # NY continuacion: 17:00-20:00 UTC
}


def _ema(closes, period):
    if len(closes) < period:
        return None
    k = 2.0 / (period + 1)
    v = sum(closes[:period]) / period
    for c in closes[period:]:
        v = c * k + v * (1 - k)
    return round(v, 2)


def _rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    g, l = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        g.append(max(d, 0.0))
        l.append(max(-d, 0.0))
    ag = sum(g[-period:]) / period
    al = sum(l[-period:]) / period
    if al == 0:
        return 100.0
    return round(100 - 100 / (1 + ag / al), 1)


def _atr(candles, period=14):
    trs = []
    for i in range(1, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i-1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period:
        return None
    return round(sum(trs[-period:]) / period, 2)


def _adx(candles, period=14):
    if len(candles) < period + 2:
        return None
    pdm, mdm, tr = [], [], []
    for i in range(1, len(candles)):
        h  = candles[i]["high"];   l  = candles[i]["low"]
        ph = candles[i-1]["high"]; pl = candles[i-1]["low"]
        pc = candles[i-1]["close"]
        u = h - ph; d = pl - l
        pdm.append(u if u > d and u > 0 else 0)
        mdm.append(d if d > u and d > 0 else 0)
        tr.append(max(h - l, abs(h - pc), abs(l - pc)))
    def sm(a):
        s = sum(a[:period]); o = [s]
        for v in a[period:]: s = s - s/period + v; o.append(s)
        return o
    s14 = sm(tr); p14 = sm(pdm); m14 = sm(mdm); dx = []
    for i in range(len(s14)):
        if s14[i] == 0: continue
        pi = 100 * p14[i] / s14[i]
        mi = 100 * m14[i] / s14[i]
        den = pi + mi
        dx.append(100 * abs(pi - mi) / den if den > 0 else 0)
    if len(dx) < period:
        return None
    return round(sum(dx[-period:]) / period, 1)


def _load(symbol, timeframe, count):
    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
    if rates is None or len(rates) == 0:
        return []
    return [{
        "time":  datetime.fromtimestamp(r["time"], tz=timezone.utc),
        "open":  float(r["open"]),
        "high":  float(r["high"]),
        "low":   float(r["low"]),
        "close": float(r["close"]),
    } for r in rates]


def _in_session(hour_utc, p):
    s1 = p["sess_ny_open"]
    s2 = p["sess_ny_cont"]
    return (s1[0] <= hour_utc < s1[1]) or (s2[0] <= hour_utc < s2[1])


def get_signal_from_mt5(p=None, verbose=False):
    """
    Genera señal para US30 usando H4 como filtro de tendencia y H1 como entrada.
    
    Returns: (signal_dict, h1_candles) o (None, candles)
    """
    if p is None:
        p = PARAMS

    try:
        if not mt5.initialize():
            if verbose: print("[signal] MT5 not available")
            return None, None

        symbol = p["symbol"]

        # Cargar H4 para tendencia
        h4 = _load(symbol, p["trend_tf"], 250)
        if len(h4) < p["trend_ema"] + 5:
            if verbose: print("[signal] Not enough H4 data")
            mt5.shutdown()
            return None, None

        # Cargar H1 para entrada
        h1 = _load(symbol, p["entry_tf"], 150)
        if len(h1) < p["entry_ema"] + 25:
            if verbose: print("[signal] Not enough H1 data")
            mt5.shutdown()
            return None, None

        mt5.shutdown()

        # Indicadores H4 (tendencia)
        h4_closes = [c["close"] for c in h4]
        trend_ema  = _ema(h4_closes, p["trend_ema"])
        if not trend_ema:
            if verbose: print("[signal] Cannot compute trend EMA")
            return None, h1

        h4_price   = h4_closes[-1]
        uptrend    = h4_price > trend_ema
        downtrend  = h4_price < trend_ema

        # Indicadores H1 (entrada)
        h1_closes = [c["close"] for c in h1]
        e50  = _ema(h1_closes, p["entry_ema"])
        rsi  = _rsi(h1_closes, p["rsi_period"])
        at   = _atr(h1, p["atr_period"])
        ad   = _adx(h1, p["adx_period"])

        if any(v is None for v in [e50, rsi, at]):
            if verbose: print("[signal] Cannot compute H1 indicators")
            return None, h1

        cur  = h1[-1]
        prev = h1[-2]
        price = h1_closes[-1]
        hour_utc = cur["time"].hour

        if verbose:
            print("[signal] H4 price=" + str(round(h4_price,0)) +
                  " EMA200=" + str(round(trend_ema,0)) +
                  " trend=" + ("UP" if uptrend else "DOWN" if downtrend else "FLAT"))
            print("[signal] H1 price=" + str(round(price,0)) +
                  " EMA50=" + str(round(e50,0)) +
                  " RSI=" + str(rsi) +
                  " ADX=" + str(ad) +
                  " ATR=" + str(round(at,1)))
            print("[signal] Hour UTC=" + str(hour_utc) +
                  " in_session=" + str(_in_session(hour_utc, p)))

        # Filtro de sesion
        if not _in_session(hour_utc, p):
            if verbose: print("[signal] Outside NY session")
            return None, h1

        # Filtro ADX
        if ad is not None and ad < p["adx_min"]:
            if verbose: print("[signal] ADX=" + str(ad) + " < " + str(p["adx_min"]) + " -- choppy market")
            return None, h1

        # Distancia previa a EMA50:
        # Precio debe haber estado >= dist_min_atr ATRs de EMA50 en ultimas lookback barras
        lookback = h1[-p["lookback_dist"]-1:-1]
        if len(lookback) < 5:
            return None, h1

        max_above = max((c["high"]  - e50) / at for c in lookback)
        max_below = max((e50 - c["low"]) / at for c in lookback)
        had_move_up   = max_above >= p["dist_min_atr"]
        had_move_down = max_below >= p["dist_min_atr"]

        # Condiciones de vela
        cur_bull  = cur["close"]  > cur["open"]
        cur_bear  = cur["close"]  < cur["open"]
        prev_bear = prev["close"] < prev["open"]
        prev_bull = prev["close"] > prev["open"]

        sig = None

        # LONG: H4 uptrend, pullback a EMA50 H1, confirmacion alcista
        if (uptrend and had_move_up
                and cur["low"]   <= e50 * 1.002
                and cur["close"] >  e50
                and cur_bull and prev_bear
                and p["rsi_long_min"] <= rsi <= p["rsi_long_max"]):
            sl_d = round(at * p["sl_mult"], 1)
            tp_d = round(at * p["tp_mult"], 1)
            rr   = round(tp_d / sl_d, 1)
            if rr >= p["min_rr"]:
                conf = 72
                if rsi < 50: conf += 5
                if ad and ad > 30: conf += 5
                if h4_price > trend_ema * 1.01: conf += 3
                sig = {
                    "signal":   "LONG",
                    "sig_type": "PB_EMA50",
                    "confidence": conf,
                    "reason":   "US30 LONG pullback EMA50 | H4 uptrend | ADX=" + str(ad) + " RSI=" + str(rsi),
                    "price":    price,
                    "rsi":      rsi,
                    "adx":      ad,
                    "atr":      at,
                    "e50":      e50,
                    "trend_ema":trend_ema,
                    "sl_dist":  sl_d,
                    "tp_dist":  tp_d,
                    "rr":       rr,
                    "hour_utc": hour_utc,
                    "dist_up":  round(max_above, 2),
                    "symbol":   symbol,
                }

        # SHORT: H4 downtrend, rally a EMA50 H1, confirmacion bajista
        elif (downtrend and had_move_down
                and cur["high"]  >= e50 * 0.998
                and cur["close"] <  e50
                and cur_bear and prev_bull
                and p["rsi_short_min"] <= rsi <= p["rsi_short_max"]):
            sl_d = round(at * p["sl_mult"], 1)
            tp_d = round(at * p["tp_mult"], 1)
            rr   = round(tp_d / sl_d, 1)
            if rr >= p["min_rr"]:
                conf = 72
                if rsi > 50: conf += 5
                if ad and ad > 30: conf += 5
                if h4_price < trend_ema * 0.99: conf += 3
                sig = {
                    "signal":   "SHORT",
                    "sig_type": "PB_EMA50",
                    "confidence": conf,
                    "reason":   "US30 SHORT rally EMA50 | H4 downtrend | ADX=" + str(ad) + " RSI=" + str(rsi),
                    "price":    price,
                    "rsi":      rsi,
                    "adx":      ad,
                    "atr":      at,
                    "e50":      e50,
                    "trend_ema":trend_ema,
                    "sl_dist":  sl_d,
                    "tp_dist":  tp_d,
                    "rr":       rr,
                    "hour_utc": hour_utc,
                    "dist_dn":  round(max_below, 2),
                    "symbol":   symbol,
                }

        if verbose:
            if sig:
                print("[signal] SETUP FOUND: " + sig["signal"] + " conf=" + str(sig["confidence"]) + "%")
            else:
                print("[signal] No setup -- uptrend=" + str(uptrend) +
                      " had_up=" + str(had_move_up) + "(" + str(round(max_above,2)) + "ATR)" +
                      " had_dn=" + str(had_move_down) + "(" + str(round(max_below,2)) + "ATR)" +
                      " cur_bull=" + str(cur_bull) + " prev_bear=" + str(prev_bear))

        return sig, h1

    except Exception as e:
        if verbose: print("[signal] error: " + str(e))
        try: mt5.shutdown()
        except: pass
        return None, None


def format_signal_summary(sig):
    if sig is None:
        return "No setup"
    return (sig["signal"] + " " + sig["sig_type"] +
            " | conf=" + str(sig["confidence"]) + "%" +
            " | price=" + str(round(sig["price"], 0)) +
            " | EMA50=" + str(round(sig["e50"], 0)) +
            " | ADX=" + str(sig["adx"]) +
            " | RSI=" + str(sig["rsi"]) +
            " | SL=" + str(sig["sl_dist"]) + "pts" +
            " | TP=" + str(sig["tp_dist"]) + "pts" +
            " | RR=" + str(sig["rr"]) +
            " | " + sig["reason"])


# Compatibilidad con imports existentes
def get_signal(candles=None, p=None, verbose=False):
    return get_signal_from_mt5(p=p, verbose=verbose)[0]


SIGNAL_PARAMS = PARAMS
