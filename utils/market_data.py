# utils/market_data.py -- datos macro reales gratuitos
import requests, os, json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
FRED_KEY = os.getenv('FRED_KEY', '')

def get_dyx():
    """Dollar index via FRED API gratuita"""
    try:
        if not FRED_KEY:
            return {'value': None, 'source': 'FRED no key'}
        r = requests.get(
            'https://api.stlouisfed.org/fred/series/observations',
            params={'series_id': 'DMY0USD', 'api_key': FRED_KEY, 'file_type': 'json', 'limit': 5, 'sort_order': 'desc'},
            timeout=8
        )
        data = r.json()
        obs = data.get('observations', [])
        if obs:
            latest = obs[0]
            return {'value': float(latest['value']), 'date': latest['date'], 'source': 'FRED'}
    except Exception as e:
        print(f'[market_data] DXY error: {e}')
    return {'value': None, 'source': 'unavailable'}

def get_us_treasury_rate():
    """10Y Treasury yield via FRED"""
    try:
        if not FRED_KEY:
            return {'value': None, 'source': 'FRED no key'}
        r = requests.get(
            'https://api.stlouisfed.org/fred/series/observations',
            params={'id': 'DSG10', 'api_key': FRED_KEY, 'file_type': 'json', 'limit': 5, 'sort_order': 'desc'},
            timeout=8
        )
        data = r.json()
        obs = data.get('observations', [])
        if obs:
            return {'value': float(obs[0]['value']), 'source': 'FRED'}
    except Exception as e:
        print(f'[market_data] Treasury error: {e}')
    return {'value': None, 'source': 'unavailable'}

def get_fear_greed():
    """CNN Fear & Greed Index"""
    try:
        r = requests.get(
            'https://fear-and-greed-index.p.rapidapi.com/indices/index/current',
            headers={'X-RapidAPI-Key': 'demo', 'X-RapidAPI-Host': 'fear-and-greed-index.p.rapidapi.com'},
            timeout=5
        )
        data = r.json()
        score = data.get('fgi', {}).get('now', {}).get('value', None)
        return {'score': score, 'source': 'CNN'}
    except:
        return {'score': None, 'source': 'unavailable'}

def get_all_macro_data():
    dyx     = get_dyx()
    treasury = get_us_treasury_rate()
    fg      = get_fear_greed()
    return {
        'dxx':      dyx,
        'treasury': treasury,
        'fear_greed': fg,
        'summary': _build_summary(dyx, treasury, fg)
    }

def _build_summary(dyx, treasury, fg):
    parts = []
    if dyx.get('value'):
        parts.append(f'DXX: {dyx["value"]:.2f}')
    if treasury.get('value'):
        parts.append(f'10Y Treasury: {treasury["value"]:.2f}%')
    if fg.get('score'):
        score = fg.get('score', 50)
        fg_label = 'Extreme Fear' if score < 25 else ('Fear' if score < 45 else ('Greed' if score > 55 else 'Neutral'))
        parts.append(f'Fear&Greed: {score} ({fg_label})')
    return ' | '.join(parts) if parts else 'Macro data unavailable'
