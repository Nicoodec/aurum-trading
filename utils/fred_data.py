import requests, os
from dotenv import load_dotenv
load_dotenv()
KEY = os.getenv("FRED_KEY", "")
BASE = "https://api.stlouisfed.org/fred/series/observations"

def _get(series):
    if not KEY: return None
    try:
        r = requests.get(BASE, params={"series_id":series,"api_key":KEY,"file_type":"json","limit":2,"sort_order":"desc"}, timeout=8)
        obs = r.json().get("observations", [])
        vals = [float(o["value"]) for o in obs if o["value"] != "."]
        return vals[0] if vals else None
    except Exception as e:
        print("[fred]", series, e)
        return None

def get_all():
    dxy = _get("DTWEXBGS")
    t10 = _get("DGS10")
    t2  = _get("DGS2")
    fed = _get("FEDFUNDS")
    parts = []
    if dxy: parts.append("DXY:"+str(round(dxy,2)))
    if t10: parts.append("10Y:"+str(t10)+"%")
    if t2:  parts.append("2Y:"+str(t2)+"%")
    if fed: parts.append("FedFunds:"+str(fed)+"%")
    bull = (dxy and dxy<100) or (t10 and t10<4.0)
    bear = (dxy and dxy>105) or (t10 and t10>4.5)
    bias = "BULLISH" if bull else ("BEARISH" if bear else "NEUTRAL")
    return {"dxy":dxy,"t10y":t10,"t2y":t2,"fedfunds":fed,"summary":" | ".join(parts),"macro_bias":bias}
