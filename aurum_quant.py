import MetaTrader5 as mt5, statistics, random, itertools, json, os, time
from datetime import datetime as dt

FTMO={"balance":25000.0,"daily_loss_pct":0.05,"total_loss_pct":0.10,
      "max_risk_per_trade":0.005,"max_positions":1,"leverage":30}
EX={"spread":0.30,"slip":0.20,"comm":3.5,"lot":100}

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
    return round(sum(t[-p:])/p,2) if len(t)>=p else None

def adx(cs,p=14):
    if len(cs)<p+2: return None
    pd2,md2,tr=[],[],[]
    for i in range(1,len(cs)):
        h=cs[i]["h"]; l=cs[i]["l"]; ph=cs[i-1]["h"]; pl=cs[i-1]["l"]; pc=cs[i-1]["c"]
        u=h-ph; d=pl-l
        pd2.append(u if u>d and u>0 else 0)
        md2.append(d if d>u and d>0 else 0)
        tr.append(max(h-l,abs(h-pc),abs(l-pc)))
    def sm(a):
        s=sum(a[:p]); o=[s]
        for v in a[p:]: s=s-s/p+v; o.append(s)
        return o
    s=sm(tr); p2=sm(pd2); m2=sm(md2); dx=[]
    for i in range(len(s)):
        if s[i]==0: continue
        pi=100*p2[i]/s[i]; mi=100*m2[i]/s[i]; den=pi+mi
        dx.append(100*abs(pi-mi)/den if den>0 else 0)
    return round(sum(dx[-p:])/p,1) if len(dx)>=p else None

def d1trend(h1_all, idx):
    start=max(0, idx-60*24)
    hist=h1_all[start:idx]
    if len(hist)<48: return "S"
    closes=[c["c"] for c in hist]
    d1c=closes[::24][-60:]
    if len(d1c)<10: return "S"
    e9=ema(d1c, min(9, len(d1c)-1))
    e21=ema(d1c, min(21,len(d1c)-1))
    if not e9 or not e21: return "S"
    p=d1c[-1]
    if e9>e21 and p>e21: return "U"
    if e9<e21 and p<e21: return "D"
    return "S"

def signal(h1_all, idx, p):
    win=150
    hist=h1_all[max(0,idx-win):idx]
    if len(hist)<max(p["es"],28)+5: return None
    hr=int(h1_all[idx]["t"][11:13]) if len(h1_all[idx]["t"])>11 else 12
    if not (p["sh"]<=hr<p["eh"]): return None
    closes=[c["c"] for c in hist]
    e9=ema(closes,p["ef"]); e21=ema(closes,p["em"]); e50=ema(closes,p["es"])
    r=rsi(closes,14); at=atr(hist,p["ap"]); ad=adx(hist,14)
    if any(v is None for v in [e9,e21,e50,r,at]): return None
    pr=closes[-1]; cv=hist[-1]
    chg=(cv["c"]-cv["o"])/cv["o"]*100 if cv["o"]>0 else 0
    fast=e9>e21; mid=e21>e50; slow=pr>e50
    d9=abs(pr-e9)/at; d21=abs(pr-e21)/at; ext=(pr-e21)/at
    tr2=ad is None or ad>p["at"]; st2=ad is not None and ad>p["at"]+5
    d1=d1trend(h1_all,idx)
    okl=d1 in("U","S"); oks=d1 in("D","S")
    cl=d1=="U"; cs=d1=="D"
    if p["tm"]/p["sm"]<2.0: return None
    sg=tp2=rs=None
    if (p["pb21"] and okl and fast and mid
        and d21<=p["p21"] and p["os"]+5<=r<=p["bm"]
        and tr2 and ext<=p["el"] and chg>-2):
        sg="L"; tp2="PB21"; rs=70+(6 if cl else 0)+(4 if st2 else 0)+(3 if r<50 else 0)
    elif (p["pb21"] and p["us"] and oks and not fast and not mid
          and d21<=p["p21"] and p["bmin"]<=r<=p["ob"]-5
          and tr2 and -ext<=p["el"] and chg<2):
        sg="S"; tp2="PB21"; rs=70+(6 if cs else 0)+(4 if st2 else 0)+(3 if r>50 else 0)
    elif (p["pb9"] and cl and fast and mid and slow
          and d9<=p["p9"] and p["os"]+8<=r<=p["bm"]-5
          and st2 and ext<=p["el"] and chg>-1.5):
        sg="L"; tp2="PB9"; rs=75+(6 if cl else 0)
    elif (p["pb9"] and p["us"] and cs and not fast and not mid and not slow
          and d9<=p["p9"] and p["bmin"]+5<=r<=p["ob"]-8
          and st2 and -ext<=p["el"] and chg<1.5):
        sg="S"; tp2="PB9"; rs=75+(6 if cs else 0)
    if sg is None: return None
    sl=round(at*p["sm"],2); tp3=round(at*p["tm"],2); rr=round(tp3/sl,2)
    if rr<2.0: return None
    return {"sig":sg,"type":tp2,"conf":rs,"pr":pr,"rsi":r,"adx":ad,"atr":at,
            "sl":sl,"tp":tp3,"rr":rr,"d1":d1,"d21":round(d21,3),"d9":round(d9,3)}

def sim(h1_all, p, cap=25000.0, seed=42):
    rng=random.Random(seed); eq=cap; pk=cap; mdd=0.0
    ec=[{"t":h1_all[0]["t"],"eq":eq}]
    ops=[]; trd=[]; dy={}
    mn=max(p["es"],p["ap"],14)+150
    for i in range(mn,len(h1_all)):
        b=h1_all[i]; date=b["t"][:10]; h=b["h"]; l=b["l"]
        still=[]
        for pos in ops:
            hs=ht=False
            if pos["d"]=="L":
                if l<=pos["sl"]: hs=True
                elif h>=pos["tp"]: ht=True
            else:
                if h>=pos["sl"]: hs=True
                elif l<=pos["tp"]: ht=True
            if hs or ht:
                ep=pos["sl"] if hs else pos["tp"]
                raw=pos["lo"]*EX["lot"]*(ep-pos["en"] if pos["d"]=="L" else pos["en"]-ep)
                pnl=round(raw-pos["lo"]*EX["comm"],2)
                eq+=pnl; pk=max(pk,eq); mdd=max(mdd,pk-eq)
                dy[date]=dy.get(date,0)+pnl
                trd.append({"open":pos["ot"],"close":b["t"],"dir":pos["d"],
                             "type":pos["tp2"],"entry":pos["en"],"exit":ep,
                             "sl":pos["sl"],"tp":pos["tp"],"lots":pos["lo"],
                             "rr":pos["rr"],"pnl":pnl,"result":"W" if pnl>0 else "L",
                             "rsi":pos.get("rsi"),"adx":pos.get("adx"),
                             "d1":pos.get("d1"),"eq":round(eq,2)})
            else: still.append(pos)
        ops=still; ec.append({"t":b["t"],"eq":round(eq,2)})
        if (cap-eq)>=cap*FTMO["total_loss_pct"]: break
        if dy.get(date,0)<=-(cap*FTMO["daily_loss_pct"]): continue
        if len(ops)>=FTMO["max_positions"]: continue
        dirs={x["d"] for x in ops}
        sg=signal(h1_all,i,p)
        if sg is None: continue
        if sg["sig"] in dirs: continue
        # Sizing conservador
        ru=round(eq*FTMO["max_risk_per_trade"],2)
        lo=ru/(sg["sl"]*EX["lot"])
        lo=round(max(0.01,min(lo,0.05)),2)  # MAX 0.05 lots
        mg=sg["pr"]*lo*EX["lot"]/FTMO["leverage"]
        if mg>eq*0.3: lo=round(lo*0.5,2)
        if lo<0.01: continue
        sl2=rng.uniform(0,EX["slip"])
        if sg["sig"]=="L":
            en=round(sg["pr"]+EX["spread"]/2+sl2,2)
            sl3=round(en-sg["sl"],2); tp4=round(en+sg["tp"],2)
        else:
            en=round(sg["pr"]-EX["spread"]/2-sl2,2)
            sl3=round(en+sg["sl"],2); tp4=round(en-sg["tp"],2)
        ops.append({"d":sg["sig"],"tp2":sg["type"],"en":en,"sl":sl3,"tp":tp4,
                    "lo":lo,"rr":sg["rr"],"ot":b["t"],"rsi":sg.get("rsi"),
                    "adx":sg.get("adx"),"d1":sg.get("d1")})
    return trd,ec,mdd

def met(t,ec,cap,mdd):
    if not t: return {"n":0,"wr":0,"pnl":0,"pf":0,"sh":0,"dd":0,"ddp":0,"aw":0,"al":0}
    w=[x for x in t if x["result"]=="W"]; l=[x for x in t if x["result"]=="L"]
    pnl=sum(x["pnl"] for x in t); gw=sum(x["pnl"] for x in w); gl=abs(sum(x["pnl"] for x in l))
    wr=len(w)/len(t)*100; pf=round(gw/gl,3) if gl>0 else 0
    aw=gw/len(w) if w else 0; al=gl/len(l) if l else 0
    rs=[(ec[i]["eq"]-ec[i-1]["eq"])/ec[i-1]["eq"] for i in range(1,len(ec))]
    mr=statistics.mean(rs) if rs else 0; sr=statistics.stdev(rs) if len(rs)>1 else 1
    sh=round(mr/sr*(252*24)**0.5,2) if sr>0 else 0
    return {"n":len(t),"wr":round(wr,1),"pnl":round(pnl,2),"pf":pf,"sh":sh,
            "dd":round(mdd,2),"ddp":round(mdd/cap*100,2),"aw":round(aw,2),"al":round(al,2)}

def sc(m):
    if m["n"]<30 or m["pf"]<1.0 or m["ddp"]>7: return -999
    return m["sh"]*2+(m["pf"]-1)*3+m["wr"]/100*1.5+min(m["n"],300)/300*0.5-m["ddp"]*0.5

if __name__=="__main__":
    mt5.initialize()
    rates=mt5.copy_rates_from_pos("XAUUSD",mt5.TIMEFRAME_H1,0,99999)
    mt5.shutdown()
    cn=[{"t":dt.fromtimestamp(r["time"]).strftime("%Y-%m-%d %H:%M"),
         "o":float(r["open"]),"h":float(r["high"]),"l":float(r["low"]),
         "c":float(r["close"])} for r in rates]
    cn=[c for c in cn if c["t"]>="2015-01-01"]
    print("Candles:",len(cn))

    # Quick test
    p0={"ef":9,"em":21,"es":50,"ap":14,"sm":1.5,"tm":3.0,"at":18,
        "p21":0.6,"p9":0.35,"el":2.5,"os":30,"ob":70,"bm":65,"bmin":35,
        "sh":7,"eh":20,"pb21":True,"pb9":True,"bb":False,"us":True}
    print("Quick test...")
    t0=time.time()
    trd,ec,mdd=sim(cn[:5000],p0)
    m=met(trd,ec,25000.0,mdd)
    print("n="+str(m["n"])+" wr="+str(m["wr"])+"% pf="+str(m["pf"])+" dd="+str(m["ddp"])+"%")
    print("Time: "+str(round(time.time()-t0,1))+"s per 5000 bars")
    if trd:
        print("Sample: "+trd[0]["open"]+" "+trd[0]["dir"]+" lots="+str(trd[0]["lots"])+" pnl=$"+str(trd[0]["pnl"]))

    # Grid search
    n=len(cn); tr=int(n*0.70)
    print("\nGrid search on train ("+str(tr)+" bars)...")
    GRID={"ef":[8,9,13],"em":[21,26],"es":[50,89],"ap":[14],
          "sm":[1.2,1.5,2.0],"tm":[2.4,3.0,4.0],"at":[18,22,28],
          "p21":[0.4,0.6,0.8],"p9":[0.25,0.4],"el":[2.0,3.0],
          "os":[28,32],"ob":[68,72],"bm":[60,65],"bmin":[35,40],
          "sh":[7],"eh":[20],"pb21":[True],"pb9":[True,False],
          "bb":[False],"us":[True]}
    keys=list(GRID.keys()); vals=list(GRID.values())
    all_c=list(itertools.product(*vals))
    rng2=random.Random(42)
    if len(all_c)>150: all_c=rng2.sample(all_c,150)
    print("Testing "+str(len(all_c))+" combos...")
    results=[]; t1=time.time()
    for i,combo in enumerate(all_c):
        p=dict(zip(keys,combo))
        if p["tm"]/p["sm"]<2.0: continue
        try:
            t2,ec2,dd2=sim(cn[:tr],p)
            m2=met(t2,ec2,25000.0,dd2)
            s2=sc(m2); results.append((s2,p,m2))
        except: pass
        if (i+1)%10==0:
            valid=sum(1 for r in results if r[0]>-900)
            best=max((r[0] for r in results),default=-999)
            elapsed=round(time.time()-t1,0)
            print(str(i+1)+"/"+str(len(all_c))+" valid="+str(valid)+" best="+str(round(best,2))+" "+str(elapsed)+"s",flush=True)
    results.sort(key=lambda x:-x[0])
    valid=sum(1 for r in results if r[0]>-900)
    print("\nDone. Valid="+str(valid))
    print("Top 5:")
    for r in results[:5]:
        print("  sc="+str(round(r[0],2))+" n="+str(r[2]["n"])+" pf="+str(r[2]["pf"])+" dd="+str(r[2]["ddp"])+"% wr="+str(r[2]["wr"])+"%")
    if valid>0:
        bp=results[0][1]; tm2=results[0][2]
        t3,ec3,dd3=sim(cn[tr:],bp)
        m3=met(t3,ec3,25000.0,dd3)
        deg=round(m3["pf"]/tm2["pf"],2) if tm2["pf"]>0 else 0
        print("\nTRAIN: n="+str(tm2["n"])+" wr="+str(tm2["wr"])+"% pf="+str(tm2["pf"])+" sh="+str(tm2["sh"])+" dd="+str(tm2["ddp"])+"%")
        print("TEST:  n="+str(m3["n"])+" wr="+str(m3["wr"])+"% pf="+str(m3["pf"])+" sh="+str(m3["sh"])+" dd="+str(m3["ddp"])+"%")
        print("PF deg: "+str(deg)+"x | "+("LOW" if deg>0.75 else "MEDIUM" if deg>0.5 else "HIGH")+" overfitting")
        print("\nBest params:"); [print("  "+k+"="+str(v)) for k,v in bp.items()]
        with open("backtest/quant_final.json","w") as f:
            json.dump({"params":bp,"train":tm2,"test":m3,"deg":deg},f,indent=2,default=str)
        print("Saved: backtest/quant_final.json")
    # Yearly on full dataset with best or default
    best_p=results[0][1] if valid>0 else p0
    print("\nYEARLY BREAKDOWN (full dataset):")
    t4,ec4,dd4=sim(cn,best_p)
    by_y={}
    for tx in t4:
        y=tx["open"][:4]
        if y not in by_y: by_y[y]={"n":0,"w":0,"pnl":0.0}
        by_y[y]["n"]+=1; by_y[y]["pnl"]+=tx["pnl"]
        if tx["result"]=="W": by_y[y]["w"]+=1
    for y in sorted(by_y.keys()):
        v=by_y[y]; wr2=round(v["w"]/v["n"]*100,1) if v["n"]>0 else 0
        sign="+" if v["pnl"]>=0 else ""
        print("  "+y+" n="+str(v["n"])+" wr="+str(wr2)+"% pnl="+sign+"$"+str(round(v["pnl"],0)))
