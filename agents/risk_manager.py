# agents/risk_manager.py
from config import CAPITAL, MAX_RISK_PCT, MIN_RR

LEVERAGE      = 30
CONTRACT_SIZE = 100  # oz por lote XAU/USD

# Para swing trading: minimo de movimiento esperado
MIN_TP_DISTANCE_PCT = 0.008   # 0.8% minimo de take profit
MIN_SL_DISTANCE_PCT = 0.004   # 0.4% minimo de stop loss

def calculate(debate_result, tech_data, price_data, account_balance=None):
    balance = account_balance or CAPITAL
    price   = price_data.get('price', 0)
    winner  = debate_result.get('winner', 'TIE')
    margin  = debate_result.get('margin', 0)

    if winner == 'TIE':
        return {'valid': False, 'reason': 'Debate ended in tie -- STAY OUT'}

    win_prob   = (debate_result.get('avg_bull_confidence', 50) if winner == 'BULL'
                  else debate_result.get('avg_bear_confidence', 50)) / 100
    direction  = 'LONG' if winner == 'BULL' else 'SHORT'

    # Niveles tecnicos -- garantizar distancia minima para swing
    raw_support    = tech_data.get('support',    price * 0.985)
    raw_resistance = tech_data.get('resistance', price * 1.015)

    # Distancia minima forzada para swing trading
    min_sl_dist = price * MIN_SL_DISTANCE_PCT   # ~ en 
    min_tp_dist = price * MIN_TP_DISTANCE_PCT   # ~ en 

    if direction == 'LONG':
        # SL por debajo del soporte, minimo 0.4% abajo
        sl_from_support = price - raw_support
        stop   = price - max(sl_from_support, min_sl_dist)
        # TP por encima de resistencia, minimo RR 1:2
        target = price + max(price - stop, min_tp_dist) * MIN_RR
        # Si resistencia esta mas lejos, usar resistencia
        if raw_resistance > target:
            target = raw_resistance
    else:
        sl_from_resistance = raw_resistance - price
        stop   = price + max(sl_from_resistance, min_sl_dist)
        target = price - max(stop - price, min_tp_dist) * MIN_RR
        if raw_support < target:
            target = raw_support

    stop   = round(stop, 2)
    target = round(target, 2)

    sl_distance = abs(price - stop)
    tp_distance = abs(target - price)

    if sl_distance < 1:
        return {'valid': False, 'reason': f'SL distance too small: '}

    rr = tp_distance / sl_distance
    if round(rr, 4) < MIN_RR:
        return {'valid': False, 'reason': f'R:R {rr:.2f} below minimum {MIN_RR} even after adjustment'}

    # Kelly Criterion
    kelly_f = max(0, (win_prob * (rr + 1) - 1) / rr)
    kelly_f = min(kelly_f, MAX_RISK_PCT)

    # Sizing XAU/USD MT5
    # 1 lote = 100oz. P&L por lote = sl_distance * 100
    risk_usd = round(balance * kelly_f, 2)
    risk_usd = min(risk_usd, balance * MAX_RISK_PCT)
    lot_size = risk_usd / (sl_distance * CONTRACT_SIZE)
    lot_size = max(0.01, round(lot_size, 2))

    # Check margen
    notional      = lot_size * CONTRACT_SIZE * price
    margin_needed = notional / LEVERAGE
    max_margin    = balance * 0.30
    if margin_needed > max_margin:
        lot_size      = round((max_margin * LEVERAGE) / (CONTRACT_SIZE * price), 2)
        lot_size      = max(0.01, lot_size)
        risk_usd      = round(lot_size * CONTRACT_SIZE * sl_distance, 2)

    actual_risk_pct = (lot_size * CONTRACT_SIZE * sl_distance) / balance * 100

    return {
        'valid':           True,
        'direction':       direction,
        'entry':           round(price, 2),
        'stop_loss':       stop,
        'take_profit':     round(target, 2),
        'sl_distance':     round(sl_distance, 2),
        'tp_distance':     round(tp_distance, 2),
        'risk_reward':     round(rr, 2),
        'win_probability': round(win_prob * 100, 1),
        'kelly_fraction':  round(kelly_f * 100, 2),
        'risk_usd':        risk_usd,
        'actual_risk_pct': round(actual_risk_pct, 2),
        'contracts':       lot_size,
        'margin_needed':   round(margin_needed, 2),
        'debate_margin':   margin,
        'balance_used':    balance
    }
