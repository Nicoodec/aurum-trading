"""
AURUM Signal Engine v3
=======================
Estrategia probada para FTMO gold:
- EMA200 H1 como filtro de tendencia
- EMA50 H1 como nivel de pullback
- Filtro de distancia: precio debe haber estado > 2 ATR de EMA50 antes del pullback
- Confirmacion: vela cierra de vuelta en direccion de tendencia
- Vela anterior counter-trend (pullback real)
- Solo sesiones London 07-10 UTC y NY overlap 12-16 UTC
- Filtro de regimen: ADX > 20 (mercado en tendencia)
"""
import MetaTrader5 as mt5
from datetime import datetime

def _ema(closes, period):
    if len(closes) < period: return None
    k = 2.0/(period+1); v = sum(closes[:period])/period
    for c in closes[period:]: v = c*k + v*(1-k)
    return round(v, 3)

def _rsi(closes, period=14):
    if len(closes) < period+1: return None
    g,l=[],[]
    for i in range(1,len(closes)):
        d=closes[i]-closes[i-1]; g.append(max(d,0)); l.append(max(-d,0))
    ag=sum(g[-period:])/period; al=sum(l[-period:])/period
    return 100.0 if al==0 else round(100-100/(1+ag/al),1)

def _atr(candles, period=14):
    t=[]
    for i in range(1,len(candles)):
        h=candles[i]["high"]; l=candles[i]["low"]; pc=candles[i-1]["close"]
        t.append(max(h-l,abs(h-pc),abs(l-pc)))
    return round(sum(t[-period:])/period,3) if len(t)>=period else None

def _adx(candles, period=14):
    if len(candles)<period+2: return None
    pdm,mdm,tr=[],[],[]
    for i in range(1,len(candles)):
        h=candles[i]["high"]; l=candles[i]["low"]
        ph=candles[i-1]["high"]; pl=candles[i-1]["low"]; pc=candles[i-1]["close"]
        u=h-ph; d=pl-l
        pdm.append(u if u>d and u>0 else 0)
        mdm.append(d if d>u and d>0 else 0)
        tr.append(max(h-l,abs(h-pc),abs(l-pc)))
    def sm(a):
        s=sum(a[:period]); o=[s]
        for v in a[period:]: s=s-s/period+v; o.append(s)
        return o
    s=sm(tr); p2=sm(pdm); m2=sm(mdm); dx=[]
    for i in range(len(s)):
        if s[i]==0: continue
        pi=100*p2[i]/s[i]; mi=100*m2[i]/s[i]; den=pi+mi
        dx.append(100*abs(pi-mi)/den if den>0 else 0)
    return round(sum(dx[-period:])/period,1) if len(dx)>=period else None

def _load_h1(n=300):
    rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, n)
    if rates is None: return []
    return [{"time":r["time"],"open":float(r["open"]),"high":float(r["high"]),
             "low":float(r["low"]),"close":float(r["close"])} for r in rates]

def get_signal_from_mt5(verbose=False):
    try:
        if not mt5.initialize(): return None, None
        candles = _load_h1(300)
        if len(candles) < 210:
            mt5.shutdown(); return None, None

        closes = [c["close"] for c in candles]
        cur    = candles[-1]
        prev   = candles[-2]
        hour   = datetime.fromtimestamp(cur["time"]).hour

        # Session filter: London 07-10 UTC, NY overlap 12-16 UTC
        in_session = (7 <= hour < 10) or (12 <= hour < 16)
        if not in_session:
            if verbose: print("      [signal] Outside session hours ("+str(hour)+"UTC)")
            mt5.shutdown(); return None, candles

        # Indicators
        ema200 = _ema(closes, 200)
        ema50  = _ema(closes, 50)
        rsi14  = _rsi(closes, 14)
        atr14  = _atr(candles, 14)
        adx14  = _adx(candles, 14)

        if any(v is None for v in [ema200, ema50, rsi14, atr14, adx14]):
            mt5.shutdown(); return None, candles

        price = closes[-1]

        # Regime filter: ADX > 20 (trending market)
        if adx14 < 20:
            if verbose: print("      [signal] ADX="+str(adx14)+" < 20, market choppy")
            mt5.shutdown(); return None, candles

        # Trend direction
        uptrend   = price > ema200
        downtrend = price < ema200

        # Pullback distance filter:
        # Price must have been >= 2 ATR away from EMA50 in last 20 bars
        lookback = candles[-21:-1]
        max_above = max((c["high"] - ema50) / atr14 for c in lookback)
        max_below = max((ema50 - c["low"])  / atr14 for c in lookback)
        had_move_up   = max_above >= 2.0
        had_move_down = max_below >= 2.0

        # Candle conditions
        cur_bullish  = cur["close"] > cur["open"]
        cur_bearish  = cur["close"] < cur["open"]
        prev_bearish = prev["close"] < prev["open"]
        prev_bullish = prev["close"] > prev["open"]

        sig = None

        # LONG setup
        if (uptrend and had_move_up
            and cur["low"]   <= ema50 * 1.001  # touched EMA50
            and cur["close"] >  ema50            # closed back above
            and cur_bullish                      # current candle bullish
            and prev_bearish                     # previous candle bearish (pullback)
            and 35 <= rsi14 <= 65):              # RSI not extreme
            sl_d = round(atr14 * 1.2, 2)
            tp_d = round(atr14 * 3.0, 2)
            if tp_d/sl_d >= 2.0:
                conf = 75
                if rsi14 < 50: conf += 5
                if adx14 > 25: conf += 5
                if price > ema200 * 1.01: conf += 3
                sig = {
                    "signal":   "LONG",
                    "sig_type": "PB_EMA50",
                    "confidence": conf,
                    "reason":   "EMA50 pullback LONG | EMA200 uptrend | ADX="+str(adx14)+" RSI="+str(rsi14),
                    "price":    price,
                    "rsi":      rsi14,
                    "adx":      adx14,
                    "atr":      atr14,
                    "ema50":    ema50,
                    "ema200":   ema200,
                    "sl_dist":  sl_d,
                    "tp_dist":  tp_d,
                    "rr":       round(tp_d/sl_d, 1),
                    "hour_utc": hour,
                    "max_dist": round(max_above, 2),
                }

        # SHORT setup
        elif (downtrend and had_move_down
              and cur["high"]  >= ema50 * 0.999  # touched EMA50
              and cur["close"] <  ema50            # closed back below
              and cur_bearish                      # current candle bearish
              and prev_bullish                     # previous candle bullish (rally)
              and 35 <= rsi14 <= 65):              # RSI not extreme
            sl_d = round(atr14 * 1.2, 2)
            tp_d = round(atr14 * 3.0, 2)
            if tp_d/sl_d >= 2.0:
                conf = 75
                if rsi14 > 50: conf += 5
                if adx14 > 25: conf += 5
                if price < ema200 * 0.99: conf += 3
                sig = {
                    "signal":   "SHORT",
                    "sig_type": "PB_EMA50",
                    "confidence": conf,
                    "reason":   "EMA50 rally SHORT | EMA200 downtrend | ADX="+str(adx14)+" RSI="+str(rsi14),
                    "price":    price,
                    "rsi":      rsi14,
                    "adx":      adx14,
                    "atr":      atr14,
                    "ema50":    ema50,
                    "ema200":   ema200,
                    "sl_dist":  sl_d,
                    "tp_dist":  tp_d,
                    "rr":       round(tp_d/sl_d, 1),
                    "hour_utc": hour,
                    "max_dist": round(max_below, 2),
                }

        mt5.shutdown()

        if verbose:
            print("      [signal] price="+str(price)+" ema50="+str(ema50)+" ema200="+str(ema200))
            print("      [signal] ADX="+str(adx14)+" RSI="+str(rsi14)+" ATR="+str(atr14))
            print("      [signal] uptrend="+str(uptrend)+" had_move_up="+str(had_move_up)+"("+str(round(max_above,2))+"ATR)")
            print("      [signal] downtrend="+str(downtrend)+" had_move_down="+str(had_move_down)+"("+str(round(max_below,2))+"ATR)")
            if sig: print("      [signal] SETUP FOUND: "+sig["signal"]+" conf="+str(sig["confidence"])+"%")
            else: print("      [signal] No setup")

        return sig, candles

    except Exception as e:
        print("      [signal] error:", e)
        try: mt5.shutdown()
        except: pass
        return None, None

def format_signal_summary(sig):
    if sig is None: return "No technical setup"
    return (sig["signal"]+" "+sig["sig_type"]+
            " | conf="+str(sig["confidence"])+"%"+
            " | ADX="+str(sig["adx"])+" RSI="+str(sig["rsi"])+
            " | SL=$"+str(sig["sl_dist"])+" TP=$"+str(sig["tp_dist"])+" RR="+str(sig["rr"])+
            " | dist="+str(sig["max_dist"])+"ATR"+
            " | "+sig["reason"])

# Compatibilidad con main.py
def get_signal(candles=None, p=None, verbose=False):
    return get_signal_from_mt5(verbose=verbose)[0]
