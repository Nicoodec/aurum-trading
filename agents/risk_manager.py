# agents/risk_manager.py — Kelly Criterion adaptado + sizing
from utils.ollama_client import chat, extract_json
from config import MODEL_LIGHT, CAPITAL, MAX_RISK_PCT, MIN_RR

SYSTEM = """You are a risk manager for gold trading (XAU/USD).
Rules: Max 2% capital per trade. Min R:R 1:2. Stop loss mandatory.
Use Kelly Criterion adapted: kelly_fraction = (p*(b+1)-1)/b where b=R:R, p=win_rate_estimate."""

def calculate(debate_result, tech_data, price_data):
    price = price_data.get('price', 0)
    winner = debate_result.get('winner', 'TIE')
    margin = debate_result.get('margin', 0)
    win_prob = (debate_result.get('avg_bull_confidence', 50) if winner == 'BULL'
                else debate_result.get('avg_bear_confidence', 50)) / 100
    support = tech_data.get('support', price * 0.98)
    resistance = tech_data.get('resistance', price * 1.02)

    if winner == 'BULL':
        entry = price
        stop = support * 0.998
        target = resistance
    elif winner == 'BEAR':
        entry = price
        stop = resistance * 1.002
        target = support
    else:
        return {'valid': False, 'reason': 'Debate ended in tie — STAY OUT'}

    risk_per_oz = abs(entry - stop)
    reward_per_oz = abs(target - entry)
    rr = reward_per_oz / risk_per_oz if risk_per_oz > 0 else 0

    if rr < MIN_RR:
        return {'valid': False, 'reason': f'R:R {rr:.2f} below minimum {MIN_RR}'}

    kelly_b = rr
    kelly_p = win_prob
    kelly_f = max(0, (kelly_p * (kelly_b + 1) - 1) / kelly_b)
    kelly_f = min(kelly_f, MAX_RISK_PCT)  # cap at 2%

    risk_usd = CAPITAL * kelly_f
    contracts = round(risk_usd / (risk_per_oz * 100), 2) if risk_per_oz > 0 else 0

    return {
        'valid': True,
        'direction': winner,
        'entry': round(entry, 2),
        'stop_loss': round(stop, 2),
        'take_profit': round(target, 2),
        'risk_reward': round(rr, 2),
        'win_probability': round(win_prob * 100, 1),
        'kelly_fraction': round(kelly_f * 100, 2),
        'risk_usd': round(risk_usd, 2),
        'contracts': contracts,
        'debate_margin': margin
    }
