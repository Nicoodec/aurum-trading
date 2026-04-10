import MetaTrader5 as mt5
from datetime import datetime
import statistics

mt5.initialize()
rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, 99999)
mt5.shutdown()
cn = [{"t":datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d %H:%M"),
       "o":float(r["open"]),"h":float(r["high"]),"l":float(r["low"]),
       "c":float(r["close"])} for r in rates]
cn = [c for c in cn if c["t"] >= "2018-01-01"]

def ema(c,p):
    if len(c)<p: return None
    k=2/(p+1); v=sum(c[:p])/p
    for x in c[p:]: v=x*k+v*(1-k)
    return round(v,3)

def adx(cs,p=14):
    if len(cs)<p+2: return None
    pdm,mdm,tr=[],[],[]
    for i in range(1,len(cs)):
        h=cs[i]["h"]; l=cs[i]["l"]
        ph=cs[i-1]["h"]; pl=cs[i-1]["l"]; pc=cs[i-1]["c"]
        u=h-ph; d=pl-l
        pdm.append(u if u>d and u>0 else 0)
        mdm.append(d if d>u and d>0 else 0)
        tr.append(max(h-l,abs(h-pc),abs(l-pc)))
    def sm(a):
        s=sum(a[:p]); o=[s]
        for v in a[p:]: s=s-s/p+v; o.append(s)
        return o
    s=sm(tr); p2=sm(pdm); m2=sm(mdm); dx=[]
    for i in range(len(s)):
        if s[i]==0: continue
        pi=100*p2[i]/s[i]; mi=100*m2[i]/s[i]; den=pi+mi
        dx.append(100*abs(pi-mi)/den if den>0 else 0)
    return round(sum(dx[-p:])/p,1) if len(dx)>=p else None

def atr(cs,p=14):
    t=[]
    for i in range(1,len(cs)):
        h=cs[i]["h"]; l=cs[i]["l"]; pc=cs[i-1]["c"]
        t.append(max(h-l,abs(h-pc),abs(l-pc)))
    return round(sum(t[-p:])/p,3) if len(t)>=p else None

print("MARKET REGIME ANALYSIS BY YEAR")
print()
print(f"  {'Year':<5} {'ADX':>6} {'ATR':>6} {'Trend%':>8} {'Bias':>8} {'Change':>8}")
print("  "+"-"*48)

for year in range(2018,2027):
    yc=[c for c in cn if c["t"][:4]==str(year)]
    if len(yc)<300: continue
    adx_vals=[]; atr_vals=[]; tr=0; ch=0
    for i in range(220,len(yc),24):
        hist=yc[max(0,i-200):i]
        if len(hist)<50: continue
        ad=adx(hist,14); at=atr(hist,14)
        if ad:
            adx_vals.append(ad)
            if ad>25: tr+=1
            else: ch+=1
        if at: atr_vals.append(at)
    total=tr+ch
    adx_avg=round(statistics.mean(adx_vals),1) if adx_vals else 0
    atr_avg=round(statistics.mean(atr_vals),1) if atr_vals else 0
    tp=round(tr/total*100,0) if total>0 else 0
    closes=[c["c"] for c in yc]
    chg=round((closes[-1]-closes[0])/closes[0]*100,1)
    bias="BULL" if chg>2 else ("BEAR" if chg<-2 else "FLAT")
    print(f"  {year:<5} {adx_avg:>6} {atr_avg:>6} {tp:>7}% {bias:>8} {chg:>+7}%")

print()
print("Strategy works best: ADX>25, strong directional bias (BULL/BEAR)")
print("Strategy fails:      ADX<22, FLAT market or choppy regime")
