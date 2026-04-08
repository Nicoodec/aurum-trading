from utils.ollama_client import chat, extract_json
from config import MODEL_HEAVY

SYSTEM = (
    "You are a senior macro analyst specializing in gold (XAU/USD). "
    "You have access to real-time Federal Reserve data and breaking news. "
    "Gold is driven by: DXY (inverse), real yields (inverse), geopolitical risk (positive), "
    "inflation expectations (positive), central bank demand (positive). "
    "Be DECISIVE. Use the specific numbers provided. Do not be vague."
)

def analyze(news_data, price_data):
    price = price_data.get("price", 0)
    chg   = price_data.get("change_pct", 0)
    h     = price_data.get("high", price)
    l     = price_data.get("low",  price)

    # News data
    ni     = news_data.get("news_items", []) if news_data else []
    sent   = news_data.get("sentiment",  "NEUTRAL") if news_data else "NEUTRAL"
    summ   = news_data.get("summary",    "") if news_data else ""
    kevt   = news_data.get("key_events", []) if news_data else []

    # FRED data
    fred   = news_data.get("fred", {}) if news_data else {}
    dxy    = fred.get("dxy")
    t10    = fred.get("t10y")
    t2     = fred.get("t2y")
    fed    = fred.get("fedfunds")

    # DeltaOne headlines
    delta  = [x for x in ni if x.get("source") == "DeltaOne"]
    others = [x for x in ni if x.get("source") != "DeltaOne"]
    delta_str  = chr(10).join(["- " + x["title"] for x in delta[:8]])  if delta  else "None"
    others_str = chr(10).join(["- " + x["title"] for x in others[:5]]) if others else "None"

    # Compute real yield (approximate)
    real_yield = None
    if t10 is not None:
        # Approximate: real yield = 10Y - breakeven inflation (~2.3% currently)
        real_yield = round(t10 - 2.3, 2)

    # Build comprehensive prompt
    p = []
    p.append("Analyze the macro environment for XAU/USD gold trading.")
    p.append("")
    p.append("PRICE ACTION")
    p.append("XAU/USD: $" + str(price) + " | Change: " + str(chg) + "% | Range: $" + str(l) + "-$" + str(h))
    p.append("")
    p.append("FEDERAL RESERVE DATA (real-time via FRED)")
    p.append("DXY (USD Broad Index): " + (str(round(dxy,2)) if dxy else "N/A"))
    p.append("10Y Treasury Yield:    " + (str(t10)+"%" if t10 else "N/A"))
    p.append("2Y Treasury Yield:     " + (str(t2)+"%" if t2 else "N/A"))
    p.append("Fed Funds Rate:        " + (str(fed)+"%" if fed else "N/A"))
    if t10 and t2:
        p.append("Yield Curve (10Y-2Y): " + str(round(t10-t2,2)) + "% (" + ("inverted - recession risk" if t10<t2 else "normal") + ")")
    if real_yield is not None:
        p.append("Approx Real Yield:    " + str(real_yield) + "% (" + ("negative - BULLISH gold" if real_yield < 0 else "positive - BEARISH gold") + ")")
    p.append("")
    p.append("MACRO INTERPRETATION RULES")
    if dxy:
        if dxy > 108:   p.append("-> DXY=" + str(round(dxy,1)) + ": VERY STRONG dollar -> BEARISH gold")
        elif dxy > 104: p.append("-> DXY=" + str(round(dxy,1)) + ": Strong dollar -> bearish gold")
        elif dxy < 98:  p.append("-> DXY=" + str(round(dxy,1)) + ": Weak dollar -> BULLISH gold")
        else:           p.append("-> DXY=" + str(round(dxy,1)) + ": Neutral dollar")
    if t10:
        if t10 > 4.5:   p.append("-> 10Y=" + str(t10) + "%: HIGH yields -> BEARISH gold")
        elif t10 > 4.0: p.append("-> 10Y=" + str(t10) + "%: Elevated yields -> mildly bearish gold")
        elif t10 < 3.5: p.append("-> 10Y=" + str(t10) + "%: LOW yields -> BULLISH gold")
        else:           p.append("-> 10Y=" + str(t10) + "%: Moderate yields -> neutral")
    p.append("")
    p.append("DELTAONE BLOOMBERG FEED")
    p.append(delta_str)
    p.append("")
    p.append("OTHER NEWS")
    p.append(others_str)
    p.append("")
    p.append("NEWS SENTIMENT: " + sent)
    p.append("Summary: " + summ)
    p.append("Key events: " + str(kevt[:4]))
    p.append("")
    p.append("Based on ALL of the above (especially DXY, yields, and DeltaOne headlines),")
    p.append("provide a DECISIVE macro assessment for gold in the next 24-48 hours.")
    p.append("Reference specific numbers in your analysis.")
    p.append("")
    p.append("Respond ONLY in raw JSON:")
    p.append("{" + chr(34) + "macro_bias" + chr(34) + ":" + chr(34) + "BULLISH" + chr(34) + "," +
             chr(34) + "confidence" + chr(34) + ":70," +
             chr(34) + "key_drivers" + chr(34) + ":[" + chr(34) + "driver1" + chr(34) + "]," +
             chr(34) + "risks" + chr(34) + ":[" + chr(34) + "risk1" + chr(34) + "]," +
             chr(34) + "scheduled_event_warning" + chr(34) + ":false," +
             chr(34) + "analysis" + chr(34) + ":" + chr(34) + "2 sentence analysis with specific numbers" + chr(34) + "}")

    prompt = chr(10).join(p)
    raw    = chat(prompt, model=MODEL_HEAVY, system=SYSTEM, temperature=0.4)
    result = extract_json(raw)

    if not result or "macro_bias" not in result:
        # Fallback: derive from data
        bull_score = 0
        if sent == "BULLISH_GOLD":  bull_score += 2
        if sent == "BEARISH_GOLD":  bull_score -= 2
        if dxy and dxy < 100:       bull_score += 2
        if dxy and dxy > 106:       bull_score -= 2
        if t10 and t10 < 3.8:       bull_score += 1
        if t10 and t10 > 4.5:       bull_score -= 2
        if chg and chg > 0.5:       bull_score += 1
        if chg and chg < -0.5:      bull_score -= 1

        if bull_score >= 2:   bias, conf = "BULLISH", 62
        elif bull_score <= -2: bias, conf = "BEARISH", 62
        else:                 bias, conf = "NEUTRAL", 52

        result = {
            "macro_bias":              bias,
            "confidence":              conf,
            "key_drivers":             kevt[:3] if kevt else ["Price action"],
            "risks":                   ["Limited model data"],
            "scheduled_event_warning": False,
            "analysis":                (
                "DXY=" + str(round(dxy,1) if dxy else "N/A") +
                " 10Y=" + str(t10 if t10 else "N/A") + "%" +
                " Sentiment=" + sent +
                " Price change=" + str(chg) + "%"
            )
        }

    # Ensure confidence is meaningful
    if result.get("confidence", 0) < 50 and result.get("macro_bias") != "NEUTRAL":
        result["confidence"] = 58

    return result
