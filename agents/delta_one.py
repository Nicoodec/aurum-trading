import os, re, html

GOLD_KW = [
    "gold","xau","fed","rate","inflation","dollar","treasury",
    "tariff","iran","war","geopolit","safe haven","powell",
    "cpi","nfp","payroll","gdp","recession","china","risk",
    "breaking","flash","alert","crude","oil","brent","hormuz",
    "sanctions","nuclear","ceasefire","vance","trump","ukraine"
]

BREAKING_KW = ["breaking","flash","alert","urgent","just in","rtrs","bbg","sources say"]

def fetch_deltaone(max_items=20):
    import requests
    FEEDS = [
        "https://nitter.net/DeItaone/rss",
        "https://nitter.poast.org/DeItaone/rss",
        "https://nitter.privacydev.net/DeItaone/rss",
        "https://nitter.it/DeItaone/rss",
        "https://nitter.cz/DeItaone/rss",
        "https://nitter.1d4.us/DeItaone/rss",
    ]
    for url in FEEDS:
        try:
            r = requests.get(url, headers={"User-Agent":"Mozilla/5.0 AURUM/1.0"}, timeout=10)
            if r.status_code != 200 or "<item>" not in r.text:
                continue
            titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", r.text, re.DOTALL)
            items = []
            for t in titles[1:max_items+5]:
                text = re.sub(r"<[^>]+>", "", t).strip()
                text = html.unescape(text)
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) < 15 or text.startswith("@"):
                    continue
                tl = text.lower()
                relevant  = any(k in tl for k in GOLD_KW)
                breaking  = any(k in tl for k in BREAKING_KW)
                items.append({
                    "source":   "DeltaOne",
                    "title":    text[:180],
                    "body":     "",
                    "relevant": relevant,
                    "breaking": breaking,
                })
            if items:
                print(f"[deltaone] {len(items)} items from {url.split('/')[2]}")
                rel = [i for i in items if i["relevant"]]
                oth = [i for i in items if not i["relevant"]]
                return (rel + oth)[:max_items]
        except Exception as e:
            print(f"[deltaone] {url.split('/')[2]}: {type(e).__name__}")
    print("[deltaone] all sources unavailable")
    return []

def get_breaking_from_deltaone():
    items = fetch_deltaone()
    brk = [i for i in items if i.get("breaking")]
    return brk or [i for i in items if i.get("relevant")][:5]
