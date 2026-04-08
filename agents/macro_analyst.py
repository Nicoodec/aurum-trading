from utils.ollama_client import chat, extract_json
from config import MODEL_HEAVY

SYSTEM = (
    'You are a macro analyst for gold XAU/USD. '
    'April 2026: prices near ATH 4600-4900. '
    'US tariff wars, Fed rate path, geopolitical tensions. '
    'Be DECISIVE. Use the news provided.'
)

def analyze(news_data, price_data):
    price  = price_data.get('price', 0)
    chg    = price_data.get('change_pct', 0)
    h      = price_data.get('high', price)
    l      = price_data.get('low',  price)
    ni     = news_data.get('news_items', []) if news_data else []
    sent   = news_data.get('sentiment', 'NEUTRAL') if news_data else 'NEUTRAL'
    summ   = news_data.get('summary', 'No news') if news_data else 'No news'
    events = news_data.get('key_events', []) if news_data else []
    hl     = chr(10).join(['- ' + x['title'] for x in ni[:10]]) if ni else 'No headlines'
    p = []
    p.append('Macro analysis for XAU/USD.')
    p.append('PRICE: ' + str(price) + ' chg:' + str(chg) + '% H:' + str(h) + ' L:' + str(l))
    p.append('NEWS SENTIMENT: ' + sent)
    p.append('KEY EVENTS: ' + str(events[:5]))
    p.append('SUMMARY: ' + summ)
    p.append('HEADLINES:')
    p.append(hl)
    p.append('')
    p.append('BULLISH if: geopolitical risk, dollar weak, inflation, safe haven demand')
    p.append('BEARIISH if: dollar strong, rate hikes, risk-on, profit taking')
    p.append('Respond ONLY raw JSON no markdown:')
    p.append('{"macro_bias":"BULLISH","confidence":70,"key_drivers":["d1"],"risks":["r1"],"scheduled_event_warning":false,"analysis":"summary"}')
    prompt = chr(10).join(p)
    raw    = chat(prompt, model=MODEL_HEAVY, system=SYSTEM, temperature=0.4)
    result = extract_json(raw)
    if not result or 'macro_bias' not in result:
        if 'BULLISH' in sent:   bias, conf = 'BULLISH', 65
        elif 'BEARISH' in sent: bias, conf = 'BEARISH', 65
        elif chg > 0.5:         bias, conf = 'BULLISH', 58
        elif chg < -0.5:        bias, conf = 'BEARISH', 58
        else:                   bias, conf = 'NEUTRAL', 50
        result = {'macro_bias': bias, 'confidence': conf,
            'key_drivers': events[:3] if events else ['Price action'],
            'risks': ['Limited data'], 'scheduled_event_warning': False,
            'analysis': 'Based on ' + str(len(ni)) + ' items. Sentiment: ' + sent}
    if result.get('confidence', 0) < 50 and result.get('macro_bias') != 'NEUTRAL':
        result['confidence'] = 55
    return result
