import json, os
from datetime import date
from config import STATE_DIR

BALANCE_INICIAL    = 25000.0
MAX_DAILY_LOSS_PCT = 0.05
MAX_TOTAL_LOSS_PCT = 0.10
PROFIT_TARGET_PCT  = 0.10
WARN_DAILY_PCT     = 0.03
WARN_TOTAL_PCT     = 0.07

def _daily_pnl():
    today = date.today().isoformat()
    f = os.path.join(STATE_DIR, 'positions.json')
    if not os.path.exists(f): return 0.0
    try:
        with open(f, encoding='utf-8') as fh: pos = json.load(fh)
        total = 0.0
        for p in pos:
            closed = p.get('closed_at') or ''
            if isinstance(closed, str) and closed[:10] == today:
                total += float(p.get('pnl') or 0)
        return total
    except Exception as e:
        print('[ftmo] daily_pnl error: ' + str(e))
        return 0.0

def get_ftmo_status(account_info=None):
    bal = account_info.get('balance', BALANCE_INICIAL) if account_info else BALANCE_INICIAL
    eq  = account_info.get('equity',  BALANCE_INICIAL) if account_info else BALANCE_INICIAL
    dd  = BALANCE_INICIAL * MAX_DAILY_LOSS_PCT
    td  = BALANCE_INICIAL * MAX_TOTAL_LOSS_PCT
    tgt = BALANCE_INICIAL * PROFIT_TARGET_PCT
    ttl_dd = BALANCE_INICIAL - eq
    dpnl = _daily_pnl()
    ok = True; reasons = []; warnings = []
    if ttl_dd >= td: ok = False; reasons.append('TOTAL LOSS LIMIT $' + str(round(ttl_dd,2)))
    if dpnl <= -dd: ok = False; reasons.append('DAILY LOSS LIMIT $' + str(round(dpnl,2)))
    if ttl_dd >= BALANCE_INICIAL*WARN_TOTAL_PCT and ok: warnings.append('WARNING total DD $'+str(round(ttl_dd,2)))
    if dpnl <= -(BALANCE_INICIAL*WARN_DAILY_PCT) and ok: warnings.append('WARNING daily $'+str(round(dpnl,2)))
    return {'can_trade':ok,'reasons':reasons,'warnings':warnings,
            'balance':bal,'equity':eq,'total_drawdown':round(ttl_dd,2),'daily_pnl':round(dpnl,2),
            'daily_remaining':round(dd+dpnl,2),'total_remaining':round(td-ttl_dd,2),
            'profit_target':tgt,'profit_remaining':round(tgt-(bal-BALANCE_INICIAL),2),
            'target_reached':(bal-BALANCE_INICIAL)>=tgt}

def validate_before_trade(risk_plan, account_info=None):
    s = get_ftmo_status(account_info)
    if not s['can_trade']: return {'approved':False,'reason':' | '.join(s['reasons']),'ftmo_status':s}
    risk = risk_plan.get('risk_usd',0) or 0
    if risk > s['daily_remaining']: return {'approved':False,'reason':'Risk exceeds daily remaining','ftmo_status':s}
    if s.get('target_reached'): return {'approved':False,'reason':'Profit target reached','ftmo_status':s}
    return {'approved':True,'reason':'FTMO OK','warnings':s.get('warnings',[]),'ftmo_status':s}