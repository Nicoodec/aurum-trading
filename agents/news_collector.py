# agents/news_collector.py
import time
from utils.ollama_client import chat, extract_json
from config import MODEL_LIGHT

QUERIES = [
    'gold XAU USD price forecast today',
    'Federal Reserve rates gold impact',
    'US dollar DXY gold 2025',
]

def _search(query, max_results=2):
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))
    except ImportError:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results, backend='lite'))

def collect():
    news = []
    for q in QUERIES:
        try:
            results = _search(q)
            for r in results:
                news.append({'title': r.get('title',''), 'body': r.get('body','')[:300]})
            time.sleep(4)
        except Exception as e:
            print(f'[news] skipping: {type(e).__name__}')
            time.sleep(8)

    if not news:
        print('[news] unavailable — technical analysis only')
        return {'key_events': [], 'scheduled_events': [],
                'sentiment': 'NEUTRAL',
                'summary': 'No news available. Analysis based on price action only.'}

    raw = chat(
        f"Summarize for gold trader. News: {str(news[:8])}\n"
        "Respond ONLY raw JSON no markdown:\n"
        '{"key_events":["..."],"scheduled_events":[],"sentiment":"NEUTRAL","summary":"..."}',
        model=MODEL_LIGHT, temperature=0.2
    )
    result = extract_json(raw)
    if not result:
        result = {'key_events': [], 'scheduled_events': [],
                  'sentiment': 'NEUTRAL', 'summary': raw[:300]}
    return result
