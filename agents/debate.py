from utils.ollama_client import chat, extract_json, extract_confidence
from config import MODEL_HEAVY

BULL_SYSTEM = (
    "You are an aggressive gold BULL trader. XAU/USD specialist. "
    "Your job: argue decisively why gold will RISE. Use the news and data. "
    "Be specific and confident. Do NOT be neutral. "
    "Respond ONLY in JSON: {\"argument\": \"your case\", \"confidence\": 72, \"target\": 4900}"
)

BEAR_SYSTEM = (
    "You are an aggressive gold BEAR trader. XAU/USD specialist. "
    "Your job: argue decisively why gold will FALL. Use the news and data. "
    "Be specific and confident. Do NOT be neutral. "
    "Respond ONLY in JSON: {\"argument\": \"your case\", \"confidence\": 68, \"target\": 4500}"
)

def _ctx(macro, tech, price, news):
    p   = price.get("price", 0)
    chg = price.get("change_pct", 0)
    h   = price.get("high", p)
    l   = price.get("low", p)
    rsi = tech.get("rsi_value", "N/A")
    s   = tech.get("support", 0)
    r   = tech.get("resistance", 0)
    s20 = tech.get("sma20", "N/A")
    ni  = news.get("news_items", []) if news else []
    hl  = chr(10).join(["- ["+x["source"]+"] "+x["title"] for x in ni[:10]]) if ni else "No news"
    sent = news.get("sentiment", "NEUTRAL") if news else "NEUTRAL"
    fred = news.get("fred", {}) if news else {}
    dxy  = fred.get("dxy")
    t10  = fred.get("t10y")
    return chr(10).join([
        "=== LIVE MARKET DATA ===",
        "XAU/USD: $"+str(p)+" | Change: "+str(chg)+"% | High: $"+str(h)+" | Low: $"+str(l),
        "RSI(14): "+str(rsi)+" | SMA20: $"+str(s20)+" | Trend: "+str(tech.get("trend")),
        "Support: $"+str(s)+" | Resistance: $"+str(r),
        "Macro: "+str(macro.get("macro_bias"))+" ("+str(macro.get("confidence"))+"%) | Drivers: "+str(macro.get("key_drivers",[])),
        "DXY: "+str(dxy)+" | 10Y Treasury: "+str(t10)+"%",
        "News sentiment: "+sent,
        "=== BREAKING HEADLINES ===",
        hl,
        "",
        "Give a STRONG, DECISIVE argument. Pick a clear side. Your confidence should reflect real market conviction."
    ])

def _parse(raw, fallback):
    r = extract_json(raw)
    if r and "confidence" in r:
        c = int(r["confidence"])
        if 35 <= c <= 95:
            return str(r.get("argument", raw[:300])), c
    c = extract_confidence(raw)
    return raw[:300], (c if c != 57 else fallback)

def run_debate(macro_data, tech_data, price_data, news_data=None):
    if news_data is None: news_data = {}
    ctx  = _ctx(macro_data, tech_data, price_data, news_data)
    sent = news_data.get("sentiment", "NEUTRAL")
    mb   = macro_data.get("macro_bias", "NEUTRAL")
    rsi  = float(tech_data.get("rsi_value", 50) or 50)
    fred = news_data.get("fred", {})
    dxy  = fred.get("dxy") or 100
    t10  = fred.get("t10y") or 4.0

    # Bases informadas por datos reales
    # Bull base: informado por sentimiento y macro
    if sent == "BULLISH_GOLD" or mb == "BULLISH":
        bull_base = 67
    elif mb == "BEARISH":
        bull_base = 46
    else:
        bull_base = 54

    # Bear base: informado por RSI, DXY y yields - siempre diferente de bull_base
    if sent == "BEARISH_GOLD" or (rsi > 72) or (dxy > 105 and t10 > 4.5):
        bear_base = 71  # condiciones claramente bearish
    elif rsi > 68 or dxy > 103:
        bear_base = 63  # condiciones moderadamente bearish
    else:
        bear_base = 49  # condiciones neutrales-bullish

    # Garantizar que nunca sean identicos
    if bull_base == bear_base:
        bear_base += 3

    hs, bls, brs = [], [], []

    r1b = chat(ctx+chr(10)+"Make your decisive BULL case. JSON only.", model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.82)
    r1r = chat(ctx+chr(10)+"Make your decisive BEAR case. JSON only.", model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.82)
    a1b, s1b = _parse(r1b, bull_base)
    a1r, s1r = _parse(r1r, bear_base)
    bls.append(s1b); brs.append(s1r)
    hs.append({"round":1,"bull":a1b,"bear":a1r})
    print("      Round 1 -- Bull: "+str(s1b)+"% | Bear: "+str(s1r)+"%")

    r2b = chat(ctx+chr(10)+"Bear argued: "+a1r[:300]+chr(10)+"Refute directly with NEW points. JSON only.", model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.78)
    r2r = chat(ctx+chr(10)+"Bull argued: "+a1b[:300]+chr(10)+"Refute directly with NEW points. JSON only.", model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.78)
    a2b, s2b = _parse(r2b, bull_base)
    a2r, s2r = _parse(r2r, bear_base)
    bls.append(s2b); brs.append(s2r)
    hs.append({"round":2,"bull":a2b,"bear":a2r})
    print("      Round 2 -- Bull: "+str(s2b)+"% | Bear: "+str(s2r)+"%")

    r3b = chat(ctx+chr(10)+"FINAL ROUND. Best bear point: "+a2r[:200]+chr(10)+"Final decisive verdict. JSON only.", model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.72)
    r3r = chat(ctx+chr(10)+"FINAL ROUND. Best bull point: "+a2b[:200]+chr(10)+"Final decisive verdict. JSON only.", model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.72)
    a3b, s3b = _parse(r3b, bull_base)
    a3r, s3r = _parse(r3r, bear_base)
    bls.append(s3b); brs.append(s3r)
    hs.append({"round":3,"bull":a3b,"bear":a3r})
    print("      Round 3 -- Bull: "+str(s3b)+"% | Bear: "+str(s3r)+"%")

    ab = round(sum(bls)/3, 1)
    ar = round(sum(brs)/3, 1)
    mg = round(abs(ab-ar), 1)
    tie = mg < 3
    win = "TIE" if tie else ("BULL" if ab > ar else "BEAR")

    return {
        "history": hs, "avg_bull_confidence": ab, "avg_bear_confidence": ar,
        "margin": mg, "winner": win, "is_tie": tie,
        "final_bull": a3b, "final_bear": a3r, "round_scores": list(zip(bls,brs))
    }
