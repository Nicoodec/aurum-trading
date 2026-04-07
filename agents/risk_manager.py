# agents/risk_manager.py
# XAU/USD en MT5: 1 lote = 100 oz. Con precio ~4650, 1 lote = ~,000 nocional
# Con leverage 30x: margen por lote = 465000/30 = ~,500
# Max risk 2% de ,000 =  por operacion
# Para SL de 20 pips (2 dolares en XAU): 1 lote =  por pip-dolar
# lots = risk_usd / (sl_distance_usd * 100)

from utils.ollama_client import chat, extract_json
from config import MODEL_LIGHT, CAPITAL, MAX_RISK_PCT, MIN_RR

FTMO_MAX_DAILY_LOSS_PCT = 0.05   # 5% = ,250
FTMO_MAX_TOTAL_LOSS_PCT = 0.10   # 10% = ,500
FTMO_PROFIT_TARGET_PCT  = 0.10   # 10% = ,500
LEVERAGE = 30
CONTRACT_SIZE = 100  # oz por lote en XAU/USD

def calculate(debate_result, tech_data, price_data, account_balance=None):
    balance = account_balance or CAPITAL
    price = price_data.get('price', 0)
    winner = debate_result.get('winner', 'TIE')
    margin = debate_result.get('margin', 0)

    if winner == 'TIE':
        return {'valid': False, 'reason': 'Debate ended in tie — STAY OUT'}

    win_prob = (debate_result.get('avg_bull_confidence', 50) if winner == 'BULL'
                else debate_result.get('avg_bear_confidence', 50)) / 100

    support    = tech_data.get('support',    price * 0.990)
    resistance = tech_data.get('resistance', price * 1.010)

    # Entries y niveles
    if winner == 'BULL':
        direction  = 'LONG'
        entry      = price
        stop       = round(support * 0.998, 2)
        target     = round(resistance * 0.998, 2)
    else:
        direction  = 'SHORT'
        entry      = price
        stop       = round(resistance * 1.002, 2)
        target     = round(support * 1.002, 2)

    sl_distance  = abs(entry - stop)    # en USD por oz
    tp_distance  = abs(target - entry)

    if sl_distance < 1:
        return {'valid': False, 'reason': f'SL distance too small: {sl_distance:.2f}'}

    rr = tp_distance / sl_distance
    if rr < MIN_RR:
        return {'valid': False, 'reason': f'R:R {rr:.2f} below minimum {MIN_RR}'}

    # Kelly Criterion
    kelly_b = rr
    kelly_f = max(0, (win_prob * (kelly_b + 1) - 1) / kelly_b)
    kelly_f = min(kelly_f, MAX_RISK_PCT)  # cap 2%

    # Sizing correcto para XAU/USD MT5
    # 1 lote mueve  por cada  que se mueva el precio
    risk_usd   = round(balance * kelly_f, 2)
    risk_usd   = min(risk_usd, balance * MAX_RISK_PCT)  # hard cap
    lot_size   = risk_usd / (sl_distance * CONTRACT_SIZE)
    lot_size   = max(0.01, round(lot_size, 2))

    # Verificar margen requerido
    notional      = lot_size * CONTRACT_SIZE * price
    margin_needed = notional / LEVERAGE
    max_margin    = balance * 0.30  # no usar mas del 30% del balance en margen

    if margin_needed > max_margin:
        lot_size      = round((max_margin * LEVERAGE) / (CONTRACT_SIZE * price), 2)
        lot_size      = max(0.01, lot_size)
        risk_usd      = round(lot_size * CONTRACT_SIZE * sl_distance, 2)

    actual_risk_pct = (lot_size * CONTRACT_SIZE * sl_distance) / balance * 100

    return {
        'valid':            True,
        'direction':        direction,
        'entry':            round(entry, 2),
        'stop_loss':        stop,
        'take_profit':      target,
        'sl_distance':      round(sl_distance, 2),
        'tp_distance':      round(tp_distance, 2),
        'risk_reward':      round(rr, 2),
        'win_probability':  round(win_prob * 100, 1),
        'kelly_fraction':   round(kelly_f * 100, 2),
        'risk_usd':         risk_usd,
        'actual_risk_pct':  round(actual_risk_pct, 2),
        'contracts':        lot_size,
        'margin_needed':    round(margin_needed, 2),
        'debate_margin':    margin,
        'balance_used':     balance
    }
