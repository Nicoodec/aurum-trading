# agents/auto_close.py — cierre automatico de posiciones
from datetime import datetime, timedelta
from portfolio import load_positions, close_position
from config import MACRO_EVENT_BUFFER_H

FRIDAY_CLOSE_HOUR_UTC = 21  # cerrar todo antes de las 21 UTC viernes

def should_close_for_weekend():
    now = datetime.utcnow()
    return now.weekday() == 4 and now.hour >= FRIDAY_CLOSE_HOUR_UTC

def should_close_for_macro(news_data):
    scheduled = news_data.get('scheduled_events', [])
    imminent = [e for e in scheduled
                if isinstance(e, dict) and e.get('hours_away', 99) < MACRO_EVENT_BUFFER_H]
    return len(imminent) > 0, imminent

def run_auto_close(news_data=None, force=False):
    positions = load_positions()
    open_pos  = [p for p in positions if p['status'] == 'OPEN' and p.get('ticket')]

    if not open_pos:
        return []

    closed = []
    reasons = []

    if force:
        reasons.append('FORCED CLOSE')
    if should_close_for_weekend():
        reasons.append('WEEKEND — market closing')
    if news_data:
        macro_close, events = should_close_for_macro(news_data)
        if macro_close:
            reasons.append(f'MACRO EVENT IMMINENT: {events}')

    if not reasons:
        return []

    print(f'[auto_close] Closing {len(open_pos)} positions — {reasons}')

    try:
        from agents.mt5_broker import connect, close_trade, disconnect, get_open_positions
        if connect():
            mt5_positions = {p['ticket']: p for p in get_open_positions()}
            for pos in open_pos:
                ticket = pos.get('ticket')
                if ticket and ticket in mt5_positions:
                    mt5_pos = mt5_positions[ticket]
                    result  = close_trade(ticket)
                    if result:
                        close_position(pos['id'], result['close_price'], result['pnl'])
                        closed.append(pos)
                        print(f'[auto_close] Closed ticket={ticket} pnl=')
                        try:
                            from utils.telegram_alerts import alert_position_closed
                            alert_position_closed(pos, result['close_price'])
                        except: pass
            disconnect()
    except Exception as e:
        print(f'[auto_close] MT5 error: {e}')

    return closed
