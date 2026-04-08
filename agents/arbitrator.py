from utils.ollama_client import chat, extract_json
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
        "Final trading decision for XAU/USD.\n\n"
        "Debate winner: " + str(winner) + " (margin: " + str(margin) + "pts)\n"
        "Bull confidence: " + str(bull) + "% | Bear confidence: " + str(bear) + "%\n"
        "Direction: " + str(risk_plan.get("direction")) + "\n"
        "Entry: " + str(risk_plan.get("entry")) + " | SL: " + str(risk_plan.get("stop_loss")) + " | TP: " + str(risk_plan.get("take_profit")) + "\n"
        "R:R: " + str(rr) + " | Risk: $" + str(risk_plan.get("risk_usd")) + "\n"
        "Macro: " + str(macro_data.get("macro_bias")) + " (" + str(macro_data.get("confidence")) + "%)\n"
        "News sentiment: " + str(news_data.get("sentiment","NEUTRAL") if news_data else "NEUTRAL") + "\n\n"
        "This is a DEMO account. If debate is clear and R:R is good, APPROVE the trade.\n"
        "Respond ONLY raw JSON: {"decision": "LONG", "confidence": 72, "reason": "..."}"
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
