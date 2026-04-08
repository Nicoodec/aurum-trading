from utils.ollama_client import chat, extract_json
from config import MODEL_HEAVY

SYSTEM = """You are a macro analyst for gold (XAU/USD).
Gold context April 2026: prices near all-time highs $4600-4900.
Key factors: US tariff wars, Fed rate path, geopolitical tensions, dollar strength.
Analyze the news provided and give a DECISIVE macro bias, not neutral unless truly mixed."""

def analyze(news_data, price_data):
    price = price_data.get("price", 0)
    chg   = price_data.get("change_pct", 0)
    h     = price_data.get("high", price)
    l     = price_data.get("low",  price)
    ni    = news_data.get("news_items", []) if news_data else []
    sent  = news_data.get("sentiment", "NEUTRAL") if news_data else "NEUTRAL"
    summ  = news_data.get("summary", "No news") if news_data else "No news"
    events = news_data.get("key_events", []) if news_data else []
    headlines = "\n".join(["- " + x["title"] for x in ni[:10]]) if ni else "No headlines"

    prompt = (
        "Macro analysis for XAU/USD gold trading.\n\n"
        "PRICE: $" + str(price) + " | Change: " + str(chg) + "% | H:" + str(h) + " L:" + str(l) + "\n\n"
        "NEWS SENTIMENT: " + sent + "\n"
        "KEY EVENTS: " + str(events[:5]) + "\n"
        "SUMMARY: " + summ + "\n\n"
        "HEADLINES:\n" + headlines + "\n\n"
        "Based on this news, give a DECISIVE macro assessment for gold.\n"
        "If news is bullish for gold (geopolitical risk, dollar weakness, inflation) -> BULLISH\n"
        "If news is bearish for gold (dollar strength, rate hikes, risk-on) -> BEARISH\n"
        "Only say NEUTRAL if truly mixed signals.\n\n"
        "Respond ONLY raw JSON:\n"
        "{"macro_bias":"BULLISH","confidence":70,"key_drivers":["driver1","driver2"],"
        ""risks":["risk1"],"scheduled_event_warning":false,"analysis":"2 sentence summary"}"
    )

    raw    = chat(prompt, model=MODEL_HEAVY, system=SYSTEM, temperature=0.4)
    result = extract_json(raw)

    if not result or "macro_bias" not in result:
        if "BULLISH" in sent:
            bias, conf = "BULLISH", 65
        elif "BEARISH" in sent:
            bias, conf = "BEARISH", 65
        elif chg > 0.5:
            bias, conf = "BULLISH", 58
        elif chg < -0.5:
            bias, conf = "BEARISH", 58
        else:
            bias, conf = "NEUTRAL", 50
        result = {
            "macro_bias": bias, "confidence": conf,
            "key_drivers": events[:3] if events else ["Price action"],
            "risks": ["Limited data"], "scheduled_event_warning": False,
            "analysis": "Based on " + str(len(ni)) + " news items. Sentiment: " + sent
        }

    if result.get("confidence", 0) < 50 and result.get("macro_bias") != "NEUTRAL":
        result["confidence"] = 55
    return result
