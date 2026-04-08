from utils.ollama_client import chat, extract_confidence
from config import MODEL_HEAVY

BULL_SYSTEM = """You are a veteran gold bull trader. XAU/USD specialist.
Build the STRONGEST case for gold RISING in 24-48h.
Use ALL data provided: price, RSI, trend, news headlines.
Be specific — reference actual prices and news.
Structure: 1) Primary catalyst  2) Technical confirmation  3) Why bears wrong  4) Price target
FINAL LINE MUST BE EXACTLY: Confidence: XX%
(honest number 45-85, not 50 unless truly neutral)"""

BEAR_SYSTEM = """You are a veteran gold bear trader. XAU/USD specialist.
Build the STRONGEST case for gold FALLING in 24-48h.
Use ALL data provided: price, RSI, trend, news headlines.
Be specific — reference actual prices and news.
Structure: 1) Primary catalyst  2) Technical breakdown  3) Why bulls wrong  4) Downside target
FINAL LINE MUST BE EXACTLY: Confidence: XX%
(honest number 45-85, not 50 unless truly neutral)"""

def _build_context(macro, tech, price, news):
    p   = price.get("price", 0)
    chg = price.get("change_pct", 0)
    h   = price.get("high", p)
    l   = price.get("low",  p)
    rsi = tech.get("rsi_value", "N/A")
    s   = tech.get("support", 0)
    r   = tech.get("resistance", 0)
    s20 = tech.get("sma20", "N/A")
    ni  = news.get("news_items", []) if news else []
    top = [x["title"] for x in ni[:8]]
    sent = news.get("sentiment", "NEUTRAL") if news else "NEUTRAL"
    summ = news.get("summary", "") if news else ""
    events = news.get("key_events", []) if news else []
    return (
        "=== LIVE MARKET DATA ===\n"
        "XAU/USD NOW: $" + str(p) + "\n"
        "Today change: " + str(chg) + "% | High: $" + str(h) + " | Low: $" + str(l) + "\n"
        "\n=== CALCULATED TECHNICAL INDICATORS ===\n"
        "RSI(14): " + str(rsi) + " | SMA20: $" + str(s20) + "\n"
        "Key support: $" + str(s) + " | Key resistance: $" + str(r) + "\n"
        "20-day trend: " + str(tech.get("trend","N/A")) + " | Technical bias: " + str(tech.get("bias","N/A")) + "\n"
        "\n=== MACRO CONTEXT ===\n"
        "Macro bias: " + str(macro.get("macro_bias","N/A")) + " (" + str(macro.get("confidence",0)) + "%)\n"
        "Key drivers: " + ", ".join(macro.get("key_drivers", [])) + "\n"
        "Macro analysis: " + str(macro.get("analysis","")) + "\n"
        "\n=== BREAKING NEWS (USE THESE IN YOUR ARGUMENT) ===\n"
        "Overall news sentiment for gold: " + sent + "\n"
        "Summary: " + summ + "\n"
        "Key events: " + ", ".join(events[:5]) + "\n"
        "Headlines:\n" + "\n".join(["- " + n for n in top])
    )

def run_debate(macro_data, tech_data, price_data, news_data=None):
    if news_data is None:
        news_data = {}
    ctx = _build_context(macro_data, tech_data, price_data, news_data)
    history, bull_scores, bear_scores = [], [], []

    bull1 = chat(ctx + "\n\nMake your BULL case. Reference the actual news above. Final line: Confidence: XX%",
                 model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.75)
    bear1 = chat(ctx + "\n\nMake your BEAR case. Reference the actual news above. Final line: Confidence: XX%",
                 model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.75)
    bs1, br1 = extract_confidence(bull1), extract_confidence(bear1)
    bull_scores.append(bs1); bear_scores.append(br1)
    history.append({"round": 1, "bull": bull1, "bear": bear1})
    print("      Round 1 -- Bull: " + str(bs1) + "% | Bear: " + str(br1) + "%")

    bull2 = chat(ctx + "\n\nBEAR ARGUED:\n" + bear1[-500:] +
                 "\n\nRefute the bear directly. New arguments only. Final line: Confidence: XX%",
                 model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.7)
    bear2 = chat(ctx + "\n\nBULL ARGUED:\n" + bull1[-500:] +
                 "\n\nRefute the bull directly. New arguments only. Final line: Confidence: XX%",
                 model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.7)
    bs2, br2 = extract_confidence(bull2), extract_confidence(bear2)
    bull_scores.append(bs2); bear_scores.append(br2)
    history.append({"round": 2, "bull": bull2, "bear": bear2})
    print("      Round 2 -- Bull: " + str(bs2) + "% | Bear: " + str(br2) + "%")

    bull3 = chat(ctx + "\n\nFINAL ROUND. Best bear argument: " + bear2[-300:] +
                 "\n\nFinal verdict. Be decisive. Commit to a direction. Final line: Confidence: XX%",
                 model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.65)
    bear3 = chat(ctx + "\n\nFINAL ROUND. Best bull argument: " + bull2[-300:] +
                 "\n\nFinal verdict. Be decisive. Commit to a direction. Final line: Confidence: XX%",
                 model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.65)
    bs3, br3 = extract_confidence(bull3), extract_confidence(bear3)
    bull_scores.append(bs3); bear_scores.append(br3)
    history.append({"round": 3, "bull": bull3, "bear": bear3})
    print("      Round 3 -- Bull: " + str(bs3) + "% | Bear: " + str(br3) + "%")

    avg_bull = round(sum(bull_scores) / 3, 1)
    avg_bear = round(sum(bear_scores) / 3, 1)
    margin   = round(abs(avg_bull - avg_bear), 1)
    is_tie   = margin < 8   # reducido de 10 a 8
    winner   = "TIE" if is_tie else ("BULL" if avg_bull > avg_bear else "BEAR")

    return {
        "history":             history,
        "avg_bull_confidence": avg_bull,
        "avg_bear_confidence": avg_bear,
        "margin":              margin,
        "winner":              winner,
        "is_tie":              is_tie,
        "final_bull":          bull3,
        "final_bear":          bear3,
        "round_scores":        list(zip(bull_scores, bear_scores)),
    }
