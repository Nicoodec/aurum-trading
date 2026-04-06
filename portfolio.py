# portfolio.py — P&L tracker con MT5 + paper trading
import json, os
from datetime import datetime
from config import STATE_DIR, CAPITAL

POSITIONS_FILE = os.path.join(STATE_DIR, 'positions.json')

def load_positions():
    if os.path.exists(POSITIONS_FILE):
        with open(POSITIONS_FILE) as f:
            return json.load(f)
    return []

def save_positions(positions):
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(POSITIONS_FILE, 'w') as f:
        json.dump(positions, f, indent=2, default=str)

def add_position(cycle_data, ticket=None):
    positions = load_positions()
    risk = cycle_data.get('risk_plan', {})
    pos = {
        'id': len(positions) + 1,
        'ticket': ticket,
        'direction': risk.get('direction'),
        'entry': risk.get('entry'),
        'stop_loss': risk.get('stop_loss'),
        'take_profit': risk.get('take_profit'),
        'risk_usd': risk.get('risk_usd'),
        'contracts': risk.get('contracts'),
        'rr': risk.get('risk_reward'),
        'opened_at': datetime.now().isoformat(),
        'status': 'OPEN',
        'pnl': None,
        'closed_at': None,
        'cycle_ts': cycle_data.get('ts')
    }
    positions.append(pos)
    save_positions(positions)
    return pos

def close_position(position_id, exit_price, pnl=None):
    positions = load_positions()
    for pos in positions:
        if pos['id'] == position_id and pos['status'] == 'OPEN':
            if pnl is None:
                entry = pos['entry'] or 0
                contracts = pos['contracts'] or 1
                if pos['direction'] == 'LONG':
                    pnl = (exit_price - entry) * contracts * 100
                else:
                    pnl = (entry - exit_price) * contracts * 100
            pos['pnl'] = round(pnl, 2)
            pos['exit_price'] = exit_price
            pos['status'] = 'WIN' if pnl > 0 else 'LOSS'
            pos['closed_at'] = datetime.now().isoformat()
            break
    save_positions(positions)
    return positions

def get_stats():
    positions = load_positions()
    closed = [p for p in positions if p['status'] in ('WIN','LOSS')]
    open_pos = [p for p in positions if p['status'] == 'OPEN']
    total_pnl = sum(p['pnl'] or 0 for p in closed)
    wins = [p for p in closed if p['status'] == 'WIN']
    losses = [p for p in closed if p['status'] == 'LOSS']
    win_rate = len(wins) / len(closed) * 100 if closed else 0
    avg_win = sum(p['pnl'] for p in wins) / len(wins) if wins else 0
    avg_loss = sum(p['pnl'] for p in losses) / len(losses) if losses else 0
    return {
        'capital': CAPITAL,
        'total_pnl': round(total_pnl, 2),
        'equity': round(CAPITAL + total_pnl, 2),
        'total_trades': len(closed),
        'open_positions': len(open_pos),
        'win_rate': round(win_rate, 1),
        'wins': len(wins),
        'losses': len(losses),
        'avg_win': round(avg_win, 2),
        'avg_loss': round(avg_loss, 2),
        'profit_factor': round(abs(sum(p['pnl'] for p in wins) / sum(p['pnl'] for p in losses)), 2) if losses and sum(p['pnl'] for p in losses) != 0 else 0
    }
