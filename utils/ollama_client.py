from __future__ import annotations
import requests, json, re, time
from config import OLLAMA_BASE, MODEL_HEAVY, MODEL_LIGHT

def _strip_thinking(text):
    text = re.sub(r'<think>[\s\S]*?</think>', '', text, flags=re.IGNORECASE)
    return text.strip()

def chat(prompt, model=MODEL_HEAVY, system=None, temperature=0.7, timeout=300):
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})
    for attempt in range(3):
        try:
            r = requests.post(f'{OLLAMA_BASE}/api/chat', json={
                'model': model, 'messages': messages,
                'stream': False, 'options': {'temperature': temperature, 'num_predict': 800}
            }, timeout=timeout)
            r.raise_for_status()
            raw = r.json()['message']['content']
            return _strip_thinking(raw)
        except requests.exceptions.ReadTimeout:
            print(f'[ollama] timeout attempt {attempt+1}/3', flush=True)
            time.sleep(5)
        except Exception as e:
            print(f'[ollama] error: {e}', flush=True)
            time.sleep(5)
    return 'ERROR: Model timeout'

def extract_confidence(text):
    text = _strip_thinking(text)
    # Coger LA ULTIMA linea que tenga "Confidence: XX%"
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    for line in reversed(lines):
        m = re.search(r'[Cc]onfidence[:\s]+(\d{2,3})\s*%?', line)
        if m:
            val = int(m.group(1))
            if 10 <= val <= 99:
                return val
    # Buscar en todo el texto, coger el ultimo
    all_matches = re.findall(r'\b(\d{2,3})\s*%\s*(?:confidence|)\s*$', text, re.IGNORECASE|re.MULTILINE)
    if all_matches:
        val = int(all_matches[-1])
        if 40 <= val <= 95:
            return val
    # Inferir por palabras clave
    tl = text.lower()
    if any(p in tl for p in ['strongly bullish', 'highly confident', strong bull']): return 75
    if any(p in tl for p in ['bullish', 'rise', 'upside', 'long']): return 63
    if any(p in tl for p in ['strongly bearish', 'highly bearish']): return 74
    if any(p in tl for p in ['bearish', 'fall', 'downside', 'short']): return 62
    return 57

def extract_json(text):
    text = _strip_thinking(text)
    text = re.sub(r'```json|```', '', text).strip()
    try:
        return json.loads(text)
    except: pass
    m = re.search(r'\{[\s\S]+\}', text)
    if m:
        try: return json.loads(m.group())
        except: pass
    return {}
