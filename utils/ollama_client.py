import requests, json, re, time
from config import OLLAMA_BASE, MODEL_HEAVY, MODEL_LIGHT

def _strip(t): return re.sub(r'<think>[\s\S]*?</think>', '', t, flags=re.IGNORECASE).strip()

def chat(prompt, model=MODEL_HEAVY, system=None, temperature=0.7, timeout=300):
    msgs = []
    if system: msgs.append({'role': 'system', 'content': system})
    msgs.append({'role': 'user', 'content': prompt})
    for attempt in range(3):
        try:
            r = requests.post(OLLAMA_BASE + '/api/chat', json={'model': model, 'messages': msgs, 'stream': False, 'options': {'temperature': temperature, 'num_predict': 800}}, timeout=timeout)
            r.raise_for_status()
            return _strip(r.json()['message']['content'])
        except requests.exceptions.ReadTimeout:
            print('[ollama] timeout attempt ' + str(attempt+1), flush=True)
            time.sleep(5)
        except Exception as e:
            print('[ollama] error: ' + str(e), flush=True)
            time.sleep(5)
    return 'ERROR: timeout'

def extract_confidence(text):
    text = _strip(text)
    lines = [l.strip() for l in text.strip().split(chr(10)) if l.strip()]
    for line in reversed(lines):
        m = re.search(r'[Cc]onfidence[:\s]+(\d{2,3})\s*%?', line)
        if m:
            v = int(m.group(1))
            if 10 <= v <= 99: return v
    all_m = re.findall(r'\b(\d{2,3})\s*%', text)
    for v in reversed(all_m):
        v = int(v)
        if 40 <= v <= 95: return v
    tl = text.lower()
    if any(p in tl for p in ['strongly bullish', 'highly confident', 'strong bull']): return 75
    if any(p in tl for p in ['bullish', 'rise', 'upside', 'long']): return 63
    if any(p in tl for p in ['strongly bearish', 'highly bearish']): return 74
    if any(p in tl for p in ['bearish', 'fall', 'downside', 'short']): return 62
    return 57

def extract_json(text):
    text = _strip(text)
    text = re.sub(r'`json|`', '', text).strip()
    try: return json.loads(text)
    except: pass
    m = re.search(r'\{[\s\S]+\}', text)
    if m:
        try: return json.loads(m.group())
        except: pass
    return {}
