# utils/ollama_client.py
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
                'model':   model,
                'messages': messages,
                'stream':  False,
                'options': {'temperature': temperature, 'num_predict': 800}
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
    # Buscar patron explicito "Confidence: XX%" -- coger el ULTIMO que aparece
    explicit = re.findall(r'[Cc]onfidence[:\s]+(\d{2,3})\s*%?', text)
    if explicit:
        val = int(explicit[-1])
        if 10 <= val <= 99:
            return val
    # Buscar "XX% confidence"
    explicit2 = re.findall(r'(\d{2,3})\s*%\s*[Cc]onfidence', text)
    if explicit2:
        val = int(explicit2[-1])
        if 10 <= val <= 99:
            return val
    # Ultima linea del texto -- suele tener el score final
    lines = [l.strip() for l in text.strip().split('\n') if l.strip()]
    for line in reversed(lines[-5:]):
        nums = re.findall(r'\b(\d{2,3})\b', line)
        for n in nums:
            if 40 <= int(n) <= 95:
                return int(n)
    # Inferir por tono
    tl = text.lower()
    if any(w in tl for w in ['strongly bullish', 'very bullish', 'highly confident', 'strong conviction']):
        return 74
    if any(w in tl for w in ['bullish', 'likely to rise', 'upside', 'long']):
        return 63
    if any(w in tl for w in ['strongly bearish', 'very bearish']):
        return 71
    if any(w in tl for w in ['bearish', 'likely to fall', 'downside', 'short']):
        return 62
    if any(w in tl for w in ['uncertain', 'mixed', 'unclear', 'neutral']):
        return 48
    return 57

def extract_json(text):
    text = _strip_thinking(text)
    text = re.sub(r'`json|`', '', text).strip()
    try:
        return json.loads(text)
    except: pass
    m = re.search(r'\{[\s\S]+\}', text)
    if m:
        try:
            return json.loads(m.group())
        except: pass
    return {}
