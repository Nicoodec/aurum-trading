from utils.ollama_client import chat, extract_json
from config import MODEL_HEAVY, MACRO_EVENT_BUFFER_H

SYSTEM = (
    'You are the final arbitrator for XAU/USD gold trading on FTMO demo. '
    'Rules: Approve if debate has clear winner AND RR >= 2.0. '
    'On DEMO: be willing to trade when signals are reasonably clear. '
    'Block only if macro event imminent or deadlocked debate.'
)

def decide(debate_result, risk_plan, macro_data, news_data):
    scheduled = news_data.get('scheduled_events', []) if news_data else []
    imminent = [e for e in scheduled if isinstance(e, dict) and e.get('hours_away', 99) < MACRO_EVENT_BUFFER_H]
    if imminent:
        return {'decision': 'STAY OUT', 'reason': 'Macro event imminent: ' + str(imminent), 'confidence': 0}
    if debate_result.get('is_tie'):
        return {'decision': 'STAY OUT', 'reason': 'Debate tie (margin ' + str(debate_result.get('margin')) + 'pts)', 'confidence': 0}
    if not risk_plan.get('valid'):
        return {'decision': 'STAY OUT', 'reason': risk_plan.get('reason', 'Invalid risk plan'), 'confidence': 0}
    winner = debate_result.get('winner')
    bull   = debate_result.get('avg_bull_confidence', 50)
    bear   = debate_result.get('avg_bear_confidence', 50)
    margin = debate_result.get('margin', 0)
    rr     = risk_plan.get('risk_reward', 0)
    p = []
    p.append('Final trading decision for XAU/USD.')
    p.append('Debate winner: ' + str(winner) + ' (margin: ' + str(margin) + 'pts)')
    p.append('Bull conf: ' + str(bull) + '% | Bear conf: ' + str(bear) + '%')
    p.append('Direction: ' + str(risk_plan.get('direction')))
    p.append('Entry: ' + str(risk_plan.get('entry')) + ' | SL: ' + str(risk_plan.get('stop_loss')) + ' | TP: ' + str(risk_plan.get('take_profit')))
    p.append('RR: ' + str(rr) + ' | Risk: $' + str(risk_plan.get('risk_usd')))
    p.append('Macro: ' + str(macro_data.get('macro_bias')) + ' (' + str(macro_data.get('confidence')) + '%)')
    p.append('News sentiment: ' + str(news_data.get('sentiment', 'NEUTRAL') if news_data else 'NEUTRAL'))
    p.append('')
    p.append('This is a DEMO account. Approve if signals are clear and RR is good.')
    p.append('Respond ONLY raw JSON: {"decision": "LONG", "confidence": 72, "reason": "..."}')
    prompt = chr(10).join(p)
    raw    = chat(prompt, model=MODEL_HEAVY, system=SYSTEM, temperature=0.3)
    result = extract_json(raw)
    if not result or 'decision' not in result:
        direction = risk_plan.get('direction', '')
        if winner == 'BULL' and direction == 'LONG':
            return {'decision': 'LONG',  'confidence': int(bull), 'reason': 'Bull debate winner'}
        elif winner == 'BEAR' and direction == 'SHORT':
            return {'decision': 'SHORT', 'confidence': int(bear), 'reason': 'Bear debate winner'}
        return {'decision': 'STAY OUT', 'confidence': 0, 'reason': 'Parse error'}
    return result
