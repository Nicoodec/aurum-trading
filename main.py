# main.py — AURUM orchestrator
import json
from datetime import datetime
from agents.news_collector import collect as collect_news
from agents.price_feed import get_technical_data
from agents.macro_analyst import analyze as macro_analyze
from agents.technical_analyst import analyze as tech_analyze
from agents.debate import run_debate
from agents.risk_manager import calculate as risk_calc
from agents.arbitrator import decide
from utils.state_manager import save_cycle, load_history
from utils.github_sync import sync

def run_cycle():
    print(f'\n{"="*50}')
    print(f'AURUM CYCLE — {datetime.now().strftime("%Y-%m-%d %H:%M")}')
    print('='*50)

    print('[1/7] Collecting news...')
    news = collect_news()

    print('[2/7] Getting price feed...')
    price = get_technical_data()
    print(f'      XAU/USD: {price.get("price")} ({price.get("source")})')

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
        print(f'      R:R {risk.get("risk_reward")} | Risk  | Kelly {risk.get("kelly_fraction")}%')
    else:
        print(f'      INVALID: {risk.get("reason")}')

    print('[7/7] Arbitrator deciding...')
    final = decide(debate, risk, macro, news)
    print(f'\n>>> DECISION: {final.get("decision")} (confidence: {final.get("confidence")}%)')
    print(f'    Reason: {final.get("reason")}')
    if risk.get('valid') and final.get('decision') != 'STAY OUT':
        print(f'    Entry: {risk.get("entry")} | SL: {risk.get("stop_loss")} | TP: {risk.get("take_profit")}')

    cycle_data = {
        'ts': datetime.now().isoformat(),
        'price': price.get('price'),
        'decision': final.get('decision'),
        'confidence': final.get('confidence'),
        'reason': final.get('reason'),
        'risk_plan': risk,
        'debate_summary': {
            'winner': debate.get('winner'),
            'bull_conf': debate.get('avg_bull_confidence'),
            'bear_conf': debate.get('avg_bear_confidence'),
            'margin': debate.get('margin')
        },
        'macro': {'bias': macro.get('macro_bias'), 'drivers': macro.get('key_drivers')},
        'technical': {'trend': tech.get('trend'), 'support': tech.get('support'), 'resistance': tech.get('resistance')}
    }

    folder = save_cycle(cycle_data)
    print(f'\n[SAVED] {folder}')
    sync(f'AURUM: {final.get("decision")} @ {price.get("price")} — {datetime.now().strftime("%H:%M")}')
    return cycle_data

if __name__ == '__main__':
    run_cycle()
