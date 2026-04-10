import MetaTrader5 as mt5
from datetime import datetime
import statistics, random, itertools, json, os, time

FTMO = {"balance":25000.0,"daily_loss_pct":0.05,"total_loss_pct":0.10,
        "target_phase1":0.10,"max_positions":1,"leverage":30}
EXEC = {"spread":0.25,"slippage":0.15,"commission":3.50,"lot_size":100}

def ema(c,p):
    if len(c)<p: return None
    k=2/(p+1); v=sum(c[:p])/p
    for x in c[p:]: v=x*k+v*(1-k)
    return round(v,3)

def rsi(c,p=14):
    if len(c)<p+1: return None
    g,l=[],[]
    for i in range(1,len(c)):
        d=c[i]-c[i-1]; g.append(max(d,0)); l.append(max(-d,0))
    ag=sum(g[-p:])/p; al=sum(l[-p:])/p
    return 100.0 if al==0 else round(100-100/(1+ag/al),1)

def atr(cs,p=14):
    t=[]
    for i in range(1,len(cs)):
        h=cs[i]["h"]; l=cs[i]["l"]; pc=cs[i-1]["c"]
        t.append(max(h-l,abs(h-pc),abs(l-pc)))
    return round(sum(t[-p:])/p,3) if len(t)>=p else None

def in_session(hour, p):
    return (p["s1s"]<=hour<p["s1e"]) or (p["s2s"]<=hour<p["s2e"])

def signal(candles, p):
    """
    REAL pullback detection:
    1. Price must be at least N ATRs AWAY from EMA50 in last M bars
       (confirming there WAS a trend move away from EMA)
    2. Price pulls BACK to touch EMA50
    3. Candle CLOSES back in trend direction
    4. Previous candle was counter-trend (actual pullback candle)
    """
    mn = max(p["te"],p["ee"],14) + p["lb"] + 5
    if len(candles) < mn: return None

    closes = [c["c"] for c in candles]
    t_ema  = ema(closes, p["te"])
    e_ema  = ema(closes, p["ee"])
    r      = rsi(closes, 14)
    at     = atr(candles, 14)
    if any(v is None for v in [t_ema,e_ema,r,at]): return None

    cur  = candles[-1]
    prev = candles[-2]
    price = closes[-1]

    # Trend
    uptrend   = price > t_ema
    downtrend = price < t_ema

    # --- KEY FILTER: Was price significantly AWAY from EMA50 recently? ---
    # Look back p["lb"] bars and check if price was > p["md"] ATRs from EMA
    lookback_closes = closes[-(p["lb"]+1):-1]
    lookback_emas   = []
    for j in range(len(lookback_closes)):
        sub = closes[-(p["lb"]+1+5):-(p["lb"])+j+1] if j>0 else closes[-(p["lb"]+6):-p["lb"]]
        le  = ema(closes[:-(p["lb"])+j] if j < p["lb"] else closes, p["ee"])
        if le: lookback_emas.append(le)

    # Simpler: just check if max distance from EMA50 in last N bars was > threshold
    recent = candles[-(p["lb"]+1):-1]
    if not recent: return None
    max_dist_up   = max((c["h"] - e_ema) / at for c in recent if at > 0)
    max_dist_down = max((e_ema - c["l"]) / at for c in recent if at > 0)

    # Was there a meaningful move AWAY from EMA before this pullback?
    had_move_up   = max_dist_up   >= p["md"]  # price was above EMA by md ATRs
    had_move_down = max_dist_down >= p["md"]  # price was below EMA by md ATRs

    sig = stype = reason = None
    conf = 0

    # LONG: uptrend, had move above EMA50, now pulled back to touch it
    if (uptrend and had_move_up
        and cur["l"] <= e_ema * 1.001   # touched EMA
        and cur["c"] > e_ema             # closed back above
        and prev["c"] < prev["o"]        # previous candle bearish (pullback)
        and p["ros"]+5 <= r <= p["rom"]  # RSI in range
        and cur["c"] > cur["o"]):        # current candle bullish (reversal)
        sig="LONG"; conf=75
        if r < 55: conf+=5
        if price > t_ema * 1.01: conf+=4
        reason="PB_LONG ema"+str(p["ee"])+" d="+str(round(max_dist_up,2))+"ATR rsi="+str(r)

    # SHORT: downtrend, had move below EMA50, now rallied back to touch it
    elif (downtrend and had_move_down
          and cur["h"] >= e_ema * 0.999  # touched EMA
          and cur["c"] < e_ema            # closed back below
          and prev["c"] > prev["o"]       # previous candle bullish (rally)
          and p["ros"] <= r <= p["rom"]-5 # RSI in range
          and cur["c"] < cur["o"]):       # current candle bearish (reversal)
        sig="SHORT"; conf=75
        if r > 45: conf+=5
        if price < t_ema * 0.99: conf+=4
        reason="PB_SHORT ema"+str(p["ee"])+" d="+str(round(max_dist_down,2))+"ATR rsi="+str(r)

    if sig is None: return None

    sl_d = round(at*p["sm"],2); tp_d = round(at*p["tm"],2)
    rr   = round(tp_d/sl_d,2)
    if rr < 2.0: return None

    return {"sig":sig,"conf":conf,"reason":reason,"price":price,
            "rsi":r,"atr":at,"t_ema":t_ema,"e_ema":e_ema,
            "sl_d":sl_d,"tp_d":tp_d,"rr":rr}

def sim(candles, p, cap=25000.0, seed=42):
    rng=random.Random(seed); eq=cap; pk=cap; mdd=0.0
    ec=[{"t":candles[0]["t"],"eq":eq}]
    pos=None; trades=[]; daily={}; tdays=set()
    mn=max(p["te"],p["ee"],14)+p["lb"]+5
    for i in range(mn,len(candles)):
        b=candles[i]; date=b["t"][:10]; h=b["h"]; l=b["l"]
        hour=int(b["t"][11:13]) if len(b["t"])>11 else 0
        if pos:
            hs=ht=False
            if pos["d"]=="LONG":
                if l<=pos["sl"]: hs=True
                elif h>=pos["tp"]: ht=True
            else:
                if h>=pos["sl"]: hs=True
                elif l<=pos["tp"]: ht=True
            if hs or ht:
                ep=pos["sl"] if hs else pos["tp"]
                raw=pos["lo"]*EXEC["lot_size"]*(ep-pos["en"] if pos["d"]=="LONG" else pos["en"]-ep)
                pnl=round(raw-pos["lo"]*EXEC["commission"],2)
                eq+=pnl; pk=max(pk,eq); mdd=max(mdd,pk-eq)
                daily[date]=daily.get(date,0)+pnl; tdays.add(date)
                trades.append({"open":pos["ot"],"close":b["t"],"dir":pos["d"],
                               "entry":pos["en"],"exit":ep,"sl":pos["sl"],"tp":pos["tp"],
                               "lots":pos["lo"],"rr":pos["rr"],"pnl":pnl,
                               "result":"W" if pnl>0 else "L","rsi":pos.get("rsi"),
                               "atr":pos.get("atr"),"conf":pos.get("conf"),"eq":round(eq,2)})
                pos=None
        ec.append({"t":b["t"],"eq":round(eq,2)})
        if (cap-eq)>=cap*FTMO["total_loss_pct"]: break
        if daily.get(date,0)<=-(cap*FTMO["daily_loss_pct"]): continue
        if eq>=cap+cap*FTMO["target_phase1"]: break
        if pos: continue
        # consecutive loss check
        today_l=sum(1 for t in trades if t["close"][:10]==date and t["result"]=="L")
        if today_l>=p["ml"]: continue
        if not in_session(hour,p): continue
        hist=candles[max(0,i-p["te"]-p["lb"]-10):i]
        sg=signal(hist,p)
        if sg is None: continue
        ru=round(eq*0.01,2); sl_d=sg["sl_d"]
        lo=ru/(sl_d*EXEC["lot_size"]); lo=round(max(0.01,min(lo,2.0)),2)
        mg=sg["price"]*lo*EXEC["lot_size"]/FTMO["leverage"]
        if mg>eq*0.5: lo=round(lo*0.5,2)
        if lo<0.01: continue
        sl2=rng.uniform(0,EXEC["slippage"])
        if sg["sig"]=="LONG":
            en=round(sg["price"]+EXEC["spread"]/2+sl2,2)
            sl3=round(en-sl_d,2); tp4=round(en+sg["tp_d"],2)
        else:
            en=round(sg["price"]-EXEC["spread"]/2-sl2,2)
            sl3=round(en+sl_d,2); tp4=round(en-sg["tp_d"],2)
        pos={"d":sg["sig"],"en":en,"sl":sl3,"tp":tp4,"lo":lo,"rr":sg["rr"],
             "ot":b["t"],"rsi":sg.get("rsi"),"atr":sg.get("atr"),"conf":sg.get("conf")}
        tdays.add(date)
    return trades,ec,mdd,len(tdays)

def met(t,ec,cap,mdd,days=0):
    if not t: return {"n":0,"wr":0,"pnl":0,"pf":0,"sh":0,"dd":0,"ddp":0,"aw":0,"al":0,"exp":0}
    w=[x for x in t if x["result"]=="W"]; l=[x for x in t if x["result"]=="L"]
    pnl=sum(x["pnl"] for x in t); gw=sum(x["pnl"] for x in w); gl=abs(sum(x["pnl"] for x in l))
    wr=len(w)/len(t)*100; pf=round(gw/gl,3) if gl>0 else 0
    aw=gw/len(w) if w else 0; al=gl/len(l) if l else 0
    exp=round((wr/100*aw)-((1-wr/100)*al),2)
    rs=[(ec[i]["eq"]-ec[i-1]["eq"])/ec[i-1]["eq"] for i in range(1,len(ec))]
    mr=statistics.mean(rs) if rs else 0; sr=statistics.stdev(rs) if len(rs)>1 else 1
    sh=round(mr/sr*(252*24)**0.5,2) if sr>0 else 0
    return {"n":len(t),"wr":round(wr,1),"pnl":round(pnl,2),"pf":pf,"sh":sh,
            "dd":round(mdd,2),"ddp":round(mdd/cap*100,2),"aw":round(aw,2),
            "al":round(al,2),"exp":exp}

def sc(m):
    if m["n"]<15 or m["pf"]<1.0 or m["ddp"]>8 or m["wr"]<38: return -999
    return m["sh"]*2+(m["pf"]-1)*4+m["wr"]/100*3+min(m["n"],100)/100-m["ddp"]*0.8

if __name__=="__main__":
    mt5.initialize()
    rates=mt5.copy_rates_from_pos("XAUUSD",mt5.TIMEFRAME_H1,0,99999)
    mt5.shutdown()
    cn=[{"t":datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d %H:%M"),
         "o":float(r["open"]),"h":float(r["high"]),"l":float(r["low"]),
         "c":float(r["close"])} for r in rates]
    cn=[c for c in cn if c["t"]>="2018-01-01"]
    print("Candles:",len(cn))

    # Quick test with different pullback distances
    print("\nTesting pullback distance filter:")
    for md in [0.5, 1.0, 1.5, 2.0, 2.5]:
        p={"te":200,"ee":50,"sm":1.2,"tm":2.4,"lb":10,"md":md,
           "ros":30,"rom":70,"s1s":7,"s1e":10,"s2s":12,"s2e":16,"ml":2}
        t2,ec2,dd2,days2=sim(cn[:5000],p)
        m2=met(t2,ec2,25000.0,dd2,days2)
        print(f"  md={md}: n={m2['n']} wr={m2['wr']}% pf={m2['pf']} dd={m2['ddp']}%")

    print("\nGrid search...")
    n=len(cn); tr=int(n*0.70)
    GRID={"te":[100,150,200],"ee":[21,34,50],
          "sm":[1.0,1.2,1.5],"tm":[2.0,2.5,3.0],
          "lb":[8,12,16],   # lookback bars for move detection
          "md":[1.0,1.5,2.0], # min ATR distance required
          "ros":[28,35],"rom":[65,72],
          "s1s":[7],"s1e":[10],"s2s":[12],"s2e":[16],"ml":[2,3]}
    keys=list(GRID.keys()); vals=list(GRID.values())
    all_c=list(itertools.product(*vals))
    rng2=random.Random(42)
    if len(all_c)>200: all_c=rng2.sample(all_c,200)
    print("Testing",len(all_c),"combos on train ("+str(tr)+" bars)...")
    results=[]; t1=time.time()
    for i,combo in enumerate(all_c):
        p=dict(zip(keys,combo))
        if p["tm"]/p["sm"]<2.0: continue
        try:
            t2,ec2,dd2,days2=sim(cn[:tr],p)
            m2=met(t2,ec2,25000.0,dd2,days2)
            s2=sc(m2); results.append((s2,p,m2))
        except: pass
        if (i+1)%25==0:
            valid=sum(1 for r in results if r[0]>-900)
            best=max((r[0] for r in results),default=-999)
            print(str(i+1)+"/"+str(len(all_c))+" valid="+str(valid)+" best="+str(round(best,2))+" "+str(round(time.time()-t1,0))+"s",flush=True)
    results.sort(key=lambda x:-x[0])
    valid=sum(1 for r in results if r[0]>-900)
    print("\nDone. Valid="+str(valid))
    print("Top 5:")
    for r in results[:5]:
        print("  sc="+str(round(r[0],2))+" n="+str(r[2]["n"])+" wr="+str(r[2]["wr"])+"% pf="+str(r[2]["pf"])+" dd="+str(r[2]["ddp"])+"% exp=$"+str(r[2]["exp"]))
    if valid>0:
        bp=results[0][1]; tm2=results[0][2]
        t3,ec3,dd3,days3=sim(cn[tr:],bp)
        m3=met(t3,ec3,25000.0,dd3,days3)
        deg=round(m3["pf"]/tm2["pf"],2) if tm2["pf"]>0 else 0
        print("\nTRAIN: n="+str(tm2["n"])+" wr="+str(tm2["wr"])+"% pf="+str(tm2["pf"])+" sh="+str(tm2["sh"])+" dd="+str(tm2["ddp"])+"%")
        print("TEST:  n="+str(m3["n"])+" wr="+str(m3["wr"])+"% pf="+str(m3["pf"])+" sh="+str(m3["sh"])+" dd="+str(m3["ddp"])+"%")
        print("PF deg: "+str(deg)+"x")
        print("\nBest params:"); [print("  "+k+"="+str(v)) for k,v in bp.items()]
        # Yearly
        t4,ec4,dd4,days4=sim(cn,bp)
        by_y={}
        for tx in t4:
            y=tx["open"][:4]
            if y not in by_y: by_y[y]={"n":0,"w":0,"pnl":0.0}
            by_y[y]["n"]+=1; by_y[y]["pnl"]+=tx["pnl"]
            if tx["result"]=="W": by_y[y]["w"]+=1
        print("\nYEARLY:")
        for y in sorted(by_y.keys()):
            v=by_y[y]; wr2=round(v["w"]/v["n"]*100,1) if v["n"]>0 else 0
            print("  "+y+" n="+str(v["n"])+" wr="+str(wr2)+"% pnl=$"+str(round(v["pnl"],0)))
        with open("backtest/ftmo_v2.json","w") as f:
            json.dump({"params":bp,"train":tm2,"test":m3,"deg":deg},f,indent=2,default=str)
        print("\nSaved: backtest/ftmo_v2.json")
