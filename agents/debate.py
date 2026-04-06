# agents/debate.py — Bull Case vs Bear Case, 3 rounds
from utils.ollama_client import chat, extract_confidence
from config import MODEL_HEAVY, DEBATE_ROUNDS

BULL_SYSTEM = """You are a gold BULL analyst. Your job: argue for a price INCREASE
in XAU/USD in the next 24-48 hours. Be specific, use data provided.
End every response with: Confidence: X% (0-100)"""

BEAR_SYSTEM = """You are a gold BEAR analyst. Your job: argue for a price DECREASE
in XAU/USD in the next 24-48 hours. Attack the bull's weak points.
Be specific, use data provided.
End every response with: Confidence: X% (0-100)"""

def run_debate(macro_data, tech_data, price_data):
    context = f"""XAU/USD: {price_data.get('price')}
Macro bias: {macro_data.get('macro_bias')} (confidence {macro_data.get('confidence')}%)
Macro drivers: {macro_data.get('key_drivers')}
Technical trend: {tech_data.get('trend')}, Support: {tech_data.get('support')}, Resistance: {tech_data.get('resistance')}
Technical bias: {tech_data.get('bias')} (confidence {tech_data.get('confidence')}%)"""

    history = []
    bull_scores, bear_scores = [], []

    # Round 1: Both open independently
    bull_msg = chat(f"Context:\n{context}\n\nMake your opening bull case for gold.", model=MODEL_HEAVY, system=BULL_SYSTEM)
    bear_msg = chat(f"Context:\n{context}\n\nMake your opening bear case for gold.", model=MODEL_HEAVY, system=BEAR_SYSTEM)
    bull_scores.append(extract_confidence(bull_msg))
    bear_scores.append(extract_confidence(bear_msg))
    history.append({'round': 1, 'bull': bull_msg, 'bear': bear_msg})

    # Rounds 2-3: Each responds to the other
    for r in range(2, DEBATE_ROUNDS + 1):
        bull_msg = chat(f"Context:\n{context}\n\nBear said:\n{bear_msg}\n\nRefute and strengthen your bull case.", model=MODEL_HEAVY, system=BULL_SYSTEM)
        bear_msg = chat(f"Context:\n{context}\n\nBull said:\n{bull_msg}\n\nRefute and strengthen your bear case.", model=MODEL_HEAVY, system=BEAR_SYSTEM)
        bull_scores.append(extract_confidence(bull_msg))
        bear_scores.append(extract_confidence(bear_msg))
        history.append({'round': r, 'bull': bull_msg, 'bear': bear_msg})

    avg_bull = sum(bull_scores) / len(bull_scores)
    avg_bear = sum(bear_scores) / len(bear_scores)
    margin = abs(avg_bull - avg_bear)
    winner = 'BULL' if avg_bull > avg_bear else 'BEAR'
    is_tie = margin < 10  # menos de 10 puntos = empate

    return {
        'history': history,
        'avg_bull_confidence': round(avg_bull, 1),
        'avg_bear_confidence': round(avg_bear, 1),
        'margin': round(margin, 1),
        'winner': 'TIE' if is_tie else winner,
        'is_tie': is_tie,
        'final_bull': history[-1]['bull'],
        'final_bear': history[-1]['bear']
    }
