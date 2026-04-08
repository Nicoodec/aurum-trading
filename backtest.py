import random
from agents.risk_manager import calculate as risk_calc

SAMPLE_PRICES = [
    {"price": 4600, "change_pct": 0.3,  "high": 4630, "low": 4580, "open": 4590},
    {"price": 4550, "change_pct": -1.1, "high": 4610, "low": 4540, "open": 4600},
    {"price": 4680, "change_pct": 2.9,  "high": 4700, "low": 4545, "open": 4555},
    {"price": 4720, "change_pct": 0.9,  "high": 4740, "low": 4670, "open": 4682},
    {"price": 4700, "change_pct": -0.4, "high": 4730, "low": 4690, "open": 4720},
    {"price": 4780, "change_pct": 1.7,  "high": 4800, "low": 4695, "open": 4702},
    {"price": 4750, "change_pct": -0.6, "high": 4790, "low": 4740, "open": 4780},
    {"price": 4820, "change_pct": 1.5,  "high": 4840, "low": 4745, "open": 4752},
    {"price": 4860, "change_pct": 0.8,  "high": 4880, "low": 4815, "open": 4822},
    {"price": 4840, "change_pct": -0.4, "high": 4870, "low": 4830, "open": 4860},
    {"price": 4900, "change_pct": 1.2,  "high": 4920, "low": 4835, "open": 4842},
    {"price": 4880, "change_pct": -0.4, "high": 4910, "low": 4870, "open": 4900},
    {"price": 4950, "change_pct": 1.4,  "high": 4970, "low": 4875, "open": 4882},
    {"price": 4990, "change_pct": 0.8,  "high": 5010, "low": 4945, "open": 4952},
    {"price": 4960, "change_pct": -0.6, "high": 5000, "low": 4950, "open": 4990},
    {"price": 5020, "change_pct": 1.2,  "high": 5040, "low": 4955, "open": 4962},
    {"price": 5060, "change_pct": 0.8,  "high": 5080, "low": 5015, "open": 5022},
    {"price": 5040, "change_pct": -0.4, "high": 5070, "low": 5030, "open": 5060},
    {"price": 5100, "change_pct": 1.2,  "high": 5120, "low": 5035, "open": 5042},
    {"price": 5080, "change_pct": -0.4, "high": 5110, "low": 5070, "open": 5100},
]

def sim_debate(change_pct):
    if change_pct > 1.0:
        bull = random.randint(62, 82)
        bear = random.randint(42, 62)
    elif change_pct < -1.0:
        bull = random.randint(42, 62)
        bear = random.randint(62, 82)
    elif change_pct > 0.3:
        bull = random.randint(55, 75)
        bear = random.randint(45, 65)
    elif change_pct < -0.3:
        bull = random.randint(45, 65)
        bear = random.randint(55, 75)
    else:
        bull = random.randint(48, 68)
        bear = random.randint(48, 68)
    margin = abs(bull - bear)
    is_tie = margin < 10
    winner = "TIE" if is_tie else ("BULL" if bull > bear else "BEAR")
    return {"winner": winner, "is_tie": is_tie,
            "avg_bull_confidence": bull, "avg_bear_confidence": bear, "margin": margin}

def sim_tech(p):
    return {
        "trend":      "UP",
        "support":    round(p * 0.982, 2),
        "resistance": round(p * 1.025, 2),
        "rsi_zone":   "NEUTRAL",
        "bias":       "BULLISH",
        "rsi_value":  55,
        "sma20":      round(p * 0.995, 2),
    }

def run_backtest(capital=25000):
    balance = capital
    trades  = []
    sep = "=" * 60
    print()
    print(sep)
    print("AURUM BACKTEST | " + str(len(SAMPLE_PRICES)) + " cycles | Capital: $" + str(capital))
    print(sep)

    for i, pd in enumerate(SAMPLE_PRICES):
        pd["source"] = "backtest"
        tech   = sim_tech(pd["price"])
        debate = sim_debate(pd["change_pct"])

        if debate["is_tie"]:
            print("[" + str(i+1).zfill(2) + "] $" + str(pd["price"]) + " | STAY OUT (tie)")
            continue

        risk = risk_calc(debate, tech, pd, balance)
        if not risk["valid"]:
            print("[" + str(i+1).zfill(2) + "] $" + str(pd["price"]) + " | STAY OUT (" + risk["reason"][:45] + ")")
            continue

        entry = risk["entry"]
        sl    = risk["stop_loss"]
        tp    = risk["take_profit"]
        lots  = risk["contracts"]
        dirn  = risk["direction"]

        if i + 1 < len(SAMPLE_PRICES):
            nx   = SAMPLE_PRICES[i+1]
            nh   = nx.get("high", nx["price"] * 1.005)
            nl   = nx.get("low",  nx["price"] * 0.995)
            if dirn == "LONG":
                if nl <= sl:
                    pnl, res = round((sl - entry) * lots * 100, 2), "LOSS"
                elif nh >= tp:
                    pnl, res = round((tp - entry) * lots * 100, 2), "WIN"
                else:
                    pnl, res = round((nx["price"] - entry) * lots * 100, 2), "OPEN"
            else:
                if nh >= sl:
                    pnl, res = round((entry - sl) * lots * 100, 2), "LOSS"
                elif nl <= tp:
                    pnl, res = round((entry - tp) * lots * 100, 2), "WIN"
                else:
                    pnl, res = round((entry - nx["price"]) * lots * 100, 2), "OPEN"
        else:
            pnl, res = 0, "OPEN"

        balance += pnl
        trades.append({"direction": dirn, "pnl": pnl, "result": res, "balance": balance})
        mk = "WIN " if res == "WIN" else ("LOSS" if res == "LOSS" else "... ")
        print("[" + str(i+1).zfill(2) + "] $" + str(pd["price"]) + " | " + dirn.ljust(5) + " | " + mk + " | PnL: $" + str(pnl) + " | Bal: $" + str(round(balance,2)))

    closed = [t for t in trades if t["result"] in ("WIN","LOSS")]
    wins   = [t for t in closed if t["result"] == "WIN"]
    losses = [t for t in closed if t["result"] == "LOSS"]
    print()
    print(sep)
    print("BACKTEST RESULTS")
    print("  Trades: " + str(len(closed)) + " | Wins: " + str(len(wins)) + " | Losses: " + str(len(losses)))
    if closed:
        wr = round(len(wins)/len(closed)*100,1)
        print("  Win rate: " + str(wr) + "%")
    print("  Total PnL: $" + str(round(balance-capital,2)))
    print("  Final balance: $" + str(round(balance,2)))
    print("  Return: " + str(round((balance-capital)/capital*100,2)) + "%")
    if wins:   print("  Avg win:  $" + str(round(sum(t["pnl"] for t in wins)/len(wins),2)))
    if losses: print("  Avg loss: $" + str(round(sum(t["pnl"] for t in losses)/len(losses),2)))
    gw = sum(t["pnl"] for t in wins)
    gl = abs(sum(t["pnl"] for t in losses))
    if gl > 0: print("  Profit factor: " + str(round(gw/gl,2)))
    print(sep)
    return trades

if __name__ == "__main__":
    run_backtest()
