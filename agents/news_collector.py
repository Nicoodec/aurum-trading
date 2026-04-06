# agents/news_collector.py
from duckduckgo_search import DDGS
from utils.ollama_client import chat, extract_json
from config import MODEL_LIGHT

QUERIES = [
    'gold XAU USD price today',
    'Federal Reserve interest rates decision',
    'US CPI inflation data',
    'dollar index DXY today',
    'gold geopolitical risk demand',
    'US treasury yields real rates'
]

def collect():
    news = []
    with DDGS() as ddgs:
        for q in QUERIES:
            results = list(ddgs.text(q, max_results=3))
            for r in results:
                news.append({'query': q, 'title': r.get('title',''),
                             'body': r.get('body','')[:300]})
    summary_prompt = f"""You are a financial news summarizer.
Given these headlines about gold and macro factors, extract:
1. Key events affecting gold price (up to 5)
2. Any scheduled macro events in next 24h (Fed, CPI, NFP, etc)
3. Overall macro sentiment: BULLISH_GOLD / BEARISH_GOLD / NEUTRAL

News data:
{str(news[:15])}

Respond ONLY in JSON:
{{"key_events": ["..."], "scheduled_events": ["{{"event":"","hours_away":0}}"], "sentiment": "NEUTRAL", "summary": "..."}}"""
    raw = chat(summary_prompt, model=MODEL_LIGHT, temperature=0.2)
    result = extract_json(raw)
    if not result:
        result = {'key_events': [], 'scheduled_events': [], 'sentiment': 'NEUTRAL', 'summary': raw[:500]}
    return result
