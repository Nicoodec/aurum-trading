# agents/price_feed.py
import requests, os
from dotenv import load_dotenv
load_dotenv()

GOLDAPI_KEY = os.getenv('GOLDAPI_KEY', '')

def get_xauusd():
    key = GOLDAPI_KEY
    if not key:
        print('[price_feed] WARNING: No GOLDAPI_KEY in environment')
    try:
        r = requests.get(
            'https://www.goldapi.io/api/XAU/USD',
            headers={'x-access-token': key, 'Content-Type': 'application/json'},
            timeout=10
        )
        r.raise_for_status()
        d = r.json()
        return {
            'price':      d.get('price'),
            'open':       d.get('open_price'),
            'high':       d.get('high_price'),
            'low':        d.get('low_price'),
            'change':     d.get('ch'),
            'change_pct': d.get('chp'),
            'prev_close': d.get('prev_close_price'),
            'ask':        d.get('ask'),
            'bid':        d.get('bid'),
            'timestamp':  d.get('timestamp'),
            'source':     'goldapi.io'
        }
    except Exception as e:
        print(f'[price_feed] goldapi error: {e}')
        return {'price': None, 'open': None, 'high': None, 'low': None,
                'change': None, 'change_pct': None, 'source': 'unavailable'}

def get_technical_data():
    return get_xauusd()
