"""
AURUM Professional Backtesting System
======================================
- Walk-forward testing (70/30)
- Sensitivity analysis (parameter robustness)
- Monte Carlo simulation (1000 runs)
- Feature importance analysis
- Realistic execution (spread, slippage, fees)
- Per-signal-type analysis
- Edge detection (winners vs losers)
"""

import json, os, csv, random, itertools, statistics
from datetime import datetime
from collections import defaultdict

# ═══════════════════════════════════════════════════════════════
# 1. PARAMETERS — everything configurable, nothing hardcoded
# ═══════════════════════════════════════════════════════════════

BASE_PARAMS = {
    # Indicators
    "rsi_period":       14,
    "ema_fast":          9,
    "ema_mid":          21,
    "ema_slow":         50,
    "sma_period":       20,
    "atr_period":       14,
    "adx_period":       14,
    "bb_period":        20,

    # Signal filters
    "adx_min":          20,     # minimum ADX for "trending"
    "adx_strong":       25,     # ADX for confidence boost
    "rsi_long_min":     35,     # RSI floor for LONG signals
    "rsi_long_max":     62,     # RSI ceiling for LONG signals
    "rsi_short_min":    38,     # RSI floor for SHORT signals
    "rsi_short_max":    65,     # RSI ceiling for SHORT signals
    "rsi_oversold":     32,     # oversold threshold
    "rsi_overbought":   68,     # overbought threshold

    # EMA proximity (in ATR units)
    "pullback_ema21_dist":  0.5,    # max dist from EMA21 for pullback signal
    "pullback_ema9_dist":   0.3,    # max dist from EMA9 for pullback signal
    "trend_ema9_dist":      0.8,    # max dist from EMA9 for trend signal

    # Extension filter (in ATR units from SMA20)
    "extension_limit":  2.0,

    # Risk management
    "sl_atr_mult":      1.5,
    "tp_atr_mult":      3.0,
    "min_rr":           2.0,
    "risk_pct":         0.02,
    "max_positions":    3,

    # Execution costs (realistic)
    "spread_usd":       0.30,   # typical XAU/USD spread in USD
    "slippage_max":     0.20,   # max random slippage in USD
    "fee_per_lot":      7.0,    # commission per lot round-trip

    # Signal type switches (enable/disable each)
    "use_pullback_ema21":   True,
    "use_pullback_ema9":    True,
    "use_bb_reversal":      True,
    "use_trend":            True,
    "use_short":            True,   # allow short signals
}


# ═══════════════════════════════════════════════════════════════
# 2. INDICATORS
# ═══════════════════════════════════════════════════════════════

def calc_rsi(closes, period):
    if len(closes) < period + 1: return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0)); losses.append(max(-d, 0))
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    if al == 0: return 100.0
    return round(100 - 100 / (1 + ag/al), 1)

def calc_ema(closes, period):
    if len(closes) < period: return None
    k = 2 / (period + 1)
    ema = sum(closes[:period]) / period
    for c in closes[period:]: ema = c * k + ema * (1 - k)
    return round(ema, 2)

def calc_sma(closes, period):
    if len(closes) < period: return None
    return round(sum(closes[-period:]) / period, 2)

def calc_atr(candles, period):
    trs = []
    for i in range(1, len(candles)):
        h=candles[i]["high"]; l=candles[i]["low"]; pc=candles[i-1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if len(trs) < period: return None
    return round(sum(trs[-period:]) / period, 2)

def calc_adx(candles, period):
    if len(candles) < period + 2: return None
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, len(candles)):
        h=candles[i]["high"]; l=candles[i]["low"]
        ph=candles[i-1]["high"]; pl=candles[i-1]["low"]; pc=candles[i-1]["close"]
        up=h-ph; down=pl-l
        plus_dm.append(up   if up > down   and up > 0   else 0)
        minus_dm.append(down if down > up  and down > 0 else 0)
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    def smooth(arr):
        s = sum(arr[:period]); result = [s]
        for v in arr[period:]: s = s - s/period + v; result.append(s)
        return result
    s = smooth(trs); pd = smooth(plus_dm); md = smooth(minus_dm)
    adx_v = []
    for i in range(len(s)):
        if s[i] == 0: continue
        pdi = 100 * pd[i] / s[i]; mdi = 100 * md[i] / s[i]
        dx  = 100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) > 0 else 0
        adx_v.append(dx)
    if len(adx_v) < period: return None
    return round(sum(adx_v[-period:]) / period, 1)

def calc_bb(closes, period):
    if len(closes) < period: return None, None, None
    sma = sum(closes[-period:]) / period
    std = statistics.stdev(closes[-period:])
    return round(sma + 2*std, 2), round(sma, 2), round(sma - 2*std, 2)

def compute_indicators(candles, p):
    closes = [c["close"] for c in candles]
    rsi   = calc_rsi(closes, p["rsi_period"])
    ema9  = calc_ema(closes, p["ema_fast"])
    ema21 = calc_ema(closes, p["ema_mid"])
    ema50 = calc_ema(closes, p["ema_slow"])
    sma20 = calc_sma(closes, p["sma_period"])
    atr   = calc_atr(candles, p["atr_period"])
    adx   = calc_adx(candles, p["adx_period"])
    bb_up, bb_mid, bb_lo = calc_bb(closes, p["bb_period"])
    return rsi, ema9, ema21, ema50, sma20, atr, adx, bb_up, bb_lo


# ═══════════════════════════════════════════════════════════════
# 3. SIGNAL GENERATION (pure, parameterized)
# ═══════════════════════════════════════════════════════════════

def generate_signal(candles_so_far, p):
    min_needed = max(p["ema_slow"], p["adx_period"], p["bb_period"]) + 5
    if len(candles_so_far) < min_needed:
        return None

    rsi, ema9, ema21, ema50, sma20, atr, adx, bb_up, bb_lo = compute_indicators(candles_so_far, p)
    if any(v is None for v in [rsi, ema9, ema21, ema50, atr, sma20]):
        return None

    price = candles_so_far[-1]["close"]
    c     = candles_so_far[-1]
    chg   = round((c["close"] - c["open"]) / c["open"] * 100, 2)

    trend_fast = "UP"   if ema9  > ema21  else "DOWN"
    trend_mid  = "UP"   if ema21 > ema50  else "DOWN"
    trend_slow = "UP"   if price > ema50  else "DOWN"

    dist_ema9   = abs(price - ema9)  / atr
    dist_ema21  = abs(price - ema21) / atr
    dist_sma20  = (price - sma20)    / atr   # signed

    trending     = adx is None or adx > p["adx_min"]
    strong_trend = adx is not None  and adx > p["adx_strong"]
    ext_up       = dist_sma20 >  p["extension_limit"]
    ext_dn       = dist_sma20 < -p["extension_limit"]

    signal = None; reason = ""; confidence = 60; sig_type = ""

    # ── A: Pullback EMA21 LONG ──────────────────────────────────
    if (p["use_pullback_ema21"]
        and trend_fast == "UP" and trend_mid == "UP" and trend_slow == "UP"
        and dist_ema21 <= p["pullback_ema21_dist"]
        and p["rsi_long_min"] <= rsi <= p["rsi_long_max"] - 10
        and trending and not ext_up and chg > -2.0):
        signal="LONG"; sig_type="PULLBACK_EMA21"; confidence=78
        if strong_trend: confidence += 4
        if rsi < 48:     confidence += 3
        reason = f"Pullback EMA21 uptrend | RSI={rsi} ADX={adx}"

    # ── B: Pullback EMA9 LONG ───────────────────────────────────
    elif (p["use_pullback_ema9"]
          and trend_fast == "UP" and trend_mid == "UP" and trend_slow == "UP"
          and dist_ema9 <= p["pullback_ema9_dist"]
          and p["rsi_long_min"] + 5 <= rsi <= p["rsi_long_max"] - 7
          and strong_trend and not ext_up):
        signal="LONG"; sig_type="PULLBACK_EMA9"; confidence=74
        if adx > 30: confidence += 4
        reason = f"Pullback EMA9 strong uptrend | RSI={rsi} ADX={adx}"

    # ── C: Pullback EMA21 SHORT ─────────────────────────────────
    elif (p["use_pullback_ema21"] and p["use_short"]
          and trend_fast == "DOWN" and trend_mid == "DOWN" and trend_slow == "DOWN"
          and dist_ema21 <= p["pullback_ema21_dist"]
          and p["rsi_short_min"] + 10 <= rsi <= p["rsi_short_max"]
          and trending and not ext_dn and chg < 2.0):
        signal="SHORT"; sig_type="PULLBACK_EMA21"; confidence=78
        if strong_trend: confidence += 4
        if rsi > 52:     confidence += 3
        reason = f"Pullback EMA21 downtrend | RSI={rsi} ADX={adx}"

    # ── D: Pullback EMA9 SHORT ──────────────────────────────────
    elif (p["use_pullback_ema9"] and p["use_short"]
          and trend_fast == "DOWN" and trend_mid == "DOWN" and trend_slow == "DOWN"
          and dist_ema9 <= p["pullback_ema9_dist"]
          and p["rsi_short_min"] + 7 <= rsi <= p["rsi_short_max"] - 5
          and strong_trend and not ext_dn):
        signal="SHORT"; sig_type="PULLBACK_EMA9"; confidence=74
        if adx > 30: confidence += 4
        reason = f"Pullback EMA9 strong downtrend | RSI={rsi} ADX={adx}"

    # ── E: BB Oversold bounce ───────────────────────────────────
    elif (p["use_bb_reversal"]
          and bb_lo and price < bb_lo and rsi < p["rsi_oversold"]
          and trend_slow == "UP" and not ext_dn and chg > -3.0):
        signal="LONG"; sig_type="BB_REVERSAL"; confidence=72
        reason = f"BB lower breach oversold | RSI={rsi}"

    # ── F: BB Overbought reversal ───────────────────────────────
    elif (p["use_bb_reversal"] and p["use_short"]
          and bb_up and price > bb_up and rsi > p["rsi_overbought"]
          and trend_slow == "DOWN" and not ext_up and chg < 3.0):
        signal="SHORT"; sig_type="BB_REVERSAL"; confidence=72
        reason = f"BB upper breach overbought | RSI={rsi}"

    # ── G: Trend LONG (conservative — not extended) ────────────
    elif (p["use_trend"]
          and trend_fast == "UP" and trend_mid == "UP" and trend_slow == "UP"
          and p["rsi_long_min"] + 10 <= rsi <= p["rsi_long_max"]
          and trending and not ext_up
          and dist_ema9 < p["trend_ema9_dist"] and chg > -1.0):
        signal="LONG"; sig_type="TREND"; confidence=65
        if strong_trend: confidence += 4
        reason = f"Trend LONG near EMA9 | RSI={rsi} ADX={adx}"

    # ── H: Trend SHORT (conservative) ──────────────────────────
    elif (p["use_trend"] and p["use_short"]
          and trend_fast == "DOWN" and trend_mid == "DOWN" and trend_slow == "DOWN"
          and p["rsi_short_min"] <= rsi <= p["rsi_short_max"] - 10
          and trending and not ext_dn
          and dist_ema9 < p["trend_ema9_dist"] and chg < 1.0):
        signal="SHORT"; sig_type="TREND"; confidence=65
        if strong_trend: confidence += 4
        reason = f"Trend SHORT near EMA9 | RSI={rsi} ADX={adx}"

    if signal is None: return None

    sl_dist = round(atr * p["sl_atr_mult"], 2)
    tp_dist = round(atr * p["tp_atr_mult"], 2)
    rr      = round(tp_dist / sl_dist, 1)
    if rr < p["min_rr"]: return None

    return {
        "signal": signal, "sig_type": sig_type, "confidence": confidence,
        "reason": reason, "price": price, "rsi": rsi, "ema9": ema9,
        "ema21": ema21, "ema50": ema50, "sma20": sma20, "atr": atr,
        "adx": adx, "sl_dist": sl_dist, "tp_dist": tp_dist, "rr": rr,
        "dist_ema9": round(dist_ema9, 2), "dist_ema21": round(dist_ema21, 2),
        "dist_sma20": round(dist_sma20, 2), "trending": trending,
        "ext_up": ext_up, "ext_dn": ext_dn,
    }


# ═══════════════════════════════════════════════════════════════
# 4. REALISTIC EXECUTION ENGINE
# ═══════════════════════════════════════════════════════════════

def apply_execution_costs(price, signal, p, rng=None):
    """Add spread and random slippage to entry price."""
    spread   = p["spread_usd"]
    slip     = (rng or random).uniform(0, p["slippage_max"])
    if signal == "LONG":
        return round(price + spread/2 + slip, 2)
    else:
        return round(price - spread/2 - slip, 2)

def calc_fee(lots, p):
    return round(lots * p["fee_per_lot"], 2)


# ═══════════════════════════════════════════════════════════════
# 5. SIMULATION ENGINE
# ═══════════════════════════════════════════════════════════════

def simulate(candles, p, capital=25000.0, seed=None):
    rng = random.Random(seed)
    trades=[]; equity=capital; peak=capital; max_dd=0.0
    equity_curve=[{"date": candles[0]["date"], "equity": capital}]
    open_pos=[]; daily_pnl={}

    for i in range(1, len(candles)):
        today  = candles[i]
        history= candles[:i]
        date   = today["date"]
        h, l   = today["high"], today["low"]

        # Check exits
        still_open = []
        for pos in open_pos:
            result=None; exit_price=None
            if pos["signal"] == "LONG":
                if l <= pos["sl_price"]: result="LOSS"; exit_price=pos["sl_price"]
                elif h >= pos["tp_price"]: result="WIN"; exit_price=pos["tp_price"]
            else:
                if h >= pos["sl_price"]: result="LOSS"; exit_price=pos["sl_price"]
                elif l <= pos["tp_price"]: result="WIN"; exit_price=pos["tp_price"]

            if result:
                pnl = pos["risk_usd"] * pos["rr"] if result=="WIN" else -pos["risk_usd"]
                pnl -= calc_fee(pos["lots"], p)
                equity += pnl; peak = max(peak, equity)
                max_dd = max(max_dd, peak - equity)
                daily_pnl[date] = daily_pnl.get(date, 0) + pnl
                days = (datetime.strptime(date, "%Y-%m-%d") -
                        datetime.strptime(pos["open_date"], "%Y-%m-%d")).days
                trades.append({
                    "open_date":    pos["open_date"],
                    "close_date":   date,
                    "days_held":    days,
                    "signal":       pos["signal"],
                    "sig_type":     pos.get("sig_type",""),
                    "entry":        pos["entry"],
                    "exit":         exit_price,
                    "sl":           pos["sl_price"],
                    "tp":           pos["tp_price"],
                    "rr":           pos["rr"],
                    "lots":         pos["lots"],
                    "risk_usd":     pos["risk_usd"],
                    "pnl":          round(pnl, 2),
                    "result":       result,
                    "rsi":          pos.get("rsi"),
                    "adx":          pos.get("adx"),
                    "atr":          pos.get("atr"),
                    "dist_ema9":    pos.get("dist_ema9"),
                    "dist_ema21":   pos.get("dist_ema21"),
                    "dist_sma20":   pos.get("dist_sma20"),
                    "confidence":   pos.get("confidence", 0),
                    "equity_after": round(equity, 2),
                    "reason":       pos.get("reason",""),
                })
            else:
                still_open.append(pos)
        open_pos = still_open
        equity_curve.append({"date": date, "equity": round(equity, 2)})

        # FTMO checks
        if len(open_pos) >= p["max_positions"]: continue
        dpnl = daily_pnl.get(date, 0)
        if dpnl <= -(capital * 0.05): continue
        if (capital - equity) >= capital * 0.10: continue

        sig = generate_signal(history, p)
        if sig is None: continue

        entry    = apply_execution_costs(sig["price"], sig["signal"], p, rng)
        risk_usd = round(equity * p["risk_pct"], 2)
        lots     = max(0.01, min(round(risk_usd / (sig["sl_dist"] * 100), 2), 5.0))
        sl_p = (round(entry - sig["sl_dist"], 2) if sig["signal"]=="LONG"
                else round(entry + sig["sl_dist"], 2))
        tp_p = (round(entry + sig["tp_dist"], 2) if sig["signal"]=="LONG"
                else round(entry - sig["tp_dist"], 2))

        open_pos.append({
            **sig,
            "entry": entry, "sl_price": sl_p, "tp_price": tp_p,
            "lots": lots, "risk_usd": risk_usd, "open_date": date,
        })

    return trades, equity_curve, max_dd


# ═══════════════════════════════════════════════════════════════
# 6. METRICS
# ═══════════════════════════════════════════════════════════════

def compute_metrics(trades, equity_curve, capital, max_dd):
    if not trades:
        return {"trades":0,"wins":0,"losses":0,"win_rate":0,"total_pnl":0,
                "profit_factor":0,"sharpe":0,"max_drawdown":max_dd,"avg_win":0,"avg_loss":0}
    wins   = [t for t in trades if t["result"]=="WIN"]
    losses = [t for t in trades if t["result"]=="LOSS"]
    total_pnl  = sum(t["pnl"] for t in trades)
    gross_win  = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in losses))
    win_rate   = len(wins)/len(trades)*100 if trades else 0
    avg_win    = gross_win/len(wins)    if wins   else 0
    avg_loss   = gross_loss/len(losses) if losses else 0
    pf         = round(gross_win/gross_loss, 2) if gross_loss > 0 else 0
    returns    = [(equity_curve[i]["equity"]-equity_curve[i-1]["equity"])/equity_curve[i-1]["equity"]
                  for i in range(1, len(equity_curve))]
    mean_r = statistics.mean(returns) if returns else 0
    std_r  = statistics.stdev(returns) if len(returns) > 1 else 1
    sharpe = round((mean_r/std_r)*(252**0.5), 2) if std_r > 0 else 0
    return {
        "trades": len(trades), "wins": len(wins), "losses": len(losses),
        "win_rate": round(win_rate, 1), "total_pnl": round(total_pnl, 2),
        "profit_factor": pf, "sharpe": sharpe,
        "max_drawdown": round(max_dd, 2),
        "avg_win": round(avg_win, 2), "avg_loss": round(avg_loss, 2),
        "return_pct": round(total_pnl/capital*100, 2),
    }


# ═══════════════════════════════════════════════════════════════
# 7. WALK-FORWARD TEST
# ═══════════════════════════════════════════════════════════════

def walk_forward_test(candles, p, capital=25000.0, train_pct=0.70):
    split = int(len(candles) * train_pct)
    train = candles[:split]
    test  = candles[split:]

    print(f"  Train: {train[0]['date']} → {train[-1]['date']} ({len(train)} candles)")
    print(f"  Test:  {test[0]['date']} → {test[-1]['date']} ({len(test)} candles)")

    train_trades, train_eq, train_dd = simulate(train, p, capital, seed=42)
    test_trades,  test_eq,  test_dd  = simulate(test,  p, capital, seed=42)

    train_m = compute_metrics(train_trades, train_eq, capital, train_dd)
    test_m  = compute_metrics(test_trades,  test_eq,  capital, test_dd)

    # Degradation ratio
    pf_deg = round(test_m["profit_factor"] / train_m["profit_factor"], 2) if train_m["profit_factor"] > 0 else 0
    wr_deg = round(test_m["win_rate"] / train_m["win_rate"], 2) if train_m["win_rate"] > 0 else 0

    return train_m, test_m, pf_deg, wr_deg


# ═══════════════════════════════════════════════════════════════
# 8. SENSITIVITY ANALYSIS
# ═══════════════════════════════════════════════════════════════

def sensitivity_analysis(candles, base_p, capital=25000.0):
    """Vary each key parameter ±15% and measure impact on Sharpe and PF."""
    key_params = [
        "adx_min", "rsi_long_min", "rsi_long_max",
        "pullback_ema21_dist", "pullback_ema9_dist",
        "extension_limit", "sl_atr_mult", "tp_atr_mult",
    ]
    results = []
    base_trades, base_eq, base_dd = simulate(candles, base_p, capital, seed=42)
    base_m = compute_metrics(base_trades, base_eq, capital, base_dd)
    base_sharpe = base_m["sharpe"]
    base_pf     = base_m["profit_factor"]

    for param in key_params:
        original = base_p[param]
        row = {"param": param, "base": original, "variants": []}
        for pct in [-0.20, -0.10, +0.10, +0.20]:
            new_val = round(original * (1 + pct), 3)
            test_p  = {**base_p, param: new_val}
            t, eq, dd = simulate(candles, test_p, capital, seed=42)
            m = compute_metrics(t, eq, capital, dd)
            row["variants"].append({
                "change": f"{'+' if pct>0 else ''}{int(pct*100)}%",
                "value":  new_val,
                "sharpe": m["sharpe"],
                "pf":     m["profit_factor"],
                "wr":     m["win_rate"],
                "trades": m["trades"],
            })
        # Stability: max deviation from base Sharpe
        sharpes = [v["sharpe"] for v in row["variants"]]
        row["sharpe_std"] = round(statistics.stdev(sharpes), 3) if len(sharpes) > 1 else 0
        row["stable"]     = row["sharpe_std"] < 0.3
        results.append(row)

    return results, base_m


# ═══════════════════════════════════════════════════════════════
# 9. MONTE CARLO SIMULATION
# ═══════════════════════════════════════════════════════════════

def monte_carlo(trades, capital=25000.0, runs=1000, seed=42):
    """Reshuffle trades 1000 times, compute equity curve distribution."""
    if not trades:
        return {}
    rng = random.Random(seed)
    pnls = [t["pnl"] for t in trades]

    final_equities = []
    max_drawdowns  = []
    ruin_count     = 0  # equity drops below 50% of capital

    for _ in range(runs):
        shuffled = pnls[:]
        rng.shuffle(shuffled)
        eq = capital; peak = capital; dd = 0.0
        ruined = False
        for pnl in shuffled:
            eq += pnl
            peak = max(peak, eq)
            dd   = max(dd, peak - eq)
            if eq < capital * 0.50:
                ruined = True
        final_equities.append(eq)
        max_drawdowns.append(dd)
        if ruined: ruin_count += 1

    final_equities.sort()
    max_drawdowns.sort()
    n = len(final_equities)

    return {
        "runs":           runs,
        "ruin_pct":       round(ruin_count / runs * 100, 1),
        "median_equity":  round(final_equities[n//2], 2),
        "p5_equity":      round(final_equities[int(n*0.05)], 2),
        "p95_equity":     round(final_equities[int(n*0.95)], 2),
        "p5_return":      round((final_equities[int(n*0.05)] - capital)/capital*100, 2),
        "p95_return":     round((final_equities[int(n*0.95)] - capital)/capital*100, 2),
        "median_return":  round((final_equities[n//2] - capital)/capital*100, 2),
        "avg_max_dd":     round(statistics.mean(max_drawdowns), 2),
        "p95_max_dd":     round(max_drawdowns[int(n*0.95)], 2),
    }


# ═══════════════════════════════════════════════════════════════
# 10. FEATURE IMPORTANCE / EDGE DETECTION
# ═══════════════════════════════════════════════════════════════

def feature_importance(trades):
    """Compare feature distributions between winners and losers."""
    if not trades: return {}

    wins   = [t for t in trades if t["result"]=="WIN"]
    losses = [t for t in trades if t["result"]=="LOSS"]

    features = ["rsi","adx","dist_ema9","dist_ema21","dist_sma20","confidence","days_held"]
    result = {}

    for feat in features:
        w_vals = [t[feat] for t in wins   if t.get(feat) is not None]
        l_vals = [t[feat] for t in losses if t.get(feat) is not None]
        if not w_vals or not l_vals:
            continue
        w_mean = round(statistics.mean(w_vals), 2)
        l_mean = round(statistics.mean(l_vals), 2)
        diff   = round(w_mean - l_mean, 2)
        # Cohen's d (effect size)
        pooled_std = statistics.stdev(w_vals + l_vals) if len(w_vals+l_vals)>1 else 1
        cohen_d = round(abs(diff) / pooled_std, 2) if pooled_std > 0 else 0
        result[feat] = {
            "win_mean":  w_mean,
            "loss_mean": l_mean,
            "diff":      diff,
            "cohen_d":   cohen_d,
            "importance": "HIGH" if cohen_d > 0.5 else ("MED" if cohen_d > 0.25 else "LOW"),
        }

    # Signal type breakdown
    sig_types = defaultdict(lambda: {"trades":0,"wins":0,"pnl":0.0})
    for t in trades:
        st = t.get("sig_type","OTHER")
        sig_types[st]["trades"] += 1
        if t["result"] == "WIN": sig_types[st]["wins"] += 1
        sig_types[st]["pnl"] += t["pnl"]

    return {"features": result, "sig_types": dict(sig_types)}


# ═══════════════════════════════════════════════════════════════
# 11. MAIN RUNNER
# ═══════════════════════════════════════════════════════════════

def run_full_analysis(candles, p=None, capital=25000.0):
    if p is None: p = BASE_PARAMS

    print("\n" + "═"*68)
    print("  AURUM PROFESSIONAL BACKTEST")
    print(f"  {candles[0]['date']} → {candles[-1]['date']} | {len(candles)} candles")
    print("═"*68)

    # ── Full backtest ──────────────────────────────────────────
    print("\n[1/5] Running full backtest...")
    trades, equity_curve, max_dd = simulate(candles, p, capital, seed=42)
    m = compute_metrics(trades, equity_curve, capital, max_dd)

    print(f"  Trades: {m['trades']} | WR: {m['win_rate']}% | PF: {m['profit_factor']} | Sharpe: {m['sharpe']}")
    print(f"  P&L: {'+'if m['total_pnl']>=0 else ''}${m['total_pnl']:,.2f} ({m['return_pct']}%) | MaxDD: ${m['max_drawdown']:,.2f}")

    # ── Walk-forward ───────────────────────────────────────────
    print("\n[2/5] Walk-forward test (70% train / 30% test)...")
    train_m, test_m, pf_deg, wr_deg = walk_forward_test(candles, p, capital)
    print(f"  TRAIN → trades:{train_m['trades']} WR:{train_m['win_rate']}% PF:{train_m['profit_factor']} Sharpe:{train_m['sharpe']}")
    print(f"  TEST  → trades:{test_m['trades']}  WR:{test_m['win_rate']}% PF:{test_m['profit_factor']} Sharpe:{test_m['sharpe']}")
    overfitting_risk = "LOW" if pf_deg > 0.75 else ("MEDIUM" if pf_deg > 0.50 else "HIGH")
    print(f"  PF degradation: {pf_deg}x | WR degradation: {wr_deg}x | Overfitting risk: {overfitting_risk}")

    # ── Sensitivity ────────────────────────────────────────────
    print("\n[3/5] Sensitivity analysis (±10% / ±20% parameter variation)...")
    sens_results, _ = sensitivity_analysis(candles, p, capital)
    unstable = [r for r in sens_results if not r["stable"]]
    stable   = [r for r in sens_results if r["stable"]]
    print(f"  Stable parameters:   {[r['param'] for r in stable]}")
    print(f"  Unstable parameters: {[r['param'] for r in unstable]}")

    # ── Monte Carlo ────────────────────────────────────────────
    print("\n[4/5] Monte Carlo simulation (1,000 runs)...")
    mc = monte_carlo(trades, capital, runs=1000, seed=42)
    if mc:
        print(f"  Median return:  {mc['median_return']}%  (${mc['median_equity']:,.2f})")
        print(f"  5th pct return: {mc['p5_return']}%  (worst realistic scenario)")
        print(f"  95th pct:       {mc['p95_return']}%  (best realistic scenario)")
        print(f"  Avg max DD:     ${mc['avg_max_dd']:,.2f} | P95 max DD: ${mc['p95_max_dd']:,.2f}")
        print(f"  Ruin risk (<50% capital): {mc['ruin_pct']}%")

    # ── Feature importance ─────────────────────────────────────
    print("\n[5/5] Feature importance & edge detection...")
    fi = feature_importance(trades)
    feats = fi.get("features", {})
    if feats:
        print(f"  {'Feature':<15} {'Win avg':>9} {'Loss avg':>9} {'Diff':>7} {'Cohen d':>8} {'Importance'}")
        print(f"  {'-'*60}")
        for feat, v in sorted(feats.items(), key=lambda x: -x[1]["cohen_d"]):
            sign = "+" if v["diff"] > 0 else ""
            print(f"  {feat:<15} {v['win_mean']:>9} {v['loss_mean']:>9} {sign+str(v['diff']):>7} {v['cohen_d']:>8} {v['importance']}")

    sig_types = fi.get("sig_types", {})
    if sig_types:
        print(f"\n  {'Signal Type':<18} {'Trades':>7} {'WR':>7} {'P&L':>10}")
        print(f"  {'-'*44}")
        for st, v in sorted(sig_types.items(), key=lambda x: -x[1]["pnl"]):
            wr = round(v["wins"]/v["trades"]*100,1) if v["trades"]>0 else 0
            sign = "+" if v["pnl"]>=0 else ""
            print(f"  {st:<18} {v['trades']:>7} {wr:>6}% {sign+'$'+str(round(v['pnl'],2)):>10}")

    # ── Trade log ──────────────────────────────────────────────
    print(f"\n{'═'*68}")
    print("  FULL TRADE LOG")
    print(f"{'═'*68}")
    print(f"{'Open':<12} {'Close':<12} {'Dir':<6} {'Type':<18} {'Entry':>8} {'Exit':>8} {'RR':>4} {'RSI':>5} {'ADX':>5} {'D':>4} {'P&L':>9}  Res")
    print("-"*115)
    for t in trades:
        ps   = ("+" if t["pnl"]>=0 else "")+f"${abs(t['pnl']):,.2f}"
        adxs = str(t["adx"]) if t.get("adx") else "N/A"
        rsi  = str(t["rsi"]) if t.get("rsi") is not None else "N/A"
        print(f"{t['open_date']:<12} {t['close_date']:<12} {t['signal']:<6} {t.get('sig_type',''):<18} "
              f"{t['entry']:>8.2f} {t['exit']:>8.2f} {t['rr']:>4} {rsi:>5} {adxs:>5} "
              f"{t['days_held']:>4}  {ps:>9}  {t['result']}")

    # ── Sensitivity detail ─────────────────────────────────────
    print(f"\n{'═'*68}")
    print("  SENSITIVITY DETAIL")
    print(f"{'═'*68}")
    for r in sens_results:
        stability = "✓ STABLE" if r["stable"] else "✗ FRAGILE"
        print(f"\n  {r['param']} (base={r['base']}) — Sharpe std={r['sharpe_std']} — {stability}")
        print(f"  {'Change':>8} {'Value':>8} {'Sharpe':>8} {'PF':>6} {'WR':>6} {'Trades':>7}")
        for v in r["variants"]:
            print(f"  {v['change']:>8} {v['value']:>8} {v['sharpe']:>8} {v['pf']:>6} {v['wr']:>5}% {v['trades']:>7}")

    # ── Save all results ───────────────────────────────────────
    os.makedirs("backtest", exist_ok=True)
    summary = {
        "run_date":      datetime.now().isoformat(),
        "period":        f"{candles[0]['date']} → {candles[-1]['date']}",
        "candles":       len(candles),
        "capital":       capital,
        "full_backtest": m,
        "walk_forward":  {"train": train_m, "test": test_m,
                          "pf_degradation": pf_deg, "wr_degradation": wr_deg,
                          "overfitting_risk": overfitting_risk},
        "monte_carlo":   mc,
        "sensitivity":   [{
            "param": r["param"], "stable": r["stable"],
            "sharpe_std": r["sharpe_std"],
            "variants": r["variants"]
        } for r in sens_results],
        "feature_importance": {k: v for k,v in feats.items()},
        "signal_types":  {k: {"trades":v["trades"],"wins":v["wins"],
                               "win_rate": round(v["wins"]/v["trades"]*100,1) if v["trades"]>0 else 0,
                               "pnl":round(v["pnl"],2)} for k,v in sig_types.items()},
        "parameters":    p,
    }
    with open("backtest/pro_summary.json","w",encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    if trades:
        with open("backtest/pro_trades.csv","w",newline="",encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=trades[0].keys())
            w.writeheader(); w.writerows(trades)

    print(f"\n  Saved: backtest/pro_summary.json")
    print(f"  Saved: backtest/pro_trades.csv")

    # ── Final verdict ──────────────────────────────────────────
    print(f"\n{'═'*68}")
    print("  VERDICT")
    print(f"{'═'*68}")
    issues = []
    if m["profit_factor"] < 1.0:   issues.append("❌ Profit factor < 1.0 — strategy loses money")
    if m["win_rate"] < 35:         issues.append("❌ Win rate below 35% — too many losses")
    if overfitting_risk == "HIGH": issues.append("❌ High overfitting risk — does not generalize")
    if mc and mc["ruin_pct"] > 5:  issues.append(f"❌ Ruin risk {mc['ruin_pct']}% — position sizing too aggressive")
    if unstable:                   issues.append(f"⚠️  Fragile parameters: {[r['param'] for r in unstable]}")
    if m["profit_factor"] >= 1.3 and overfitting_risk != "HIGH":
        issues.append("✅ Strategy shows positive edge")
    if mc and mc["ruin_pct"] < 2:
        issues.append("✅ Ruin risk acceptable")
    if not unstable:
        issues.append("✅ All parameters stable — strategy robust")

    for issue in issues:
        print(f"  {issue}")

    print(f"\n  RECOMMENDATION:")
    if m["profit_factor"] >= 1.3 and overfitting_risk in ("LOW","MEDIUM"):
        print("  → Strategy viable. Focus on PULLBACK signals (higher edge).")
        print("  → Consider disabling TREND signals if WR<40%.")
        if unstable:
            print(f"  → Review fragile params: {[r['param'] for r in unstable]}")
    else:
        print("  → Strategy needs improvement before live trading.")
        print("  → Increase walk-forward test score first.")
        print("  → Consider disabling lowest-performing signal types.")

    return summary


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    try:
        import MetaTrader5 as mt5
        mt5.initialize()
        rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_D1, 0, 500)
        mt5.shutdown()
        if rates is None or len(rates) == 0:
            raise ValueError("No MT5 data")
        candles = [{
            "date":  datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d"),
            "open":  float(r["open"]),  "high": float(r["high"]),
            "low":   float(r["low"]),   "close":float(r["close"]),
            "vol":   int(r["tick_volume"])
        } for r in rates]
        print(f"MT5 data loaded: {len(candles)} candles")
    except Exception as e:
        print(f"MT5 error: {e} — using synthetic data for demo")
        import math
        candles = []
        price = 2000.0
        for i in range(500):
            price = price * (1 + (random.gauss(0.0002, 0.012)))
            candles.append({
                "date":  (datetime(2024,1,1) if i==0 else datetime.now()).strftime("%Y-%m-%d"),
                "open":  round(price * random.uniform(0.999, 1.001), 2),
                "high":  round(price * random.uniform(1.003, 1.010), 2),
                "low":   round(price * random.uniform(0.990, 0.997), 2),
                "close": round(price, 2), "vol": 1000,
            })

    run_full_analysis(candles, BASE_PARAMS, capital=25000.0)
