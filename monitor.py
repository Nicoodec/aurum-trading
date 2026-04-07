# monitor.py — corre en paralelo, vigila posiciones abiertas cada 30s
import time, json, os
from datetime import datetime
from portfolio import load_positions, close_position
from config import STATE_DIR

CHECK_INTERVAL = 30  # segundos

def check_positions_mt5():
    try:
        from agents.mt5_broker import connect, get_open_positions, get_account_summary
        from agents.ftmo_validator import get_ftmo_status
        if not connect(1513020113, 'FH2dXFt7?', 'FTMO-Demo'):
            return
        mt5_positions = get_open_positions()
        account       = get_account_summary()
        ftmo          = get_ftmo_status(account)

        # Log estado
        ts = datetime.now().strftime('%H:%M:%S')
        print(f'[{ts}] Balance:  | '
              f'Equity:  | '
              f'Profit:  | '
              f'Open: {len(mt5_positions)} | '
              f'Daily remaining: ')

        if not ftmo['can_trade'] and mt5_positions:
            print(f'[ALERT] FTMO LIMIT — {ftmo["reasons"]}')

        # Sincronizar posiciones cerradas por SL/TP con nuestro portfolio
        local_positions = load_positions()
        local_open      = {p['ticket']: p for p in local_positions
                          if p['status'] == 'OPEN' and p.get('ticket')}
        mt5_tickets     = {p['ticket'] for p in mt5_positions}

        for ticket, local_pos in local_open.items():
            if ticket not in mt5_tickets:
                # Posicion cerrada por SL o TP en MT5
                print(f'[monitor] Position {ticket} closed by MT5 (SL/TP hit)')
                # Intentar obtener precio de cierre del historial
                try:
                    import MetaTrader5 as mt5 as mt5lib
                    from datetime import timedelta
                    deals = mt5lib.history_deals_get(
                        datetime.now() - timedelta(hours=24), datetime.now())
                    if deals:
                        deal = next((d for d in deals if d.position_id == ticket), None)
                        if deal:
                            close_position(local_pos['id'], deal.price, deal.profit)
                            print(f'[monitor] Synced: ticket={ticket} pnl={deal.profit:.2f}')
                except Exception as e:
                    print(f'[monitor] Could not get deal history: {e}')
                    close_position(local_pos['id'], local_pos.get('take_profit', 0))

        # Guardar estado para dashboard
        state_file = os.path.join(STATE_DIR, 'monitor_state.json')
        with open(state_file, 'w') as f:
            json.dump({
                'ts': datetime.now().isoformat(),
                'account': account,
                'ftmo': ftmo,
                'open_positions': mt5_positions
            }, f, indent=2, default=str)

    except Exception as e:
        print(f'[monitor] error: {e}')

def run():
    print(f'[AURUM Monitor] Starting — checking every {CHECK_INTERVAL}s')
    while True:
        check_positions_mt5()
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    run()
