import requests, os
from dotenv import load_dotenv
load_dotenv()
FRED_KEY = os.getenv('FRED_KEY', '')

def get_dxy():
    if not FRED_KEY: return {'value': None, 'source': 'no FRED key'}
    try:
        r = requests.get('https://api.stlouisfed.org/fred/series/observations',
            params={'series_id': 'DTWEXBGS', 'api_key': FRED_KEY, 'file_type': 'json', 'limit': 2, 'sort_order': 'desc'}, timeout=8)
        obs = r.json().get('observations', [])
        return {'value': float(obs[0]['value']), 'date': obs[0]['date'], 'source': 'FRED'} if obs else {'value': None, 'source': 'empty'}
    except Exception as e:
        print('[market_data] DXY error: ' + str(e))
        return {'value': None, 'source': 'error'}

def get_treasury_10y():
    if not FRED_KEY: return {'value': None}
    try:
        r = requests.get('https://api.stlouisfed.org/fred/series/observations',
            params={'series_id': 'DGS10', 'api_key': FRED_KEY, 'file_type': 'json', 'limit': 2, 'sort_order': 'desc'}, timeout=8)
        obs = r.json().get('observations', [])
        return {'value': float(obs[0]['value']), 'source': 'FRED'} if obs else {'value': None}
    except: return {'value': None}

def get_all():
    dxy = get_dxy()
    t10 = get_treasury_10y()
    parts = []
    if dxy.get('value'): parts.append('DXY: ' + str(round(dxy['value'],2)))
    if t10.get('value'): parts.append('10Y Treasury: ' + str(t10['value']) + '%')
    return {'dxy': dxy, 'treasury_10y': t10, 'summary': ' | '.join(parts) if parts else 'No macro data'}