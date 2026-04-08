from utils.ollama_client import chat, extract_json
from utils.price_history import get_full_technical_context
from config import MODEL_HEAVY

KEY_LEVELS = [4000,4100,4200,4300,4400,4500,4550,4600,4650,4700,4750,4800,4850,4900,4950,5000,5100,5200]

def nearest(price, n=3):
    below = sorted([l for l in KEY_LEVELS if l<price], reverse=True)[:n]
    above = sorted([l for l in KEY_LEVELS if l>price])[:n]
    return below, above

SYSTEM = ('Professional XAU/USD technical analyst. Use real calculated indicators. '
          'Respond ONLY in JSON: {"trend":"UP","rsi_zone":"OVERBOUGHT","rsi_value":72,"support":4700,"resistance":4850,"sma20":4650,"bias":"BULLISH","confidence":68,"analysis":"summary"}')

def analyze(price_data):
    price = price_data.get('price',0)
    high  = price_data.get('high',price)
    low   = price_data.get('low',price)
    chg   = price_data.get('change_pct',0)
    ctx   = get_full_technical_context(price)
    rsi   = ctx.get('rsi')
    sma20 = ctx.get('sma20')
    sma50 = ctx.get('sma50')
    t20   = ctx.get('trend_20d','UNKNOWN')
    below, above = nearest(price)
    sup = below[0] if below else round(price*0.985,2)
    res = above[0] if above else round(price*1.015,2)
    rz  = 'OVERBOUGHT' if (rsi and rsi>70) else ('OVERSOLD' if (rsi and rsi<30) else 'NEUTRAL')
    p = [
        'XAU/USD Technical Analysis:',
        'Price:$'+str(price)+' H:'+str(high)+' L:'+str(low)+' Chg:'+str(chg)+'%',
        'RSI(14):'+str(rsi)+' Zone:'+rz,
        'SMA20:$'+str(sma20)+' SMA50:$'+str(sma50)+' Trend20d:'+t20,
        'Psychological support: '+str(below),
        'Psychological resistance: '+str(above),
        'Nearest support:$'+str(sup)+' Nearest resistance:$'+str(res),
        '',
        'Provide technical bias. Respond ONLY in JSON.'
    ]
    raw = chat(chr(10).join(p), model=MODEL_HEAVY, system=SYSTEM, temperature=0.3)
    r   = extract_json(raw)
    if not r or not r.get('support'):
        r = {'trend':t20 if t20!='UNKNOWN' else 'SIDEWAYS','rsi_zone':rz,'rsi_value':rsi or 50,
               'support':sup,'resistance':res,'sma20':sma20 or price,
               'bias':'BULLISH' if t20=='UP' else ('BEARISH' if t20=='DOWN' else 'NEUTRAL'),'confidence':58,
               'analysis':'RSI:'+str(rsi)+' SMA20:'+str(sma20)+' Trend:'+t20}
    r['support']   = sup
    r['resistance'] = res
    r['rsi_value'] = rsi or r.get('rsi_value',50)
    r['sma20']     = sma20 or r.get('sma20',price)
    return r