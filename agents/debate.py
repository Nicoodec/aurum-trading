# agents/debate.py — prompts mejorados con contexto rico
from utils.ollama_client import chat, extract_confidence
from config import MODEL_HEAVY, DEBATE_ROUNDS

BULL_SYSTEM = """You are a seasoned gold bull analyst with 20 years experience.
Your job: build the strongest possible case for XAU/USD price INCREASE in 24-48h.

Gold rises with: USD weakness, inflation fears, geopolitical risk, negative real rates,
central bank buying, risk-off sentiment, ETF inflows, technical breakouts above resistance.

Structure your argument:
1. Primary catalyst (most important driver right now)
2. Technical confirmation (price action supporting the move)
3. Risk factors you acknowledge but discount
4. Price target and timeframe
End with: Confidence: X% (be honest, 40-85% range typical)"""

BEAR_SYSTEM = """You are a seasoned gold bear analyst with 20 years experience.
Your job: build the strongest possible case for XAU/USD price DECREASE in 24-48h.

Gold falls with: USD strength, rising real rates, risk-on sentiment, hawkish Fed,
profit taking after rallies, technical breakdowns below support, ETF outflows.

Structure your argument:
1. Primary catalyst for the decline
2. Technical breakdown signals
3. Why the bull case is wrong right now
4. Downside target and timeframe
End with: Confidence: X% (be honest, 40-85% range typical)"""

def _build_context(macro, tech, price):
    p      = price.get('price', 0)
    chg    = price.get('change_pct', 0)
    high   = price.get('high', 0)
    low    = price.get('low', 0)
    open_p = price.get('open', 0)
    return f"""=== MARKET DATA ===
XAU/USD Price: 
Today: Open  | High  | Low  | Change {chg}%
Day range:  -  (spread: )

=== TECHNICAL PICTURE ===
Trend: {tech.get('trend')} | RSI zone: {tech.get('rsi_zone')} | Bias: {tech.get('bias')}
Key support:  | Key resistance: 
Technical analysis: {tech.get('analysis','')}

=== MACRO ENVIRONMENT ===
Macro bias: {macro.get('macro_bias')} (confidence: {macro.get('confidence')}%)
Key drivers: {', '.join(macro.get('key_drivers', []))}
Risks: {', '.join(macro.get('risks', []))}
Macro summary: {macro.get('analysis','')}
Scheduled events warning: {macro.get('scheduled_event_warning', False)}"""

def run_debate(macro_data, tech_data, price_data):
    context = _build_context(macro_data, tech_data, price_data)
    history = []
    bull_scores, bear_scores = [], []

    # Ronda 1 — apertura independiente
    bull_msg = chat(
        f"{context}\n\nMake your opening bull case. Be specific about current price levels and catalysts.",
        model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.7)
    bear_msg = chat(
        f"{context}\n\nMake your opening bear case. Be specific about current price levels and catalysts.",
        model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.7)
    bull_scores.append(extract_confidence(bull_msg))
    bear_scores.append(extract_confidence(bear_msg))
    history.append({'round': 1, 'bull': bull_msg, 'bear': bear_msg})
    print(f'      Round 1 — Bull: {bull_scores[-1]}% | Bear: {bear_scores[-1]}%')

    # Rondas 2-3 — rebate
    for r in range(2, DEBATE_ROUNDS + 1):
        bull_msg = chat(
            f"{context}\n\n=== BEAR ARGUMENT ===\n{bear_msg}\n\n"
            "Directly refute the bear's strongest points. Strengthen your bull case with new evidence.",
            model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.65)
        bear_msg = chat(
            f"{context}\n\n=== BULL ARGUMENT ===\n{bull_msg}\n\n"
            "Directly refute the bull's strongest points. Strengthen your bear case with new evidence.",
            model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.65)
        bull_scores.append(extract_confidence(bull_msg))
        bear_scores.append(extract_confidence(bear_msg))
        history.append({'round': r, 'bull': bull_msg, 'bear': bear_msg})
        print(f'      Round {r} — Bull: {bull_scores[-1]}% | Bear: {bear_scores[-1]}%')

    avg_bull   = sum(bull_scores) / len(bull_scores)
    avg_bear   = sum(bear_scores) / len(bear_scores)
    margin     = abs(avg_bull - avg_bear)
    is_tie     = margin < 10
    winner     = 'TIE' if is_tie else ('BULL' if avg_bull > avg_bear else 'BEAR')

    return {
        'history':              history,
        'avg_bull_confidence':  round(avg_bull, 1),
        'avg_bear_confidence':  round(avg_bear, 1),
        'margin':               round(margin, 1),
        'winner':               winner,
        'is_tie':               is_tie,
        'final_bull':           history[-1]['bull'],
        'final_bear':           history[-1]['bear'],
        'round_scores':         list(zip(bull_scores, bear_scores))
    }
