import os, json

def w(path, content):
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('OK:', path)

# FIX price_history.py - RSI con None check
w('utils/price_history.py', '''import requests, os, json
from datetime import datetime, timedelta
from config import STATE_DIR, GOLDAPI_KEY

HISTORY_FILE = os.path.join(STATE_DIR, "price_history.json")

def fetch_recent_prices(days=30):
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, encoding="utf-8") as f:
            cached = json.load(f)
        prices = cached.get("prices", [])
        last   = cached.get("last_update", "")
        if prices and len(prices) >= 10 and last[:10] == datetime.now().strftime("%Y-%m-%d"):
            return prices

    prices = []
    if GOLDAPI_KEY:
        for d in range(days, 0, -1):
            date = (datetime.now() - timedelta(days=d)).strftime("%Y%m%d")
            try:
                import requests as req
                r = req.get(
                    f"https://www.goldapi.io/api/XAU/USD/{date}",
                    headers={"x-access-token": GOLDAPI_KEY},
                    timeout=8
                )
                if r.status_code == 200:
                    data = r.json()
                    p = data.get("price")
                    if p and isinstance(p, (int, float)):
                        prices.append({
                            "date":  date,
                            "close": float(p),
                            "open":  float(data.get("open_price") or p),
                            "high":  float(data.get("high_price") or p),
                            "low":   float(data.get("low_price")  or p),
                        })
            except Exception as e:
                pass

    if prices:
        os.makedirs(STATE_DIR, exist_ok=True)
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump({"prices": prices, "last_update": datetime.now().isoformat()}, f)

    return prices

def calculate_rsi(prices, period=14):
    closes = [p["close"] for p in prices if p.get("close") and isinstance(p["close"], (int, float))]
    if len(closes) < period + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs  = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 1)

def calculate_sma(prices, period):
    closes = [p["close"] for p in prices if p.get("close") and isinstance(p["close"], (int, float))]
    if len(closes) < period:
        return None
    return round(sum(closes[-period:]) / period, 2)

def find_support_resistance(prices):
    closes = [p["close"] for p in prices if p.get("close") and isinstance(p["close"], (int, float))]
    highs  = [p.get("high") or p["close"] for p in prices if p.get("close")]
    lows   = [p.get("low")  or p["close"] for p in prices if p.get("close")]
    highs  = [h for h in highs if isinstance(h, (int, float))]
    lows   = [l for l in lows  if isinstance(l, (int, float))]
    if not closes:
        return None, None
    current    = closes[-1]
    candidates_s = sorted([l for l in lows   if l < current], reverse=True)
    candidates_r = sorted([h for h in highs  if h > current])
    support    = round(candidates_s[0], 2) if candidates_s else None
    resistance = round(candidates_r[0], 2) if candidates_r else None
    return support, resistance

def get_full_technical_context(current_price):
    prices = fetch_recent_prices(days=25)
    if current_price and isinstance(current_price, (int, float)):
        prices.append({"close": current_price, "high": current_price, "low": current_price, "open": current_price})
    if not prices:
        return {
            "rsi": None, "sma20": None, "sma50": None,
            "support": round(current_price * 0.985, 2) if current_price else None,
            "resistance": round(current_price * 1.015, 2) if current_price else None,
            "trend_20d": "UNKNOWN", "price_vs_sma": "UNKNOWN", "history_days": 0
        }
    rsi   = calculate_rsi(prices)
    sma20 = calculate_sma(prices, 20)
    sma50 = calculate_sma(prices, 50)
    support, resistance = find_support_resistance(prices)
    closes = [p["close"] for p in prices if p.get("close") and isinstance(p["close"], (int, float))]
    trend_20d = "UP" if len(closes) >= 20 and closes[-1] > closes[-20] else ("DOWN" if len(closes) >= 20 else "UNKNOWN")
    price_vs_sma = "ABOVE" if (sma20 and current_price and current_price > sma20) else "BELOW"
    return {
        "rsi": rsi, "sma20": sma20, "sma50": sma50,
        "support": support, "resistance": resistance,
        "trend_20d": trend_20d, "price_vs_sma": price_vs_sma,
        "history_days": len(prices)
    }
''')

# FIX price_feed - fallback si goldapi falla
w('agents/price_feed.py', '''import requests, os
from dotenv import load_dotenv
load_dotenv()
GOLDAPI_KEY = os.getenv("GOLDAPI_KEY", "")

FALLBACK_PRICE = None

def get_xauusd():
    global FALLBACK_PRICE
    if GOLDAPI_KEY:
        try:
            r = requests.get("https://www.goldapi.io/api/XAU/USD",
                headers={"x-access-token": GOLDAPI_KEY, "Content-Type": "application/json"},
                timeout=10)
            if r.status_code == 200:
                d = r.json()
                price = d.get("price")
                if price:
                    FALLBACK_PRICE = price
                    return {
                        "price":      float(price),
                        "open":       d.get("open_price"),
                        "high":       d.get("high_price"),
                        "low":        d.get("low_price"),
                        "change":     d.get("ch"),
                        "change_pct": d.get("chp"),
                        "prev_close": d.get("prev_close_price"),
                        "ask":        d.get("ask"),
                        "bid":        d.get("bid"),
                        "timestamp":  d.get("timestamp"),
                        "source":     "goldapi.io"
                    }
            print("[price_feed] goldapi status:", r.status_code)
        except Exception as e:
            print("[price_feed] goldapi error:", e)

    # Fallback: MT5 real-time price
    try:
        import MetaTrader5 as mt5
        if mt5.initialize():
            tick = mt5.symbol_info_tick("XAUUSD")
            if tick and tick.bid > 0:
                price = (tick.bid + tick.ask) / 2
                FALLBACK_PRICE = price
                mt5.shutdown()
                return {"price": round(price,2), "open": None, "high": None, "low": None,
                        "change": None, "change_pct": None, "source": "MT5"}
    except Exception as e:
        print("[price_feed] MT5 tick error:", e)

    if FALLBACK_PRICE:
        print("[price_feed] Using last known price:", FALLBACK_PRICE)
        return {"price": FALLBACK_PRICE, "open": None, "high": None, "low": None,
                "change": None, "change_pct": None, "source": "cached"}

    return {"price": None, "open": None, "high": None, "low": None,
            "change": None, "change_pct": None, "source": "unavailable"}

def get_technical_data():
    return get_xauusd()
''')

# FIX github_sync - forzar push y mostrar errores
w('utils/github_sync.py', '''import subprocess

def sync(message="AURUM cycle update"):
    try:
        r1 = subprocess.run(["git", "add", "-A"], capture_output=True, text=True)
        r2 = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True)
        if "nothing to commit" in r2.stdout + r2.stderr:
            print("[SYNC] Nothing to commit")
            return
        r3 = subprocess.run(["git", "push", "origin", "main"], capture_output=True, text=True)
        if r3.returncode == 0:
            print("[SYNC] GitHub push OK")
        else:
            print("[SYNC] Push failed:", r3.stderr[:200])
            print("[SYNC] Trying force push...")
            r4 = subprocess.run(["git", "push", "origin", "main", "--force"], capture_output=True, text=True)
            if r4.returncode == 0:
                print("[SYNC] Force push OK")
            else:
                print("[SYNC] Force push also failed:", r4.stderr[:100])
    except Exception as e:
        print("[SYNC] Error:", e)
''')

# FIX GPT news - manejo de errores OpenAI mejorado
w('agents/news_gpt.py', '''import os, json, requests, re
from dotenv import load_dotenv
load_dotenv()
KEY = os.getenv("OPENAI_API_KEY", "")

def analyze_news_gpt(news_items):
    if not KEY or not news_items:
        return None
    try:
        hl = chr(10).join(["- ["+i["source"]+"] "+i["title"] for i in news_items[:20]])
        q1 = chr(34)
        prompt = (
            "You are a gold XAU/USD trading analyst. Analyze these news headlines."+chr(10)+
            "Respond ONLY in valid JSON with these exact fields:"+chr(10)+
            "{"+q1+"sentiment"+q1+":"+q1+"BULLISH_GOLD"+q1+","+q1+"confidence"+q1+":75,"+
            q1+"key_events"+q1+":["+q1+"event1"+q1+"],"+
            q1+"scheduled_events"+q1+":[],"+
            q1+"bull_factors"+q1+":["+q1+"factor1"+q1+"],"+
            q1+"bear_factors"+q1+":["+q1+"factor1"+q1+"],"+
            q1+"summary"+q1+":"+q1+"2 sentence analysis"+q1+"}"+chr(10)+chr(10)+
            "HEADLINES:"+chr(10)+hl
        )
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer "+KEY, "Content-Type": "application/json"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.2,
                "response_format": {"type": "json_object"}
            },
            timeout=25
        )
        data = r.json()
        if "error" in data:
            print("[gpt] API error:", data["error"].get("message","")[:100])
            return None
        if "choices" not in data:
            print("[gpt] unexpected response:", str(data)[:200])
            return None
        content = data["choices"][0]["message"]["content"]
        result = json.loads(content)
        return result
    except Exception as e:
        print("[gpt] error:", e)
        return None
''')

# DELTA ONE Twitter/X scraper (sin API key)
w('agents/delta_one.py', '''import requests, re, time
from datetime import datetime

# DeltaOne (@DeItaone) - Bloomberg terminal en Twitter
# Usamos nitter (espejo publico de Twitter) para scraping sin API

NITTER_INSTANCES = [
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
]

GOLD_KEYWORDS = [
    "gold", "xau", "fed", "rate", "inflation", "dollar", "treasury",
    "tariff", "iran", "war", "geopolit", "safe haven", "powell",
    "cpi", "nfp", "payroll", "gdp", "recession", "china", "risk"
]

def fetch_deltaone(max_items=15):
    items = []
    for instance in NITTER_INSTANCES:
        try:
            url = instance + "/DeItaone"
            r = requests.get(url,
                headers={"User-Agent": "Mozilla/5.0 AURUM/1.0"},
                timeout=10)
            if r.status_code != 200:
                continue
            # Extraer tweets del HTML
            tweets = re.findall(r\'<div class="tweet-content[^"]*"[^>]*>(.*?)</div>\', r.text, re.DOTALL)
            for tweet in tweets[:20]:
                text = re.sub(r\'<[^>]+>\', \'\', tweet).strip()
                text = re.sub(r\'\\s+\', \' \', text).strip()
                if len(text) > 20:
                    tl = text.lower()
                    relevant = any(k in tl for k in GOLD_KEYWORDS)
                    items.append({
                        "source": "DeltaOne",
                        "title":  text[:150],
                        "body":   "",
                        "relevant": relevant,
                        "ts": datetime.now().isoformat()
                    })
            if items:
                print(f"[deltaone] Got {len(items)} tweets from {instance}")
                break
        except Exception as e:
            print(f"[deltaone] {instance}: {type(e).__name__}")
            continue

    relevant = [i for i in items if i["relevant"]]
    all_items = relevant + [i for i in items if not i["relevant"]]
    return all_items[:max_items]

def get_breaking_from_deltaone():
    items = fetch_deltaone()
    if not items:
        return []
    breaking_kw = ["breaking", "flash", "alert", "urgent", "just in", "reuters", "bloomberg"]
    breaking = [i for i in items if any(k in i["title"].lower() for k in breaking_kw)]
    return breaking or items[:5]
''')

# TRAINING/FEEDBACK LOOP
w('training/feedback.py', '''import json, os
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
''')

# TRAINING __init__
w('training/__init__.py', '')

print("All files written OK")
