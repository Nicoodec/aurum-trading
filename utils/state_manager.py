# utils/state_manager.py
import json, os
from datetime import datetime
from config import STATE_DIR

def save_cycle(cycle_data):
    ts = datetime.now().strftime('%Y%m%d_%H%M')
    folder = os.path.join(STATE_DIR, f'cycle_{ts}')
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, 'cycle.json'), 'w') as f:
        json.dump(cycle_data, f, indent=2, default=str)
    # Append to history
    hist_path = os.path.join(STATE_DIR, 'history.json')
    history = []
    if os.path.exists(hist_path):
        with open(hist_path) as f:
            history = json.load(f)
    summary = {'ts': ts, 'decision': cycle_data.get('decision','?'),
                'price': cycle_data.get('price'), 'confidence': cycle_data.get('confidence', 0)}
    history.append(summary)
    with open(hist_path, 'w') as f:
        json.dump(history, f, indent=2)
    return folder

def load_history():
    hist_path = os.path.join(STATE_DIR, 'history.json')
    if os.path.exists(hist_path):
        with open(hist_path) as f:
            return json.load(f)
    return []
