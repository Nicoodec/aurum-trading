import json, os
from datetime import datetime
from portfolio import load_positions, get_stats
from config import STATE_DIR

TRAINING_FILE = os.path.join("training", "feedback_log.json")
os.makedirs("training", exist_ok=True)

def load_feedback():
    if os.path.exists(TRAINING_FILE):
        with open(TRAINING_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"trades": [], "patterns": {}, "stats": {}}

def save_feedback(data):
    with open(TRAINING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)

def record_outcome(cycle_data, outcome):
    feedback = load_feedback()
    record = {
        "ts":          datetime.now().isoformat(),
        "decision":    cycle_data.get("decision"),
        "outcome":     outcome,
        "price":       cycle_data.get("price"),
        "macro_bias":  cycle_data.get("macro", {}).get("bias"),
        "tech_trend":  cycle_data.get("technical", {}).get("trend"),
        "rsi":         cycle_data.get("technical", {}).get("rsi_value"),
        "bull_conf":   cycle_data.get("debate_summary", {}).get("bull_conf"),
        "bear_conf":   cycle_data.get("debate_summary", {}).get("bear_conf"),
        "margin":      cycle_data.get("debate_summary", {}).get("margin"),
        "sentiment":   (cycle_data.get("news_items") or [{}])[0].get("source","") if cycle_data.get("news_items") else "",
        "fred_dxy":    cycle_data.get("fred", {}).get("dxy"),
        "fred_t10y":   cycle_data.get("fred", {}).get("t10y"),
        "risk_reward": cycle_data.get("risk_plan", {}).get("risk_reward"),
        "pnl":         None
    }
    feedback["trades"].append(record)
    _update_patterns(feedback)
    save_feedback(feedback)
    return record

def _update_patterns(feedback):
    trades = feedback["trades"]
    wins   = [t for t in trades if t.get("outcome") == "WIN"]
    losses = [t for t in trades if t.get("outcome") == "LOSS"]
    if not trades:
        return
    patterns = {}
    # RSI patterns
    win_rsi    = [t["rsi"] for t in wins   if t.get("rsi")]
    loss_rsi   = [t["rsi"] for t in losses if t.get("rsi")]
    if win_rsi:   patterns["avg_rsi_wins"]   = round(sum(win_rsi)/len(win_rsi), 1)
    if loss_rsi:  patterns["avg_rsi_losses"] = round(sum(loss_rsi)/len(loss_rsi), 1)
    # Debate margin patterns
    win_margin  = [t["margin"] for t in wins   if t.get("margin")]
    loss_margin = [t["margin"] for t in losses if t.get("margin")]
    if win_margin:  patterns["avg_margin_wins"]   = round(sum(win_margin)/len(win_margin), 1)
    if loss_margin: patterns["avg_margin_losses"] = round(sum(loss_margin)/len(loss_margin), 1)
    # Best conditions
    patterns["win_rate"]    = round(len(wins)/len(trades)*100, 1) if trades else 0
    patterns["total_trades"] = len(trades)
    feedback["patterns"] = patterns

def get_trading_insights():
    feedback = load_feedback()
    patterns = feedback.get("patterns", {})
    insights = []
    wr = patterns.get("win_rate", 50)
    if wr > 60:
        insights.append(f"WIN RATE {wr}% -- system performing well")
    elif wr < 40:
        insights.append(f"WIN RATE {wr}% -- review signal quality")
    rsi_w = patterns.get("avg_rsi_wins")
    rsi_l = patterns.get("avg_rsi_losses")
    if rsi_w and rsi_l:
        insights.append(f"Best RSI for wins: {rsi_w} | Avg RSI on losses: {rsi_l}")
    mg_w = patterns.get("avg_margin_wins")
    mg_l = patterns.get("avg_margin_losses")
    if mg_w and mg_l:
        insights.append(f"Winning debate margin avg: {mg_w}pts | Losing: {mg_l}pts")
    return insights, patterns

def sync_closed_positions():
    positions = load_positions()
    feedback  = load_feedback()
    recorded  = {t["ts"][:16] for t in feedback["trades"]}
    for pos in positions:
        if pos.get("status") in ("WIN", "LOSS") and pos.get("closed_at"):
            key = pos["closed_at"][:16]
            if key not in recorded:
                record = {
                    "ts":       pos["closed_at"],
                    "decision": pos.get("direction"),
                    "outcome":  pos.get("status"),
                    "pnl":      pos.get("pnl"),
                    "price":    pos.get("entry"),
                }
                feedback["trades"].append(record)
    _update_patterns(feedback)
    save_feedback(feedback)
    insights, patterns = get_trading_insights()
    return insights, patterns
