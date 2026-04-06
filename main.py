# main.py — AURUM orchestrator v2
import json, os
from datetime import datetime
from agents.news_collector import collect as collect_news
from agents.price_feed import get_technical_data
from agents.macro_analyst import analyze as macro_analyze
from agents.technical_analyst import analyze as tech_analyze
from agents.debate import run_debate
from agents.risk_manager import calculate as risk_calc
from agents.arbitrator import decide
from utils.state_manager import save_cycle
from utils.github_sync import sync
from portfolio import add_position, get_stats
from config import MAX_POSITIONS

MT5_ENABLED = False   # cambiar a True cuando estes listo con credenciales FTMO
MT5_LOGIN    = None   # tu login FTMO demo
MT5_PASSWORD = None
MT5_SERVER   = None   # ej: 'FTMO-Demo'

def run_cycle():
    print(f'\n{"="*50}')
    print(f'AURUM CYCLE — {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print('='*50)

    # Check posiciones abiertas
    stats = get_stats()
    print(f'[portfolio] Equity:  | Open: {stats["open_positions"]}/{MAX_POSITIONS}')
    if stats['open_positions'] >= MAX_POSITIONS:
        print('[portfolio] MAX positions reached — skipping cycle')
        return None

    print('[1/7] Collecting news...')
    news = collect_news()

    print('[2/7] Getting price feed...')
    price = get_technical_data()
    print(f'      XAU/USD: {price.get("price")} ({price.get("source")}) | Change: {price.get("change_pct")}%')

    print('[3/7] Macro analysis...')
    macro = macro_analyze(news, price)
    print(f'      Bias: {macro.get("macro_bias")} ({macro.get("confidence")}%)')

    print('[4/7] Technical analysis...')
    tech = tech_analyze(price)
    print(f'      Trend: {tech.get("trend")} | S: {tech.get("support")} R: {tech.get("resistance")}')

    print('[5/7] Running debate (3 rounds)...')
    debate = run_debate(macro, tech, price)
    print(f'      Winner: {debate.get("winner")} | Bull {debate.get("avg_bull_confidence")}% vs Bear {debate.get("avg_bear_confidence")}%')

    print('[6/7] Risk management...')
    risk = risk_calc(debate, tech, price)
    if risk.get('valid'):
        print(f'      Direction: {risk.get("direction")} | R:R {risk.get("risk_reward")} | Risk  | Kelly {risk.get("kelly_fraction")}%')
    else:
        print(f'      INVALID: {risk.get("reason")}')

    print('[7/7] Arbitrator deciding...')
    final = decide(debate, risk, macro, news)
    decision = final.get('decision')
    print(f'\n>>> DECISION: {decision} (confidence: {final.get("confidence")}%)')
    print(f'    Reason: {final.get("reason")}')

    ticket = None
    if risk.get('valid') and decision in ('LONG', 'SHORT'):
        print(f'    Entry: {risk.get("entry")} | SL: {risk.get("stop_loss")} | TP: {risk.get("take_profit")} | Lots: {risk.get("contracts")}')
        if MT5_ENABLED:
            try:
                from agents.mt5_broker import connect, open_trade
                if connect(MT5_LOGIN, MT5_PASSWORD, MT5_SERVER):
                    lot_size = max(0.01, round(risk.get('contracts', 0.01), 2))
                    result = open_trade(decision, lot_size, risk['stop_loss'], risk['take_profit'])
                    if result:
                        ticket = result['ticket']
                        print(f'    [MT5] Order placed: ticket={ticket}')
            except Exception as e:
                print(f'    [MT5] Error: {e}')

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
        print(f'    [portfolio] Position recorded')

    folder = save_cycle(cycle_data)
    print(f'\n[SAVED] {folder}')

    # Generar dashboard actualizado
    generate_dashboard(cycle_data)

    sync(f'AURUM: {decision} @ {price.get("price")} — {datetime.now().strftime("%H:%M")}')
    return cycle_data

def generate_dashboard(latest):
    from utils.state_manager import load_history
    history = load_history()
    stats = get_stats()
    # Escribir estado para dashboard
    import json
    os.makedirs('dashboard', exist_ok=True)
    with open('dashboard/state.json', 'w') as f:
        json.dump({'latest': latest, 'history': history[-50:], 'stats': stats}, f, indent=2, default=str)

if __name__ == '__main__':
    run_cycle()
