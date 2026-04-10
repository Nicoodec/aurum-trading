import MetaTrader5 as mt5
from datetime import datetime
import statistics
from aurum_quant import simulate, metrics, generate_signal, get_d1_trend

mt5.initialize()
rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, 99999)
mt5.shutdown()
candles = [{"t":datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d %H:%M"),
            "o":float(r["open"]),"h":float(r["high"]),"l":float(r["low"]),
            "c":float(r["close"]),"v":int(r["tick_volume"])} for r in rates]

# Parametros del mejor combo que encontramos
p = {
    "ema_fast":9,"ema_mid":21,"ema_slow":50,
    "rsi_period":14,"rsi_ob":68,"rsi_os":30,
    "rsi_bull_max":65,"rsi_bear_min":35,
    "atr_period":14,"sl_mult":1.5,"tp_mult":3.0,
    "adx_period":14,"adx_trend":20,
    "pb_ema21":0.6,"pb_ema9":0.3,"ext_limit":2.0,
    "sess_start":7,"sess_end":20,
    "use_pb21":True,"use_pb9":True,"use_bb":True,"use_trend":True,"use_short":True,
}

print("Running simulation on full dataset...")
trades, ec, max_dd = simulate(candles, p, capital=25000.0)
m = metrics(trades, ec, 25000.0, max_dd)

print("n=" + str(m["n"]) + " wr=" + str(m["wr"]) + "% pf=" + str(m["pf"]) + " maxdd=" + str(m["maxdd_pct"]) + "%")
print()

wins = [t for t in trades if t["result"] == "WIN"]
losses = [t for t in trades if t["result"] == "LOSS"]

# Analisis por tipo de senal
print("=== BY SIGNAL TYPE ===")
for stype in ["PB21","PB9","BB","TR"]:
    tw = [t for t in wins   if t.get("type") == stype]
    tl = [t for t in losses if t.get("type") == stype]
    tn = tw + tl
    if not tn: continue
    pnl = sum(t["pnl"] for t in tn)
    wr  = round(len(tw)/len(tn)*100,1)
    print(stype + ": n=" + str(len(tn)) + " wr=" + str(wr) + "% pnl=$" + str(round(pnl,2)))

print()
print("=== BY D1 TREND ===")
for d1t in ["UP","DOWN","SIDEWAYS","UNKNOWN"]:
    tw = [t for t in wins   if t.get("d1") == d1t]
    tl = [t for t in losses if t.get("d1") == d1t]
    tn = tw + tl
    if not tn: continue
    pnl = sum(t["pnl"] for t in tn)
    wr  = round(len(tw)/len(tn)*100,1)
    print(d1t + ": n=" + str(len(tn)) + " wr=" + str(wr) + "% pnl=$" + str(round(pnl,2)))

print()
print("=== WIN CONDITIONS ===")
if wins:
    print("Avg RSI wins:  " + str(round(statistics.mean(t["rsi"] for t in wins if t.get("rsi")),2)))
    print("Avg ADX wins:  " + str(round(statistics.mean(t["adx"] for t in wins if t.get("adx")),2)))
    print("Avg ATR wins:  " + str(round(statistics.mean(t["atr"] for t in wins if t.get("atr")),2)))
if losses:
    print("Avg RSI loss:  " + str(round(statistics.mean(t["rsi"] for t in losses if t.get("rsi")),2)))
    print("Avg ADX loss:  " + str(round(statistics.mean(t["adx"] for t in losses if t.get("adx")),2)))
    print("Avg ATR loss:  " + str(round(statistics.mean(t["atr"] for t in losses if t.get("atr")),2)))

print()
print("=== YEARLY BREAKDOWN ===")
by_year = {}
for t in trades:
    y = t["open"][:4]
    if y not in by_year: by_year[y] = {"n":0,"wins":0,"pnl":0.0}
    by_year[y]["n"] += 1
    by_year[y]["pnl"] += t["pnl"]
    if t["result"] == "WIN": by_year[y]["wins"] += 1
for y in sorted(by_year.keys()):
    v = by_year[y]
    wr = round(v["wins"]/v["n"]*100,1) if v["n"]>0 else 0
    bar = ("+" if v["pnl"]>=0 else "") + str(round(v["pnl"],0))
    print(y + ": n=" + str(v["n"]) + " wr=" + str(wr) + "% pnl=$" + bar)

print()
print("=== LAST 10 TRADES ===")
for t in trades[-10:]:
    print(t["open"][:13] + " " + t["dir"] + " " + str(t.get("type","?")) +
          " entry=" + str(t["entry"]) + " exit=" + str(t["exit"]) +
          " pnl=$" + str(t["pnl"]) + " " + t["result"] +
          " d1=" + str(t.get("d1","?")))
