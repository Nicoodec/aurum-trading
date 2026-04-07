# agents/debate.py
from utils.ollama_client import chat, extract_confidence
from config import MODEL_HEAVY, DEBATE_ROUNDS

BULL_SYSTEM = """You are a seasoned gold bull analyst. Argue for XAU/USD price INCREASE in 24-48h.
Use: USD weakness, inflation, geopolitical risk, negative real rates, technical breakouts.
Structure: 1) Primary catalyst 2) Technical confirmation 3) Price target
IMPORTANT: You MUST end your response with exactly this format on the last line:
Confidence: XX%
Where XX is a number between 40 and 85."""

BEAR_SYSTEM = """You are a seasoned gold bear analyst. Argue for XAU/USD price DECREASE in 24-48h.
Use: USD strength, rising real rates, profit taking, technical breakdowns, hawkish Fed.
Structure: 1) Primary catalyst 2) Technical breakdown 3) Downside target
IMPORTANT: You MUST end your response with exactly this format on the last line:
Confidence: XX%
Where XX is a number between 40 and 85."""

def _build_context(macro, tech, price):
    p   = price.get('price', 0)
    chg = price.get('change_pct', 0)
    h   = price.get('high', p)
    l   = price.get('low', p)
    return (
        f"XAU/USD:  | Change: {chg}% | Range: -\n"
        f"Trend: {tech.get('trend')} | Support:  | Resistance: \n"
        f"RSI: {tech.get('rsi_zone')} | Technical bias: {tech.get('bias')}\n"
        f"Macro: {macro.get('macro_bias')} ({macro.get('confidence')}%) | {macro.get('analysis','')}\n"
        f"Drivers: {', '.join(macro.get('key_drivers', []))}"
    )

def run_debate(macro_data, tech_data, price_data):
    context = _build_context(macro_data, tech_data, price_data)
    history = []
    bull_scores, bear_scores = [], []

    bull_msg = chat(
        f"Market data:\n{context}\n\nMake your bull case. End with 'Confidence: XX%'",
        model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.7)
    bear_msg = chat(
        f"Market data:\n{context}\n\nMake your bear case. End with 'Confidence: XX%'",
        model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.7)
    bull_scores.append(extract_confidence(bull_msg))
    bear_scores.append(extract_confidence(bear_msg))
    history.append({'round': 1, 'bull': bull_msg, 'bear': bear_msg})
    print(f'      Round 1 -- Bull: {bull_scores[-1]}% | Bear: {bear_scores[-1]}%')

    for r in range(2, DEBATE_ROUNDS + 1):
        bull_msg = chat(
            f"Market data:\n{context}\n\nBear argued:\n{bear_msg[-800:]}\n\nRefute and strengthen bull case. End with 'Confidence: XX%'",
            model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.65)
        bear_msg = chat(
            f"Market data:\n{context}\n\nBull argued:\n{bull_msg[-800:]}\n\nRefute and strengthen bear case. End with 'Confidence: XX%'",
            model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.65)
        bull_scores.append(extract_confidence(bull_msg))
        bear_scores.append(extract_confidence(bear_msg))
        history.append({'round': r, 'bull': bull_msg, 'bear': bear_msg})
        print(f'      Round {r} -- Bull: {bull_scores[-1]}% | Bear: {bear_scores[-1]}%')

    avg_bull = sum(bull_scores) / len(bull_scores)
    avg_bear = sum(bear_scores) / len(bear_scores)
    margin   = abs(avg_bull - avg_bear)
    is_tie   = margin < 10
    winner   = 'TIE' if is_tie else ('BULL' if avg_bull > avg_bear else 'BEAR')

    return {
        'history':             history,
        'avg_bull_confidence': round(avg_bull, 1),
        'avg_bear_confidence': round(avg_bear, 1),
        'margin':              round(margin, 1),
        'winner':              winner,
        'is_tie':              is_tie,
        'final_bull':          history[-1]['bull'],
        'final_bear':          history[-1]['bear'],
        'round_scores':        list(zip(bull_scores, bear_scores))
    }
