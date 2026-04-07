# agents/technical_analyst.py
from utils.ollama_client import chat, extract_json
from utils.price_history import get_full_technical_context
from config import MODEL_HEAVY

SYSTEM = """You are a professional technical analyst for XAU/USD with real calculated indicators.
Analyze the data provided and give a precise trading bias.
Gold is at historically high levels. Use the actual RSI, SMAs and support/resistance provided."""

def analyze(price_data):
    price = price_data.get('price', 0)
    high  = price_data.get('high',  price)
    low   = price_data.get('low',   price)
    chg   = price_data.get('change_pct', 0)

    # Calcular indicadores reales
    ctx = get_full_technical_context(price)
    rsi         = ctx.get('rsi')
    sma20       = ctx.get('sma20')
    sma50       = ctx.get('sma50')
    support     = ctx.get('support',    round(price * 0.985, 2))
    resistance  = ctx.get('resistance', round(price * 1.015, 2))
    trend_20d   = ctx.get('trend_20d',  'UNKNOWN')
    price_vs_sma = ctx.get('price_vs_sma', 'UNKNOWN')

    rsi_zone = 'NEUTRAL'
    if rsi:
        if rsi > 70: rsi_zone = 'OVERBOUGHT'
        elif rsi < 30: rsi_zone = 'OVERSOLD'

    prompt = f"""Technical analysis for XAU/USD with real data.

PRICE DATA:
Current:  | Today: - | Change: {chg}%

CALCULATED INDICATORS:
RSI(14): {rsi} ({rsi_zone})
SMA20:    | Price vs SMA20: {price_vs_sma}
SMA50:   
20-day trend: {trend_20d}

KEY LEVELS (calculated from {ctx.get('history_days',0)} days of data):
Support:    
Resistance: 

Based on these REAL indicators, provide your technical assessment.
Consider: Is RSI overbought/oversold? Is price above/below SMAs? Is trend intact?

Respond ONLY raw JSON:
{{"trend": "UP/DOWN/SIDEWAYS", "rsi_zone": "{rsi_zone}", "rsi_value": {rsi or 50},
  "support": {support}, "resistance": {resistance},
  "sma20": {sma20 or price}, "entry_zone": {round(price,2)},
  "bias": "BULLISH/BEARISH/NEUTRAL", "confidence": 65,
  "analysis": "specific 2 sentence analysis mentioning the actual indicator values"}}"""

    raw    = chat(prompt, model=MODEL_HEAVY, system=SYSTEM, temperature=0.3)
    result = extract_json(raw)

    if not result or not result.get('support'):
        result = {
            'trend':      trend_20d if trend_20d != 'UNKNOWN' else 'SIDEWAYS',
            'rsi_zone':   rsi_zone,
            'rsi_value':  rsi or 50,
            'support':    support,
            'resistance': resistance,
            'sma20':      sma20 or price,
            'bias':       'BULLISH' if trend_20d == 'UP' else ('BEARISH' if trend_20d == 'DOWN' else 'NEUTRAL'),
            'confidence': 58,
            'analysis':   f'RSI: {rsi}, SMA20: {sma20}, Trend 20d: {trend_20d}, Price vs SMA: {price_vs_sma}'
        }
    # Garantizar niveles reales
    result['support']    = support
    result['resistance'] = resistance
    result['rsi_value']  = rsi or result.get('rsi_value', 50)
    return result
