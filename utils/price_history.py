# utils/price_history.py -- calcula indicadores tecnicos reales
import requests, os, json
from datetime import datetime, timedelta
from config import GOLDAPI_KEY, STATE_DIR

HISTORY_FILE = os.path.join(STATE_DIR, 'price_history.json')

def fetch_recent_prices(days=30):
    # Intentar cargar cache local primero
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding='utf-8') as f:
            cached = json.load(f)
        if cached.get('prices') and len(cached['prices']) >= 10:
            last_update = cached.get('last_update', '')
            if last_update[:10] == datetime.now().strftime('%Y-%m-%d'):
                return cached['prices']

    # Goldapi historico (tier gratuito da datos limitados)
    prices = []
    try:
        for d in range(days, 0, -1):
            date = (datetime.now() - timedelta(days=d)).strftime('%Y%m%d')
            r = requests.get(
                f'https://www.goldapi.io/api/XAU/USD/{date}',
                headers={'x-access-token': GOLDAPI_KEY},
                timeout=8
            )
            if r.status_code == 200:
                data = r.json()
                if data.get('price'):
                    prices.append({
                        'date':  date,
                        'close': data['price'],
                        'open':  data.get('open_price', data['price']),
                        'high':  data.get('high_price', data['price']),
                        'low':   data.get('low_price',  data['price']),
                    })
    except Exception as e:
        print(f'[price_history] fetch error: {e}')

    if prices:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump({'prices': prices, 'last_update': datetime.now().isoformat()}, f)

    return prices

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    closes = [p['close'] for p in prices]
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    rs  = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 1)

def calculate_sma(prices, period):
    closes = [p['close'] for p in prices]
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)

def find_support_resistance(prices, window=5):
    if len(prices) < window * 2:
        return None, None
    highs  = [p['high']  for p in prices]
    lows   = [p['low']   for p in prices]
    closes = [p['close'] for p in prices]

    # Soporte: minimo de los ultimos 20 dias
    support    = round(min(lows[-20:]),  2) if len(lows)  >= 20 else round(min(lows),  2)
    resistance = round(max(highs[-20:]), 2) if len(highs) >= 20 else round(max(highs), 2)

    # Refinar: soporte mas cercano al precio actual por encima del minimo
    current = closes[-1]
    candidate_supports    = sorted([l for l in lows   if l < current],  reverse=True)
    candidate_resistances = sorted([h for h in highs  if h > current])
    if candidate_supports:
        support    = round(candidate_supports[0],    2)
    if candidate_resistances:
        resistance = round(candidate_resistances[0], 2)

    return support, resistance

def get_full_technical_context(current_price):
    prices = fetch_recent_prices(days=25)
    if not prices:
        # Fallback con precio actual
        return {
            'rsi':          None,
            'sma20':        None,
            'sma50':        None,
            'support':      round(current_price * 0.985, 2),
            'resistance':   round(current_price * 1.015, 2),
            'trend_20d':    'UNKNOWN',
            'price_vs_sma': 'UNKNOWN',
            'history_days': 0
        }

    # Añadir precio actual como ultimo punto
    prices.append({'close': current_price, 'high': current_price, 'low': current_price, 'open': current_price})

    rsi   = calculate_rsi(prices)
    sma20 = calculate_sma(prices, 20)
    sma50 = calculate_sma(prices, 50)
    support, resistance = find_support_resistance(prices)

    # Tendencia 20 dias
    if len(prices) >= 20:
        trend_20d = 'UP' if prices[-1]['close'] > prices[-20]['close'] else 'DOWN'
    else:
        trend_20d = 'UNKNOWN'

    price_vs_sma = 'ABOVE' if (sma20 and current_price > sma20) else 'BELOW'

    return {
        'rsi':          rsi,
        'sma20':        sma20,
        'sma50':        sma50,
        'support':      support,
        'resistance':   resistance,
        'trend_20d':    trend_20d,
        'price_vs_sma': price_vs_sma,
        'history_days': len(prices)
    }
