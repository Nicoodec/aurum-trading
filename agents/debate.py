from utils.ollama_client import chat, extract_json, extract_confidence
from config import MODEL_HEAVY

BULL_SYSTEM = (
    'You are a veteran gold BULL analyst for XAU/USD. '
    'TASK: Argue why gold will RISE in 24-48h using the data provided. '
    'CRITICAL: Respond ONLY with valid JSON, no other text. '
    'Format: {"argument": "detailed bull case here", "confidence": 72, "target": 4900}'
)

BEAR_SYSTEM = (
    'You are a veteran gold BEAR analyst for XAU/USD. '
    'TASK: Argue why gold will FALL in 24-48h using the data provided. '
    'CRITICAL: Respond ONLY with valid JSON, no other text. '
    'Format: {"argument": "detailed bear case here", "confidence": 68, "target": 4500}'
)

def _ctx(macro, tech, price, news):
    p  = price.get('price', 0)
    ni = news.get('news_items', []) if news else []
    hl = chr(10).join(['- ' + x['title'] for x in ni[:8]]) if ni else 'No news available'
    parts = [
        'MARKET DATA:',
        'XAU/USD: $' + str(p) + ' | Change: ' + str(price.get('change_pct', 0)) + '% | High: ' + str(price.get('high', p)) + ' | Low: ' + str(price.get('low', p)),
        'RSI(14): ' + str(tech.get('rsi_value', 'N/A')) + ' | 20d Trend: ' + str(tech.get('trend', 'N/A')) + ' | SMA20: ' + str(tech.get('sma20', 'N/A')),
        'Support: $' + str(tech.get('support', 0)) + ' | Resistance: $' + str(tech.get('resistance', 0)),
        'Macro bias: ' + str(macro.get('macro_bias', 'N/A')) + ' (' + str(macro.get('confidence', 0)) + '%) | Drivers: ' + str(macro.get('key_drivers', [])[:3]),
        'News sentiment: ' + str(news.get('sentiment', 'NEUTRAL') if news else 'NEUTRAL'),
        'BREAKING NEWS:',
        hl,
        '',
        'Based on ALL the above data, provide your trading argument as JSON.'
    ]
    return chr(10).join(parts)

def _parse(raw, fallback):
    r = extract_json(raw)
    if r and 'confidence' in r:
        c = int(r['confidence'])
        if 35 <= c <= 95:
            return str(r.get('argument', raw[:300])), c
    c = extract_confidence(raw)
    return raw[:300], (c if c != 57 else fallback)

def run_debate(macro_data, tech_data, price_data, news_data=None):
    if news_data is None: news_data = {}
    ctx  = _ctx(macro_data, tech_data, price_data, news_data)
    sent = news_data.get('sentiment', 'NEUTRAL')
    mb   = macro_data.get('macro_bias', 'NEUTRAL')
    rsi  = float(tech_data.get('rsi_value', 50) or 50)
    bb = 66 if (sent == 'BULLISH_GOLD' or mb == 'BULLISH') else (53 if mb == 'NEUTRAL' else 46)
    br = 67 if (sent == 'BEARISH_GOLD' or rsi > 70) else (56 if rsi > 60 else 48)
    hs, bls, brs = [], [], []
    r1b = chat(ctx + chr(10) + 'Make your BULL case now. JSON only.', model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.8)
    r1r = chat(ctx + chr(10) + 'Make your BEAR case now. JSON only.', model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.8)
    a1b, s1b = _parse(r1b, bb)
    a1r, s1r = _parse(r1r, br)
    bls.append(s1b); brs.append(s1r)
    hs.append({'round': 1, 'bull': a1b, 'bear': a1r})
    print('      Round 1 -- Bull: ' + str(s1b) + '% | Bear: ' + str(s1r) + '%')
    r2b = chat(ctx + chr(10) + 'Bear argued: ' + a1r[:300] + chr(10) + 'Refute specifically. JSON only.', model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.75)
    r2r = chat(ctx + chr(10) + 'Bull argued: ' + a1b[:300] + chr(10) + 'Refute specifically. JSON only.', model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.75)
    a2b, s2b = _parse(r2b, bb)
    a2r, s2r = _parse(r2r, br)
    bls.append(s2b); brs.append(s2r)
    hs.append({'round': 2, 'bull': a2b, 'bear': a2r})
    print('      Round 2 -- Bull: ' + str(s2b) + '% | Bear: ' + str(s2r) + '%')
    r3b = chat(ctx + chr(10) + 'FINAL. Bear best arg: ' + a2r[:200] + chr(10) + 'Final verdict. JSON only.', model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.65)
    r3r = chat(ctx + chr(10) + 'FINAL. Bull best arg: ' + a2b[:200] + chr(10) + 'Final verdict. JSON only.', model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.65)
    a3b, s3b = _parse(r3b, bb)
    a3r, s3r = _parse(r3r, br)
    bls.append(s3b); brs.append(s3r)
    hs.append({'round': 3, 'bull': a3b, 'bear': a3r})
    print('      Round 3 -- Bull: ' + str(s3b) + '% | Bear: ' + str(s3r) + '%')
    ab = round(sum(bls)/3, 1)
    ar = round(sum(brs)/3, 1)
    mg = round(abs(ab - ar), 1)
    tie = mg < 5
    win = 'TIE' if tie else ('BULL' if ab > ar else 'BEAR')
    return {'history': hs, 'avg_bull_confidence': ab, 'avg_bear_confidence': ar,
            'margin': mg, 'winner': win, 'is_tie': tie,
            'final_bull': a3b, 'final_bear': a3r,
            'round_scores': list(zip(bls, brs))}