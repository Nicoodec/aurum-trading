# resolve.py — cerrar posiciones y calcular P&L
import json, os, sys
from datetime import datetime
from utils.state_manager import load_history

def resolve_position(cycle_folder, exit_price):
    cycle_path = os.path.join(cycle_folder, 'cycle.json')
    with open(cycle_path) as f:
        cycle = json.load(f)
    risk = cycle.get('risk_plan', {})
    if not risk.get('valid'):
        print('No valid position in this cycle')
        return
    entry = risk['entry']
    direction = risk['direction']
    contracts = risk.get('contracts', 1)
    if direction == 'BULL':
        pnl = (exit_price - entry) * contracts * 100
    else:
        pnl = (entry - exit_price) * contracts * 100
    cycle['resolved'] = {'exit_price': exit_price, 'pnl_usd': round(pnl, 2),
                         'resolved_at': datetime.now().isoformat(),
                         'result': 'WIN' if pnl > 0 else 'LOSS'}
    with open(cycle_path, 'w') as f:
        json.dump(cycle, f, indent=2)
    print(f'P&L:  ({cycle["resolved"]["result"]})')
    print(f'Entry: {entry} -> Exit: {exit_price}')

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print('Usage: python resolve.py <cycle_folder> <exit_price>')
    else:
        resolve_position(sys.argv[1], float(sys.argv[2]))
