import MetaTrader5 as mt5
from datetime import datetime
from aurum_quant import simulate, generate_signal, metrics, score, FTMO

mt5.initialize()
rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, 99999)
mt5.shutdown()
candles = [{"t":datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d %H:%M"),
            "o":float(r["open"]),"h":float(r["high"]),"l":float(r["low"]),
            "c":float(r["close"]),"v":int(r["tick_volume"])} for r in rates]

print("Loaded:", len(candles), "candles")

# Test con parametros muy relajados
p = {
    "ema_fast":9,"ema_mid":21,"ema_slow":50,
    "rsi_period":14,"rsi_ob":72,"rsi_os":30,
    "rsi_bull_max":68,"rsi_bear_min":32,
    "atr_period":14,"sl_mult":1.5,"tp_mult":3.0,
    "adx_period":14,"adx_trend":15,
    "pb_ema21":0.8,"pb_ema9":0.5,"ext_limit":3.0,
    "sess_start":0,"sess_end":24,
    "use_pb21":True,"use_pb9":True,"use_bb":True,"use_trend":True,"use_short":True,
}

# Contar senales en 2000 velas
print("Scanning 2000 H1 candles for signals...")
count = 0
mn = max(p["ema_slow"], p["adx_period"], p["rsi_period"]) + 5
sample = candles[70000:72000]
for i in range(mn, len(sample)):
    history = sample[max(0,i-200):i]
    bar = sample[i]
    hour = int(bar["t"][11:13])
    sig = generate_signal(history, p, hour_utc=hour, d1t="SIDEWAYS")
    if sig:
        count += 1
        if count <= 8:
            print("  " + sig["signal"] + " " + sig["type"] +
                  " RSI=" + str(sig["rsi"]) +
                  " ADX=" + str(sig["adx"]) +
                  " d21=" + str(sig["d21"]) +
                  " d9=" + str(sig["d9"]))

print("Signals in 2000 bars:", count)
print("Approx per year:", round(count * 8760 / 2000))

# Simular con estos parametros en muestra de 5000 velas
print()
print("Simulating 5000 bars...")
sample5k = candles[65000:70000]
t, ec, dd = simulate(sample5k, p, capital=25000.0)
m = metrics(t, ec, 25000.0, dd)
s = score(m)
print("Trades:", m["n"])
print("Win rate:", m["wr"], "%")
print("PF:", m["pf"])
print("Sharpe:", m["sharpe"])
print("MaxDD:", m["maxdd_pct"], "%")
print("Score:", round(s, 3))
print()
if m["n"] == 0:
    print("PROBLEM: Zero trades - signal generation broken or filters too strict")
elif m["n"] < 20:
    print("PROBLEM: Too few trades -", m["n"], "need at least 20")
else:
    print("OK: Enough trades to evaluate")
