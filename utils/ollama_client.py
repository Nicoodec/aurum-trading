# utils/ollama_client.py
import requests, json, re
from config import OLLAMA_BASE, MODEL_HEAVY, MODEL_LIGHT

def chat(prompt, model=MODEL_HEAVY, system=None, temperature=0.7):
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})
    r = requests.post(f'{OLLAMA_BASE}/api/chat', json={
        'model': model, 'messages': messages,
        'stream': False, 'options': {'temperature': temperature}
    }, timeout=120)
    r.raise_for_status()
    return r.json()['message']['content']

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
