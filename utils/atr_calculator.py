import os, json
from config import STATE_DIR

def calculate_atr(prices, period=14):
    if len(prices) < period + 1: return None
    trs = []
    for i in range(1, len(prices)):
        h  = prices[i].get('high',  prices[i]['close'])
        l  = prices[i].get('low',   prices[i]['close'])
        pc = prices[i-1]['close']
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return round(sum(trs[-period:]) / period, 2)

def get_atr_from_history():
    try:
        f = os.path.join(STATE_DIR, 'price_history.json')
        if not os.path.exists(f): return None
        with open(f, encoding='utf-8') as fh: data = json.load(fh)
        return calculate_atr(data.get('prices', []))
    except Exception as e:
        print('[ATR] error: ' + str(e))
        return None

def get_swing_levels(price, atr, direction, risk_mult=1.5, reward_mult=3.0):
    if not atr: atr = price * 0.008
    sl = round(atr * risk_mult, 2)
    tp = round(atr * reward_mult, 2)
    if direction == 'LONG':
        return {'stop': round(price-sl,2), 'target': round(price+tp,2), 'sl_dist': sl, 'tp_dist': tp, 'rr': round(tp/sl,2), 'atr': atr}
    return {'stop': round(price+sl,2), 'target': round(price-tp,2), 'sl_dist': sl, 'tp_dist': tp, 'rr': round(tp/sl,2), 'atr': atr}