import os, json, requests, re
from dotenv import load_dotenv
load_dotenv()
OPENAI_KEY = os.getenv("OPENAI_API_KEY", "")

SYSTEM = """You are a senior gold (XAU/USD) macro analyst for a prop trading firm.
Your job is to evaluate whether current news and macro conditions SUPPORT, are NEUTRAL toward,
or should VETO a proposed trade direction.

Rules:
- CONFIRM: News and macro clearly support the trade direction
- NEUTRAL: No strong evidence either way — let technical signal decide
- VETO: Strong macro/news reason to NOT take this trade right now

You must be decisive. NEUTRAL is the default when uncertain.
Respond ONLY in valid JSON."""

def analyze(direction, news_items, fred_data, delta_items=None):
    """
    direction: "LONG" or "SHORT"
    Returns: {"verdict": "CONFIRM"|"NEUTRAL"|"VETO", "confidence": 0-100, "reason": str}
    """
    if not OPENAI_KEY:
        return {"verdict": "NEUTRAL", "confidence": 50,
                "reason": "No OpenAI key — defaulting to NEUTRAL"}

    # Build news context
    all_items = list(news_items or [])
    delta     = list(delta_items or [])

    delta_str = chr(10).join([
        "  [BLOOMBERG/DELTAONE] " + i["title"]
        for i in delta[:8]
    ]) if delta else "  None"

    other_str = chr(10).join([
        "  [" + i.get("source","NEWS") + "] " + i["title"]
        for i in all_items if i.get("source") != "DeltaOne"
    ][:8]) if all_items else "  None"

    # FRED interpretation
    dxy  = fred_data.get("dxy")
    t10  = fred_data.get("t10y")
    t2   = fred_data.get("t2y")
    fed  = fred_data.get("fedfunds")

    fred_lines = []
    if dxy:
        if dxy > 108:   fred_lines.append(f"DXY={round(dxy,1)} — VERY STRONG dollar (bearish gold)")
        elif dxy > 104: fred_lines.append(f"DXY={round(dxy,1)} — strong dollar (bearish gold)")
        elif dxy < 98:  fred_lines.append(f"DXY={round(dxy,1)} — weak dollar (bullish gold)")
        else:           fred_lines.append(f"DXY={round(dxy,1)} — neutral dollar")
    if t10:
        if t10 > 4.5:   fred_lines.append(f"10Y={t10}% — high yields (bearish gold)")
        elif t10 < 3.5: fred_lines.append(f"10Y={t10}% — low yields (bullish gold)")
        else:           fred_lines.append(f"10Y={t10}% — moderate yields")
    if t2 and t10:
        spread = round(t10 - t2, 2)
        fred_lines.append(f"Yield curve spread: {spread}% ({'inverted - recession risk' if spread < 0 else 'normal'})")
    if fed:
        fred_lines.append(f"Fed Funds: {fed}%")

    fred_str = chr(10).join(["  " + l for l in fred_lines]) if fred_lines else "  No FRED data"

    q = chr(34)
    schema = (
        "{" + q+"verdict"+q+":"+q+"CONFIRM"+q+"," +
        q+"confidence"+q+":75," +
        q+"reason"+q+":"+q+"specific reason referencing data"+q +
        "}"
    )

    prompt = chr(10).join([
        f"Proposed trade direction: {direction} XAU/USD",
        "",
        "FRED MACRO DATA:",
        fred_str,
        "",
        "DELTAONE BLOOMBERG FEED (real-time):",
        delta_str,
        "",
        "OTHER FINANCIAL NEWS:",
        other_str,
        "",
        "Based on the above, should we CONFIRM, stay NEUTRAL, or VETO this " + direction + " trade?",
        "",
        "CONFIRM if: macro and news clearly support " + direction,
        "NEUTRAL if: mixed signals or insufficient information",
        "VETO if: strong macro/news reason against " + direction,
        "",
        "Reference specific data (DXY level, headlines) in your reason.",
        "Respond ONLY in JSON: " + schema,
    ])

    try:
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer " + OPENAI_KEY,
                     "Content-Type": "application/json"},
            json={
                "model":           "gpt-4o-mini",
                "messages":        [{"role": "system", "content": SYSTEM},
                                    {"role": "user",   "content": prompt}],
                "temperature":     0.2,
                "response_format": {"type": "json_object"},
            },
            timeout=20,
        )
        data = r.json()
        if "error" in data:
            print("[news_filter] API error:", data["error"].get("message","")[:80])
            return {"verdict": "NEUTRAL", "confidence": 50, "reason": "API error"}
        content = data["choices"][0]["message"]["content"]
        result  = json.loads(content)
        verdict = result.get("verdict", "NEUTRAL").upper()
        if verdict not in ("CONFIRM", "NEUTRAL", "VETO"):
            verdict = "NEUTRAL"
        return {
            "verdict":    verdict,
            "confidence": int(result.get("confidence", 50)),
            "reason":     str(result.get("reason", ""))[:300],
        }
    except Exception as e:
        print("[news_filter] error:", e)
        return {"verdict": "NEUTRAL", "confidence": 50, "reason": str(e)[:100]}
