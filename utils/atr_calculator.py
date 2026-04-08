# utils/atr_calculator.py -- ATR dinamico para SL/TP realista
import os, json
from config import STATE_1DIR

def calculate_atr(prices, period=14):
    """Calcula ATR real desde historial de precios"""
    if len(prices) < period + 1:
        return None
    trs = []
    for i in range(1, len(prices)):
        h = prices[i].get('high', prices[i]['close'])
        l = prices[i].get('low',  prices[i]['close'])
        pc = prices[i-1]['close']
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)
    atr = sum(trs[-period:]) / period
    return round(atr, 2)

def get_atr_from_history():
    """Lee historial guardado y calcula ATR"""
    try:
        hist_file = os.path.join(STATE_DIR, 'price_history.json')
        if not os.path.exists(hist_file):
            return None
        with open(hist_file, encoding='utf-8') as f:
            data = json.load(f)
        prices = data.get('prices', [])
        return calculate_atr(prices)
    except Exception as e:
        print(f'[ATR] error: {e}')
        return None

def get_swing_levels(price, atr, direction, risk_multiplier=1.5, reward_multiplier=3.0):
    """
    Genera SL/TP realistas basados en ATR para swing trading.
    SL = 1.5 * ATR (proteccion realista)
    TP = 3.0 * ATR (RR 2:)
    """
    if not atr:
        atr = price * 0.008  # fallback 0.8%
    sl_dist = round(atr * risk_multiplier, 2)
    tp_dist = round(atr * reward_multiplier, 2)
    if direction == 'LONG':
        stop   = round(price - sl_dist, 2)
        target = round(price + tp_dist, 2)
    else:
        stop   = round(price + sl_dist, 2)
        target = round(price - tp_dist, 2)
    return {
        'stop':   stop,
        'target': target,
        'sl_dist': sl_dist,
        'tp_dist': tp_dist,
        'rr':      round(tp_dist / sl_dist, 2),
        'atr_used': atr
    }
