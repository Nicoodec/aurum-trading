# backtest.py — simula ciclos sobre datos historicos de XAU/USD
import json, os, random
from datetime import datetime, timedelta
from agents.risk_manager import calculate as risk_calc
from portfolio import get_stats

# Datos sinteticos basados en movimientos reales XAU/USD 2024-2025
# En produccion reemplazar con datos reales de goldapi historico o yfinance
SAMPLE_PRICES = [
    {'price': 2320, 'change_pct': 0.3,  'high': 2335, 'low': 2310, 'open': 2315},
    {'price': 2280, 'change_pct': -1.7, 'high': 2325, 'low': 2275, 'open': 2320},
    {'price': 2350, 'change_pct': 3.1,  'high': 2365, 'low': 2280, 'open': 2285},
    {'price': 2400, 'change_pct': 2.1,  'high': 2415, 'low': 2345, 'open': 2355},
    {'price': 2380, 'change_pct': -0.8, 'high': 2410, 'low': 2370, 'open': 2400},
    {'price': 2450, 'change_pct': 2.9,  'high': 2465, 'low': 2375, 'open': 2382},
    {'price': 2420, 'change_pct': -1.2, 'high': 2455, 'low': 2415, 'open': 2450},
    {'price': 2480, 'change_pct': 2.5,  'high': 2495, 'low': 2418, 'open': 2422},
    {'price': 2510, 'change_pct': 1.2,  'high': 2525, 'low': 2475, 'open': 2480},
    {'price': 2490, 'change_pct': -0.8, 'high': 2520, 'low': 2485, 'open': 2510},
    {'price': 2550, 'change_pct': 2.4,  'high': 2565, 'low': 2488, 'open': 2492},
    {'price': 2530, 'change_pct': -0.8, 'high': 2558, 'low': 2520, 'open': 2550},
    {'price': 2600, 'change_pct': 2.8,  'high': 2615, 'low': 2528, 'open': 2532},
    {'price': 2650, 'change_pct': 1.9,  'high': 2668, 'low': 2598, 'open': 2602},
    {'price': 2700, 'change_pct': 1.9,  'high': 2718, 'low': 2645, 'open': 2652},
    {'price': 2680, 'change_pct': -0.7, 'high': 2715, 'low': 2672, 'open': 2700},
    {'price': 2750, 'change_pct': 2.6,  'high': 2768, 'low': 2678, 'open': 2682},
    {'price': 2800, 'change_pct': 1.8,  'high': 2818, 'low': 2748, 'open': 2752},
    {'price': 2780, 'change_pct': -0.7, 'high': 2812, 'low': 2772, 'open': 2800},
    {'price': 2850, 'change_pct': 2.5,  'high': 2868, 'low': 2778, 'open': 2782},
]

def simulate_debate_result(price_data, bias='random'):
    if bias == 'random':
        bull = random.randint(45, 80)
        bear = random.randint(45, 80)
    elif bias == 'bull':
        bull = random.randint(60, 85)
        bear = random.randint(40, 60)
    else:
        bull = random.randint(40, 60)
        bear = random.randint(60, 85)
    margin = abs(bull - bear)
    is_tie = margin < 10
    winner = 'TIE' if is_tie else ('BULL' if bull > bear else 'BEAR')
    return {
        'winner': winner, 'is_tie': is_tie,
        'avg_bull_confidence': bull,
        'avg_bear_confidence': bear,
        'margin': margin
    }

def simulate_tech(price_data):
    p = price_data['price']
    return {
        'trend': 'UP' if price_data['change_pct'] > 0 else 'DOWN',
        'support': round(p * 0.990, 2),
        'resistance': round(p * 1.010, 2),
        'rsi_zone': 'OVERBOUGHT' if price_data['change_pct'] > 2 else 'NEUTRAL',
        'bias': 'BULLISH' if price_data['change_pct'] > 0 else 'BEARISH'
    }

def run_backtest(capital=25000, n_cycles=None):
    prices = SAMPLE_PRICES if not n_cycles else SAMPLE_PRICES[:n_cycles]
    balance = capital
    trades = []
    print(f'\n{"="*55}')
    print(f'AURUM BACKTEST — {len(prices)} cycles | Capital: ')
    print('='*55)

    for i, price_data in enumerate(prices):
        price_data['source'] = 'backtest'
        tech = simulate_tech(price_data)
        # Bias basado en cambio de precio
        bias = 'bull' if price_data['change_pct'] > 0.5 else ('bear' if price_data['change_pct'] < -0.5 else 'random')
        debate = simulate_debate_result(price_data, bias)

        if debate['is_tie']:
            print(f'[{i+1:02d}]  | STAY OUT (tie)')
            continue

        risk = risk_calc(debate, tech, price_data, balance)
        if not risk['valid']:
            print(f'[{i+1:02d}]  | STAY OUT ({risk["reason"][:40]})')
            continue

        direction = risk['direction']
        entry = risk['entry']
        sl = risk['stop_loss']
        tp = risk['take_profit']
        lots = risk['contracts']

        # Simular resultado: precio siguiente determina si SL o TP se toca
        if i + 1 < len(prices):
            next_price = prices[i+1]['price']
            next_high  = prices[i+1].get('high', next_price * 1.005)
            next_low   = prices[i+1].get('low',  next_price * 0.995)
            if direction == 'LONG':
                if next_low <= sl:
                    pnl = round((sl - entry) * lots * 100, 2)
                    result = 'LOSS'
                elif next_high >= tp:
                    pnl = round((tp - entry) * lots * 100, 2)
                    result = 'WIN'
                else:
                    pnl = round((next_price - entry) * lots * 100, 2)
                    result = 'OPEN'
            else:
                if next_high >= sl:
                    pnl = round((entry - sl) * lots * 100, 2)
                    result = 'LOSS'
                elif next_low <= tp:
                    pnl = round((entry - tp) * lots * 100, 2)
                    result = 'WIN'
                else:
                    pnl = round((entry - next_price) * lots * 100, 2)
                    result = 'OPEN'
        else:
            pnl = 0
            result = 'OPEN'

        balance += pnl
        trades.append({'direction': direction, 'entry': entry, 'sl': sl, 'tp': tp,
                       'lots': lots, 'pnl': pnl, 'result': result, 'balance': balance})
        marker = 'WIN' if result == 'WIN' else ('LOSS' if result == 'LOSS' else '...')
        print(f'[{i+1:02d}]  | {direction:5s} | {marker:4s} | P&L:  | Balance: ')

    closed = [t for t in trades if t['result'] in ('WIN','LOSS')]
    wins   = [t for t in closed if t['result'] == 'WIN']
    losses = [t for t in closed if t['result'] == 'LOSS']

    print(f'\n{"="*55}')
    print(f'BACKTEST RESULTS')
    print(f'  Total trades:   {len(closed)}')
    print(f'  Wins:           {len(wins)} | Losses: {len(losses)}')
    print(f'  Win rate:       {len(wins)/len(closed)*100:.1f}%' if closed else '  Win rate: N/A')
    print(f'  Total P&L:      ')
    print(f'  Final balance:  ')
    print(f'  Return:         {(balance-capital)/capital*100:+.1f}%')
    if wins:   print(f'  Avg win:        ')
    if losses: print(f'  Avg loss:       ')
    gross_win  = sum(t['pnl'] for t in wins)
    gross_loss = abs(sum(t['pnl'] for t in losses))
    if gross_loss > 0:
        print(f'  Profit factor:  {gross_win/gross_loss:.2f}')
    print('='*55)
    return trades

if __name__ == '__main__':
    run_backtest()
