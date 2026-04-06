# agents/arbitrator.py — decisión final
from utils.ollama_client import chat, extract_json
from config import MODEL_HEAVY, MACRO_EVENT_BUFFER_H

SYSTEM = """You are the final arbitrator for gold trading decisions.
You only approve trades when: debate is clear (no tie), R:R >= 1:2,
no major macro events within 2 hours, confidence is sufficient."""

def decide(debate_result, risk_plan, macro_data, news_data):
    # Regla: no operar si hay evento macro en menos de 2h
    scheduled = news_data.get('scheduled_events', [])
    imminent = [e for e in scheduled if isinstance(e, dict) and e.get('hours_away', 99) < MACRO_EVENT_BUFFER_H]
    if imminent:
        return {'decision': 'STAY OUT', 'reason': f'Macro event imminent: {imminent}', 'confidence': 0}

    # Regla: no operar si empate
    if debate_result.get('is_tie'):
        return {'decision': 'STAY OUT', 'reason': 'Debate ended in tie', 'confidence': 0}

    # Regla: riesgo inválido
    if not risk_plan.get('valid'):
        return {'decision': 'STAY OUT', 'reason': risk_plan.get('reason', 'Invalid risk plan'), 'confidence': 0}

    prompt = f"""Make final trading decision for XAU/USD.

Debate winner: {debate_result.get('winner')} (margin: {debate_result.get('margin')}%)
Bull confidence: {debate_result.get('avg_bull_confidence')}%
Bear confidence: {debate_result.get('avg_bear_confidence')}%
Direction: {risk_plan.get('direction')}
Entry: {risk_plan.get('entry')} | Stop: {risk_plan.get('stop_loss')} | Target: {risk_plan.get('take_profit')}
R:R: {risk_plan.get('risk_reward')} | Risk USD: {risk_plan.get('risk_usd')}
Macro bias: {macro_data.get('macro_bias')}
Scheduled events warning: {macro_data.get('scheduled_event_warning')}

Should we trade? Be decisive. Respond ONLY in JSON:
{{"decision": "LONG/SHORT/STAY OUT", "confidence": 75, "reason": "..."}}"""

    raw = chat(prompt, model=MODEL_HEAVY, system=SYSTEM, temperature=0.3)
    result = extract_json(raw)
    if not result or 'decision' not in result:
        result = {'decision': 'STAY OUT', 'reason': 'Parse error — staying safe', 'confidence': 0}
    return result
