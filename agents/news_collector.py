# agents/news_collector.py
# Fuentes: Reuters RSS, BBC RSS, FT RSS, Investing.com RSS, directo sin DDG
import time, re
from urllib.request import urlopen, Request
from urllib.error import URLError
from utils.ollama_client import chat, extract_json
from config import MODEL_LIGHT

# Fuentes RSS que no necesitan auth ni ddg
RSS_FEEDS = [
    ('Reuters Markets',   'https://feeds.reuters.com/reuters/businessNews'),
    ('Reuters Economy',   'https://feeds.reuters.com/news/economy'),
    ('BBC Business',      'https://feeds.bbci.co.uk/news/business/rss.xml'),
    ('MarketWatch',       'https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines'),
    ('FXStreet Gold',     'https://www.fxstreet.com/rss/news/category/commodities/gold-silver'),
    ('Kitco News',        'https://www.kitco.com/rss/kitco-news.xml'),
]

# Keywords para filtrar noticias relevantes para oro
GOLD_KEYWORDS = [
    'gold', 'xau', 'federal reserve', 'fed', 'inflation', 'cpi', 'dollar', 'dxy',
    'interest rate', 'treasury', 'geopolit', 'war', 'conflict', 'tariff', 'trump',
    'china', 'russia', 'iran', 'safe haven', 'risk', 'recession', 'gdp', 'nfp',
    'payroll', 'unemployment', 'powell', 'yellen', 'ecb', 'oil', 'commodit'
]

def _fetch_rss(url, source_name, max_items=5):
    items = []
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urlopen(req, timeout=8) as resp:
            content = resp.read().decode('utf-8', errors='ignore')
        # Extraer titulos y descripciones con regex simple
        titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>', content)
        descs  = re.findall(r'<description><!\[CDATA\[(.*?)\]\]></description>|<description>(.*?)</description>', content)
        for i, t in enumerate(titles[1:max_items+1]):  # skip feed title
            title = (t[0] or t[1]).strip()
            desc  = ''
            if i < len(descs):
                d = descs[i]
                desc = (d[0] or d[1]).strip()[:200]
            # Limpiar HTML
            title = re.sub(r'<[^>]+>', '', title).strip()
            desc  = re.sub(r'<[^>]+>', '', desc).strip()
            if title and len(title) > 10:
                items.append({'source': source_name, 'title': title, 'body': desc})
    except Exception as e:
        print(f'[news] {source_name}: {type(e).__name__}')
    return items

def _is_relevant(item):
    text = (item['title'] + ' ' + item['body']).lower()
    return any(kw in text for kw in GOLD_KEYWORDS)

def collect():
    print('      Searching news from', len(RSS_FEEDS), 'sources...')
    all_items = []

    for source_name, url in RSS_FEEDS:
        items = _fetch_rss(url, source_name, max_items=6)
        relevant = [i for i in items if _is_relevant(i)]
        all_items.extend(relevant)
        if relevant:
            print(f'      [{source_name}] {len(relevant)} relevant items')
        time.sleep(0.5)

    if not all_items:
        print('      No news available from any source')
        return {
            'key_events': ['No news available'],
            'scheduled_events': [],
            'sentiment': 'NEUTRAL',
            'summary': 'No news data. Analysis based on price action only.',
            'news_items': [],
            'raw_count': 0
        }

    print(f'      Total relevant news: {len(all_items)} items')
    for item in all_items[:8]:
        print(f'      >> [{item["source"]}] {item["title"][:80]}')

    # Resumir con LLM
    news_text = '\n'.join([
        f'[{i["source"]}] {i["title"]}: {i["body"][:150]}'
        for i in all_items[:15]
    ])

    prompt = (
        "You are a gold trading analyst. Analyze these news headlines for XAU/USD impact.\n\n"
        "NEWS:\n" + news_text + "\n\n"
        "Identify:\n"
        "1. Events that move gold UP (geopolitical risk, dollar weakness, inflation, Fed dovish)\n"
        "2. Events that move gold DOWN (dollar strength, risk-on, Fed hawkish, rate hikes)\n"
        "3. Any scheduled macro events in next 24h (Fed, CPI, NFP, etc)\n"
        "4. Overall sentiment for gold\n\n"
        "Respond ONLY raw JSON:\n"
        '{"key_events":["event1","event2"],"scheduled_events":[],'
        '"sentiment":"BULLISH_GOLD","summary":"2 sentence summary of gold impact"}'
    )

    raw    = chat(prompt, model=MODEL_LIGHT, temperature=0.2)
    result = extract_json(raw)

    if not result:
        result = {
            'key_events':       [i['title'][:80] for i in all_items[:5]],
            'scheduled_events': [],
            'sentiment':        'NEUTRAL',
            'summary':          f'{len(all_items)} relevant news items collected. Manual review recommended.'
        }

    result['news_items'] = [{'source': i['source'], 'title': i['title'][:100]} for i in all_items[:20]]
    result['raw_count']  = len(all_items)
    return result
