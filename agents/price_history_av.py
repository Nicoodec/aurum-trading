import requests, os, json
from datetime import datetime
from dotenv import load_dotenv
from config import STATE_DIR
load_dotenv()
KEY = os.getenv("ALPHAVANTAGE_KEY", "")

def fetch_ohlcv():
    if not KEY: return []
    try:
        r = requests.get("https://www.alphavantage.co/query",
            params={"function":"FX_DAILY","from_symbol":"XAU","to_symbol":"USD","outputsize":"compact","apikey":KEY},
            timeout=15)
        ts = r.json().get("Time Series FX (Daily)", {})
        if not ts:
            print("[av] no data:", list(r.json().keys())[:3])
            return []
        prices = []
        for d,v in sorted(ts.items()):
            prices.append({"date":d,"open":float(v["1. open"]),"high":float(v["2. high"]),"low":float(v["3. low"]),"close":float(v["4. close"])})
        os.makedirs(STATE_DIR, exist_ok=True)
        path = os.path.join(STATE_DIR, "price_history.json")
        with open(path,"w",encoding="utf-8") as f:
            json.dump({"prices":prices,"last_update":datetime.now().isoformat(),"source":"alphavantage"},f)
        print("[av] Saved", len(prices), "candles")
        return prices
    except Exception as e:
        print("[av] error:",e)
        return []
