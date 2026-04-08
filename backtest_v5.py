import MetaTrader5 as mt5
import json, os, csv, statistics
from datetime import datetime

OUTPUT_DIR = "backtest"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def calc_rsi(closes, period=14):
    if len(closes) < period+1: return None
    gains,losses=[],[]
    for i in range(1,len(closes)):
        d=closes[i]-closes[i-1]
        gains.append(max(d,0)); losses.append(max(-d,0))
    ag=sum(gains[-period:])/period; al=sum(losses[-period:])/period
    if al==0: return 100.0
    return round(100-100/(1+ag/al),1)

def calc_ema(closes,period):
    if len(closes)<period: return None
    k=2/(period+1); ema=sum(closes[:period])/period
    for c in closes[period:]: ema=c*k+ema*(1-k)
    return round(ema,2)

def calc_sma(closes,period):
    if len(closes)<period: return None
    return round(sum(closes[-period:])/period,2)

def calc_atr(candles,period=14):
    trs=[]
    for i in range(1,len(candles)):
        h=candles[i]["high"]; l=candles[i]["low"]; pc=candles[i-1]["close"]
        trs.append(max(h-l,abs(h-pc),abs(l-pc)))
    if len(trs)<period: return None
    return round(sum(trs[-period:])/period,2)

def calc_adx(candles,period=14):
    if len(candles)<period+2: return None
    plus_dm,minus_dm,trs=[],[],[]
    for i in range(1,len(candles)):
        h=candles[i]["high"]; l=candles[i]["low"]
        ph=candles[i-1]["high"]; pl=candles[i-1]["low"]; pc=candles[i-1]["close"]
        up=h-ph; down=pl-l
        plus_dm.append(up   if up>down   and up>0   else 0)
        minus_dm.append(down if down>up  and down>0 else 0)
        trs.append(max(h-l,abs(h-pc),abs(l-pc)))
    def smooth(arr,p):
        s=sum(arr[:p]); result=[s]
        for v in arr[p:]: s=s-s/p+v; result.append(s)
        return result
    s14=smooth(trs,period); pd14=smooth(plus_dm,period); md14=smooth(minus_dm,period)
    adx_v=[]
    for i in range(len(s14)):
        if s14[i]==0: continue
        pdi=100*pd14[i]/s14[i]; mdi=100*md14[i]/s14[i]
        dx=100*abs(pdi-mdi)/(pdi+mdi) if (pdi+mdi)>0 else 0
        adx_v.append(dx)
    if len(adx_v)<period: return None
    return round(sum(adx_v[-period:])/period,1)

def calc_bb(closes,period=20):
    if len(closes)<period: return None,None,None
    sma=sum(closes[-period:])/period
    std=statistics.stdev(closes[-period:])
    return round(sma+2*std,2),round(sma,2),round(sma-2*std,2)

def generate_signal_v5(candles_so_far):
    """
    v5: Pullback-first strategy
    - Solo entra TREND cuando precio muy cerca de EMA9 (no extendido)
    - Filtro de extension: no entrar si precio >2xATR de SMA20
    - Prioriza pullbacks a EMA21 en tendencia clara
    - Short signals activados (antes solo LONG)
    """
    if len(candles_so_far)<30: return None
    closes=[c["close"] for c in candles_so_far]
    highs =[c["high"]  for c in candles_so_far]
    lows  =[c["low"]   for c in candles_so_far]

    rsi  =calc_rsi(closes)
    ema9 =calc_ema(closes,9)
    ema21=calc_ema(closes,21)
    ema50=calc_ema(closes,50)
    sma20=calc_sma(closes,20)
    atr  =calc_atr(candles_so_far)
    adx  =calc_adx(candles_so_far)
    bb_up,bb_mid,bb_lo=calc_bb(closes)

    if any(v is None for v in [rsi,ema9,ema21,ema50,atr,sma20]): return None

    price=closes[-1]
    c=candles_so_far[-1]; cp=candles_so_far[-2] if len(candles_so_far)>=2 else c
    chg=round((c["close"]-c["open"])/c["open"]*100,2)

    # Trend structure
    trend_fast="UP"  if ema9>ema21  else "DOWN"
    trend_mid ="UP"  if ema21>ema50 else "DOWN"
    trend_slow="UP"  if price>ema50 else "DOWN"

    # Distance filters
    dist_from_ema9  = abs(price-ema9)/atr   # in ATR units
    dist_from_sma20 = (price-sma20)/atr     # positive = above, negative = below
    trending = adx is None or adx>20

    # Extension filter: price too far from mean?
    extended_up   = dist_from_sma20 >  2.0   # price >2 ATR above SMA20
    extended_down = dist_from_sma20 < -2.0   # price >2 ATR below SMA20

    signal=None; reason=""; confidence=0; sig_type=""

    # ── SIGNAL A: Deep Pullback LONG (best signal) ──────────────
    # Price pulls back to EMA21 in uptrend, RSI reset to neutral
    if (trend_fast=="UP" and trend_mid=="UP" and trend_slow=="UP"
        and price<=ema21*1.005 and price>=ema21*0.995  # within 0.5% of EMA21
        and 35<=rsi<=52                                  # RSI reset
        and trending and not extended_up
        and chg>-2.0):                                   # not a huge red candle
        signal="LONG"; sig_type="PULLBACK_EMA21"; confidence=78
        if adx and adx>25: confidence+=4
        if rsi<48: confidence+=3
        reason="Pullback to EMA21 in uptrend | RSI="+str(rsi)+" | ADX="+str(adx)

    # ── SIGNAL B: Pullback to EMA9 LONG (trend continuation) ────
    # Shallow pullback to fast EMA in strong trend
    elif (trend_fast=="UP" and trend_mid=="UP" and trend_slow=="UP"
          and price<=ema9*1.003 and price>=ema9*0.997   # within 0.3% of EMA9
          and 40<=rsi<=55                                # mild RSI reset
          and trending and not extended_up
          and adx and adx>25):                           # need strong trend
        signal="LONG"; sig_type="PULLBACK_EMA9"; confidence=74
        if adx>30: confidence+=4
        reason="Pullback to EMA9 in strong trend | RSI="+str(rsi)+" | ADX="+str(adx)

    # ── SIGNAL C: Deep Pullback SHORT ───────────────────────────
    elif (trend_fast=="DOWN" and trend_mid=="DOWN" and trend_slow=="DOWN"
          and price>=ema21*0.995 and price<=ema21*1.005
          and 48<=rsi<=65
          and trending and not extended_down
          and chg<2.0):
        signal="SHORT"; sig_type="PULLBACK_EMA21"; confidence=78
        if adx and adx>25: confidence+=4
        if rsi>52: confidence+=3
        reason="Pullback to EMA21 in downtrend | RSI="+str(rsi)+" | ADX="+str(adx)

    # ── SIGNAL D: Pullback to EMA9 SHORT ────────────────────────
    elif (trend_fast=="DOWN" and trend_mid=="DOWN" and trend_slow=="DOWN"
          and price>=ema9*0.997 and price<=ema9*1.003
          and 45<=rsi<=60
          and trending and not extended_down
          and adx and adx>25):
        signal="SHORT"; sig_type="PULLBACK_EMA9"; confidence=74
        if adx>30: confidence+=4
        reason="Pullback to EMA9 in strong downtrend | RSI="+str(rsi)+" | ADX="+str(adx)

    # ── SIGNAL E: BB Oversold in uptrend ────────────────────────
    elif (bb_lo and price<bb_lo and rsi<32
          and trend_slow=="UP" and not extended_down
          and chg>-3.0):
        signal="LONG"; sig_type="BB_REVERSAL"; confidence=72
        reason="BB lower breach | RSI="+str(rsi)+" oversold | uptrend intact"

    # ── SIGNAL F: BB Overbought in downtrend ────────────────────
    elif (bb_up and price>bb_up and rsi>68
          and trend_slow=="DOWN" and not extended_up
          and chg<3.0):
        signal="SHORT"; sig_type="BB_REVERSAL"; confidence=72
        reason="BB upper breach | RSI="+str(rsi)+" overbought | downtrend intact"

    # ── SIGNAL G: Trend LONG (only if not extended) ─────────────
    elif (trend_fast=="UP" and trend_mid=="UP" and trend_slow=="UP"
          and 45<=rsi<=62 and trending
          and not extended_up                            # KEY: not overextended
          and dist_from_ema9<0.8                        # close to EMA9
          and chg>-1.0):
        signal="LONG"; sig_type="TREND"; confidence=65
        if adx and adx>28: confidence+=4
        reason="Trend LONG near EMA9 | not extended | RSI="+str(rsi)

    # ── SIGNAL H: Trend SHORT (only if not extended) ────────────
    elif (trend_fast=="DOWN" and trend_mid=="DOWN" and trend_slow=="DOWN"
          and 38<=rsi<=55 and trending
          and not extended_down
          and dist_from_ema9<0.8
          and chg<1.0):
        signal="SHORT"; sig_type="TREND"; confidence=65
        if adx and adx>28: confidence+=4
        reason="Trend SHORT near EMA9 | not extended | RSI="+str(rsi)

    if signal is None: return None

    sl_dist=round(atr*1.5,2); tp_dist=round(atr*3.0,2)
    rr=round(tp_dist/sl_dist,1)
    if rr<2.0: return None

    return {
        "signal":signal,"confidence":confidence,"reason":reason,"sig_type":sig_type,
        "price":price,"rsi":rsi,"ema9":ema9,"ema21":ema21,"ema50":ema50,
        "sma20":sma20,"atr":atr,"adx":adx,"sl_dist":sl_dist,"tp_dist":tp_dist,"rr":rr,
        "dist_ema9":round(dist_from_ema9,2),"dist_sma20":round(dist_from_sma20,2),
        "extended":extended_up or extended_down,
    }

def simulate(candles,capital=25000.0,risk_pct=0.02,max_pos=3):
    trades=[]; equity=capital; peak=capital; max_dd=0.0
    equity_curve=[{"date":candles[0]["date"],"equity":capital}]
    open_pos=[]; daily_pnl={}

    for i in range(30,len(candles)):
        today=candles[i]; history=candles[:i]
        date=today["date"]; h=today["high"]; l=today["low"]

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
                daily_pnl[date]=daily_pnl.get(date,0)+pnl
                days=(datetime.strptime(date,"%Y-%m-%d")-datetime.strptime(pos["open_date"],"%Y-%m-%d")).days
                trades.append({
                    "open_date":pos["open_date"],"close_date":date,"days_held":days,
                    "signal":pos["signal"],"sig_type":pos.get("sig_type",""),
                    "entry":pos["entry"],"exit":exit_price,
                    "sl":pos["sl_price"],"tp":pos["tp_price"],"rr":pos["rr"],
                    "lots":pos["lots"],"risk_usd":pos["risk_usd"],
                    "pnl":round(pnl,2),"result":result,
                    "rsi":pos["rsi"],"adx":pos.get("adx"),"atr":pos["atr"],
                    "dist_ema9":pos.get("dist_ema9"),"dist_sma20":pos.get("dist_sma20"),
                    "equity_after":round(equity,2),"reason":pos["reason"],
                    "confidence":pos.get("confidence",0),
                })
            else: still_open.append(pos)
        open_pos=still_open
        equity_curve.append({"date":date,"equity":round(equity,2)})

        if len(open_pos)>=max_pos: continue
        dpnl=daily_pnl.get(date,0)
        if dpnl<=-(capital*0.05): continue
        if (capital-equity)>=capital*0.10: continue

        sig=generate_signal_v5(history)
        if sig is None: continue

        risk_usd=round(equity*risk_pct,2)
        lots=max(0.01,min(round(risk_usd/(sig["sl_dist"]*100),2),5.0))
        sl_p=(round(sig["price"]-sig["sl_dist"],2) if sig["signal"]=="LONG"
              else round(sig["price"]+sig["sl_dist"],2))
        tp_p=(round(sig["price"]+sig["tp_dist"],2) if sig["signal"]=="LONG"
              else round(sig["price"]-sig["tp_dist"],2))

        open_pos.append({
            "signal":sig["signal"],"sig_type":sig.get("sig_type",""),
            "entry":sig["price"],"sl_price":sl_p,"tp_price":tp_p,
            "sl_dist":sig["sl_dist"],"tp_dist":sig["tp_dist"],
            "rr":sig["rr"],"lots":lots,"risk_usd":risk_usd,
            "open_date":date,"rsi":sig["rsi"],"adx":sig.get("adx"),
            "atr":sig["atr"],"reason":sig["reason"],"confidence":sig.get("confidence",0),
            "dist_ema9":sig.get("dist_ema9"),"dist_sma20":sig.get("dist_sma20"),
        })

    return trades,equity_curve,max_dd

# ── MAIN ──────────────────────────────────────────────────────
print()
print("="*68)
print("  AURUM BACKTEST v5 -- Pullback-First Strategy | 500 dias")
print("="*68)

mt5.initialize()
rates=mt5.copy_rates_from_pos("XAUUSD",mt5.TIMEFRAME_D1,0,500)
mt5.shutdown()

candles=[{
    "date":datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d"),
    "open":float(r["open"]),"high":float(r["high"]),
    "low":float(r["low"]),"close":float(r["close"]),
    "vol":int(r["tick_volume"])
} for r in rates]

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

sig_types={}
for t in trades:
    st=t.get("sig_type","OTHER")
    if st not in sig_types: sig_types[st]={"trades":0,"wins":0,"pnl":0}
    sig_types[st]["trades"]+=1
    if t["result"]=="WIN": sig_types[st]["wins"]+=1
    sig_types[st]["pnl"]+=t["pnl"]

monthly={}
for t in trades:
    m=t["close_date"][:7]
    monthly[m]=monthly.get(m,0)+t["pnl"]

print("="*68)
print("  RESULTADOS")
print("="*68)
print(f"Capital inicial:    ${CAPITAL:,.2f}")
print(f"Capital final:      ${final_eq:,.2f}")
print(f"Total P&L:          {'+'if total_pnl>=0 else ''}${total_pnl:,.2f}")
print(f"Return total:       {total_pnl/CAPITAL*100:.2f}%")
print(f"Return anualizado:  {total_pnl/CAPITAL*100*(365/500)*2:.2f}% (est)")
print()
print(f"Trades totales:     {len(trades)}")
print(f"Wins:               {len(wins)} ({win_rate:.1f}%)")
print(f"Losses:             {len(losses)} ({100-win_rate:.1f}%)")
print(f"Avg win:            +${avg_win:,.2f}")
print(f"Avg loss:           -${avg_loss:,.2f}")
print(f"Win/Loss ratio:     {avg_win/avg_loss:.2f}x" if avg_loss>0 else "N/A")
print(f"Profit factor:      {pf}")
print(f"Sharpe ratio:       {sharpe}")
print(f"Max drawdown:       -${max_dd:,.2f} ({max_dd/CAPITAL*100:.1f}%)")
if best:  print(f"Best trade:         +${best['pnl']:,.2f} ({best['open_date']} {best['signal']})")
if worst: print(f"Worst trade:        ${worst['pnl']:,.2f} ({worst['open_date']} {worst['signal']})")
print()
print("─"*45)
print("  POR TIPO DE SEÑAL")
print("─"*45)
for st,v in sorted(sig_types.items()):
    wr=v["wins"]/v["trades"]*100 if v["trades"]>0 else 0
    print(f"  {st:<18} trades:{v['trades']:>3}  wr:{wr:.0f}%  pnl:{'+'if v['pnl']>=0 else ''}${v['pnl']:,.2f}")
print()
print("─"*45)
print("  P&L MENSUAL")
print("─"*45)
for m,pnl in sorted(monthly.items()):
    bar="█"*int(abs(pnl)/80)
    print(f"  {m}  {'+'if pnl>=0 else '-'}${abs(pnl):>8,.2f}  {'▲'if pnl>=0 else '▼'} {bar[:30]}")
print()
print("="*68)
print("  TRADE LOG")
print("="*68)
print(f"{'Open':<12} {'Close':<12} {'Dir':<6} {'Type':<18} {'Entry':>8} {'Exit':>8} {'RR':>4} {'RSI':>5} {'ADX':>5} {'D':>4} {'P&L':>9}  Res")
print("-"*115)
for t in trades:
    ps=("+" if t["pnl"]>=0 else "")+f"${abs(t['pnl']):,.2f}"
    adxs=str(t["adx"]) if t.get("adx") else "N/A"
    print(f"{t['open_date']:<12} {t['close_date']:<12} {t['signal']:<6} {t.get('sig_type',''):<18} {t['entry']:>8.2f} {t['exit']:>8.2f} {t['rr']:>4} {t['rsi']:>5} {adxs:>5} {t['days_held']:>4}  {ps:>9}  {t['result']}")

if trades:
    with open("backtest/trades_v5.csv","w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=trades[0].keys())
        w.writeheader(); w.writerows(trades)

with open("backtest/summary_v5.json","w",encoding="utf-8") as f:
    json.dump({
        "period":candles[0]["date"]+" to "+candles[-1]["date"],
        "candles":len(candles),"capital":CAPITAL,
        "final_equity":round(final_eq,2),"total_pnl":round(total_pnl,2),
        "return_pct":round(total_pnl/CAPITAL*100,2),
        "trades":len(trades),"wins":len(wins),"losses":len(losses),
        "win_rate":round(win_rate,1),"avg_win":round(avg_win,2),
        "avg_loss":round(avg_loss,2),"profit_factor":pf,
        "sharpe":sharpe,"max_drawdown":round(max_dd,2),
        "by_signal_type":{k:{"trades":v["trades"],"wins":v["wins"],"pnl":round(v["pnl"],2)} for k,v in sig_types.items()},
        "monthly_pnl":{k:round(v,2) for k,v in monthly.items()},
    },f,indent=2)

print()
print("CSV:    backtest/trades_v5.csv")
print("JSON:   backtest/summary_v5.json")
print()
print("AURUM BACKTEST v5 COMPLETE")
