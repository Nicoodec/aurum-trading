from config import CAPITAL, MAX_RISK_PCT, MIN_RR
from utils.atr_calculator import get_atr_from_history, get_swing_levels

LEVERAGE = 30
CONTRACT_SIZE = 100

def calculate(debate_result, tech_data, price_data, account_balance=None):
    balance   = account_balance or CAPITAL
    price     = price_data.get('price', 0)
    winner    = debate_result.get('winner', 'TIE')
    margin    = debate_result.get('margin', 0)
    if winner == 'TIE':
        return {'valid': False, 'reason': 'Debate ended in tie'}
    win_prob  = (debate_result.get('avg_bull_confidence', 50) if winner == 'BULL' else debate_result.get('avg_bear_confidence', 50)) / 100
    direction = 'LONG' if winner == 'BULL' else 'SHORT'
    atr = get_atr_from_history()
    if not atr:
        atr = price * 0.008
        print('[risk] ATR fallback: ' + str(round(atr,2)))
    else:
        print('[risk] ATR real: ' + str(atr))
    lv = get_swing_levels(price, atr, direction)
    stop, target, sl_dist, tp_dist, rr = lv['stop'], lv['target'], lv['sl_dist'], lv['tp_dist'], lv['rr']
    if sl_dist < 1: return {'valid': False, 'reason': 'SL too small'}
    if round(rr, 4) < MIN_RR: return {'valid': False, 'reason': 'RR ' + str(round(rr,2)) + ' below min ' + str(MIN_RR)}
    kelly_f  = max(0, (win_prob * (rr + 1) - 1) / rr)
    kelly_f  = min(kelly_f, MAX_RISK_PCT)
    risk_usd = round(min(balance * kelly_f, balance * MAX_RISK_PCT), 2)
    lot_size = max(0.01, round(risk_usd / (sl_dist * CONTRACT_SIZE), 2))
    notional = lot_size * CONTRACT_SIZE * price
    margin_needed = notional / LEVERAGE
    if margin_needed > balance * 0.30:
        lot_size = max(0.01, round((balance * 0.30 * LEVERAGE) / (CONTRACT_SIZE * price), 2))
        risk_usd = round(lot_size * CONTRACT_SIZE * sl_dist, 2)
        margin_needed = round(lot_size * CONTRACT_SIZE * price / LEVERAGE, 2)
    return {'valid': True, 'direction': direction, 'entry': round(price,2),
            'stop_loss': stop, 'take_profit': target,
            'sl_distance': sl_dist, 'tp_distance': tp_dist,
            'risk_reward': rr, 'win_probability': round(win_prob*100,1),
            'kelly_fraction': round(kelly_f*100,2), 'risk_usd': risk_usd,
            'contracts': lot_size, 'margin_needed': round(margin_needed,2),
            'atr_used': atr, 'debate_margin': margin, 'balance_used': balance}