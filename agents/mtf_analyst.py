# agents/mtf_analyst.py — Multi-timeframe confluence
from utils.ollama_client import chat, extract_json
from config import MODEL_HEAVY

SYSTEM = """You are a multi-timeframe gold analyst.
You analyze XAU/USD across 3 timeframes: Daily (trend), 4H (structure), 1H (entry).
Confluence across timeframes = higher probability trades.
All 3 aligned = strong signal. 2/3 = moderate. 1/3 or less = no trade."""

def analyze(price_data):
    price      = price_data.get('price', 0)
    high       = price_data.get('high', price)
    low        = price_data.get('low', price)
    change_pct = price_data.get('change_pct', 0)

    # Niveles dinamicos por timeframe
    daily_s  = round(price * 0.975, 2)
    daily_r  = round(price * 1.025, 2)
    h4_s     = round(price * 0.990, 2)
    h4_r     = round(price * 1.010, 2)
    h1_s     = round(price * 0.995, 2)
    h1_r     = round(price * 1.005, 2)

    prompt = f"""Multi-timeframe analysis for XAU/USD.

Current price: 
Today range:  -  | Change: {change_pct}%

Estimated key levels:
DAILY: Support {daily_s} | Resistance {daily_r}
4H:    Support {h4_s}   | Resistance {h4_r}
1H:    Support {h1_s}   | Resistance {h1_r}

Analyze trend and bias on each timeframe based on current price position.
Determine overall confluence signal.

Respond ONLY raw JSON:
{{"daily": {{"trend": "UP/DOWN/SIDEWAYS", "bias": "BULLISH/BEARISH/NEUTRAL", "key_level": 0.0}},
  "h4":    {{"trend": "UP/DOWN/SIDEWAYS", "bias": "BULLISH/BEARISH/NEUTRAL", "key_level": 0.0}},
  "h1":    {{"trend": "UP/DOWN/SIDEWAYS", "bias": "BULLISH/BEARISH/NEUTRAL", "key_level": 0.0}},
  "confluence": "STRONG_BULL/STRONG_BEAR/MODERATE_BULL/MODERATE_BEAR/NO_SIGNAL",
  "aligned_timeframes": 0,
  "recommendation": "LONG/SHORT/WAIT",
  "analysis": "brief summary"}}"""

    raw = chat(prompt, model=MODEL_HEAVY, system=SYSTEM, temperature=0.4)
    result = extract_json(raw)
    if not result:
        result = {
            'daily': {'trend': 'SIDEWAYS', 'bias': 'NEUTRAL'},
            'h4':    {'trend': 'SIDEWAYS', 'bias': 'NEUTRAL'},
            'h1':    {'trend': 'SIDEWAYS', 'bias': 'NEUTRAL'},
            'confluence': 'NO_SIGNAL',
            'aligned_timeframes': 0,
            'recommendation': 'WAIT',
            'analysis': 'MTF analysis unavailable'
        }
    return result
