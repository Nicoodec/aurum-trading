# agents/mt5_broker.py — MetaTrader 5 integration para FTMO demo
import MetaTrader5 as mt5
from datetime import datetime
import json, os

SYMBOL = 'XAUUSD'
MAGIC  = 20260407  # identificador unico AURUM

def connect(login=None, password=None, server=None):
    if not mt5.initialize():
        print(f'[MT5] initialize() failed: {mt5.last_error()}')
        return False
    if login and password and server:
        authorized = mt5.login(login, password=password, server=server)
        if not authorized:
            print(f'[MT5] login failed: {mt5.last_error()}')
            return False
    info = mt5.account_info()
    if info:
        print(f'[MT5] Connected: {info.name} | Balance: {info.balance} {info.currency} | Server: {info.server}')
        return True
    return False

def disconnect():
    mt5.shutdown()

def get_balance():
    info = mt5.account_info()
    return info.balance if info else None

def open_trade(direction, lot_size, stop_loss, take_profit, comment='AURUM'):
    symbol_info = mt5.symbol_info(SYMBOL)
    if symbol_info is None:
        print(f'[MT5] Symbol {SYMBOL} not found')
        return None
    if not symbol_info.visible:
        mt5.symbol_select(SYMBOL, True)

    tick = mt5.symbol_info_tick(SYMBOL)
    if direction == 'LONG':
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
    else:
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid

    request = {
        'action':   mt5.TRADE_ACTION_DEAL,
        'symbol':   SYMBOL,
        'volume':   lot_size,
        'type':     order_type,
        'price':    price,
        'sl':       stop_loss,
        'tp':       take_profit,
        'deviation': 20,
        'magic':    MAGIC,
        'comment':  comment,
        'type_time': mt5.ORDER_TIME_GTC,
        'type_filling': mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f'[MT5] Order failed: {result.retcode} — {result.comment}')
        return None
    print(f'[MT5] Order opened: ticket={result.order} price={result.price}')
    return {'ticket': result.order, 'price': result.price, 'volume': lot_size,
            'direction': direction, 'sl': stop_loss, 'tp': take_profit,
            'opened_at': datetime.now().isoformat()}

def close_trade(ticket):
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        print(f'[MT5] Position {ticket} not found')
        return None
    pos = positions[0]
    tick = mt5.symbol_info_tick(SYMBOL)
    close_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
    price = tick.bid if pos.type == 0 else tick.ask
    request = {
        'action':   mt5.TRADE_ACTION_DEAL,
        'symbol':   SYMBOL,
        'volume':   pos.volume,
        'type':     close_type,
        'position': ticket,
        'price':    price,
        'deviation': 20,
        'magic':    MAGIC,
        'comment':  'AURUM close',
        'type_filling': mt5.ORDER_FILLING_IOC,
    }
    result = mt5.order_send(request)
    if result.retcode != mt5.TRADE_RETCODE_DONE:
        print(f'[MT5] Close failed: {result.retcode}')
        return None
    pnl = pos.profit
    print(f'[MT5] Closed ticket={ticket} profit={pnl}')
    return {'ticket': ticket, 'close_price': price, 'pnl': pnl,
            'closed_at': datetime.now().isoformat()}

def get_open_positions():
    positions = mt5.positions_get(symbol=SYMBOL, magic=MAGIC)
    if positions is None:
        return []
    return [{'ticket': p.ticket, 'direction': 'LONG' if p.type==0 else 'SHORT',
             'volume': p.volume, 'open_price': p.price_open,
             'sl': p.sl, 'tp': p.tp, 'profit': p.profit,
             'opened_at': datetime.fromtimestamp(p.time).isoformat()}
            for p in positions]

def get_account_summary():
    info = mt5.account_info()
    if not info: return {}
    return {'balance': info.balance, 'equity': info.equity,
            'margin': info.margin, 'free_margin': info.margin_free,
            'profit': info.profit, 'currency': info.currency,
            'leverage': info.leverage, 'server': info.server}
