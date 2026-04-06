# agents/technical_analyst.py
from utils.ollama_client import chat, extract_json
from config import MODEL_HEAVY

SYSTEM = """You are a technical analyst for XAU/USD (Gold).
Gold is currently trading around -4700. Key psychological levels:
4500, 4550, 4600, 4650, 4700, 4750, 4800.
Use the actual current price provided to identify realistic support/resistance."""

def analyze(price_data):
    price = price_data.get('price', 0)
    high  = price_data.get('high', price * 1.01)
    low   = price_data.get('low',  price * 0.99)
    open_p = price_data.get('open', price)
    change_pct = price_data.get('change_pct', 0)

    # Dynamic levels based on real price
    s1 = round(price * 0.990, 2)
    s2 = round(price * 0.982, 2)
    r1 = round(price * 1.010, 2)
    r2 = round(price * 1.018, 2)

    prompt = f"""Technical analysis for XAU/USD.

Current price: {price}
Today open: {open_p} | High: {high} | Low: {low} | Change: {change_pct}%
Nearest support levels: {s1}, {s2}
Nearest resistance levels: {r1}, {r2}

Analyze: trend direction, momentum, key levels to watch, entry bias.
Respond ONLY raw JSON:
{{"trend":"UP/DOWN/SIDEWAYS","rsi_zone":"OVERBOUGHT/NEUTRAL/OVERSOLD",
"support":{s1},"resistance":{r1},"entry_zone":{price},
"bias":"BULLISH/BEARISH/NEUTRAL","confidence":60,
"analysis":"2 sentence summary"}}"""

    raw = chat(prompt, model=MODEL_HEAVY, system=SYSTEM, temperature=0.4)
    result = extract_json(raw)
    if not result:
        result = {'trend': 'SIDEWAYS', 'bias': 'NEUTRAL', 'confidence': 40,
                  'support': s1, 'resistance': r1, 'entry_zone': price,
                  'analysis': 'Technical analysis unavailable'}
    # Garantizar que support/resistance sean realistas
    if not result.get('support') or result['support'] < 1000:
        result['support'] = s1
    if not result.get('resistance') or result['resistance'] < 1000:
        result['resistance'] = r1
    return result
