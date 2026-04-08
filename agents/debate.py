from utils.ollama_client import chat, extract_json, extract_confidence
from config import MODEL_HEAVY

BULL_SYSTEM = (
    "You are an elite gold BULL trader with 20 years on XAU/USD. "
    "You have access to real-time Bloomberg terminal data via DeltaOne. "
    "Build the STRONGEST possible case for gold RISING in the next 24-48 hours. "
    "Use ALL provided data: price levels, RSI, macro indicators (DXY, yields), "
    "and especially the breaking news headlines. "
    "Reference specific headlines and numbers in your argument. "
    "Be decisive and specific - no vague statements. "
    "Respond ONLY in JSON: {\"argument\": \"your detailed bull case\", \"confidence\": 72, \"target\": 4900}"
)

BEAR_SYSTEM = (
    "You are an elite gold BEAR trader with 20 years on XAU/USD. "
    "You have access to real-time Bloomberg terminal data via DeltaOne. "
    "Build the STRONGEST possible case for gold FALLING in the next 24-48 hours. "
    "Use ALL provided data: price levels, RSI, macro indicators (DXY, yields), "
    "and especially the breaking news headlines. "
    "Reference specific headlines and numbers in your argument. "
    "Be decisive and specific - no vague statements. "
    "Respond ONLY in JSON: {\"argument\": \"your detailed bear case\", \"confidence\": 68, \"target\": 4500}"
)

def _build_context(macro, tech, price, news):
    p    = price.get("price", 0)
    chg  = price.get("change_pct", 0)
    h    = price.get("high", p)
    l    = price.get("low", p)
    rsi  = tech.get("rsi_value", "N/A")
    s    = tech.get("support", 0)
    r    = tech.get("resistance", 0)
    s20  = tech.get("sma20", "N/A")
    t20  = tech.get("trend", "N/A")
    rz   = tech.get("rsi_zone", "N/A")

    fred = news.get("fred", {}) if news else {}
    dxy  = fred.get("dxy")
    t10  = fred.get("t10y")
    t2   = fred.get("t2y")
    fed  = fred.get("fedfunds")

    ni   = news.get("news_items", []) if news else []
    sent = news.get("sentiment", "NEUTRAL") if news else "NEUTRAL"
    summ = news.get("summary", "") if news else ""
    kevt = news.get("key_events", []) if news else []

    # Separar DeltaOne de otros
    delta_items = [x for x in ni if x.get("source") == "DeltaOne"]
    other_items = [x for x in ni if x.get("source") != "DeltaOne"]

    delta_str = chr(10).join([
        "  [" + ("BREAKING" if x.get("breaking") else "NEWS") + "] " + x["title"]
        for x in delta_items[:8]
    ]) if delta_items else "  No DeltaOne data available"

    other_str = chr(10).join([
        "  [" + x["source"] + "] " + x["title"]
        for x in other_items[:6]
    ]) if other_items else "  No other news"

    # DXY interpretation
    dxy_interp = ""
    if dxy:
        if dxy > 108:   dxy_interp = " (VERY STRONG dollar - BEARISH for gold)"
        elif dxy > 104: dxy_interp = " (strong dollar - bearish for gold)"
        elif dxy > 100: dxy_interp = " (mild dollar strength)"
        elif dxy > 96:  dxy_interp = " (mild dollar weakness - bullish for gold)"
        else:           dxy_interp = " (WEAK dollar - BULLISH for gold)"

    # Yield interpretation
    yield_interp = ""
    if t10:
        if t10 > 4.5:   yield_interp = " (high real rates - BEARISH gold)"
        elif t10 > 4.0: yield_interp = " (elevated rates - mildly bearish gold)"
        elif t10 > 3.5: yield_interp = " (moderate rates - neutral)"
        else:           yield_interp = " (low rates - BULLISH gold)"

    # RSI interpretation
    rsi_interp = ""
    if rsi and isinstance(rsi, (int, float)):
        if rsi > 75:   rsi_interp = " SEVERELY OVERBOUGHT - high reversal risk"
        elif rsi > 70: rsi_interp = " OVERBOUGHT - caution on longs"
        elif rsi < 25: rsi_interp = " SEVERELY OVERSOLD - high bounce risk"
        elif rsi < 30: rsi_interp = " OVERSOLD - caution on shorts"
        else:          rsi_interp = " neutral momentum"

    lines = [
        "=" * 55,
        "LIVE MARKET DATA",
        "=" * 55,
        "XAU/USD: $" + str(p) + " | Change: " + str(chg) + "%",
        "Today range: $" + str(l) + " - $" + str(h),
        "",
        "TECHNICAL INDICATORS (calculated)",
        "RSI(14): " + str(rsi) + rsi_interp,
        "SMA20:   $" + str(s20) + " | Price vs SMA: " + ("ABOVE" if p and s20 and p > s20 else "BELOW"),
        "Trend 20d: " + str(t20),
        "Key support:    $" + str(s),
        "Key resistance: $" + str(r),
        "",
        "MACRO DATA (FRED - real-time)",
        "DXY (USD index): " + (str(round(dxy,2)) if dxy else "N/A") + dxy_interp,
        "10Y Treasury:    " + (str(t10) + "%" if t10 else "N/A") + yield_interp,
        "2Y Treasury:     " + (str(t2) + "%" if t2 else "N/A"),
        "Fed Funds Rate:  " + (str(fed) + "%" if fed else "N/A"),
        "Yield curve (10Y-2Y): " + (str(round(t10-t2,2))+"%" if t10 and t2 else "N/A"),
        "",
        "MACRO ANALYST ASSESSMENT",
        "Bias: " + str(macro.get("macro_bias","N/A")) + " (" + str(macro.get("confidence",0)) + "% confidence)",
        "Key drivers: " + ", ".join(macro.get("key_drivers",[])[:4]),
        "Analysis: " + str(macro.get("analysis","")),
        "",
        "NEWS SENTIMENT: " + sent,
        "Summary: " + summ,
        "Key events: " + ", ".join(kevt[:4]),
        "",
        "DELTAONE BLOOMBERG TERMINAL FEED (real-time)",
        delta_str,
        "",
        "OTHER FINANCIAL NEWS",
        other_str,
        "=" * 55,
        "Use the DeltaOne headlines as your primary news source.",
        "Reference specific numbers (DXY=" + str(round(dxy,1) if dxy else "N/A") + ", RSI=" + str(rsi) + ") in your argument.",
        "Your confidence score must reflect the ACTUAL balance of evidence above.",
    ]
    return chr(10).join(lines)

def _parse(raw, fallback):
    result = extract_json(raw)
    if result and "confidence" in result:
        c = int(result["confidence"])
        if 35 <= c <= 95:
            return str(result.get("argument", raw[:400])), c
    c = extract_confidence(raw)
    return raw[:400], (c if c != 57 else fallback)

def _compute_bases(macro, tech, news):
    """Compute informed bull/bear base confidences from real data."""
    fred = news.get("fred", {}) if news else {}
    dxy  = fred.get("dxy") or 100
    t10  = fred.get("t10y") or 4.0
    rsi  = float(tech.get("rsi_value", 50) or 50)
    sent = news.get("sentiment", "NEUTRAL") if news else "NEUTRAL"
    mb   = macro.get("macro_bias", "NEUTRAL")
    mc   = macro.get("confidence", 50)

    # Bull score: accumulate points
    bull_pts = 50
    if sent == "BULLISH_GOLD":  bull_pts += 10
    if sent == "BEARISH_GOLD":  bull_pts -= 10
    if mb == "BULLISH":         bull_pts += int(mc * 0.15)
    if mb == "BEARISH":         bull_pts -= int(mc * 0.15)
    if dxy < 98:                bull_pts += 8   # weak dollar
    if dxy > 106:               bull_pts -= 10  # strong dollar
    if t10 < 3.5:               bull_pts += 6   # low yields
    if t10 > 4.5:               bull_pts -= 8   # high yields
    if rsi < 30:                bull_pts += 8   # oversold bounce
    if rsi > 70:                bull_pts -= 6   # overbought

    # Bear score: mirror + own adjustments
    bear_pts = 50
    if sent == "BEARISH_GOLD":  bear_pts += 10
    if sent == "BULLISH_GOLD":  bear_pts -= 10
    if mb == "BEARISH":         bear_pts += int(mc * 0.15)
    if mb == "BULLISH":         bear_pts -= int(mc * 0.15)
    if dxy > 106:               bear_pts += 10  # strong dollar
    if dxy < 98:                bear_pts -= 8   # weak dollar
    if t10 > 4.5:               bear_pts += 8   # high yields
    if t10 < 3.5:               bear_pts -= 6   # low yields
    if rsi > 73:                bear_pts += 10  # overbought = bear opportunity
    if rsi < 30:                bear_pts -= 8   # oversold = not time to short

    # Clamp to reasonable range
    bull_base = max(42, min(82, bull_pts))
    bear_base = max(42, min(82, bear_pts))

    # Guarantee they are never identical
    if bull_base == bear_base:
        if mb == "BULLISH":
            bull_base += 4
        else:
            bear_base += 4

    return bull_base, bear_base

def _compute_tie_threshold(macro, tech, news):
    """Dynamic tie threshold: tighter when data is clear, looser when ambiguous."""
    fred = news.get("fred", {}) if news else {}
    dxy  = fred.get("dxy") or 100
    t10  = fred.get("t10y") or 4.0
    sent = news.get("sentiment", "NEUTRAL") if news else "NEUTRAL"
    mb   = macro.get("macro_bias", "NEUTRAL")

    clarity_score = 0
    if sent in ("BULLISH_GOLD", "BEARISH_GOLD"): clarity_score += 2
    if mb in ("BULLISH", "BEARISH"):             clarity_score += 1
    if dxy < 96 or dxy > 108:                   clarity_score += 1
    if t10 < 3.5 or t10 > 4.8:                  clarity_score += 1

    # More clear data = lower threshold needed to declare winner
    if clarity_score >= 4: return 3   # very clear: 3pts margin enough
    if clarity_score >= 2: return 5   # moderately clear: 5pts
    return 7                           # ambiguous: need 7pts

def run_debate(macro_data, tech_data, price_data, news_data=None):
    if news_data is None: news_data = {}

    ctx = _build_context(macro_data, tech_data, price_data, news_data)
    bull_base, bear_base = _compute_bases(macro_data, tech_data, news_data)
    tie_threshold = _compute_tie_threshold(macro_data, tech_data, news_data)

    print("      [debate] Bull base: " + str(bull_base) + "% | Bear base: " + str(bear_base) + "% | Tie threshold: " + str(tie_threshold) + "pts")

    hs, bls, brs = [], [], []

    # Round 1 - opening arguments
    r1b = chat(
        ctx + chr(10) + chr(10) + "Make your decisive BULL case now. Reference specific data above. JSON only.",
        model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.82
    )
    r1r = chat(
        ctx + chr(10) + chr(10) + "Make your decisive BEAR case now. Reference specific data above. JSON only.",
        model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.82
    )
    a1b, s1b = _parse(r1b, bull_base)
    a1r, s1r = _parse(r1r, bear_base)
    bls.append(s1b); brs.append(s1r)
    hs.append({"round": 1, "bull": a1b, "bear": a1r})
    print("      Round 1 -- Bull: " + str(s1b) + "% | Bear: " + str(s1r) + "%")

    # Round 2 - rebuttals
    r2b = chat(
        ctx + chr(10) + chr(10) +
        "BEAR ARGUED: " + a1r[:350] + chr(10) + chr(10) +
        "Now DIRECTLY REFUTE the bear. Address their specific points. Use new evidence from the data. JSON only.",
        model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.78
    )
    r2r = chat(
        ctx + chr(10) + chr(10) +
        "BULL ARGUED: " + a1b[:350] + chr(10) + chr(10) +
        "Now DIRECTLY REFUTE the bull. Address their specific points. Use new evidence from the data. JSON only.",
        model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.78
    )
    a2b, s2b = _parse(r2b, bull_base)
    a2r, s2r = _parse(r2r, bear_base)
    bls.append(s2b); brs.append(s2r)
    hs.append({"round": 2, "bull": a2b, "bear": a2r})
    print("      Round 2 -- Bull: " + str(s2b) + "% | Bear: " + str(s2r) + "%")

    # Round 3 - final verdict
    r3b = chat(
        ctx + chr(10) + chr(10) +
        "FINAL ROUND. Bear best point: " + a2r[:250] + chr(10) + chr(10) +
        "Give your FINAL decisive verdict. Commit to a direction and price target. JSON only.",
        model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.72
    )
    r3r = chat(
        ctx + chr(10) + chr(10) +
        "FINAL ROUND. Bull best point: " + a2b[:250] + chr(10) + chr(10) +
        "Give your FINAL decisive verdict. Commit to a direction and price target. JSON only.",
        model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.72
    )
    a3b, s3b = _parse(r3b, bull_base)
    a3r, s3r = _parse(r3r, bear_base)
    bls.append(s3b); brs.append(s3r)
    hs.append({"round": 3, "bull": a3b, "bear": a3r})
    print("      Round 3 -- Bull: " + str(s3b) + "% | Bear: " + str(s3r) + "%")

    avg_bull = round(sum(bls) / 3, 1)
    avg_bear = round(sum(brs) / 3, 1)
    margin   = round(abs(avg_bull - avg_bear), 1)
    is_tie   = margin < tie_threshold
    winner   = "TIE" if is_tie else ("BULL" if avg_bull > avg_bear else "BEAR")

    print("      Winner: " + winner + " | Margin: " + str(margin) + "pts | Threshold: " + str(tie_threshold) + "pts")

    return {
        "history":             hs,
        "avg_bull_confidence": avg_bull,
        "avg_bear_confidence": avg_bear,
        "margin":              margin,
        "winner":              winner,
        "is_tie":              is_tie,
        "tie_threshold":       tie_threshold,
        "bull_base":           bull_base,
        "bear_base":           bear_base,
        "final_bull":          a3b,
        "final_bear":          a3r,
        "round_scores":        list(zip(bls, brs)),
    }
