# agents/ftmo_validator.py
# Valida reglas FTMO antes de cada operacion
# Free Trial Swing: max daily loss 5%, max total loss 10%, target 10%

import json, os
from datetime import datetime, date
from config import STATE_DIR

BALANCE_INICIAL = 25000.0
MAX_DAILY_LOSS  = 0.05   # 5%  = ,250
MAX_TOTAL_LOSS  = 0.10   # 10% = ,500
PROFIT_TARGET   = 0.10   # 10% = ,500

def get_ftmo_status(account_info=None):
    balance   = account_info.get('balance', BALANCE_INICIAL) if account_info else BALANCE_INICIAL
    equity    = account_info.get('equity',  BALANCE_INICIAL) if account_info else BALANCE_INICIAL
    profit    = account_info.get('profit',  0)               if account_info else 0

    daily_loss_limit  = BALANCE_INICIAL * MAX_DAILY_LOSS   # ,250
    total_loss_limit  = BALANCE_INICIAL * MAX_TOTAL_LOSS   # ,500
    profit_target_usd = BALANCE_INICIAL * PROFIT_TARGET    # ,500

    total_drawdown = BALANCE_INICIAL - equity
    daily_pnl      = _get_daily_pnl()

    can_trade = True
    reasons   = []

    if total_drawdown >= total_loss_limit:
        can_trade = False
        reasons.append(f'TOTAL LOSS LIMIT HIT: drawdown  >= ')

    if daily_pnl <= -daily_loss_limit:
        can_trade = False
        reasons.append(f'DAILY LOSS LIMIT HIT: today  <= -')

    daily_remaining  = daily_loss_limit + daily_pnl
    total_remaining  = total_loss_limit - total_drawdown
    profit_remaining = profit_target_usd - (balance - BALANCE_INICIAL)

    return {
        'can_trade':         can_trade,
        'reasons':           reasons,
        'balance':           balance,
        'equity':            equity,
        'total_drawdown':    round(total_drawdown, 2),
        'daily_pnl':         round(daily_pnl, 2),
        'daily_loss_limit':  daily_loss_limit,
        'total_loss_limit':  total_loss_limit,
        'daily_remaining':   round(daily_remaining, 2),
        'total_remaining':   round(total_remaining, 2),
        'profit_target':     profit_target_usd,
        'profit_remaining':  round(profit_remaining, 2),
        'target_reached':    (balance - BALANCE_INICIAL) >= profit_target_usd
    }

def _get_daily_pnl():
    today = date.today().isoformat()
    daily = 0.0
    positions_file = os.path.join(STATE_DIR, 'positions.json')
    if not os.path.exists(positions_file):
        return 0.0
    with open(positions_file) as f:
        positions = json.load(f)
    for p in positions:
        closed_at = p.get('closed_at', '')
        if closed_at and closed_at[:10] == today and p.get('pnl') is not None:
            daily += p['pnl']
    return daily

def validate_before_trade(risk_plan, account_info=None):
    status = get_ftmo_status(account_info)

    if not status['can_trade']:
        return {'approved': False, 'reason': ' | '.join(status['reasons']), 'ftmo_status': status}

    risk_usd = risk_plan.get('risk_usd', 0)
    if risk_usd > status['daily_remaining']:
        return {'approved': False,
                'reason': f'Trade risk  exceeds daily remaining ',
                'ftmo_status': status}

    if risk_usd > status['total_remaining']:
        return {'approved': False,
                'reason': f'Trade risk  exceeds total remaining ',
                'ftmo_status': status}

    if status['target_reached']:
        return {'approved': False, 'reason': 'PROFIT TARGET REACHED — stop trading and request payout',
                'ftmo_status': status}

    return {'approved': True, 'reason': 'All FTMO rules OK', 'ftmo_status': status}
