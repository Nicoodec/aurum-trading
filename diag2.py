import MetaTrader5 as mt5
from datetime import datetime
from aurum_ftmo import sim, met, signal

mt5.initialize()
rates = mt5.copy_rates_from_pos("XAUUSD", mt5.TIMEFRAME_H1, 0, 99999)
mt5.shutdown()
cn = [{"t":datetime.fromtimestamp(r["time"]).strftime("%Y-%m-%d %H:%M"),
       "o":float(r["open"]),"h":float(r["high"]),"l":float(r["low"]),
       "c":float(r["close"])} for r in rates]
cn = [c for c in cn if c["t"] >= "2018-01-01"]

bp = {"te":150,"ee":21,"sm":1.2,"tm":2.5,"lb":12,"md":2.0,
      "ros":35,"rom":72,"s1s":7,"s1e":10,"s2s":12,"s2e":16,"ml":2}

print("Testing year by year with best params:")
print()
for year in range(2018, 2027):
    year_cn = [c for c in cn if c["t"][:4] == str(year)]
    if len(year_cn) < 300: continue
    t2,ec2,dd2,days2 = sim(year_cn, bp, cap=25000.0)
    m2 = met(t2, ec2, 25000.0, dd2, days2)
    status = "PASS" if m2["pnl"] > 0 else "FAIL"
    print(str(year)+" n="+str(m2["n"])+" wr="+str(m2["wr"])+"% pf="+str(m2["pf"])+" pnl=$"+str(m2["pnl"])+" dd="+str(m2["ddp"])+"% "+status)

print()
print("Testing md=2.5 year by year:")
bp25 = {**bp, "md":2.5}
for year in range(2018, 2027):
    year_cn = [c for c in cn if c["t"][:4] == str(year)]
    if len(year_cn) < 300: continue
    t2,ec2,dd2,days2 = sim(year_cn, bp25, cap=25000.0)
    m2 = met(t2, ec2, 25000.0, dd2, days2)
    status = "PASS" if m2["pnl"] > 0 else "FAIL"
    print(str(year)+" n="+str(m2["n"])+" wr="+str(m2["wr"])+"% pf="+str(m2["pf"])+" pnl=$"+str(m2["pnl"])+" dd="+str(m2["ddp"])+"% "+status)
