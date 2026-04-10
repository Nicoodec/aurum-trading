import MetaTrader5 as mt5
from datetime import datetime
from aurum_ftmo import simulate, generate_signal, DEFAULT_PARAMS, metrics

mt5.initialize()
rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, 99999)
mt5.shutdown()

cn = [{"t":datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d %H:%M"),
       "o":float(r["open"]),"h":float(r["high"]),"l":float(r["low"]),
       "c":float(r["close"]),"v":int(r["tick_volume"])} for r in rates]
cn = [c for c in cn if c["t"] >= "2018-01-01"]
print("Candles:", len(cn))

# Ver cuantas senales genera en total
p = DEFAULT_PARAMS
min_bars = max(p["trend_ema"], p["entry_ema"], p["atr_period"]) + 5
signals = []

for i in range(min_bars, len(cn)):
    bar = cn[i]
    hour = int(bar["t"][11:13])
    # Sin filtro de sesion para ver cuantas senales hay
    hist = cn[max(0, i - p["trend_ema"] - 10):i]
    from aurum_ftmo import ema, rsi, atr
    closes = [c["c"] for c in hist]
    t_ema = ema(closes, p["trend_ema"])
    e_ema = ema(closes, p["entry_ema"])
    if not t_ema or not e_ema: continue
    price = closes[-1]
    cur = hist[-1]
    uptrend = price > t_ema
    downtrend = price < t_ema
    touched_long = cur["l"] <= e_ema * 1.001
    confirmed_long = cur["c"] > e_ema
    touched_short = cur["h"] >= e_ema * 0.999
    confirmed_short = cur["c"] < e_ema

    if uptrend and touched_long and confirmed_long:
        signals.append({"t":bar["t"],"type":"LONG","price":price,"e_ema":e_ema,"t_ema":t_ema})
    elif downtrend and touched_short and confirmed_short:
        signals.append({"t":bar["t"],"type":"SHORT","price":price,"e_ema":e_ema,"t_ema":t_ema})

print("Total signals (no session filter):", len(signals))
print("Per year:")
by_y = {}
for s in signals:
    y = s["t"][:4]
    if y not in by_y: by_y[y] = {"L":0,"S":0}
    by_y[y][s["type"][0]] += 1
for y in sorted(by_y.keys()):
    print("  "+y+" LONG="+str(by_y[y]["L"])+" SHORT="+str(by_y[y]["S"]))

print("\nFirst 10 signals:")
for s in signals[:10]:
    print("  "+s["t"]+" "+s["type"]+" price="+str(s["price"])+" ema50="+str(s["e_ema"])+" ema200="+str(s["t_ema"]))

# Simular con default y ver los trades
print("\nSimulating with default params...")
trades, ec, dd, days = simulate(cn, DEFAULT_PARAMS)
m = metrics(trades, ec, 25000.0, dd, days)
print("n="+str(m["n"])+" wr="+str(m["wr"])+"% pf="+str(m["pf"])+" dd="+str(m["maxdd_pct"])+"%")
print("\nAll trades:")
for t in trades[:20]:
    print("  "+t["open"][:13]+" "+t["dir"]+" entry="+str(t["entry"])+" exit="+str(t["exit"])+" sl="+str(t["sl"])+" tp="+str(t["tp"])+" pnl=$"+str(t["pnl"])+" "+t["result"])
