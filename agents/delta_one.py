import requests, re, json
from datetime import datetime

GOLD_KEYWORDS = [
    "gold","xau","fed","rate","inflation","dollar","treasury",
    "tariff","iran","war","geopolit","safe haven","powell",
    "cpi","nfp","payroll","gdp","recession","china","risk",
    "breaking","flash","alert","crude","oil"
]

def _fetch_via_rss():
    # Usar Nitter RSS feed alternativo
    urls = [
        "https://nitter.poast.org/DeItaone/rss",
        "https://nitter.privacydev.net/DeItaone/rss",
        "https://nitter.net/DeItaone/rss",
        "https://nitter.it/DeItaone/rss",
        "https://nitter.1d4.us/DeItaone/rss",
        "https://nitter.cz/DeItaone/rss",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers={"User-Agent":"Mozilla/5.0 AURUM/1.0"}, timeout=8)
            if r.status_code == 200 and "<item>" in r.text:
                titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", r.text, re.DOTALL)
                items = []
                for t in titles[1:20]:  # skip feed title
                    text = re.sub(r"<[^>]+>", "", t).strip()
                    text = re.sub(r"\s+", " ", text).strip()
                    if len(text) > 15 and "@" not in text[:10]:
                        tl = text.lower()
                        items.append({
                            "source":   "DeltaOne",
                            "title":    text[:160],
                            "body":     "",
                            "relevant": any(k in tl for k in GOLD_KEYWORDS)
                        })
                if items:
                    print(f"[deltaone] {len(items)} items from {url}")
                    return items
        except Exception as e:
            print(f"[deltaone] {url.split('/')[2]}: {type(e).__name__}")
    return []

def _fetch_via_twscraper():
    try:
        from twscraper import scrape_user
        tweets = scrape_user("DeItaone", limit=15)
        items = []
        for t in tweets:
            text = t.get("text","").strip()
            if len(text) > 15:
                tl = text.lower()
                items.append({
                    "source":   "DeltaOne",
                    "title":    text[:160],
                    "body":     "",
                    "relevant": any(k in tl for k in GOLD_KEYWORDS)
                })
        if items:
            print(f"[deltaone] {len(items)} tweets via twscraper")
            return items
    except Exception as e:
        print(f"[deltaone] twscraper: {e}")
    return []

def fetch_deltaone(max_items=15):
    items = _fetch_via_rss()
    if not items:
        items = _fetch_via_twscraper()
    if not items:
        print("[deltaone] all methods unavailable")
        return []
    relevant = [i for i in items if i["relevant"]]
    other    = [i for i in items if not i["relevant"]]
    result   = (relevant + other)[:max_items]
    return result

def get_breaking_from_deltaone():
    items = fetch_deltaone()
    breaking_kw = ["breaking","flash","alert","urgent","just in","rtrs","bbg"]
    breaking = [i for i in items if any(k in i["title"].lower() for k in breaking_kw)]
    return breaking or items[:5]
