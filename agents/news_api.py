import requests, os
from dotenv import load_dotenv
load_dotenv()
KEY = os.getenv("NEWSAPI_KEY", "")
QUERIES = ["gold XAU price","Federal Reserve gold","Trump tariffs gold","geopolitical safe haven gold"]

def fetch_newsapi():
    if not KEY: return []
    items = []
    for q in QUERIES:
        try:
            r = requests.get("https://newsapi.org/v2/everything",
                params={"q":q,"language":"en","sortBy":"publishedAt","pageSize":5,"apiKey":KEY}, timeout=8)
            for a in r.json().get("articles",[]):
                t = (a.get("title") or "").strip()
                d = (a.get("description") or "")[:200]
                s = a.get("source",{}).get("name","NewsAPI")
                if len(t)>10: items.append({"source":s,"title":t,"body":d})
        except Exception as e:
            print("[newsapi]",e)
    seen=set(); out=[]
    for i in items:
        if i["title"] not in seen: seen.add(i["title"]); out.append(i)
    return out[:25]
