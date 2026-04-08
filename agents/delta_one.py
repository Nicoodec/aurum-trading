import requests, re, time
from datetime import datetime

# DeltaOne (@DeItaone) - Bloomberg terminal en Twitter
# Usamos nitter (espejo publico de Twitter) para scraping sin API

NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
]

GOLD_KEYWORDS = [
    "gold", "xau", "fed", "rate", "inflation", "dollar", "treasury",
    "tariff", "iran", "war", "geopolit", "safe haven", "powell",
    "cpi", "nfp", "payroll", "gdp", "recession", "china", "risk"
]

def fetch_deltaone(max_items=15):
    items = []
    for instance in NITTER_INSTANCES:
        try:
            url = instance + "/DeItaone"
            r = requests.get(url,
                headers={"User-Agent": "Mozilla/5.0 AURUM/1.0"},
                timeout=10)
            if r.status_code != 200:
                continue
            # Extraer tweets del HTML
            tweets = re.findall(r'<div class="tweet-content[^"]*"[^>]*>(.*?)</div>', r.text, re.DOTALL)
            for tweet in tweets[:20]:
                text = re.sub(r'<[^>]+>', '', tweet).strip()
                text = re.sub(r'\s+', ' ', text).strip()
                if len(text) > 20:
                    tl = text.lower()
                    relevant = any(k in tl for k in GOLD_KEYWORDS)
                    items.append({
                        "source": "DeltaOne",
                        "title":  text[:150],
                        "body":   "",
                        "relevant": relevant,
                        "ts": datetime.now().isoformat()
                    })
            if items:
                print(f"[deltaone] Got {len(items)} tweets from {instance}")
                break
        except Exception as e:
            print(f"[deltaone] {instance}: {type(e).__name__}")
            continue

    relevant = [i for i in items if i["relevant"]]
    all_items = relevant + [i for i in items if not i["relevant"]]
    return all_items[:max_items]

def get_breaking_from_deltaone():
    items = fetch_deltaone()
    if not items:
        return []
    breaking_kw = ["breaking", "flash", "alert", "urgent", "just in", "reuters", "bloomberg"]
    breaking = [i for i in items if any(k in i["title"].lower() for k in breaking_kw)]
    return breaking or items[:5]
