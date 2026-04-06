# agents/macro_analyst.py
from utils.ollama_client import chat, extract_json
from config import MODEL_HEAVY

SYSTEM = """You are a macro analyst specialized in gold (XAU/USD).
You know that gold rises with: high inflation, weak dollar, negative real rates,
geopolitical uncertainty, central bank buying, risk-off sentiment.
Gold falls with: strong dollar, rising real rates, risk-on, hawkish Fed."""

def analyze(news_data, price_data):
    prompt = f"""Analyze the macro environment for gold trading.

Current XAU/USD price: {price_data.get('price', 'N/A')}
News summary: {news_data.get('summary', '')}
Key events: {news_data.get('key_events', [])}
Scheduled macro events: {news_data.get('scheduled_events', [])}
News sentiment: {news_data.get('sentiment', 'NEUTRAL')}

Provide macro analysis for gold in next 24-48h.
Confidence 0-100. Respond ONLY in JSON:
{{"macro_bias": "BULLISH/BEARISH/NEUTRAL", "confidence": 70,
  "key_drivers": ["driver1", "driver2"], "risks": ["risk1"],
  "scheduled_event_warning": true/false, "analysis": "2-3 sentence summary"}}"""
    raw = chat(prompt, model=MODEL_HEAVY, system=SYSTEM, temperature=0.5)
    result = extract_json(raw)
    if not result:
        result = {'macro_bias': 'NEUTRAL', 'confidence': 40,
                  'key_drivers': [], 'risks': [], 'analysis': raw[:500]}
    return result
