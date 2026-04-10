import time, re
from urllib.request import urlopen, Request

RSS_FEEDS = [
    ('BBC Business',  'https://feeds.bbci.co.uk/news/business/rss.xml'),
    ('MarketWatch',   'https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines'),
    ('FXStreet Gold', 'https://www.fxstreet.com/rss/news/category/commodities/gold-silver'),
    ('CNBC Economy',  'https://www.cnbc.com/id/20910258/device/rss/rss.html'),
    ('Yahoo Finance', 'https://finance.yahoo.com/news/rssindex'),
    ('Investing.com', 'https://www.investing.com/rss/news_14.rss'),
]

GOLD_KW = ['gold','xau','fed','inflation','cpi','dollar','dxy','treasury','tariff','trump','war','iran','israel','russia','china','geopolit','rate','powell','recession','safe haven','oil','nfp','ceasefire','sanctions','hormuz']

def _fetch(url, name, n=6):
    items = []
    try:
        req = Request(url, headers={'User-Agent': 'Mozilla/5.0 AURUM/1.0'})
        with urlopen(req, timeout=8) as r: raw = r.read().decode('utf-8', errors='ignore')
        ts = __import__('re').findall(r'<title>(?:<![CDATA[)?(.*?)(?:]>)?</title>', raw, __import__('re').DOTALL)
        ds = __import__('re').findall(r'<description>(?:<![CDATA[)?(.*?)(?:]>)?</description>', raw, __import__('re').DOTALL)
        for i, t in enumerate(ts[1:n+1]):
            t = __import__('re').sub(r'<[^>]+>', '', t).strip()
            d = __import__('re').sub(r'<[^>]+>', '', ds[i] if i<len(ds) else '').strip()[:200]
            if len(t)>10: items.append({'source':name,'title':t,'body':d})
    except Exception as e: print('[news]', name+':', type(e).__name__)
    return items

def _ok(i): return any(k in (i['title']+' '+i['body']).lower() for k in GOLD_KW)

def collect():
    print('      Searching', len(RSS_FEEDS), 'sources...')
    all_items = []
    for name, url in RSS_FEEDS:
        items = [i for i in _fetch(url,name) if _ok(i)]
        all_items.extend(items)
        if items: print('      ['+name+'] '+str(len(items))+' items')
        __import__('time').sleep(0.3)
    if not all_items:
        return {'key_events':[],'scheduled_events':[],'sentiment':'NEUTRAL','summary':'No news','news_items':[],'raw_count':0}
    print('      Total: '+str(len(all_items))+' items')
    txt = ' '.join(i['title'].lower() for i in all_items)
    bull_kw = ['ceasefire','safe haven','inflation','crisis','war','attack','tension','sanctions','gold rises','gold climbs']
    bear_kw = ['dollar rises','dollar jumps','yields rise','rate hike','gold falls','gold drops','risk on']
    bs = sum(1 for k in bull_kw if k in txt)
    rs = sum(1 for k in bear_kw if k in txt)
    sent = 'BULLISH_GOLD' if bs>rs else ('BEARISH_GOLD' if rs>bs else 'NEUTRAL')
    return {'key_events':[i['title'] for i in all_items[:5]],'scheduled_events':[],'sentiment':sent,'summary':str(len(all_items))+' items','news_items':[{'source':i['source'],'title':i['title'][:100]} for i in all_items[:20]],'raw_count':len(all_items)}