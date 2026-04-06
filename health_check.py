# health_check.py — verificar sistema antes de ciclo
import requests, os
from dotenv import load_dotenv
load_dotenv()

def check():
    ok = True
    # Ollama
    try:
        r = requests.get('http://localhost:11434/api/tags', timeout=5)
        models = [m['name'] for m in r.json().get('models',[])]
        print(f'[OK] Ollama: {len(models)} models — {models}')
    except Exception as e:
        print(f'[FAIL] Ollama: {e}'); ok=False

    # GoldAPI
    key = os.getenv('GOLDAPI_KEY','')
    try:
        r = requests.get('https://www.goldapi.io/api/XAU/USD',
            headers={'x-access-token': key}, timeout=10)
        price = r.json().get('price')
        print(f'[OK] GoldAPI: XAU/USD = {price}')
    except Exception as e:
        print(f'[FAIL] GoldAPI: {e}'); ok=False

    # MT5
    try:
        import MetaTrader5 as mt5
        print(f'[OK] MetaTrader5 module installed (v{mt5.__version__})')
    except Exception as e:
        print(f'[WARN] MT5: {e} (optional)')

    # State dir
    if os.path.exists('state'):
        files = os.listdir('state')
        print(f'[OK] State dir: {len(files)} items')
    else:
        os.makedirs('state'); print('[OK] State dir created')

    print(f'\nSystem {"READY" if ok else "HAS ISSUES"}')
    return ok

if __name__ == '__main__':
    check()
