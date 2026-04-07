# main.py
import json, os
from datetime import datetime
from agents.news_collector import collect as collect_news
from agents.price_feed import get_technical_data
from agents.macro_analyst import analyze as macro_analyze
from agents.technical_analyst import analyze as tech_analyze
from agents.debate import run_debate
from agents.risk_manager import calculate as risk_calc
from agents.arbitrator import decide
from agents.ftmo_validator import validate_before_trade
from utils.state_manager import save_cycle
from utils.github_sync import sync
from portfolio import add_position, get_stats
from config import MAX_POSITIONS

MT5_ENABLED  = True
MT5_LOGIN    = 1513020113
MT5_PASSWORD = 'FH2dXFt7?'
MT5_SERVER   = 'FTMO-Demo'

def run_cycle():
    print()
    print('='*50)
    print('AURUM CYCLE --', datetime.now().strftime('%Y-%m-%d %H:%M'))
    print('='*50)

    stats = get_stats()
    print('[portfolio] Equity: $' + str(stats['equity']) + ' | Open: ' + str(stats['open_positions']) + '/' + str(MAX_POSITIONS))
    if stats['open_positions'] >= MAX_POSITIONS:
        print('[portfolio] MAX positions reached')
        return None

    print('[1/7] Collecting news...')
    news = collect_news()

    print('[2/7] Getting price feed...')
    price = get_technical_data()
    print('      XAU/USD:', price.get('price'), '|', price.get('source'), '| Change:', price.get('change_pct'), '%')

    print('[3/7] Macro analysis...')
    macro = macro_analyze(news, price)
    print('      Bias:', macro.get('macro_bias'), 'conf:', macro.get('confidence'))

    print('[4/7] Technical analysis...')
    tech = tech_analyze(price)
    print('      Trend:', tech.get('trend'), 'S:', tech.get('support'), 'R:', tech.get('resistance'))

    print('[5/7] Running debate 3 rounds...')
    debate = run_debate(macro, tech, price)
    print('      Winner:', debate.get('winner'), 'Bull:', debate.get('avg_bull_confidence'), 'Bear:', debate.get('avg_bear_confidence'))

    print('[6/7] Risk management...')
    account_info = None
    if MT5_ENABLED:
        try:
            from agents.mt5_broker import connect, get_account_summary, disconnect
            if connect(MT5_LOGIN, MT5_PASSWORD, MT5_SERVER):
                account_info = get_account_summary()
                disconnect()
        except Exception as e:
            print('      [MT5] error:', e)
    risk = risk_calc(debate, tech, price, account_info.get('balance') if account_info else None)
    if risk.get('valid'):
        print('      Dir:', risk.get('direction'), 'R:R:', risk.get('risk_reward'), 'Risk $' + str(risk.get('risk_usd')), 'Lots:', risk.get('contracts'))
    else:
        print('      INVALID:', risk.get('reason'))

    ftmo_check = validate_before_trade(risk, account_info)
    if not ftmo_check['approved']:
        print('      [FTMO] BLOCKED:', ftmo_check['reason'])
        risk['valid'] = False
        risk['reason'] = ftmo_check['reason']
    else:
        fs = ftmo_check['ftmo_status']
        print('      [FTMO] OK | Daily remaining: $' + str(fs['daily_remaining']) + ' | Total: $' + str(fs['total_remaining']))

    print('[7/7] Arbitrator deciding...')
    final = decide(debate, risk, macro, news)
    decision = final.get('decision')
    print('>>> DECISION:', decision, 'conf:', final.get('confidence'))
    print('    Reason:', final.get('reason'))

    ticket = None
    if risk.get('valid') and decision in ('LONG', 'SHORT'):
        print('    Entry:', risk.get('entry'), 'SL:', risk.get('stop_loss'), 'TP:', risk.get('take_profit'), 'Lots:', risk.get('contracts'))
        if MT5_ENABLED:
            try:
                from agents.mt5_broker import connect, open_trade, disconnect
                if connect(MT5_LOGIN, MT5_PASSWORD, MT5_SERVER):
                    lot_size = max(0.01, round(risk.get('contracts', 0.01), 2))
                    result = open_trade(decision, lot_size, risk['stop_loss'], risk['take_profit'])
                    if result:
                        ticket = result['ticket']
                        print('    [MT5] ticket:', ticket)
                    disconnect()
            except Exception as e:
                print('    [MT5] Error:', e)

    cycle_data = {
        'ts': datetime.now().isoformat(),
        'price': price.get('price'),
        'change_pct': price.get('change_pct'),
        'decision': decision,
        'confidence': final.get('confidence'),
        'reason': final.get('reason'),
        'risk_plan': risk,
        'mt5_ticket': ticket,
        'debate_summary': {
            'winner': debate.get('winner'),
            'bull_conf': debate.get('avg_bull_confidence'),
            'bear_conf': debate.get('avg_bear_confidence'),
            'margin': debate.get('margin'),
            'is_tie': debate.get('is_tie')
        },
        'macro': {
            'bias': macro.get('macro_bias'),
            'confidence': macro.get('confidence'),
            'drivers': macro.get('key_drivers'),
            'risks': macro.get('risks')
        },
        'technical': {
            'trend': tech.get('trend'),
            'support': tech.get('support'),
            'resistance': tech.get('resistance'),
            'rsi_zone': tech.get('rsi_zone'),
            'bias': tech.get('bias')
        },
        'portfolio': get_stats()
    }

    if decision in ('LONG', 'SHORT') and risk.get('valid'):
        add_position(cycle_data, ticket=ticket)
        print('    [portfolio] Position recorded')

    folder = save_cycle(cycle_data)
    generate_dashboard(cycle_data)
    print('[SAVED]', folder)

    # Multi-timeframe analysis
    from agents.mtf_analyst import analyze as mtf_analyze
    mtf = mtf_analyze(price)
    print('      MTF confluence:', mtf.get('confluence'), '| Aligned:', mtf.get('aligned_timeframes'), '/3')
    cycle_data['mtf'] = mtf

    # Auto-close check
    from agents.auto_close import run_auto_close
    closed = run_auto_close(news)
    if closed:
        print('[auto_close] Closed', len(closed), 'positions')

    # Telegram alert
    try:
        from utils.telegram_alerts import alert_decision
        alert_decision(cycle_data)
    except Exception as e:
        print('[telegram] alert error:', e)
    sync('AURUM: ' + decision + ' @ ' + str(price.get('price')))
    return cycle_data

def generate_dashboard(latest):
    from utils.state_manager import load_history
    from gen_dashboard import generate as gen_html
    history = load_history()
    stats = get_stats()
    gen_html(latest=latest, history=history, stats=stats)

if __name__ == '__main__':
    run_cycle()
