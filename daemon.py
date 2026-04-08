import time, traceback
from datetime import datetime, timezone

NEWS_INTERVAL  = 300
CYCLE_INTERVAL = 14400
MON_INTERVAL   = 60

last_cycle = 0
last_news  = 0
seen       = set()

def market_open():
    n=datetime.now(timezone.utc); wd,h=n.weekday(),n.hour
    if wd==5: return False
    if wd==6 and h<22: return False
    if wd==4 and h>=22: return False
    return True

def check_news():
    from agents.news_collector import collect
    from utils.telegram_alerts import alert_news_flash
    HIGH=['trump','fed ','cpi','nfp','war','attack','iran','israel','russia','emergency','crisis','tariff','sanction','collapse']
    try:
        news=collect(); items=news.get('news_items',[]); sent=news.get('sentiment','NEUTRAL')
        brk=[i['title'] for i in items if i['title'] not in seen and any(k in i['title'].lower() for k in HIGH)]
        for b in brk: seen.add(b)
        if len(seen)>500: seen.clear()
        if brk:
            print('[daemon] BREAKING: '+brk[0][:80])
            if sent in ('BULLISH_GOLD','BEARISH_GOLD'): alert_news_flash(brk[0][:120],sent)
            return True,news
        return False,news
    except Exception as e: print('[daemon] news: '+str(e)); return False,{}

def monitor():
    try:
        from agents.mt5_broker import connect,get_open_positions,get_account_summary,disconnect
        from agents.ftmo_validator import get_ftmo_status
        from utils.telegram_alerts import alert_ftmo
        from portfolio import load_positions,close_position
        if not connect(1513020113,'FH2dXFt7?','FTMO-Demo'): return
        acc=get_account_summary(); ftmo=get_ftmo_status(acc)
        pos=get_open_positions(); tick={p['ticket'] for p in pos}
        ts=datetime.now().strftime('%H:%M:%S')
        print('['+ts+'] Eq:$'+str(round(acc.get('equity',0),2))+' Profit:$'+str(round(acc.get('profit',0),2))+' Open:'+str(len(pos))+' Daily:$'+str(ftmo['daily_remaining']))
        for w in ftmo.get('warnings',[]): print('[FTMO] '+w)
        if not ftmo['can_trade']: alert_ftmo(' | '.join(ftmo.get('reasons',[])))
        local=load_positions()
        for p in local:
            if p['status']=='OPEN' and p.get('ticket') and p['ticket'] not in tick:
                print('[daemon] Closed by MT5: ticket '+str(p['ticket']))
                try:
                    import MetaTrader5 as mt5
                    from datetime import timedelta
                    deals=mt5.history_deals_get(datetime.now()-timedelta(hours=48),datetime.now())
                    deal=next((d for d in (deals or []) if d.position_id==p['ticket']),None)
                    ep=deal.price if deal else p.get('take_profit',0)
                    pnl=deal.profit if deal else 0
                    close_position(p['id'],ep,pnl)
                    from utils.telegram_alerts import alert_closed
                    alert_closed(p,ep)
                except Exception as e2: print('[daemon] deal err: '+str(e2))
        disconnect()
    except Exception as e: print('[daemon] monitor: '+str(e))

def cycle():
    try:
        from main import run_cycle
        run_cycle()
    except Exception as e: print('[daemon] cycle: '+str(e)); traceback.print_exc()

from utils.telegram_alerts import send
send('AURUM DAEMON started. News:5min Cycle:4h Monitor:1min')
print('[AURUM DAEMON] Running')
cycle(); last_cycle=time.time(); last_news=time.time()

while True:
    now=time.time()
    try:
        monitor()
        if now-last_news>=NEWS_INTERVAL:
            last_news=now
            if market_open():
                brk,_=check_news()
                if brk: cycle(); last_cycle=now
        if now-last_cycle>=CYCLE_INTERVAL:
            last_cycle=now
            if market_open(): cycle()
            else: print('[daemon] Market closed')
        time.sleep(MON_INTERVAL)
    except KeyboardInterrupt: send('AURUM DAEMON stopped'); break
    except Exception as e: print('[daemon] loop: '+str(e)); time.sleep(30)