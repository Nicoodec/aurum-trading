# utils/ollama_client.py
import requests, json, re, time
from config import OLLAMA_BASE, MODEL_HEAVY, MODEL_LIGHT

def _strip_thinking(text):
    # qwen3 envuelve razonamiento en <think>...</think>
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
                'model':   model,
                'messages': messages,
                'stream':  False,
                'options': {'temperature': temperature, 'num_predict': 600}
            }, timeout=timeout)
            r.raise_for_status()
            raw = r.json()['message']['content']
            return _strip_thinking(raw)
        except requests.exceptions.ReadTimeout:
            print(f'[ollama] timeout attempt {attempt+1}/3, retrying...')
            time.sleep(5)
        except Exception as e:
            print(f'[ollama] error: {e}')
            time.sleep(5)
    return 'ERROR: Model timeout after 3 attempts'

def extract_confidence(text):
    text = _strip_thinking(text)
    # Patrones en orden de especificidad
    patterns = [
        r'[Cc]onfidence[:\s]+(\d+)\s*%',
        r'(\d+)\s*%\s*[Cc]onfidence',
        r'[Cc]onfidence[:\s]+(\d+)',
        r'\b(9[0-9]|[4-8][0-9])\s*%',  # cualquier porcentaje razonable 40-99
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            val = int(m.group(1))
            if 10 <= val <= 99:
                return val
    # Si no encuentra nada, estimar por palabras clave
    text_lower = text.lower()
    if any(w in text_lower for w in ['strongly', 'clearly', 'definitely', 'high confidence']):
        return 72
    if any(w in text_lower for w in ['likely', 'probable', 'expect']):
        return 62
    if any(w in text_lower for w in ['uncertain', 'unclear', 'mixed']):
        return 45
    return 55  # default neutral pero no 50 exacto

def extract_json(text):
    text = _strip_thinking(text)
    text = re.sub(r'`json|`', '', text).strip()
    # Intentar parsear directo
    try:
        return json.loads(text)
    except: pass
    # Buscar primer objeto JSON
    m = re.search(r'\{[\s\S]+\}', text)
    if m:
        try:
            return json.loads(m.group())
        except:
            # Intentar reparar JSON truncado
            fragment = m.group()
            try:
                return json.loads(fragment + '}')
            except: pass
    return {}
