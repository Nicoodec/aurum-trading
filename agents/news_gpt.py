import os, json, requests, re
from dotenv import load_dotenv
load_dotenv()
KEY = os.getenv("OPENAI_API_KEY", "")

def analyze_news_gpt(news_items):
    if not KEY or not news_items: return None
    try:
        hl = chr(10).join(["- ["+i["source"]+"] "+i["title"] for i in news_items[:20]])
        prompt = "You are a gold XAU/USD analyst. Analyze these headlines.\nRespond ONLY in JSON: {" + chr(34) + "sentiment" + chr(34) + ":" + chr(34) + "BULLISH_GOLD" + chr(34) + "," + chr(34) + "confidence" + chr(34) + ":75," + chr(34) + "key_events" + chr(34) + ":[]," + chr(34) + "scheduled_events" + chr(34) + ":[]," + chr(34) + "bull_factors" + chr(34) + ":[]," + chr(34) + "bear_factors" + chr(34) + ":[]," + chr(34) + "summary" + chr(34) + ":" + chr(34) + chr(34) + "}\n\nHEADLINES:\n" + hl
        r = requests.post("https://api.openai.com/v1/chat/completions",
            headers={"Authorization":"Bearer "+KEY,"Content-Type":"application/json"},
            json={"model":"gpt-4o-mini","messages":[{"role":"user","content":prompt}],"temperature":0.2},
            timeout=20)
        content = r.json()["choices"][0]["message"]["content"]
        m = re.search(r"{[\s\S]+?}", content)
        return json.loads(m.group()) if m else None
    except Exception as e:
        print("[gpt]",e)
        return None
