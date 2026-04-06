# agents/technical_analyst.py
from utils.ollama_client import chat, extract_json
from config import MODEL_HEAVY

SYSTEM = """You are a technical analyst for XAU/USD (Gold).
Key levels 2024-2025: Support 2300, 2250, 2200. Resistance 2450, 2500, 2550, 2600.
Trend is bullish above 2300. RSI overbought >70, oversold <30."""

def analyze(price_data):
    price = price_data.get('price')
    open_p = price_data.get('open')
    change = ((price - open_p) / open_p * 100) if price and open_p else 0

    prompt = f"""Perform technical analysis for XAU/USD.

Current price: {price}
Open: {open_p} | Change: {change:.2f}%

Based on current price level and known key levels:
- Identify nearest support and resistance
- Estimate RSI zone (overbought/neutral/oversold)
- Determine trend direction
- Identify potential entry zone

Respond ONLY in JSON:
{{"trend": "UP/DOWN/SIDEWAYS", "rsi_zone": "OVERBOUGHT/NEUTRAL/OVERSOLD",
  "support": 0.0, "resistance": 0.0, "entry_zone": 0.0,
  "bias": "BULLISH/BEARISH/NEUTRAL", "confidence": 60,
  "analysis": "2-3 sentence summary"}}"""
    raw = chat(prompt, model=MODEL_HEAVY, system=SYSTEM, temperature=0.4)
    result = extract_json(raw)
    if not result:
        result = {'trend': 'SIDEWAYS', 'bias': 'NEUTRAL', 'confidence': 40,
                  'support': 0, 'resistance': 0, 'analysis': raw[:500]}
    return result
