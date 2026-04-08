import requests, re, time
from datetime import datetime

GOLD_KEYWORDS = [
    "gold","xau","fed","rate","inflation","dollar","treasury",
    "tariff","iran","war","geopolit","safe haven","powell",
    "cpi","nfp","payroll","gdp","recession","china","risk",
    "breaking","flash","alert"
]

def _try_nitter(username, max_items=15):
    instances = [
        "https://nitter.poast.org",
        "https://nitter.net",
        "https://nitter.it",
        "https://nitter.privacydev.net",
    ]
    for inst in instances:
        try:
            r = requests.get(inst+"/"+username, headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
            if r.status_code == 200 and "tweet" in r.text.lower():
                tweets = re.findall(r'<div class="tweet-content[^"]*"[^>]*>(.*?)</div>', r.text, re.DOTALL)
                items = []
                for t in tweets[:20]:
                    text = re.sub(r'<[^>]+>', '', t).strip()
                    text = re.sub(r'\s+', ' ', text).strip()
                    if len(text) > 20:
                        tl = text.lower()
                        items.append({"source":"DeltaOne","title":text[:150],"body":"","relevant":any(k in tl for k in GOLD_KEYWORDS)})
                if items:
                    print(f"[deltaone] {len(items)} tweets from {inst}")
                    return items
        except Exception as e:
            print(f"[deltaone] {inst}: {type(e).__name__}")
    return []

def _try_rss_bridge(username):
    bridges = [
        f"https://rss-bridge.org/bridge01/?action=display&bridge=Twitter&context=By+username&u={username}&format=Atom",
    ]
    for bridge in bridges:
        try:
            r = requests.get(bridge, headers={"User-Agent":"Mozilla/5.0"}, timeout=8)
            if r.status_code == 200:
                titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>', r.text, re.DOTALL)
                items = []
                for t in titles[1:15]:
                    text = (t[0] or t[1]).strip()
                    text = re.sub(r'<[^>]+>', '', text).strip()
                    if len(text) > 20:
                        tl = text.lower()
                        items.append({"source":"DeltaOne","title":text[:150],"body":"","relevant":any(k in tl for k in GOLD_KEYWORDS)})
                if items:
                    print(f"[deltaone] {len(items)} items from RSS bridge")
                    return items
        except: pass
    return []

def fetch_deltaone(max_items=15):
    items = _try_nitter("DeItaone", max_items)
    if not items:
        items = _try_rss_bridge("DeItaone")
    if not items:
        print("[deltaone] all sources unavailable")
        return []
    rel = [i for i in items if i["relevant"]]
    return (rel + [i for i in items if not i["relevant"]])[:max_items]

def get_breaking_from_deltaone():
    items = fetch_deltaone()
    breaking_kw = ["breaking","flash","alert","urgent","just in"]
    breaking = [i for i in items if any(k in i["title"].lower() for k in breaking_kw)]
    return breaking or items[:5]
