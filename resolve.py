# resolve.py — cerrar posiciones manualmente o via MT5
import sys, json
from portfolio import close_position, get_stats, load_positions

def resolve_by_id(pos_id, exit_price):
    positions = load_positions()
    pos = next((p for p in positions if p['id'] == pos_id and p['status'] == 'OPEN'), None)
    if not pos:
        print(f'Position {pos_id} not found or already closed')
        return
    updated = close_position(pos_id, float(exit_price))
    closed = next(p for p in updated if p['id'] == pos_id)
    result = 'WIN' if closed['pnl'] > 0 else 'LOSS'
    print(f'[{result}] Position {pos_id} closed')
    print(f'  Entry: {pos["entry"]} -> Exit: {exit_price}')
    print(f'  P&L: ')
    stats = get_stats()
    print(f'  Portfolio equity:  | Win rate: {stats["win_rate"]}%')

def resolve_via_mt5(pos_id):
    try:
        from agents.mt5_broker import connect, close_trade
        if not connect():
            print('MT5 not connected')
            return
        positions = load_positions()
        pos = next((p for p in positions if p['id'] == pos_id), None)
        if not pos or not pos.get('ticket'):
            print('No MT5 ticket for this position')
            return
        result = close_trade(pos['ticket'])
        if result:
            close_position(pos_id, result['close_price'], result['pnl'])
    except Exception as e:
        print(f'MT5 close error: {e}')

def list_open():
    positions = load_positions()
    open_pos = [p for p in positions if p['status'] == 'OPEN']
    if not open_pos:
        print('No open positions')
        return
    for p in open_pos:
        print(f"  [{p['id']}] {p['direction']} entry={p['entry']} SL={p['stop_loss']} TP={p['take_profit']} opened={p['opened_at'][:16]}")

if __name__ == '__main__':
    if len(sys.argv) == 1:
        list_open()
    elif sys.argv[1] == 'list':
        list_open()
    elif sys.argv[1] == 'close' and len(sys.argv) == 4:
        resolve_by_id(int(sys.argv[2]), sys.argv[3])
    elif sys.argv[1] == 'mt5' and len(sys.argv) == 3:
        resolve_via_mt5(int(sys.argv[2]))
    else:
        print('Usage:')
        print('  python resolve.py list')
        print('  python resolve.py close <id> <exit_price>')
        print('  python resolve.py mt5 <id>')
