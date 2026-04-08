import requests, os, json
from datetime import datetime
from dotenv import load_dotenv
from config import STATE_DIR
load_dotenv()
KEY = os.getenv("ALPHAVANTAGE_KEY", "")

def fetch_ohlcv():
    if not KEY: return []
    # XAU/USD via FOREX endpoint
    for function in ["FX_DAILY", "CURRENCY_EXCHANGE_RATE"]:
        try:
            if function == "FX_DAILY":
                r = requests.get("https://www.alphavantage.co/query",
                    params={"function":"FX_DAILY","from_symbol":"XAU","to_symbol":"USD","outputsize":"compact","apikey":KEY},
                    timeout=15)
                data = r.json()
                ts = data.get("Time Series FX (Daily)", {})
                if ts:
                    prices = []
                    for d,v in sorted(ts.items()):
                        try:
                            prices.append({"date":d,"open":float(v["1. open"]),"high":float(v["2. high"]),"low":float(v["3. low"]),"close":float(v["4. close"])})
                        except: pass
                    if prices:
                        os.makedirs(STATE_DIR, exist_ok=True)
                        with open(os.path.join(STATE_DIR,"price_history.json"),"w",encoding="utf-8") as f:
                            json.dump({"prices":prices,"last_update":datetime.now().isoformat(),"source":"alphavantage"},f)
                        print("[av] Saved",len(prices),"candles via FX_DAILY")
                        return prices
                info = data.get("Information","") or data.get("Error Message","") or data.get("Note","")
                if info: print("[av]",info[:100])
        except Exception as e:
            print("[av] error:",e)
    return []
