"""
AURUM Backtest US30 - Production Model
========================================
Replica exactamente la logica de produccion para US30:
- H4 EMA200 filtro de tendencia
- H1 EMA50 pullback con confirmacion de vela
- ADX H1 > 20
- Distancia previa >= 1.5 ATR de EMA50
- Sesiones NY open (14-17 UTC) y continuacion (17-20 UTC)
- SL 1.5xATR, TP 3.0xATR
- 1% riesgo por trade
- Para el dia con 2 perdidas consecutivas
- FTMO: 5% daily DD, 10% total DD

US30 sizing:
- 1 lot = $1 por punto
- P&L = lots x (exit - entry) para LONG
"""

import json, os, statistics, random
from datetime import datetime, timezone

# Parametros FTMO
CAPITAL        = 25000.0
RISK_PCT       = 0.01
MAX_CONS_LOSS  = 2
DAILY_DD_PCT   = 0.05
TOTAL_DD_PCT   = 0.10

# Parametros estrategia
TREND_EMA      = 200   # H4
ENTRY_EMA      = 50    # H1
ADX_MIN        = 20
DIST_MIN       = 1.5   # ATR units
SL_MULT        = 1.5
TP_MULT        = 3.0
MIN_RR         = 2.0
LOOKBACK       = 20    # barras H1 para distancia

# Sesiones UTC
SESS_NY        = (14, 20)  # 14:00-20:00 UTC

# Costes US30
SPREAD         = 2.5   # puntos
SLIP_MAX       = 1.0   # puntos
COMMISSION     = 0.50  # $ por lot round trip (muy bajo en indices)
LOT_PNL        = 1.0   # $1 por punto por lot


def ema(c, p):
    if len(c) < p: return None
    k = 2/(p+1); v = sum(c[:p])/p
    for x in c[p:]: v = x*k + v*(1-k)
    return round(v, 2)

def rsi(c, p=14):
    if len(c) < p+1: return None
    g, l = [], []
    for i in range(1, len(c)):
        d = c[i]-c[i-1]; g.append(max(d,0)); l.append(max(-d,0))
    ag = sum(g[-p:])/p; al = sum(l[-p:])/p
    return 100.0 if al==0 else round(100-100/(1+ag/al), 1)

def atr_f(cs, p=14):
    t = []
    for i in range(1, len(cs)):
        h=cs[i]["h"]; l=cs[i]["l"]; pc=cs[i-1]["c"]
        t.append(max(h-l, abs(h-pc), abs(l-pc)))
    return round(sum(t[-p:])/p, 2) if len(t) >= p else None

def adx_f(cs, p=14):
    if len(cs) < p+2: return None
    pdm, mdm, tr = [], [], []
    for i in range(1, len(cs)):
        h=cs[i]["h"]; l=cs[i]["l"]
        ph=cs[i-1]["h"]; pl=cs[i-1]["l"]; pc=cs[i-1]["c"]
        u=h-ph; d=pl-l
        pdm.append(u if u>d and u>0 else 0)
        mdm.append(d if d>u and d>0 else 0)
        tr.append(max(h-l, abs(h-pc), abs(l-pc)))
    def sm(a):
        s=sum(a[:p]); o=[s]
        for v in a[p:]: s=s-s/p+v; o.append(s)
        return o
    s=sm(tr); p2=sm(pdm); m2=sm(mdm); dx=[]
    for i in range(len(s)):
        if s[i]==0: continue
        pi=100*p2[i]/s[i]; mi=100*m2[i]/s[i]; den=pi+mi
        dx.append(100*abs(pi-mi)/den if den>0 else 0)
    return round(sum(dx[-p:])/p, 1) if len(dx) >= p else None


def signal(h1_candles, h4_ema200, idx):
    """
    Genera senal en el indice idx de h1_candles.
    h4_ema200: valor de EMA200 H4 en ese momento.
    """
    if idx < ENTRY_EMA + LOOKBACK + 5:
        return None

    hist  = h1_candles[max(0, idx-150):idx]
    if len(hist) < ENTRY_EMA + 5:
        return None

    closes = [c["c"] for c in hist]
    e50    = ema(closes, ENTRY_EMA)
    r      = rsi(closes, 14)
    at     = atr_f(hist, 14)
    ad     = adx_f(hist, 14)

    if any(v is None for v in [e50, r, at]):
        return None

    cur   = hist[-1]
    prev  = hist[-2] if len(hist) >= 2 else cur
    price = closes[-1]
    hour  = cur["hour"]

    # Filtro sesion NY
    if not (SESS_NY[0] <= hour < SESS_NY[1]):
        return None

    # Filtro ADX
    if ad is not None and ad < ADX_MIN:
        return None

    # Tendencia H4
    uptrend   = price > h4_ema200
    downtrend = price < h4_ema200

    # Distancia previa
    lookback_c = hist[-LOOKBACK-1:-1]
    if len(lookback_c) < 5:
        return None
    max_above = max((c["h"] - e50) / at for c in lookback_c)
    max_below = max((e50 - c["l"]) / at for c in lookback_c)
    had_up    = max_above >= DIST_MIN
    had_dn    = max_below >= DIST_MIN

    # Condiciones de vela
    cur_bull  = cur["c"] > cur["o"]
    cur_bear  = cur["c"] < cur["o"]
    prev_bear = prev["c"] < prev["o"]
    prev_bull = prev["c"] > prev["o"]

    sl_d = round(at * SL_MULT, 1)
    tp_d = round(at * TP_MULT, 1)
    rr   = round(tp_d / sl_d, 1)
    if rr < MIN_RR:
        return None

    # LONG
    if (uptrend and had_up
            and cur["l"] <= e50 * 1.002
            and cur["c"] > e50
            and cur_bull and prev_bear
            and 35 <= r <= 70):
        return {"sig":"LONG","price":price,"sl_d":sl_d,"tp_d":tp_d,
                "rr":rr,"atr":at,"adx":ad,"rsi":r,"e50":e50}

    # SHORT
    if (downtrend and had_dn
            and cur["h"] >= e50 * 0.998
            and cur["c"] < e50
            and cur_bear and prev_bull
            and 30 <= r <= 65):
        return {"sig":"SHORT","price":price,"sl_d":sl_d,"tp_d":tp_d,
                "rr":rr,"atr":at,"adx":ad,"rsi":r,"e50":e50}

    return None


def simulate(h1, h4_ema_series, capital=CAPITAL, seed=42):
    """
    h1: lista de velas H1 con campos t,o,h,l,c,hour
    h4_ema_series: dict de {h1_index: ema200_value}
    """
    rng = random.Random(seed)
    eq  = capital; peak = capital; max_dd = 0.0
    trades = []; daily = {}; tdays = set()
    pos = None; cons_l = 0; last_date = ""

    for i in range(TREND_EMA * 4 + LOOKBACK + 10, len(h1)):
        bar  = h1[i]
        date = bar["t"][:10]
        h    = bar["h"]; l = bar["l"]

        if date != last_date:
            cons_l = 0
            last_date = date

        # Check exit
        if pos:
            hs = ht = False
            if pos["dir"] == "LONG":
                if l <= pos["sl"]: hs = True
                elif h >= pos["tp"]: ht = True
            else:
                if h >= pos["sl"]: hs = True
                elif l <= pos["tp"]: ht = True

            if hs or ht:
                ep  = pos["sl"] if hs else pos["tp"]
                pnl = round(pos["lo"] * LOT_PNL * (ep - pos["en"] if pos["dir"] == "LONG"
                                                     else pos["en"] - ep)
                            - pos["lo"] * COMMISSION, 2)
                eq += pnl; peak = max(peak, eq)
                max_dd = max(max_dd, peak - eq)
                daily[date] = daily.get(date, 0) + pnl
                tdays.add(date)
                result = "WIN" if pnl > 0 else "LOSS"
                if pnl < 0: cons_l += 1
                else: cons_l = 0
                trades.append({
                    "open": pos["ot"], "close": bar["t"],
                    "dir": pos["dir"], "entry": pos["en"],
                    "exit": ep, "sl": pos["sl"], "tp": pos["tp"],
                    "lots": pos["lo"], "rr": pos["rr"], "pnl": pnl,
                    "result": result, "adx": pos.get("adx"),
                    "rsi": pos.get("rsi"), "atr": pos.get("atr"),
                    "eq": round(eq, 2),
                })
                pos = None

        # FTMO checks
        if (capital - eq) >= capital * TOTAL_DD_PCT: break
        if daily.get(date, 0) <= -(capital * DAILY_DD_PCT): continue
        if cons_l >= MAX_CONS_LOSS: continue
        if pos: continue

        # Get H4 EMA200 for this bar
        h4_e200 = h4_ema_series.get(i)
        if h4_e200 is None: continue

        sg = signal(h1, h4_e200, i)
        if sg is None: continue

        # Sizing: 1% riesgo
        ru   = round(eq * RISK_PCT, 2)
        lots = ru / (sg["sl_d"] * LOT_PNL)
        lots = round(max(0.01, min(lots, 50.0)), 2)

        slip = rng.uniform(0, SLIP_MAX)
        if sg["sig"] == "LONG":
            en = round(sg["price"] + SPREAD/2 + slip, 2)
            sl = round(en - sg["sl_d"], 2)
            tp = round(en + sg["tp_d"], 2)
        else:
            en = round(sg["price"] - SPREAD/2 - slip, 2)
            sl = round(en + sg["sl_d"], 2)
            tp = round(en - sg["tp_d"], 2)

        pos = {
            "dir": sg["sig"], "en": en, "sl": sl, "tp": tp,
            "lo": lots, "rr": sg["rr"], "ot": bar["t"],
            "adx": sg.get("adx"), "rsi": sg.get("rsi"), "atr": sg.get("atr"),
        }
        tdays.add(date)

    return trades, max_dd, len(tdays)


def metrics(trades, max_dd, days, capital):
    if not trades:
        return {"n":0,"wr":0,"pnl":0,"pf":0,"sharpe":0,
                "dd":0,"ddp":0,"aw":0,"al":0,"exp":0,"days":days}
    w  = [t for t in trades if t["result"]=="WIN"]
    l  = [t for t in trades if t["result"]=="LOSS"]
    pnl = sum(t["pnl"] for t in trades)
    gw  = sum(t["pnl"] for t in w)
    gl  = abs(sum(t["pnl"] for t in l))
    wr  = len(w)/len(trades)*100
    pf  = round(gw/gl, 3) if gl > 0 else 0
    aw  = gw/len(w)       if w else 0
    al  = gl/len(l)       if l else 0
    exp = round((wr/100*aw) - ((1-wr/100)*al), 2)
    return {
        "n":    len(trades), "wins": len(w), "losses": len(l),
        "wr":   round(wr,1), "pnl": round(pnl,2),
        "ret":  round(pnl/capital*100,1), "pf": pf,
        "dd":   round(max_dd,2), "ddp": round(max_dd/capital*100,2),
        "aw":   round(aw,2), "al": round(al,2),
        "exp":  exp, "days": days,
    }


def monte_carlo(trades, capital=CAPITAL, runs=2000, seed=42):
    if not trades: return {}
    rng = random.Random(seed)
    pnls = [t["pnl"] for t in trades]
    fins, dds, ruin, target = [], [], 0, 0
    for _ in range(runs):
        sh = pnls[:]; rng.shuffle(sh)
        eq = capital; pk = capital; dd = 0.0
        for p in sh:
            eq += p; pk = max(pk, eq); dd = max(dd, pk-eq)
            if eq < capital * 0.90: ruin += 1; break
        fins.append(eq); dds.append(dd)
        if eq >= capital * 1.10: target += 1
    fins.sort(); dds.sort(); n = len(fins)
    return {
        "runs":       runs,
        "ruin_pct":   round(ruin/runs*100,1),
        "target_pct": round(target/runs*100,1),
        "p5":         round((fins[int(n*.05)]-capital)/capital*100,1),
        "p50":        round((fins[n//2]-capital)/capital*100,1),
        "p95":        round((fins[int(n*.95)]-capital)/capital*100,1),
        "p95_dd":     round(dds[int(n*.95)],2),
    }


if __name__ == "__main__":
    import MetaTrader5 as mt5
    print("Loading US30 data from MT5...")
    mt5.initialize()

    # H1 para entrada
    r_h1 = mt5.copy_rates_from_pos("US30.cash", mt5.TIMEFRAME_H1, 0, 99999)
    # H4 para tendencia
    r_h4 = mt5.copy_rates_from_pos("US30.cash", mt5.TIMEFRAME_H4, 0, 99999)
    mt5.shutdown()

    h1 = []
    for r in r_h1:
        dt = datetime.fromtimestamp(r["time"], tz=timezone.utc)
        if dt.year < 2019: continue
        h1.append({
            "t":    dt.strftime("%Y-%m-%d %H:%M"),
            "o":    float(r["open"]),
            "h":    float(r["high"]),
            "l":    float(r["low"]),
            "c":    float(r["close"]),
            "hour": dt.hour,
        })

    h4 = []
    for r in r_h4:
        dt = datetime.fromtimestamp(r["time"], tz=timezone.utc)
        if dt.year < 2019: continue
        h4.append({
            "t": dt.strftime("%Y-%m-%d %H:%M"),
            "c": float(r["close"]),
        })

    print("H1 candles: " + str(len(h1)) + " | H4 candles: " + str(len(h4)))

    # Precalcular EMA200 H4
    # Para cada vela H1 encontrar el valor de EMA200 H4 mas reciente
    print("Computing H4 EMA200...")
    h4_closes = [c["c"] for c in h4]
    h4_times  = [c["t"] for c in h4]

    # EMA200 en cada punto H4
    h4_ema_vals = {}
    for i in range(TREND_EMA, len(h4)):
        e = ema(h4_closes[:i], TREND_EMA)
        h4_ema_vals[h4_times[i]] = e

    # Mapear cada indice H1 al EMA200 H4 mas reciente
    h4_ema_series = {}
    h4_idx = 0
    last_h4_ema = None
    for i, bar in enumerate(h1):
        # Avanzar el indice H4 hasta el tiempo del bar H1
        while h4_idx < len(h4_times) and h4_times[h4_idx] <= bar["t"]:
            if h4_times[h4_idx] in h4_ema_vals:
                last_h4_ema = h4_ema_vals[h4_times[h4_idx]]
            h4_idx += 1
        if last_h4_ema is not None:
            h4_ema_series[i] = last_h4_ema

    print("Running backtest with production parameters...")
    print("H4 EMA200 trend | H1 EMA50 pullback | ADX>20 | dist>=1.5ATR")
    print("NY session 14:00-20:00 UTC | SL=1.5xATR | TP=3.0xATR | 1% risk")
    print()

    trades, max_dd, tdays = simulate(h1, h4_ema_series)
    m = metrics(trades, max_dd, tdays, CAPITAL)
    months = len(h1) / (21 * 24)

    print("=" * 60)
    print("BACKTEST RESULTS -- US30 (2019-2026)")
    print("=" * 60)
    print("Trades:       " + str(m["n"]))
    print("Per month:    " + str(round(m["n"]/months, 1)))
    print("Win rate:     " + str(m["wr"]) + "%")
    print("Profit F:     " + str(m["pf"]))
    print("Expectancy:   $" + str(m["exp"]) + " per trade")
    print("Total P&L:    $" + str(m["pnl"]) + " (" + str(m["ret"]) + "%)")
    print("Max DD:       $" + str(m["dd"]) + " (" + str(m["ddp"]) + "%)")
    print("Avg win:      $" + str(m["aw"]))
    print("Avg loss:     $" + str(m["al"]))
    print("Trading days: " + str(m["days"]))
    print()

    print("YEARLY:")
    by_y = {}
    for t in trades:
        y = t["open"][:4]
        if y not in by_y: by_y[y]={"n":0,"w":0,"pnl":0.0}
        by_y[y]["n"]+=1; by_y[y]["pnl"]+=t["pnl"]
        if t["result"]=="WIN": by_y[y]["w"]+=1
    for y in sorted(by_y.keys()):
        v=by_y[y]; wr=round(v["w"]/v["n"]*100,1) if v["n"]>0 else 0
        sign="+" if v["pnl"]>=0 else ""
        tpm=round(v["n"]/12,1)
        ok="PASS" if v["pnl"]>0 else "FAIL"
        print("  "+y+" | n="+str(v["n"])+" ("+str(tpm)+"/mo) | WR="+str(wr)+"% | PnL="+sign+"$"+str(round(v["pnl"],0))+" | "+ok)

    print()
    mc = monte_carlo(trades)
    if mc:
        print("MONTE CARLO (2000 runs):")
        print("  Target hit (>10%): " + str(mc["target_pct"]) + "%")
        print("  Ruin risk  (<10%): " + str(mc["ruin_pct"]) + "%")
        print("  P5/P50/P95:        " + str(mc["p5"]) + "% / " + str(mc["p50"]) + "% / " + str(mc["p95"]) + "%")
        print("  P95 MaxDD:         $" + str(mc["p95_dd"]))

    print()
    print("DIRECTION BREAKDOWN:")
    by_dir = {}
    for t in trades:
        d=t["dir"]
        if d not in by_dir: by_dir[d]={"n":0,"w":0,"pnl":0.0}
        by_dir[d]["n"]+=1; by_dir[d]["pnl"]+=t["pnl"]
        if t["result"]=="WIN": by_dir[d]["w"]+=1
    for d,v in sorted(by_dir.items()):
        wr=round(v["w"]/v["n"]*100,1) if v["n"]>0 else 0
        print("  "+d+" | n="+str(v["n"])+" | WR="+str(wr)+"% | PnL=$"+str(round(v["pnl"],0)))

    print()
    print("LAST 20 TRADES:")
    print("  {:<18} {:<6} {:>8} {:>8} {:>5} {:>9}  {}".format(
        "Open","Dir","Entry","Exit","RR","PnL","Result"))
    print("  "+"-"*65)
    for t in trades[-20:]:
        print("  {:<18} {:<6} {:>8.0f} {:>8.0f} {:>5.1f} {:>9}  {}".format(
            t["open"], t["dir"], t["entry"], t["exit"],
            t["rr"], "$"+str(t["pnl"]), t["result"]))

    print()
    print("=" * 60)
    print("VERDICT FOR FTMO $25k:")
    print("=" * 60)
    tpm_avg = m["n"] / months
    issues = []; ok_l = []
    if tpm_avg >= 6:  ok_l.append("OK  Trades/month: " + str(round(tpm_avg,1)))
    else: issues.append("WARN Trades/month: " + str(round(tpm_avg,1)) + " (<6)")
    if m["pf"] >= 1.3: ok_l.append("OK  Profit factor: " + str(m["pf"]))
    elif m["pf"] >= 1.1: issues.append("WARN PF: " + str(m["pf"]) + " (aim >1.3)")
    else: issues.append("FAIL PF: " + str(m["pf"]))
    if m["ddp"] <= 6:  ok_l.append("OK  MaxDD: " + str(m["ddp"]) + "%")
    elif m["ddp"] <= 8: issues.append("WARN MaxDD: " + str(m["ddp"]) + "% (close to limit)")
    else: issues.append("FAIL MaxDD: " + str(m["ddp"]) + "% (>8%)")
    if m["wr"] >= 45:  ok_l.append("OK  Win rate: " + str(m["wr"]) + "%")
    elif m["wr"] >= 38: issues.append("WARN WR: " + str(m["wr"]) + "%")
    else: issues.append("FAIL WR: " + str(m["wr"]) + "% (<38%)")
    if mc and mc["ruin_pct"] < 5: ok_l.append("OK  Ruin: " + str(mc["ruin_pct"]) + "%")
    elif mc: issues.append("WARN Ruin: " + str(mc["ruin_pct"]) + "%")
    for msg in ok_l + issues: print("  " + msg)
    viable = all(not m.startswith("FAIL") for m in issues)
    print("\n  " + ("STRATEGY VIABLE FOR FTMO" if viable else "NEEDS IMPROVEMENT"))

    os.makedirs("backtest", exist_ok=True)
    with open("backtest/us30_backtest.json","w") as f:
        json.dump({"params":{"trend_ema":TREND_EMA,"entry_ema":ENTRY_EMA,
                             "adx_min":ADX_MIN,"dist_min":DIST_MIN,
                             "sl_mult":SL_MULT,"tp_mult":TP_MULT},
                   "metrics":m,"by_year":by_y,"monte_carlo":mc,"viable":viable},
                  f, indent=2, default=str)
    print("\n  Saved: backtest/us30_backtest.json")
