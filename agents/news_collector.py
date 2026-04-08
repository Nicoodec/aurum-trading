import time, re
from urllib.request import urlopen, Request
from utils.ollama_client import chat, extract_json
from config import MODEL_LIGHT

RSS_FEEDS = [
    ('BBC Business',    'https://feeds.bbci.co.uk/news/business/rss.xml'),
    ('MarketWatch',    'https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines'),
    ('FXStreet Gold', 'https://www.fxstreet.com/rss/news/category/commodities/gold-silver'),
    ('CNBC Economy',  'https://www.cnbc.com/id/20910258/device/rss/rss.html'),
    ('Yahoo Finance', 'https://finance.yahoo.com/news/rssindex'),
    ('Investing.com', 'https://www.investing.com/rss/news_14.rss'),
]

GOLD_KW = ['gold','xau','fed','federal reserve','inflation','cpi','dollar','dxy','treasury','tariff','trump','war','iran','israel','russia','china','geopolit','rate','powell','recession','safe haven','oil','nfp','payroll']

def _fetch(url, name, n=6):
    items = []
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0 AURUM/1.0'})
        with urlopen(req, timeout=8) as r: raw = r.read().decode('utf-8', errors='ignore')
        ts = re.findall(r'<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', raw, re.DOTALL)
        ds = re.findall(r'<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>', raw, re.DOTALL)
        for i, t in enumerate(ts[1:n+1]):
            t = re.sub(r'<[^>]+>', '', t).strip()
            d = re.sub(r'<[^>]+>', '', ds[i] if i<len(ds) else '').strip()[:200]
            if len(t)>10: items.append({'source':name,'title':t,'body':d})
    except Exception as e: print('[news] '+name+': '+type(e).__name__)
    return items

def _ok(i): return any(k in (i['title']+' '+i['body']).lower() for k in GOLD_KW)

def collect():
    print('      Searching '+str(len(RSS_FEEDS))+' sources...')
    all_items = []
    for name, url in RSS_FEEDS:
        items = [i for i in _fetch(url,name) if _ok(i)]
        all_items.extend(items)
        if items: print('      ['+name+'] '+str(len(items))+' items')
        time.sleep(0.3)
    if not all_items:
        return {'key_events':[],'scheduled_events':[],'sentiment':'NEUTRAL','summary':'No news','news_items':[],'raw_count':0}
    print('      Total: '+str(len(all_items))+' items')
    for i in all_items[:8]: print('      >> ['+i['source']+'] '+i['title'][:80])
    txt = chr(10).join(['['+i['source']+'] '+i['title']+': '+i['body'][:100] for i in all_items[:15]])
    p = ['Analyze these news for XAU/USD gold trading.', 'NEWS:', txt, '',
         'Classify: BULLISH_GOLD if supports gold rising, BEARISH_GOLD if falling, NEUTRAL if mixed.',
         'Extract key events and scheduled macro events with hours until release.',
         'Respond raw JSON: {"key_events":["e1"],"scheduled_events":[],"sentiment":"BULLISH_GOLD","summary":"summary"}']
    raw = chat(chr(10).join(p), model=MODEL_LIGHT, temperature=0.2)
    res = extract_json(raw)
    if not res: res = {'key_events':[i['title'] for i in all_items[:5]],'scheduled_events':[],'sentiment':'NEUTRAL','summary':'collected'}
    res['news_items'] = [{'source':i['source'],'title':i['title'][:100]} for i in all_items[:20]]
    res['raw_count'] = len(all_items)
    return res