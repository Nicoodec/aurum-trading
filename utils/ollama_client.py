# utils/ollama_client.py
import requests, json, re, time
from config import OLLAMA_BASE, MODEL_HEAVY, MODEL_LIGHT

def chat(prompt, model=MODEL_HEAVY, system=None, temperature=0.7, timeout=300):
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})
    for attempt in range(3):
        try:
            r = requests.post(f'{OLLAMA_BASE}/api/chat', json={
                'model': model, 'messages': messages,
                'stream': False, 'options': {'temperature': temperature, 'num_predict': 512}
            }, timeout=timeout)
            r.raise_for_status()
            return r.json()['message']['content']
        except requests.exceptions.ReadTimeout:
            print(f'[ollama] timeout attempt {attempt+1}/3, retrying...')
            time.sleep(5)
        except Exception as e:
            print(f'[ollama] error: {e}')
            time.sleep(5)
    return 'ERROR: Model timeout after 3 attempts'

def extract_confidence(text):
    m = re.search(r'confidence[:\s]+(\d+)%?', text, re.IGNORECASE)
    if m: return int(m.group(1))
    m = re.search(r'(\d+)%\s*confidence', text, re.IGNORECASE)
    if m: return int(m.group(1))
    return 50

def extract_json(text):
    text = re.sub(r'`json|`', '', text).strip()
    m = re.search(r'\{[\s\S]+\}', text)
    if m:
        try: return json.loads(m.group())
        except: pass
    return {}
