import sys, json, os

print("=" * 60)
print("AURUM FLOW TEST -- US30 + GPT")
print("=" * 60)

# 1. Signal Engine
print()
print("[1/5] SIGNAL ENGINE (US30 H4+H1)...")
try:
    from agents.signal_engine import get_signal_from_mt5, format_signal_summary
    sig, _ = get_signal_from_mt5(verbose=True)
    if sig:
        print("      SETUP FOUND:", format_signal_summary(sig))
    else:
        print("      No setup -- correct outside session or no pattern")
    print("      STATUS: OK")
except Exception as e:
    print("      ERROR:", e)

# 2. News
print()
print("[2/5] NEWS COLLECTOR...")
try:
    from agents.delta_one import fetch_deltaone
    from agents.news_collector import collect
    delta = fetch_deltaone()
    rss = collect()
    items = rss.get("news_items", []) + (delta or [])
    print("      DeltaOne:", len(delta or []))
    print("      RSS:", len(rss.get("news_items", [])))
    print("      Total:", len(items))
    if items:
        print("      Sample:", items[0].get("title","")[:70])
    print("      STATUS: OK")
except Exception as e:
    print("      ERROR:", e)

# 3. FRED
print()
print("[3/5] FRED MACRO...")
try:
    from utils.fred_data import get_all
    fred = get_all()
    print("      DXY:", fred.get("dxy", "N/A"))
    print("      10Y:", fred.get("t10y", "N/A"))
    print("      Fed:", fred.get("fedfunds", "N/A"))
    print("      STATUS: OK")
except Exception as e:
    print("      ERROR:", e)

# 4. GPT
print()
print("[4/5] GPT-4o API TEST...")
try:
    import requests
    key = os.getenv("OPENAI_API_KEY", "")
    if not key:
        print("      ERROR: No OPENAI_API_KEY")
    else:
        payload = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Say only: OK"}],
            "max_tokens": 10
        }
        r = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
            json=payload,
            timeout=15
        )
        data = r.json()
        if "error" in data:
            print("      API ERROR:", data["error"].get("message","")[:80])
        else:
            reply = data["choices"][0]["message"]["content"]
            model = data.get("model","--")
            print("      Reply:", reply.strip())
            print("      Model:", model)
            print("      STATUS: OK")
except Exception as e:
    print("      ERROR:", e)

# 5. MT5
print()
print("[5/5] MT5 + US30...")
try:
    import MetaTrader5 as mt5
    mt5.initialize()
    info = mt5.account_info()
    if info:
        print("      Balance:", info.balance)
        print("      Server:", info.server)
        tick = mt5.symbol_info_tick("US30.cash")
        if tick:
            print("      US30 bid:", tick.bid, "spread:", round(tick.ask - tick.bid, 1), "pts")
        print("      STATUS: OK")
    else:
        print("      ERROR: no account info")
    mt5.shutdown()
except Exception as e:
    print("      ERROR:", e)

print()
print("=" * 60)
print("FLOW TEST DONE")
print("=" * 60)
