src = open("daemon.py", encoding="utf-8").read()

old = "    return state\n\ndef run():"
new = """    # Auto git push al final de cada scan
    try:
        from utils.github_sync import sync
        hour_utc = datetime.now(timezone.utc).hour
        in_session = (7 <= hour_utc < 10) or (12 <= hour_utc < 16)
        if in_session:
            sync("AURUM auto: " + state.get("last_trade_date","") + " daily=" + str(round(state.get("daily_pnl",0),2)))
    except Exception as e:
        print("[git] error:", e)
    return state

def run():"""

if old in src:
    open("daemon.py", "w", encoding="utf-8").write(src.replace(old, new))
    print("Auto git push added OK")
else:
    print("Pattern not found — checking...")
    lines = src.split("\\n")
    for i, l in enumerate(lines):
        if "return state" in l and i > 100:
            print(str(i+1) + ": " + l)
            break
