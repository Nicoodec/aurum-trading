# agents/price_feed.py — XAU/USD via goldapi.io (free tier)
import requests, time
from config import GOLDAPI_KEY

FALLBACK_SOURCES = [
    'https://api.metals.live/v1/spot/gold',
]

def get_xauusd():
    # Intento 1: goldapi.io
    if GOLDAPI_KEY:
        try:
            r = requests.get('https://www.goldapi.io/api/XAU/USD',
                headers={'x-access-token': GOLDAPI_KEY, 'Content-Type': 'application/json'},
                timeout=10)
            d = r.json()
            return {'price': d['price'], 'open': d.get('open_price'), 'source': 'goldapi'}
        except: pass
    # Intento 2: metals.live (sin auth)
    try:
        r = requests.get('https://api.metals.live/v1/spot/gold', timeout=10)
        data = r.json()
        price = data[0].get('gold') if isinstance(data, list) else data.get('gold')
        if price: return {'price': float(price), 'open': None, 'source': 'metals.live'}
    except: pass
    return {'price': None, 'open': None, 'source': 'unavailable'}

def get_technical_data():
    spot = get_xauusd()
    return {**spot, 'symbol': 'XAU/USD',
            'note': 'Add API key in .env for full OHLCV data'}
