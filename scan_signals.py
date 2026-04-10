import MetaTrader5 as mt5
from datetime import datetime
from agents.signal_engine import _get_h1_signal_from_candles, _get_d1_trend, SIGNAL_PARAMS, _load_candles

mt5.initialize()

# Cargar H1 completo
rates_h1 = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, 720)  # 30 dias
rates_d1 = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_D1, 0, 50)
mt5.shutdown()

candles_h1 = [{"time": datetime.fromtimestamp(r["time"]), "date": datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d %H:%M"),
               "open": float(r["open"]), "high": float(r["high"]),
               "low": float(r["low"]), "close": float(r["close"]), "vol": int(r["tick_volume"])} for r in rates_h1]

p = SIGNAL_PARAMS
signals_found = []
MIN = 55

print("Scanning", len(candles_h1), "H1 candles for signals...")
print()

for i in range(MIN, len(candles_h1)):
    history = candles_h1[:i]
    current = candles_h1[i]

    # D1 trend approximation from H1 data
    h1_closes = [c["close"] for c in history[-200:]]
    from agents.signal_engine import _ema
    ema9_d  = _ema(h1_closes[-50:], 9)
    ema21_d = _ema(h1_closes[-50:], 21)
    if ema9_d and ema21_d:
        d1_trend = "UP" if ema9_d > ema21_d else "DOWN"
    else:
        d1_trend = "SIDEWAYS"

    sig = _get_h1_signal_from_candles(history[-100:], d1_trend, p)
    if sig:
        # Simulate outcome
        future = candles_h1[i+1:i+25]  # next 24 hours
        result = "OPEN"
        exit_price = None
        exit_time = None
        for fc in future:
            if sig["signal"] == "LONG":
                if fc["low"] <= sig["price"] - sig["sl_dist"]:
                    result = "LOSS"; exit_price = sig["price"] - sig["sl_dist"]; exit_time = fc["date"]; break
                elif fc["high"] >= sig["price"] + sig["tp_dist"]:
                    result = "WIN"; exit_price = sig["price"] + sig["tp_dist"]; exit_time = fc["date"]; break
            else:
                if fc["high"] >= sig["price"] + sig["sl_dist"]:
                    result = "LOSS"; exit_price = sig["price"] + sig["sl_dist"]; exit_time = fc["date"]; break
                elif fc["low"] <= sig["price"] - sig["tp_dist"]:
                    result = "WIN"; exit_price = sig["price"] - sig["tp_dist"]; exit_time = fc["date"]; break

        signals_found.append({
            "time":     current["date"],
            "signal":   sig["signal"],
            "sig_type": sig["sig_type"],
            "conf":     sig["confidence"],
            "price":    sig["price"],
            "sl":       round(sig["price"] - sig["sl_dist"] if sig["signal"]=="LONG" else sig["price"] + sig["sl_dist"], 2),
            "tp":       round(sig["price"] + sig["tp_dist"] if sig["signal"]=="LONG" else sig["price"] - sig["tp_dist"], 2),
            "sl_dist":  sig["sl_dist"],
            "tp_dist":  sig["tp_dist"],
            "rsi":      sig["rsi"],
            "adx":      sig["adx"],
            "d1_trend": d1_trend,
            "result":   result,
            "exit":     exit_price,
            "exit_time":exit_time,
        })

        # Skip ahead to avoid overlapping signals
        i += 3

wins   = [s for s in signals_found if s["result"] == "WIN"]
losses = [s for s in signals_found if s["result"] == "LOSS"]
opens  = [s for s in signals_found if s["result"] == "OPEN"]

print(f"Total signals: {len(signals_found)}")
print(f"Wins:   {len(wins)}")
print(f"Losses: {len(losses)}")
print(f"Open:   {len(opens)}")
if len(wins)+len(losses) > 0:
    wr = round(len(wins)/(len(wins)+len(losses))*100, 1)
    print(f"Win rate: {wr}%")
print()
print(f"{'Time':<18} {'Dir':<6} {'Type':<18} {'Conf':>5} {'RSI':>5} {'ADX':>5} {'SL$':>6} {'TP$':>6} {'Result'}")
print("-"*90)
for s in signals_found:
    print(f"{s['time']:<18} {s['signal']:<6} {s['sig_type']:<18} {s['conf']:>5}% {s['rsi']:>5} {str(s['adx']):>5} {s['sl_dist']:>6} {s['tp_dist']:>6}  {s['result']}")
