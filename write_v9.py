import os, sys

files = {}

# ============================================================
# MAIN.PY — pasa news_data al debate, menos conservador en demo
# ============================================================
files['main.py'] = '''import json, os
from datetime import datetime
from agents.news_collector import collect as collect_news
from agents.price_feed import get_technical_data
from agents.macro_analyst import analyze as macro_analyze
from agents.technical_analyst import analyze as tech_analyze
from agents.debate import run_debate
from agents.risk_manager import calculate as risk_calc
from agents.arbitrator import decide
from agents.ftmo_validator import validate_before_trade
from utils.state_manager import save_cycle
from utils.github_sync import sync
from portfolio import add_position, get_stats
from config import MAX_POSITIONS
from gen_dashboard import generate as gen_html
from utils.state_manager import load_history

MT5_ENABLED  = True
MT5_LOGIN    = 1513020113
MT5_PASSWORD = "FH2dXFt7?"
MT5_SERVER   = "FTMO-Demo"

def run_cycle():
    print()
    print("=" * 52)
    print("AURUM CYCLE -- " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 52)

    stats = get_stats()
    print("[portfolio] Equity: $" + str(stats["equity"]) + " | Open: " + str(stats["open_positions"]) + "/" + str(MAX_POSITIONS))
    if stats["open_positions"] >= MAX_POSITIONS:
        print("[portfolio] MAX positions -- skipping")
        return None

    print("[1/7] Collecting news...")
    news = collect_news()
    ni = news.get("news_items", [])
    print("      Got " + str(len(ni)) + " news items | Sentiment: " + str(news.get("sentiment","NEUTRAL")))
    for n in ni[:5]:
        print("      >> [" + n["source"] + "] " + n["title"][:75])

    print("[2/7] Getting price feed...")
    price = get_technical_data()
    print("      XAU/USD: " + str(price.get("price")) + " | Change: " + str(price.get("change_pct")) + "% | H:" + str(price.get("high")) + " L:" + str(price.get("low")))

    print("[3/7] Macro analysis...")
    macro = macro_analyze(news, price)
    print("      Bias: " + str(macro.get("macro_bias")) + " (" + str(macro.get("confidence")) + "%)")
    print("      Drivers: " + str(macro.get("key_drivers", [])))

    print("[4/7] Technical analysis...")
    tech = tech_analyze(price)
    print("      Trend: " + str(tech.get("trend")) + " | RSI: " + str(tech.get("rsi_value")) + " | S:" + str(tech.get("support")) + " R:" + str(tech.get("resistance")))

    print("[5/7] Running debate 3 rounds...")
    debate = run_debate(macro, tech, price, news)
    bull = debate.get("avg_bull_confidence")
    bear = debate.get("avg_bear_confidence")
    print("      Winner: " + str(debate.get("winner")) + " | Bull: " + str(bull) + "% | Bear: " + str(bear) + "% | Margin: " + str(debate.get("margin")) + "pts")

    print("[6/7] Risk management...")
    account_info = None
    if MT5_ENABLED:
        try:
            from agents.mt5_broker import connect, get_account_summary, disconnect
            if connect(MT5_LOGIN, MT5_PASSWORD, MT5_SERVER):
                account_info = get_account_summary()
                disconnect()
        except Exception as e:
            print("      [MT5] account error: " + str(e))

    risk = risk_calc(debate, tech, price, account_info.get("balance") if account_info else None)
    if risk.get("valid"):
        print("      Dir: " + str(risk.get("direction")) + " | R:R: " + str(risk.get("risk_reward")) + " | Risk: $" + str(risk.get("risk_usd")) + " | Lots: " + str(risk.get("contracts")))
    else:
        print("      INVALID: " + str(risk.get("reason")))

    ftmo_check = validate_before_trade(risk, account_info)
    if not ftmo_check["approved"]:
        print("      [FTMO] BLOCKED: " + str(ftmo_check["reason"]))
        risk["valid"] = False
        risk["reason"] = ftmo_check["reason"]
    else:
        fs = ftmo_check["ftmo_status"]
        print("      [FTMO] OK | Daily: $" + str(fs["daily_remaining"]) + " | Total: $" + str(fs["total_remaining"]))

    print("[7/7] Arbitrator deciding...")
    final = decide(debate, risk, macro, news)
    decision = final.get("decision")
    print()
    print(">>> DECISION: " + str(decision) + " (conf: " + str(final.get("confidence")) + "%)")
    print("    " + str(final.get("reason")))

    ticket = None
    if risk.get("valid") and decision in ("LONG", "SHORT"):
        print("    Entry: " + str(risk.get("entry")) + " | SL: " + str(risk.get("stop_loss")) + " | TP: " + str(risk.get("take_profit")) + " | Lots: " + str(risk.get("contracts")))
        if MT5_ENABLED:
            try:
                from agents.mt5_broker import connect, open_trade, disconnect
                if connect(MT5_LOGIN, MT5_PASSWORD, MT5_SERVER):
                    lot_size = max(0.01, round(risk.get("contracts", 0.01), 2))
                    result = open_trade(decision, lot_size, risk["stop_loss"], risk["take_profit"])
                    if result:
                        ticket = result["ticket"]
                        print("    [MT5] ORDER PLACED ticket=" + str(ticket))
                    disconnect()
            except Exception as e:
                print("    [MT5] Error: " + str(e))

    cycle_data = {
        "ts":         datetime.now().isoformat(),
        "price":      price.get("price"),
        "change_pct": price.get("change_pct"),
        "decision":   decision,
        "confidence": final.get("confidence"),
        "reason":     final.get("reason"),
        "risk_plan":  risk,
        "mt5_ticket": ticket,
        "news_items": ni,
        "debate_summary": {
            "winner":    debate.get("winner"),
            "bull_conf": debate.get("avg_bull_confidence"),
            "bear_conf": debate.get("avg_bear_confidence"),
            "margin":    debate.get("margin"),
            "is_tie":    debate.get("is_tie"),
            "rounds":    debate.get("round_scores", []),
        },
        "macro": {
            "bias":       macro.get("macro_bias"),
            "confidence": macro.get("confidence"),
            "drivers":    macro.get("key_drivers"),
            "risks":      macro.get("risks"),
            "analysis":   macro.get("analysis"),
        },
        "technical": {
            "trend":      tech.get("trend"),
            "rsi_value":  tech.get("rsi_value"),
            "rsi_zone":   tech.get("rsi_zone"),
            "support":    tech.get("support"),
            "resistance": tech.get("resistance"),
            "sma20":      tech.get("sma20"),
            "bias":       tech.get("bias"),
        },
        "portfolio": stats,
    }

    if decision in ("LONG", "SHORT") and risk.get("valid"):
        add_position(cycle_data, ticket=ticket)
        print("    [portfolio] Position recorded")

    folder = save_cycle(cycle_data)
    history = load_history()
    gen_html(latest=cycle_data, history=history, stats=stats)
    print("[SAVED] " + str(folder))

    try:
        from utils.telegram_alerts import alert_decision
        alert_decision(cycle_data)
    except Exception as e:
        print("[telegram] " + str(e))

    sync("AURUM: " + str(decision) + " @ " + str(price.get("price")))
    return cycle_data

if __name__ == "__main__":
    run_cycle()
'''

# ============================================================
# AGENTS/DEBATE.PY — tie threshold 8pts, noticias en contexto
# ============================================================
files['agents/debate.py'] = '''from utils.ollama_client import chat, extract_confidence
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
        "=== LIVE MARKET DATA ===\\n"
        "XAU/USD NOW: $" + str(p) + "\\n"
        "Today change: " + str(chg) + "% | High: $" + str(h) + " | Low: $" + str(l) + "\\n"
        "\\n=== CALCULATED TECHNICAL INDICATORS ===\\n"
        "RSI(14): " + str(rsi) + " | SMA20: $" + str(s20) + "\\n"
        "Key support: $" + str(s) + " | Key resistance: $" + str(r) + "\\n"
        "20-day trend: " + str(tech.get("trend","N/A")) + " | Technical bias: " + str(tech.get("bias","N/A")) + "\\n"
        "\\n=== MACRO CONTEXT ===\\n"
        "Macro bias: " + str(macro.get("macro_bias","N/A")) + " (" + str(macro.get("confidence",0)) + "%)\\n"
        "Key drivers: " + ", ".join(macro.get("key_drivers", [])) + "\\n"
        "Macro analysis: " + str(macro.get("analysis","")) + "\\n"
        "\\n=== BREAKING NEWS (USE THESE IN YOUR ARGUMENT) ===\\n"
        "Overall news sentiment for gold: " + sent + "\\n"
        "Summary: " + summ + "\\n"
        "Key events: " + ", ".join(events[:5]) + "\\n"
        "Headlines:\\n" + "\\n".join(["- " + n for n in top])
    )

def run_debate(macro_data, tech_data, price_data, news_data=None):
    if news_data is None:
        news_data = {}
    ctx = _build_context(macro_data, tech_data, price_data, news_data)
    history, bull_scores, bear_scores = [], [], []

    bull1 = chat(ctx + "\\n\\nMake your BULL case. Reference the actual news above. Final line: Confidence: XX%",
                 model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.75)
    bear1 = chat(ctx + "\\n\\nMake your BEAR case. Reference the actual news above. Final line: Confidence: XX%",
                 model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.75)
    bs1, br1 = extract_confidence(bull1), extract_confidence(bear1)
    bull_scores.append(bs1); bear_scores.append(br1)
    history.append({"round": 1, "bull": bull1, "bear": bear1})
    print("      Round 1 -- Bull: " + str(bs1) + "% | Bear: " + str(br1) + "%")

    bull2 = chat(ctx + "\\n\\nBEAR ARGUED:\\n" + bear1[-500:] +
                 "\\n\\nRefute the bear directly. New arguments only. Final line: Confidence: XX%",
                 model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.7)
    bear2 = chat(ctx + "\\n\\nBULL ARGUED:\\n" + bull1[-500:] +
                 "\\n\\nRefute the bull directly. New arguments only. Final line: Confidence: XX%",
                 model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.7)
    bs2, br2 = extract_confidence(bull2), extract_confidence(bear2)
    bull_scores.append(bs2); bear_scores.append(br2)
    history.append({"round": 2, "bull": bull2, "bear": bear2})
    print("      Round 2 -- Bull: " + str(bs2) + "% | Bear: " + str(br2) + "%")

    bull3 = chat(ctx + "\\n\\nFINAL ROUND. Best bear argument: " + bear2[-300:] +
                 "\\n\\nFinal verdict. Be decisive. Commit to a direction. Final line: Confidence: XX%",
                 model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.65)
    bear3 = chat(ctx + "\\n\\nFINAL ROUND. Best bull argument: " + bull2[-300:] +
                 "\\n\\nFinal verdict. Be decisive. Commit to a direction. Final line: Confidence: XX%",
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
'''

# ============================================================
# AGENTS/ARBITRATOR.PY — menos restrictivo en demo
# ============================================================
files['agents/arbitrator.py'] = '''from utils.ollama_client import chat, extract_json
from config import MODEL_HEAVY, MACRO_EVENT_BUFFER_H

SYSTEM = """You are the final arbitrator for XAU/USD gold trading on FTMO demo account.
Rules:
- Only approve if debate has clear winner (not tie) AND R:R >= 2.0
- Block if major macro event within 2 hours
- On DEMO account: be willing to trade when signals are reasonably clear
- Do NOT be overly conservative on demo — we need to see the system in action
- LONG if bull case clearly dominates, SHORT if bear case clearly dominates"""

def decide(debate_result, risk_plan, macro_data, news_data):
    scheduled = news_data.get("scheduled_events", []) if news_data else []
    imminent = [e for e in scheduled if isinstance(e, dict) and e.get("hours_away", 99) < MACRO_EVENT_BUFFER_H]
    if imminent:
        return {"decision": "STAY OUT", "reason": "Macro event imminent: " + str(imminent), "confidence": 0}

    if debate_result.get("is_tie"):
        return {"decision": "STAY OUT", "reason": "Debate tie (margin " + str(debate_result.get("margin")) + "pts < 8pts threshold)", "confidence": 0}

    if not risk_plan.get("valid"):
        return {"decision": "STAY OUT", "reason": risk_plan.get("reason", "Invalid risk plan"), "confidence": 0}

    winner = debate_result.get("winner")
    bull   = debate_result.get("avg_bull_confidence", 50)
    bear   = debate_result.get("avg_bear_confidence", 50)
    margin = debate_result.get("margin", 0)
    rr     = risk_plan.get("risk_reward", 0)

    prompt = (
        "Final trading decision for XAU/USD.\\n\\n"
        "Debate winner: " + str(winner) + " (margin: " + str(margin) + "pts)\\n"
        "Bull confidence: " + str(bull) + "% | Bear confidence: " + str(bear) + "%\\n"
        "Direction: " + str(risk_plan.get("direction")) + "\\n"
        "Entry: " + str(risk_plan.get("entry")) + " | SL: " + str(risk_plan.get("stop_loss")) + " | TP: " + str(risk_plan.get("take_profit")) + "\\n"
        "R:R: " + str(rr) + " | Risk: $" + str(risk_plan.get("risk_usd")) + "\\n"
        "Macro: " + str(macro_data.get("macro_bias")) + " (" + str(macro_data.get("confidence")) + "%)\\n"
        "News sentiment: " + str(news_data.get("sentiment","NEUTRAL") if news_data else "NEUTRAL") + "\\n\\n"
        "This is a DEMO account. If debate is clear and R:R is good, APPROVE the trade.\\n"
        "Respond ONLY raw JSON: {\"decision\": \"LONG\", \"confidence\": 72, \"reason\": \"...\"}"
    )

    raw    = chat(prompt, model=MODEL_HEAVY, system=SYSTEM, temperature=0.3)
    result = extract_json(raw)
    if not result or "decision" not in result:
        direction = risk_plan.get("direction", "")
        if winner == "BULL" and direction == "LONG":
            return {"decision": "LONG",  "confidence": int(bull), "reason": "Bull debate winner, fallback approval"}
        elif winner == "BEAR" and direction == "SHORT":
            return {"decision": "SHORT", "confidence": int(bear), "reason": "Bear debate winner, fallback approval"}
        return {"decision": "STAY OUT", "confidence": 0, "reason": "Parse error"}
    return result
'''

# ============================================================
# AGENTS/MACRO_ANALYST.PY — usa noticias reales
# ============================================================
files['agents/macro_analyst.py'] = '''from utils.ollama_client import chat, extract_json
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
    headlines = "\\n".join(["- " + x["title"] for x in ni[:10]]) if ni else "No headlines"

    prompt = (
        "Macro analysis for XAU/USD gold trading.\\n\\n"
        "PRICE: $" + str(price) + " | Change: " + str(chg) + "% | H:" + str(h) + " L:" + str(l) + "\\n\\n"
        "NEWS SENTIMENT: " + sent + "\\n"
        "KEY EVENTS: " + str(events[:5]) + "\\n"
        "SUMMARY: " + summ + "\\n\\n"
        "HEADLINES:\\n" + headlines + "\\n\\n"
        "Based on this news, give a DECISIVE macro assessment for gold.\\n"
        "If news is bullish for gold (geopolitical risk, dollar weakness, inflation) -> BULLISH\\n"
        "If news is bearish for gold (dollar strength, rate hikes, risk-on) -> BEARISH\\n"
        "Only say NEUTRAL if truly mixed signals.\\n\\n"
        "Respond ONLY raw JSON:\\n"
        "{\"macro_bias\":\"BULLISH\",\"confidence\":70,\"key_drivers\":[\"driver1\",\"driver2\"],"
        "\"risks\":[\"risk1\"],\"scheduled_event_warning\":false,\"analysis\":\"2 sentence summary\"}"
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
'''

# ============================================================
# UTILS/GITHUB_SYNC.PY — no falla si no hay cambios
# ============================================================
files['utils/github_sync.py'] = '''import subprocess

def sync(message="AURUM cycle update"):
    try:
        subprocess.run(["git", "add", "-A"], check=True, capture_output=True)
        result = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True)
        if "nothing to commit" in result.stdout + result.stderr:
            print("[SYNC] Nothing to commit")
            return
        subprocess.run(["git", "push", "origin", "main"], check=True, capture_output=True)
        print("[SYNC] GitHub push OK")
    except subprocess.CalledProcessError as e:
        print("[SYNC] Git error:", e)
'''

for path, content in files.items():
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Written: " + path)

print("\nAll files written OK")
