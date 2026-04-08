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
from gen_dashboard import generate as gen_html
from utils.state_manager import load_history

MT5_ENABLED  = True
MT5_LOGIN    = 1513020113
MT5_PASSWORD = "FH2dXFt7?"
MT5_SERVER   = "FTMO-Demo"

def run_cycle():
    print()
    print("=" * 52)
    print("AURUM CYCLE -- " + datetime.now().strftime("%Y-%m-%d %H:%M"))
    print("=" * 52)

    stats = get_stats()
    print("[portfolio] Equity: $" + str(stats["equity"]) + " | Open: " + str(stats["open_positions"]) + "/" + str(MAX_POSITIONS))
    if stats["open_positions"] >= MAX_POSITIONS:
        print("[portfolio] MAX positions -- skipping")
        return None

    print("[1/7] Collecting news...")
    news = collect_news()
    ni = news.get("news_items", [])
    print("      Got " + str(len(ni)) + " news items | Sentiment: " + str(news.get("sentiment","NEUTRAL")))
    for n in ni[:5]:
        print("      >> [" + n["source"] + "] " + n["title"][:75])

    print("[2/7] Getting price feed...")
    price = get_technical_data()
    print("      XAU/USD: " + str(price.get("price")) + " | Change: " + str(price.get("change_pct")) + "% | H:" + str(price.get("high")) + " L:" + str(price.get("low")))

    print("[3/7] Macro analysis...")
    macro = macro_analyze(news, price)
    print("      Bias: " + str(macro.get("macro_bias")) + " (" + str(macro.get("confidence")) + "%)")
    print("      Drivers: " + str(macro.get("key_drivers", [])))

    print("[4/7] Technical analysis...")
    tech = tech_analyze(price)
    print("      Trend: " + str(tech.get("trend")) + " | RSI: " + str(tech.get("rsi_value")) + " | S:" + str(tech.get("support")) + " R:" + str(tech.get("resistance")))

    print("[5/7] Running debate 3 rounds...")
    debate = run_debate(macro, tech, price, news)
    bull = debate.get("avg_bull_confidence")
    bear = debate.get("avg_bear_confidence")
    print("      Winner: " + str(debate.get("winner")) + " | Bull: " + str(bull) + "% | Bear: " + str(bear) + "% | Margin: " + str(debate.get("margin")) + "pts")

    print("[6/7] Risk management...")
    account_info = None
    if MT5_ENABLED:
        try:
            from agents.mt5_broker import connect, get_account_summary, disconnect
            if connect(MT5_LOGIN, MT5_PASSWORD, MT5_SERVER):
                account_info = get_account_summary()
                disconnect()
        except Exception as e:
            print("      [MT5] account error: " + str(e))

    risk = risk_calc(debate, tech, price, account_info.get("balance") if account_info else None)
    if risk.get("valid"):
        print("      Dir: " + str(risk.get("direction")) + " | R:R: " + str(risk.get("risk_reward")) + " | Risk: $" + str(risk.get("risk_usd")) + " | Lots: " + str(risk.get("contracts")))
    else:
        print("      INVALID: " + str(risk.get("reason")))

    ftmo_check = validate_before_trade(risk, account_info)
    if not ftmo_check["approved"]:
        print("      [FTMO] BLOCKED: " + str(ftmo_check["reason"]))
        risk["valid"] = False
        risk["reason"] = ftmo_check["reason"]
    else:
        fs = ftmo_check["ftmo_status"]
        print("      [FTMO] OK | Daily: $" + str(fs["daily_remaining"]) + " | Total: $" + str(fs["total_remaining"]))

    print("[7/7] Arbitrator deciding...")
    final = decide(debate, risk, macro, news)
    decision = final.get("decision")
    print()
    print(">>> DECISION: " + str(decision) + " (conf: " + str(final.get("confidence")) + "%)")
    print("    " + str(final.get("reason")))

    ticket = None
    if risk.get("valid") and decision in ("LONG", "SHORT"):
        print("    Entry: " + str(risk.get("entry")) + " | SL: " + str(risk.get("stop_loss")) + " | TP: " + str(risk.get("take_profit")) + " | Lots: " + str(risk.get("contracts")))
        if MT5_ENABLED:
            try:
                from agents.mt5_broker import connect, open_trade, disconnect
                if connect(MT5_LOGIN, MT5_PASSWORD, MT5_SERVER):
                    lot_size = max(0.01, round(risk.get("contracts", 0.01), 2))
                    result = open_trade(decision, lot_size, risk["stop_loss"], risk["take_profit"])
                    if result:
                        ticket = result["ticket"]
                        print("    [MT5] ORDER PLACED ticket=" + str(ticket))
                    disconnect()
            except Exception as e:
                print("    [MT5] Error: " + str(e))

    cycle_data = {
        "ts":         datetime.now().isoformat(),
        "price":      price.get("price"),
        "change_pct": price.get("change_pct"),
        "decision":   decision,
        "confidence": final.get("confidence"),
        "reason":     final.get("reason"),
        "risk_plan":  risk,
        "mt5_ticket": ticket,
        "news_items": ni,
        "debate_summary": {
            "winner":    debate.get("winner"),
            "bull_conf": debate.get("avg_bull_confidence"),
            "bear_conf": debate.get("avg_bear_confidence"),
            "margin":    debate.get("margin"),
            "is_tie":    debate.get("is_tie"),
            "rounds":    debate.get("round_scores", []),
        },
        "macro": {
            "bias":       macro.get("macro_bias"),
            "confidence": macro.get("confidence"),
            "drivers":    macro.get("key_drivers"),
            "risks":      macro.get("risks"),
            "analysis":   macro.get("analysis"),
        },
        "technical": {
            "trend":      tech.get("trend"),
            "rsi_value":  tech.get("rsi_value"),
            "rsi_zone":   tech.get("rsi_zone"),
            "support":    tech.get("support"),
            "resistance": tech.get("resistance"),
            "sma20":      tech.get("sma20"),
            "bias":       tech.get("bias"),
        },
        "portfolio": stats,
    }

    if decision in ("LONG", "SHORT") and risk.get("valid"):
        add_position(cycle_data, ticket=ticket)
        print("    [portfolio] Position recorded")

    folder = save_cycle(cycle_data)
    history = load_history()
    gen_html(latest=cycle_data, history=history, stats=stats)
    print("[SAVED] " + str(folder))

    try:
        from utils.telegram_alerts import alert_decision
        alert_decision(cycle_data)
    except Exception as e:
        print("[telegram] " + str(e))

    sync("AURUM: " + str(decision) + " @ " + str(price.get("price")))
    return cycle_data

if __name__ == "__main__":
    run_cycle()
