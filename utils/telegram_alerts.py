import requests, os
from dotenv import load_dotenv
load_dotenv()

TOKEN   = os.getenv("TELEGRAM_TOKEN",   "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def send(message):
    if not TOKEN or not CHAT_ID:
        print("[telegram] missing token or chat_id")
        return
    try:
        r = requests.post(
            "https://api.telegram.org/bot" + TOKEN + "/sendMessage",
            json={"chat_id": CHAT_ID, "text": message, "parse_mode": "HTML"},
            timeout=10
        )
        if r.status_code != 200:
            print("[telegram] error:", r.text[:200])
    except Exception as e:
        print("[telegram] send error:", e)

def alert_decision(cycle_data):
    d    = cycle_data.get("decision", "STAY OUT")
    p    = cycle_data.get("price", 0)
    r    = cycle_data.get("risk_plan", {})
    conf = cycle_data.get("confidence", 0)
    db   = cycle_data.get("debate_summary", {})
    te   = cycle_data.get("technical", {})
    ma   = cycle_data.get("macro", {})
    ni   = cycle_data.get("news_items", [])
    news_line = ni[0]["title"][:70] if ni else "No news"
    if d == "STAY OUT":
        lines = [
            "AURUM -- STAY OUT",
            "XAU/USD: " + str(p),
            "Reason: " + str(cycle_data.get("reason", "")),
            "Bull: " + str(db.get("bull_conf")) + "% | Bear: " + str(db.get("bear_conf")) + "%",
            "RSI: " + str(te.get("rsi_value", "--")) + " | Trend: " + str(te.get("trend", "--")),
            "Macro: " + str(ma.get("bias", "--")) + " (" + str(ma.get("confidence","--")) + "%)",
            "News: " + news_line,
        ]
    else:
        arrow = "LONG" if d == "LONG" else "SHORT"
        lines = [
            "AURUM SIGNAL -- " + arrow,
            "XAU/USD: " + str(p),
            "Entry:  " + str(r.get("entry")),
            "Stop:   " + str(r.get("stop_loss")),
            "Target: " + str(r.get("take_profit")),
            "RR: 1:" + str(r.get("risk_reward")) + " | Risk: $" + str(r.get("risk_usd")),
            "Lots: " + str(r.get("contracts")) + " | Conf: " + str(conf) + "%",
            "Bull: " + str(db.get("bull_conf")) + "% vs Bear: " + str(db.get("bear_conf")) + "%",
            "News: " + news_line,
        ]
    send("\n".join(lines))

def alert_closed(position, exit_price):
    pnl = position.get("pnl", 0)
    res = "WIN" if pnl > 0 else "LOSS"
    lines = [
        "AURUM -- Position " + res,
        str(position.get("direction")) + " " + str(position.get("entry")) + " -> " + str(exit_price),
        "PnL: $" + str(round(pnl, 2)),
    ]
    send("\n".join(lines))

def alert_ftmo(reason):
    send("AURUM FTMO WARNING\n" + str(reason))

def alert_news_flash(headline, impact):
    send("AURUM NEWS FLASH\n" + str(headline) + "\nGold impact: " + str(impact))
