import MetaTrader5 as mt5
import json, os, csv
from datetime import datetime, timedelta

# ============================================================
# AURUM BACKTEST -- 60 dias D1 reales de MT5
# ============================================================

OUTPUT_DIR = "backtest"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# --- Indicadores ---
def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i-1]
        gains.append(max(d, 0))
        losses.append(max(-d, 0))
    ag = sum(gains[-period:]) / period
    al = sum(losses[-period:]) / period
    if al == 0: return 100.0
    return round(100 - 100 / (1 + ag/al), 1)

def calc_sma(closes, period):
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)

def calc_atr(candles, period=14):
    trs = []
    for i in range(1, len(candles)):
        h  = candles[i]["high"]
        l  = candles[i]["low"]
        pc = candles[i-1]["close"]
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
    if len(trs) < period:
        return None
    return round(sum(trs[-period:]) / period, 2)

def find_levels(candles):
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]
    closes = [c["close"] for c in candles]
    if not closes:
        return None, None
    current = closes[-1]
    sup = max([l for l in lows   if l < current], default=None)
    res = min([h for h in highs  if h > current], default=None)
    return (round(sup,2) if sup else None), (round(res,2) if res else None)

# --- Signal logic ---
def generate_signal(candles_so_far):
    closes = [c["close"] for c in candles_so_far]
    rsi    = calc_rsi(closes)
    sma20  = calc_sma(closes, 20)
    sma50  = calc_sma(closes, 50)
    atr    = calc_atr(candles_so_far)
    sup, res = find_levels(candles_so_far)

    if rsi is None or atr is None or sma20 is None:
        return None

    price  = closes[-1]
    trend  = "UP"   if sma20 and price > sma20 else "DOWN"
    rsi_z  = "OVERBOUGHT" if rsi > 70 else ("OVERSOLD" if rsi < 30 else "NEUTRAL")
    c      = candles_so_far[-1]
    chg    = round((c["close"] - c["open"]) / c["open"] * 100, 2)

    # Signal rules (same as live system)
    signal = None
    reason = ""

    # LONG conditions
    if (
        trend == "UP"
        and rsi < 68          # not overbought
        and rsi > 45          # has momentum
        and chg > -0.5        # not big red candle
        and sma20 > (sma50 or 0)  # golden cross
    ):
        signal = "LONG"
        reason = "Trend UP, RSI=" + str(rsi) + ", price above SMA20, SMA20>SMA50"

    # SHORT conditions
    elif (
        trend == "DOWN"
        and rsi > 32          # not oversold
        and rsi < 55          # has downward momentum
        and chg < 0.5         # not big green candle
        and sma20 < (sma50 or 99999)  # death cross
    ):
        signal = "SHORT"
        reason = "Trend DOWN, RSI=" + str(rsi) + ", price below SMA20, SMA20<SMA50"

    # Oversold bounce
    elif rsi is not None and rsi < 28 and trend == "UP":
        signal = "LONG"
        reason = "Oversold bounce RSI=" + str(rsi) + " in uptrend"

    # Overbought short
    elif rsi is not None and rsi > 75 and trend == "DOWN":
        signal = "SHORT"
        reason = "Overbought RSI=" + str(rsi) + " in downtrend"

    if signal is None:
        return None

    # Risk management (same as live)
    sl_dist = atr * 1.5
    tp_dist = atr * 3.0
    risk_pct = 0.02
    rr = round(tp_dist / sl_dist, 1)

    if rr < 2.0:
        return None  # RR too low

    return {
        "signal":     signal,
        "reason":     reason,
        "price":      price,
        "rsi":        rsi,
        "sma20":      sma20,
        "sma50":      sma50,
        "atr":        atr,
        "support":    sup,
        "resistance": res,
        "sl_dist":    round(sl_dist, 2),
        "tp_dist":    round(tp_dist, 2),
        "rr":         rr,
        "trend":      trend,
    }

# --- Simulation ---
def simulate(candles, capital=25000.0, risk_pct=0.02, max_positions=3):
    trades    = []
    equity    = capital
    peak      = capital
    max_dd    = 0.0
    equity_curve = [{"date": candles[0]["date"], "equity": capital}]
    open_pos  = []  # {signal, entry, sl, tp, sl_price, tp_price, open_date, lots, risk_usd}

    MIN_CANDLES = 22  # need at least 22 for SMA20 + RSI

    for i in range(MIN_CANDLES, len(candles)):
        today   = candles[i]
        history = candles[:i]
        date    = today["date"]
        o, h, l, c = today["open"], today["high"], today["low"], today["close"]

        # Check open positions for exit
        still_open = []
        for pos in open_pos:
            result = None
            exit_price = None

            if pos["signal"] == "LONG":
                if l <= pos["sl_price"]:
                    result     = "LOSS"
                    exit_price = pos["sl_price"]
                elif h >= pos["tp_price"]:
                    result     = "WIN"
                    exit_price = pos["tp_price"]
            else:  # SHORT
                if h >= pos["sl_price"]:
                    result     = "LOSS"
                    exit_price = pos["sl_price"]
                elif l <= pos["tp_price"]:
                    result     = "WIN"
                    exit_price = pos["tp_price"]

            if result:
                if result == "WIN":
                    pnl = pos["risk_usd"] * pos["rr"]
                else:
                    pnl = -pos["risk_usd"]

                equity += pnl
                peak    = max(peak, equity)
                dd      = peak - equity
                max_dd  = max(max_dd, dd)

                trades.append({
                    "open_date":   pos["open_date"],
                    "close_date":  date,
                    "signal":      pos["signal"],
                    "entry":       pos["entry"],
                    "exit":        exit_price,
                    "sl":          pos["sl_price"],
                    "tp":          pos["tp_price"],
                    "rr":          pos["rr"],
                    "lots":        pos["lots"],
                    "risk_usd":    pos["risk_usd"],
                    "pnl":         round(pnl, 2),
                    "result":      result,
                    "rsi":         pos["rsi"],
                    "atr":         pos["atr"],
                    "equity_after":round(equity, 2),
                    "reason":      pos["reason"],
                })
            else:
                still_open.append(pos)

        open_pos = still_open

        # Max 3 positions
        if len(open_pos) >= max_positions:
            equity_curve.append({"date": date, "equity": round(equity, 2)})
            continue

        # FTMO daily loss check
        today_pnl = sum(t["pnl"] for t in trades if t["close_date"] == date)
        if today_pnl <= -(capital * 0.05):
            equity_curve.append({"date": date, "equity": round(equity, 2)})
            continue

        # FTMO total loss check
        if (capital - equity) >= capital * 0.10:
            equity_curve.append({"date": date, "equity": round(equity, 2)})
            continue

        # Generate signal
        sig = generate_signal(history)
        if sig is None:
            equity_curve.append({"date": date, "equity": round(equity, 2)})
            continue

        # Position sizing
        risk_usd = round(equity * risk_pct, 2)
        lots     = round(risk_usd / (sig["sl_dist"] * 100), 2)
        lots     = max(0.01, min(lots, 5.0))

        sl_price = round(sig["price"] - sig["sl_dist"], 2) if sig["signal"] == "LONG" else round(sig["price"] + sig["sl_dist"], 2)
        tp_price = round(sig["price"] + sig["tp_dist"], 2) if sig["signal"] == "LONG" else round(sig["price"] - sig["tp_dist"], 2)

        open_pos.append({
            "signal":    sig["signal"],
            "entry":     sig["price"],
            "sl_price":  sl_price,
            "tp_price":  tp_price,
            "sl_dist":   sig["sl_dist"],
            "tp_dist":   sig["tp_dist"],
            "rr":        sig["rr"],
            "lots":      lots,
            "risk_usd":  risk_usd,
            "open_date": date,
            "rsi":       sig["rsi"],
            "atr":       sig["atr"],
            "reason":    sig["reason"],
        })

        equity_curve.append({"date": date, "equity": round(equity, 2)})

    return trades, equity_curve, max_dd

# ============================================================
# MAIN
# ============================================================
print()
print("=" * 56)
print("  AURUM BACKTEST -- MT5 D1 Real Data")
print("=" * 56)

mt5.initialize()
rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_D1, 0, 60)
mt5.shutdown()

if rates is None or len(rates) == 0:
    print("ERROR: No MT5 data available")
    exit(1)

candles = []
for r in rates:
    candles.append({
        "date":  datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d"),
        "open":  float(r["open"]),
        "high":  float(r["high"]),
        "low":   float(r["low"]),
        "close": float(r["close"]),
        "vol":   int(r["tick_volume"]),
    })

print("Data: " + candles[0]["date"] + " to " + candles[-1]["date"] + " (" + str(len(candles)) + " candles)")
print()

CAPITAL = 25000.0
trades, equity_curve, max_dd = simulate(candles, capital=CAPITAL)

# ============================================================
# RESULTS
# ============================================================
wins   = [t for t in trades if t["result"] == "WIN"]
losses = [t for t in trades if t["result"] == "LOSS"]
total_pnl   = sum(t["pnl"] for t in trades)
gross_win   = sum(t["pnl"] for t in wins)
gross_loss  = abs(sum(t["pnl"] for t in losses))
win_rate    = len(wins) / len(trades) * 100 if trades else 0
avg_win     = gross_win  / len(wins)   if wins   else 0
avg_loss    = gross_loss / len(losses) if losses else 0
pf          = round(gross_win / gross_loss, 2) if gross_loss > 0 else 0
final_eq    = CAPITAL + total_pnl
best_trade  = max(trades, key=lambda t: t["pnl"]) if trades else None
worst_trade = min(trades, key=lambda t: t["pnl"]) if trades else None

# Sharpe (simplified daily returns)
if len(equity_curve) > 1:
    returns = []
    for i in range(1, len(equity_curve)):
        r = (equity_curve[i]["equity"] - equity_curve[i-1]["equity"]) / equity_curve[i-1]["equity"]
        returns.append(r)
    import statistics
    mean_r  = statistics.mean(returns)
    std_r   = statistics.stdev(returns) if len(returns) > 1 else 1
    sharpe  = round((mean_r / std_r) * (252**0.5), 2) if std_r > 0 else 0
else:
    sharpe = 0

print("=" * 56)
print("  RESULTS")
print("=" * 56)
print("Capital inicial:   $" + str(CAPITAL))
print("Capital final:     $" + str(round(final_eq, 2)))
print("Total P&L:         " + ("+" if total_pnl >= 0 else "") + "$" + str(round(total_pnl, 2)))
print("Return:            " + str(round(total_pnl/CAPITAL*100, 2)) + "%")
print()
print("Trades totales:    " + str(len(trades)))
print("Wins:              " + str(len(wins)) + " (" + str(round(win_rate, 1)) + "%)")
print("Losses:            " + str(len(losses)) + " (" + str(round(100-win_rate, 1)) + "%)")
print()
print("Avg win:           +$" + str(round(avg_win, 2)))
print("Avg loss:          -$" + str(round(avg_loss, 2)))
print("Profit factor:     " + str(pf))
print("Sharpe ratio:      " + str(sharpe))
print("Max drawdown:      -$" + str(round(max_dd, 2)))
print()
if best_trade:
    print("Best trade:        +" + str(best_trade["pnl"]) + " (" + best_trade["open_date"] + " " + best_trade["signal"] + ")")
if worst_trade:
    print("Worst trade:       " + str(worst_trade["pnl"]) + " (" + worst_trade["open_date"] + " " + worst_trade["signal"] + ")")
print("=" * 56)

# ============================================================
# TRADE LOG
# ============================================================
print()
print("TRADE LOG:")
print("-" * 100)
print(f"{'Date':<12} {'Dir':<6} {'Entry':>8} {'Exit':>8} {'SL':>8} {'TP':>8} {'RR':>5} {'Lots':>5} {'Risk$':>7} {'P&L':>8} {'Result':<6} {'RSI':>5} {'Reason'}")
print("-" * 100)
for t in trades:
    pnl_str = ("+" if t["pnl"] >= 0 else "") + str(t["pnl"])
    print(f"{t['open_date']:<12} {t['signal']:<6} {t['entry']:>8.2f} {t['exit']:>8.2f} {t['sl']:>8.2f} {t['tp']:>8.2f} {t['rr']:>5} {t['lots']:>5} ${t['risk_usd']:>6} {pnl_str:>8} {t['result']:<6} {t['rsi']:>5} {t['reason'][:40]}")

# ============================================================
# SAVE FILES
# ============================================================
# CSV
csv_path = os.path.join(OUTPUT_DIR, "trades.csv")
if trades:
    keys = trades[0].keys()
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(trades)
    print()
    print("Trades CSV saved: " + csv_path)

# Equity curve JSON
eq_path = os.path.join(OUTPUT_DIR, "equity_curve.json")
with open(eq_path, "w", encoding="utf-8") as f:
    json.dump(equity_curve, f, indent=2)

# Summary JSON
summary = {
    "run_date":       datetime.now().isoformat(),
    "period":         candles[0]["date"] + " to " + candles[-1]["date"],
    "candles":        len(candles),
    "capital":        CAPITAL,
    "final_equity":   round(final_eq, 2),
    "total_pnl":      round(total_pnl, 2),
    "return_pct":     round(total_pnl/CAPITAL*100, 2),
    "trades":         len(trades),
    "wins":           len(wins),
    "losses":         len(losses),
    "win_rate":       round(win_rate, 1),
    "avg_win":        round(avg_win, 2),
    "avg_loss":       round(avg_loss, 2),
    "profit_factor":  pf,
    "sharpe":         sharpe,
    "max_drawdown":   round(max_dd, 2),
    "best_trade":     best_trade,
    "worst_trade":    worst_trade,
}
with open(os.path.join(OUTPUT_DIR, "summary.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, indent=2, default=str)

print("Summary JSON saved: backtest/summary.json")
print("Equity curve JSON: backtest/equity_curve.json")
print()
print("AURUM BACKTEST COMPLETE")
