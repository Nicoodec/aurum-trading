# agents/macro_analyst.py
from utils.ollama_client import chat, extract_json
from config import MODEL_HEAVY

SYSTEM = """You are a macro analyst specialized in gold (XAU/USD).
Gold rises with: high inflation, weak dollar, negative real rates, geopolitical risk, central bank buying.
Gold falls with: strong dollar, rising real rates, hawkish Fed, risk-on sentiment.
Even without news, analyze the price action and known macro context of early April 2026."""

def analyze(news_data, price_data):
    price      = price_data.get('price', 0)
    change_pct = price_data.get('change_pct', 0)
    high       = price_data.get('high', price)
    low        = price_data.get('low', price)
    summary    = news_data.get('summary', 'No news available')
    events     = news_data.get('key_events', [])
    sentiment  = news_data.get('sentiment', 'NEUTRAL')

    prompt = f"""Analyze the macro environment for gold trading right now.

XAU/USD:  | Change today: {change_pct}% | Range: -
News sentiment: {sentiment}
Key events: {events if events else 'None available'}
News summary: {summary}

Context: Gold is at historically high levels (~+). April 2026 macro environment.
Key considerations: US tariff uncertainty, Fed rate path, dollar strength/weakness, geopolitical tensions.

Give your macro assessment even with limited news. Be decisive.

Respond ONLY raw JSON no markdown:
{{"macro_bias": "BULLISH", "confidence": 65, "key_drivers": ["driver1", "driver2"], "risks": ["risk1"], "scheduled_event_warning": false, "analysis": "2 sentence summary"}}"""

    raw = chat(prompt, model=MODEL_HEAVY, system=SYSTEM, temperature=0.5)
    result = extract_json(raw)
    if not result or 'macro_bias' not in result:
        # Fallback basado en precio
        bias = 'BULLISH' if change_pct > 0.3 else ('BEARISH' if change_pct < -0.3 else 'NEUTRAL')
        result = {
            'macro_bias':               bias,
            'confidence':               52,
            'key_drivers':              ['Price action', 'Historical high levels'],
            'risks':                    ['Limited news data'],
            'scheduled_event_warning':  False,
            'analysis':                 f'Gold at , change {change_pct}%. Limited news — price action driven analysis.'
        }
    # Garantizar confidence no sea 40 por defecto
    if result.get('confidence', 0) < 45:
        result['confidence'] = 52
    return result
