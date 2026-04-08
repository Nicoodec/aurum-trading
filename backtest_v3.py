import MetaTrader5 as mt5
import json, os, csv, statistics
from datetime import datetime

OUTPUT_DIR = "backtest"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def calc_rsi(closes, period=14):
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

def calc_atr(candles, period=14):
    trs = []
    for i in range(1, len(candles)):
        h=candles[i]["high"]; l=candles[i]["low"]; pc=candles[i-1]["close"]
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
    if len(trs) < period: return None
    return round(sum(trs[-period:]) / period, 2)

def calc_adx(candles, period=14):
    if len(candles) < period + 2: return None
    plus_dm, minus_dm, trs = [], [], []
    for i in range(1, len(candles)):
        h=candles[i]["high"]; l=candles[i]["low"]
        ph=candles[i-1]["high"]; pl=candles[i-1]["low"]; pc=candles[i-1]["close"]
        up=h-ph; down=pl-l
        plus_dm.append(up   if up>down and up>0   else 0)
        minus_dm.append(down if down>up and down>0 else 0)
        trs.append(max(h-l, abs(h-pc), abs(l-pc)))
    def smooth(arr, p):
        s=sum(arr[:p]); result=[s]
        for v in arr[p:]: s=s-s/p+v; result.append(s)
        return result
    str14=smooth(trs,period); pdm14=smooth(plus_dm,period); mdm14=smooth(minus_dm,period)
    adx_vals=[]
    for i in range(len(str14)):
        if str14[i]==0: continue
        pdi=100*pdm14[i]/str14[i]; mdi=100*mdm14[i]/str14[i]
        dx=100*abs(pdi-mdi)/(pdi+mdi) if (pdi+mdi)>0 else 0
        adx_vals.append(dx)
    if len(adx_vals)<period: return None
    return round(sum(adx_vals[-period:])/period, 1)

def generate_signal(candles_so_far):
    if len(candles_so_far) < 22: return None
    closes=[c["close"] for c in candles_so_far]
    rsi  = calc_rsi(closes)
    ema9 = calc_ema(closes, 9)
    ema21= calc_ema(closes, 21)
    ema50= calc_ema(closes, 50) if len(closes)>=50 else None
    sma20= calc_sma(closes, 20)
    atr  = calc_atr(candles_so_far)
    adx  = calc_adx(candles_so_far)
    if any(v is None for v in [rsi, ema9, ema21, atr, sma20]): return None

    price = closes[-1]
    c     = candles_so_far[-1]
    chg   = round((c["close"]-c["open"])/c["open"]*100, 2)

    trend_fast = "UP"   if ema9  > ema21  else "DOWN"
    trend_slow = "UP"   if price > sma20  else "DOWN"
    above_ema50= ema50 is None or price > ema50
    below_ema50= ema50 is None or price < ema50
    trending   = adx is None or adx > 18

    signal=None; reason=""; confidence=60

    # LONG
    if (trend_fast=="UP" and trend_slow=="UP" and above_ema50
        and 42 < rsi < 68 and trending and chg > -1.5):
        signal="LONG"; confidence=68
        if rsi > 50: confidence+=4
        if adx and adx>25: confidence+=4
        reason="EMA9>EMA21, price>SMA20>EMA50, RSI="+str(rsi)+", ADX="+str(adx)

    # SHORT
    elif (trend_fast=="DOWN" and trend_slow=="DOWN" and below_ema50
          and 32 < rsi < 58 and trending and chg < 1.5):
        signal="SHORT"; confidence=68
        if rsi < 50: confidence+=4
        if adx and adx>25: confidence+=4
        reason="EMA9<EMA21, price<SMA20<EMA50, RSI="+str(rsi)+", ADX="+str(adx)

    # Oversold bounce in uptrend
    elif rsi is not None and rsi<30 and trend_fast=="UP":
        signal="LONG"; confidence=65
        reason="Oversold RSI="+str(rsi)+" in uptrend"

    # Overbought in downtrend
    elif rsi is not None and rsi>70 and trend_fast=="DOWN":
        signal="SHORT"; confidence=65
        reason="Overbought RSI="+str(rsi)+" in downtrend"

    if signal is None: return None

    sl_dist=round(atr*1.5, 2); tp_dist=round(atr*3.0, 2)
    rr=round(tp_dist/sl_dist, 1)
    if rr < 2.0: return None

    return {"signal":signal,"confidence":confidence,"reason":reason,
            "price":price,"rsi":rsi,"ema9":ema9,"ema21":ema21,"ema50":ema50,
            "sma20":sma20,"atr":atr,"adx":adx,"sl_dist":sl_dist,"tp_dist":tp_dist,"rr":rr,
            "trend_fast":trend_fast,"trend_slow":trend_slow}

def simulate(candles, capital=25000.0, risk_pct=0.02, max_pos=3):
    trades=[]; equity=capital; peak=capital; max_dd=0.0
    equity_curve=[{"date":candles[0]["date"],"equity":capital}]
    open_pos=[]; MIN=22

    for i in range(MIN, len(candles)):
        today=candles[i]; history=candles[:i]
        date=today["date"]; h=today["high"]; l=today["low"]

        # Check exits
        still_open=[]
        for pos in open_pos:
            result=None; exit_price=None
            if pos["signal"]=="LONG":
                if l<=pos["sl_price"]: result="LOSS"; exit_price=pos["sl_price"]
                elif h>=pos["tp_price"]: result="WIN"; exit_price=pos["tp_price"]
            else:
                if h>=pos["sl_price"]: result="LOSS"; exit_price=pos["sl_price"]
                elif l<=pos["tp_price"]: result="WIN"; exit_price=pos["tp_price"]
            if result:
                pnl=pos["risk_usd"]*pos["rr"] if result=="WIN" else -pos["risk_usd"]
                equity+=pnl; peak=max(peak,equity); max_dd=max(max_dd,peak-equity)
                trades.append({
                    "open_date":pos["open_date"],"close_date":date,
                    "signal":pos["signal"],"entry":pos["entry"],"exit":exit_price,
                    "sl":pos["sl_price"],"tp":pos["tp_price"],"rr":pos["rr"],
                    "lots":pos["lots"],"risk_usd":pos["risk_usd"],
                    "pnl":round(pnl,2),"result":result,
                    "rsi":pos["rsi"],"adx":pos.get("adx"),"atr":pos["atr"],
                    "equity_after":round(equity,2),"reason":pos["reason"],
                    "confidence":pos.get("confidence",0),
                })
            else: still_open.append(pos)
        open_pos=still_open
        equity_curve.append({"date":date,"equity":round(equity,2)})

        if len(open_pos)>=max_pos: continue
        today_pnl=sum(t["pnl"] for t in trades if t["close_date"]==date)
        if today_pnl<=-(capital*0.05): continue
        if (capital-equity)>=capital*0.10: continue

        sig=generate_signal(history)
        if sig is None: continue

        risk_usd=round(equity*risk_pct, 2)
        lots=max(0.01, min(round(risk_usd/(sig["sl_dist"]*100), 2), 5.0))
        sl_price=round(sig["price"]-sig["sl_dist"],2) if sig["signal"]=="LONG" else round(sig["price"]+sig["sl_dist"],2)
        tp_price=round(sig["price"]+sig["tp_dist"],2) if sig["signal"]=="LONG" else round(sig["price"]-sig["tp_dist"],2)

        open_pos.append({
            "signal":sig["signal"],"entry":sig["price"],
            "sl_price":sl_price,"tp_price":tp_price,
            "sl_dist":sig["sl_dist"],"tp_dist":sig["tp_dist"],
            "rr":sig["rr"],"lots":lots,"risk_usd":risk_usd,
            "open_date":date,"rsi":sig["rsi"],"adx":sig.get("adx"),
            "atr":sig["atr"],"reason":sig["reason"],"confidence":sig.get("confidence",0),
        })

    return trades, equity_curve, max_dd

# MAIN
print()
print("="*62)
print("  AURUM BACKTEST v3 -- EMA9/21/50 + ADX + RSI")
print("="*62)

mt5.initialize()
rates=mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_D1, 0, 60)
mt5.shutdown()

candles=[{"date":datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d"),
          "open":float(r["open"]),"high":float(r["high"]),
          "low":float(r["low"]),"close":float(r["close"]),
          "vol":int(r["tick_volume"])} for r in rates]

print("Data: "+candles[0]["date"]+" to "+candles[-1]["date"]+" ("+str(len(candles))+" candles)")
print()

CAPITAL=25000.0
trades,equity_curve,max_dd=simulate(candles)

wins=[t for t in trades if t["result"]=="WIN"]
losses=[t for t in trades if t["result"]=="LOSS"]
total_pnl=sum(t["pnl"] for t in trades)
gross_win=sum(t["pnl"] for t in wins)
gross_loss=abs(sum(t["pnl"] for t in losses))
win_rate=len(wins)/len(trades)*100 if trades else 0
avg_win=gross_win/len(wins) if wins else 0
avg_loss=gross_loss/len(losses) if losses else 0
pf=round(gross_win/gross_loss,2) if gross_loss>0 else 0
final_eq=CAPITAL+total_pnl
best=max(trades,key=lambda t:t["pnl"]) if trades else None
worst=min(trades,key=lambda t:t["pnl"]) if trades else None

returns=[(equity_curve[i]["equity"]-equity_curve[i-1]["equity"])/equity_curve[i-1]["equity"]
         for i in range(1,len(equity_curve))]
mean_r=statistics.mean(returns) if returns else 0
std_r=statistics.stdev(returns) if len(returns)>1 else 1
sharpe=round((mean_r/std_r)*(252**0.5),2) if std_r>0 else 0

print("="*62)
print("  RESULTADOS")
print("="*62)
print("Capital inicial:   $"+str(CAPITAL))
print("Capital final:     $"+str(round(final_eq,2)))
print("Total P&L:         "+("+" if total_pnl>=0 else "")+"$"+str(round(total_pnl,2)))
print("Return:            "+str(round(total_pnl/CAPITAL*100,2))+"%")
print()
print("Trades totales:    "+str(len(trades)))
print("Wins:              "+str(len(wins))+" ("+str(round(win_rate,1))+"%)")
print("Losses:            "+str(len(losses))+" ("+str(round(100-win_rate,1))+"%)")
print()
print("Avg win:           +$"+str(round(avg_win,2)))
print("Avg loss:          -$"+str(round(avg_loss,2)))
print("Profit factor:     "+str(pf))
print("Sharpe ratio:      "+str(sharpe))
print("Max drawdown:      -$"+str(round(max_dd,2)))
if best:  print("Best trade:        +"+str(best["pnl"])+" ("+best["open_date"]+" "+best["signal"]+")")
if worst: print("Worst trade:       "+str(worst["pnl"])+" ("+worst["open_date"]+" "+worst["signal"]+")")
print("="*62)
print()
print("TRADE LOG:")
print("-"*115)
print(f"{'Open':<12} {'Close':<12} {'Dir':<6} {'Entry':>8} {'Exit':>8} {'RR':>4} {'ADX':>5} {'RSI':>5} {'Conf':>5} {'P&L':>9} {'Result':<7} Reason")
print("-"*115)
for t in trades:
    ps=("+" if t["pnl"]>=0 else "")+str(t["pnl"])
    adx_s=str(t["adx"]) if t.get("adx") else "N/A"
    print(f"{t['open_date']:<12} {t['close_date']:<12} {t['signal']:<6} {t['entry']:>8.2f} {t['exit']:>8.2f} {t['rr']:>4} {adx_s:>5} {t['rsi']:>5} {t['confidence']:>5}% {ps:>9}  {t['result']:<7} {t['reason'][:50]}")

if trades:
    with open("backtest/trades_v3.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=trades[0].keys())
        w.writeheader(); w.writerows(trades)
    print("\nCSV: backtest/trades_v3.csv")

with open("backtest/summary_v3.json","w",encoding="utf-8") as f:
    json.dump({"period":candles[0]["date"]+" to "+candles[-1]["date"],
               "trades":len(trades),"wins":len(wins),"losses":len(losses),
               "win_rate":round(win_rate,1),"total_pnl":round(total_pnl,2),
               "return_pct":round(total_pnl/CAPITAL*100,2),
               "profit_factor":pf,"sharpe":sharpe,"max_drawdown":round(max_dd,2)},f,indent=2)

print("\nAURUM BACKTEST v3 COMPLETE")
