from utils.ollama_client import chat, extract_confidence
from config import MODEL_HEAVY, DEBATE_ROUNDS

BULL_SYSTEM = """You are a veteran gold bull trader with 20 years experience on XAU/USD.
Your job: build the STRONGEST possible case for gold RISING in the next 24-48 hours.
Use specific data provided. Be decisive and concrete.
Structure your argument:
1. Primary catalyst driving gold up RIGHT NOW
2. Technical confirmation from the price data given
3. Why the bears are wrong
4. Specific price target

CRITICAL: Your final line MUST be exactly:
Confidence: XX%
(where XX is your honest confidence level between 45 and 85)"""

BEAR_SYSTEM = """You are a veteran gold bear trader with 20 years experience on XAU/USD.
Your job: build the STRONGEST possible case for gold FALLING in the next 24-48 hours.
Use specific data provided. Be decisive and concrete.
Structure your argument:
1. Primary catalyst driving gold down RIGHT NOW
2. Technical breakdown signals from the price data given
3. Why the bulls are wrong
4. Specific downside target

CRITICAL: Your final line MUST be exactly:
Confidence: XX%
(where XX is your honest confidence level between 45 and 85)"""

def _ctx(macro, tech, price, news):
    p   = price.get("price", 0)
    chg = price.get("change_pct", 0)
    h   = price.get("high", p)
    l   = price.get("low",  p)
    rsi = tech.get("rsi_value", "N/A")
    s   = tech.get("support", 0)
    r   = tech.get("resistance", 0)
    s20 = tech.get("sma20", "N/A")
    ni  = news.get("news_items", [])
    top_news = [x["title"] for x in ni[:5]] if ni else ["No news available"]
    return (
        "=== PRICE DATA ===\n"
        "XAU/USD: $" + str(p) + " | Change: " + str(chg) + "% | Range: $" + str(l) + "-$" + str(h) + "\n"
        "\n=== TECHNICAL INDICATORS (CALCULATED) ===\n"
        "RSI(14): " + str(rsi) + " | SMA20: $" + str(s20) + "\n"
        "Support: $" + str(s) + " | Resistance: $" + str(r) + "\n"
        "20-day trend: " + str(tech.get("trend", "N/A")) + " | Bias: " + str(tech.get("bias", "N/A")) + "\n"
        "\n=== MACRO CONTEXT ===\n"
        "Macro bias: " + str(macro.get("macro_bias", "N/A")) + " (" + str(macro.get("confidence", 0)) + "%)\n"
        "Key drivers: " + str(macro.get("key_drivers", [])) + "\n"
        "Analysis: " + str(macro.get("analysis", "")) + "\n"
        "\n=== LATEST NEWS (use these!) ===\n"
        + "\n".join(["- " + n for n in top_news])
    )

def run_debate(macro_data, tech_data, price_data, news_data=None):
    if news_data is None:
        news_data = {}
    context = _ctx(macro_data, tech_data, price_data, news_data)
    history, bull_scores, bear_scores = [], [], []

    # Round 1
    bull_msg = chat(
        context + "\n\nMake your BULL case. Be specific. Last line must be: Confidence: XX%",
        model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.75
    )
    bear_msg = chat(
        context + "\n\nMake your BEAR case. Be specific. Last line must be: Confidence: XX%",
        model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.75
    )
    bs1, br1 = extract_confidence(bull_msg), extract_confidence(bear_msg)
    bull_scores.append(bs1); bear_scores.append(br1)
    history.append({"round": 1, "bull": bull_msg, "bear": bear_msg})
    print("      Round 1 -- Bull: " + str(bs1) + "% | Bear: " + str(br1) + "%")

    # Round 2
    bull_msg2 = chat(
        context + "\n\nBEAR argued:\n" + bear_msg[-600:] +
        "\n\nDIRECTLY REFUTE the bear. Strengthen your bull case with NEW points. Last line: Confidence: XX%",
        model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.7
    )
    bear_msg2 = chat(
        context + "\n\nBULL argued:\n" + bull_msg[-600:] +
        "\n\nDIRECTLY REFUTE the bull. Strengthen your bear case with NEW points. Last line: Confidence: XX%",
        model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.7
    )
    bs2, br2 = extract_confidence(bull_msg2), extract_confidence(bear_msg2)
    bull_scores.append(bs2); bear_scores.append(br2)
    history.append({"round": 2, "bull": bull_msg2, "bear": bear_msg2})
    print("      Round 2 -- Bull: " + str(bs2) + "% | Bear: " + str(br2) + "%")

    # Round 3 - final verdict
    bull_msg3 = chat(
        context + "\n\nFINAL ROUND. Bear's best argument was:\n" + bear_msg2[-400:] +
        "\n\nGive your FINAL bull verdict. Be decisive. Last line: Confidence: XX%",
        model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.65
    )
    bear_msg3 = chat(
        context + "\n\nFINAL ROUND. Bull's best argument was:\n" + bull_msg2[-400:] +
        "\n\nGive your FINAL bear verdict. Be decisive. Last line: Confidence: XX%",
        model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.65
    )
    bs3, br3 = extract_confidence(bull_msg3), extract_confidence(bear_msg3)
    bull_scores.append(bs3); bear_scores.append(br3)
    history.append({"round": 3, "bull": bull_msg3, "bear": bear_msg3})
    print("      Round 3 -- Bull: " + str(bs3) + "% | Bear: " + str(br3) + "%")

    avg_bull = round(sum(bull_scores) / 3, 1)
    avg_bear = round(sum(bear_scores) / 3, 1)
    margin   = round(abs(avg_bull - avg_bear), 1)
    is_tie   = margin < 10
    winner   = "TIE" if is_tie else ("BULL" if avg_bull > avg_bear else "BEAR")

    return {
        "history":             history,
        "avg_bull_confidence": avg_bull,
        "avg_bear_confidence": avg_bear,
        "margin":              margin,
        "winner":              winner,
        "is_tie":              is_tie,
        "final_bull":          bull_msg3,
        "final_bear":          bear_msg3,
        "round_scores":        list(zip(bull_scores, bear_scores))
    }
