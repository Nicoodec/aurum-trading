import os, sys

files = {}

files['utils/__init__.py'] = ''

files['utils/telegram_alerts.py'] = '''import requests, os
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
    send("\\n".join(lines))

def alert_closed(position, exit_price):
    pnl = position.get("pnl", 0)
    res = "WIN" if pnl > 0 else "LOSS"
    lines = [
        "AURUM -- Position " + res,
        str(position.get("direction")) + " " + str(position.get("entry")) + " -> " + str(exit_price),
        "PnL: $" + str(round(pnl, 2)),
    ]
    send("\\n".join(lines))

def alert_ftmo(reason):
    send("AURUM FTMO WARNING\\n" + str(reason))

def alert_news_flash(headline, impact):
    send("AURUM NEWS FLASH\\n" + str(headline) + "\\nGold impact: " + str(impact))
'''

files['daemon.py'] = '''import time, traceback, os, sys
from datetime import datetime, timezone

NEWS_CHECK_INTERVAL     = 300    # 5 min
FULL_CYCLE_INTERVAL     = 14400  # 4 horas
MONITOR_INTERVAL        = 60     # 1 min

last_full_cycle = 0
last_news_check = 0
seen_headlines  = set()

def is_market_open():
    now = datetime.now(timezone.utc)
    wd, h = now.weekday(), now.hour
    if wd == 5: return False
    if wd == 6 and h < 22: return False
    if wd == 4 and h >= 22: return False
    return True

def check_breaking_news():
    from agents.news_collector import collect
    from utils.telegram_alerts import alert_news_flash
    HIGH_IMPACT = [
        "trump", "fed ", "rate decision", "cpi", "nfp", "war",
        "attack", "strike", "iran", "israel", "ukraine", "russia",
        "emergency", "crisis", "crash", "collapse", "default",
        "tariff", "sanctions", "nuclear", "invasion", "explosion"
    ]
    try:
        news = collect()
        items     = news.get("news_items", [])
        sentiment = news.get("sentiment", "NEUTRAL")
        breaking  = []
        for item in items:
            title = item.get("title", "")
            tl    = title.lower()
            if title not in seen_headlines and any(kw in tl for kw in HIGH_IMPACT):
                breaking.append(title)
                seen_headlines.add(title)
        if len(seen_headlines) > 500:
            seen_headlines.clear()
        if breaking:
            print("[daemon] BREAKING:", breaking[0][:80])
            if sentiment in ("BULLISH_GOLD", "BEARISH_GOLD"):
                alert_news_flash(breaking[0][:120], sentiment)
            return True, news
        return False, news
    except Exception as e:
        print("[daemon] news error:", e)
        return False, {}

def monitor_positions():
    try:
        from agents.mt5_broker import connect, get_open_positions, get_account_summary, disconnect
        from agents.ftmo_validator import get_ftmo_status
        from utils.telegram_alerts import alert_ftmo
        from portfolio import load_positions, close_position
        if connect(1513020113, "FH2dXFt7?", "FTMO-Demo"):
            account   = get_account_summary()
            ftmo      = get_ftmo_status(account)
            mt5_pos   = get_open_positions()
            mt5_ticks = {p["ticket"] for p in mt5_pos}
            ts = datetime.now().strftime("%H:%M:%S")
            eq = account.get("equity", 0)
            pr = account.get("profit", 0)
            dr = ftmo.get("daily_remaining", 0)
            print("[" + ts + "] Equity: " + str(round(eq,2)) + " | Profit: " + str(round(pr,2)) + " | Open: " + str(len(mt5_pos)) + " | Daily left: " + str(round(dr,2)))
            if not ftmo["can_trade"]:
                reason = " | ".join(ftmo.get("reasons", ["FTMO limit hit"]))
                print("[daemon] FTMO LIMIT:", reason)
                alert_ftmo(reason)
            local = load_positions()
            for pos in local:
                if pos["status"] == "OPEN" and pos.get("ticket") and pos["ticket"] not in mt5_ticks:
                    print("[daemon] Position " + str(pos["ticket"]) + " closed by MT5 (SL/TP)")
                    try:
                        import MetaTrader5 as mt5
                        from datetime import timedelta
                        deals = mt5.history_deals_get(
                            datetime.now() - timedelta(hours=48), datetime.now()
                        )
                        if deals:
                            deal = next((d for d in deals if d.position_id == pos["ticket"]), None)
                            if deal:
                                close_position(pos["id"], deal.price, deal.profit)
                                from utils.telegram_alerts import alert_closed
                                alert_closed(pos, deal.price)
                    except Exception as e2:
                        print("[daemon] deal history error:", e2)
                        close_position(pos["id"], pos.get("take_profit", 0))
            disconnect()
    except Exception as e:
        print("[daemon] monitor error:", e)

def run_full_cycle():
    try:
        from main import run_cycle
        print("[daemon] Starting full cycle...")
        run_cycle()
    except Exception as e:
        print("[daemon] cycle error:", e)
        traceback.print_exc()

print("[AURUM DAEMON] Starting")
print("[AURUM DAEMON] Monitor: 1min | News: 5min | Cycle: 4h")

from utils.telegram_alerts import send
send("AURUM DAEMON started\\nMonitor: 1min | News: 5min | Cycle: 4h\\nMarket open: " + str(is_market_open()))

# Primer ciclo inmediato
run_full_cycle()
last_full_cycle = time.time()
last_news_check = time.time()

while True:
    now = time.time()
    try:
        monitor_positions()

        if now - last_news_check >= NEWS_CHECK_INTERVAL:
            last_news_check = now
            if is_market_open():
                breaking, _ = check_breaking_news()
                if breaking:
                    print("[daemon] Breaking news -- immediate cycle")
                    run_full_cycle()
                    last_full_cycle = now

        if now - last_full_cycle >= FULL_CYCLE_INTERVAL:
            last_full_cycle = now
            if is_market_open():
                print("[daemon] Scheduled cycle")
                run_full_cycle()
            else:
                print("[daemon] Market closed -- skip")

        time.sleep(MONITOR_INTERVAL)

    except KeyboardInterrupt:
        print("[daemon] Stopped")
        send("AURUM DAEMON stopped by user")
        break
    except Exception as e:
        print("[daemon] loop error:", e)
        time.sleep(30)
'''

files['gen_dashboard.py'] = '''import os, json

def generate(latest=None, history=None, stats=None):
    if latest  is None: latest  = {}
    if history is None: history = []
    if stats   is None:
        stats = {"capital":25000,"equity":25000,"total_pnl":0,
                 "total_trades":0,"open_positions":0,"win_rate":0,
                 "wins":0,"losses":0,"avg_win":0,"avg_loss":0,"profit_factor":0}

    data_json = json.dumps(
        {"latest": latest, "history": history[-50:], "stats": stats},
        indent=2, default=str
    )

    p1 = """<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AURUM - Gold Trading System</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#000;color:#c9a84c;font-family:\'Courier New\',monospace;min-height:100vh}
canvas{position:fixed;top:0;left:0;z-index:0;pointer-events:none;opacity:.3}
.wrap{position:relative;z-index:1;max-width:1400px;margin:0 auto;padding:24px 16px}
pre.ascii{color:#f0c040;font-size:clamp(5px,1vw,12px);line-height:1.15;text-align:center;margin-bottom:6px}
.tagline{text-align:center;color:#333;font-size:10px;letter-spacing:5px;margin-bottom:24px}
.sr{display:flex;align-items:center;justify-content:center;gap:14px;margin-bottom:28px;flex-wrap:wrap}
.dot{width:8px;height:8px;border-radius:50%;background:#22c55e;animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.badge{padding:4px 14px;border-radius:3px;font-size:13px;letter-spacing:2px;font-weight:bold}
.LONG{background:#052e16;color:#4ade80;border:1px solid #166534}
.SHORT{background:#2d0a0a;color:#f87171;border:1px solid #7f1d1d}
.STAY_OUT{background:#111;color:#555;border:1px solid #222}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px;margin-bottom:16px}
.card{background:#060606;border:1px solid #c9a84c15;border-radius:6px;padding:18px}
.ct{color:#555;font-size:10px;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #111}
.m{display:flex;justify-content:space-between;align-items:center;margin:6px 0;font-size:12px}
.k{color:#333}.v{color:#e8c46a}.g{color:#4ade80}.r{color:#f87171}
.bw{background:#0a0a0a;border-radius:2px;height:5px;flex:1;margin:0 8px}
.bf{height:5px;border-radius:2px;transition:width .8s}.bb{background:#4ade80}.br{background:#f87171}
table{width:100%;border-collapse:collapse;font-size:11px}
th{color:#333;padding:8px 6px;text-align:left;border-bottom:1px solid #0f0f0f;font-size:9px;text-transform:uppercase}
td{padding:6px;border-bottom:1px solid #080808;color:#555}
td.LONG{color:#4ade80}td.SHORT{color:#f87171}td.STAY_OUT{color:#222}
.ni{color:#444;font-size:10px;padding:4px 0;border-bottom:1px solid #0a0a0a;line-height:1.4}
.ns{color:#c9a84c33}
#upd{color:#222;font-size:9px;text-align:right;margin-bottom:6px}
.footer{text-align:center;color:#111;font-size:9px;margin-top:28px;letter-spacing:2px}
</style></head><body>
<canvas id="c"></canvas>
<div class="wrap">
<pre class="ascii">
 █████╗ ██╗   ██╗██████╗ ██╗   ██╗███╗   ███╗
██╔══██╗██║   ██║██╔══██╗██║   ██║████╗ ████║
███████║██║   ██║██████╔╝██║   ██║██╔████╔██║
██╔══██║██║   ██║██╔══██╗██║   ██║██║╚██╔╝██║
██║  ██║╚██████╔╝██║  ██║╚██████╔╝██║ ╚═╝ ██║
╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝
</pre>
<p class="tagline">MULTI-AGENT GOLD SWING TRADING &middot; AI POWERED &middot; FTMO DEMO $25K</p>
<div id="upd">--</div>
<div class="sr">
  <div class="dot"></div>
  <span style="font-size:11px;color:#333;letter-spacing:2px">LIVE</span>
  <span id="xp" style="font-size:20px;color:#f0c040;font-weight:bold">XAU/USD --</span>
  <span id="xc" style="font-size:12px"></span>
  <span id="xb" class="badge STAY_OUT">STAY OUT</span>
</div>
<div class="grid">
<div class="card">
  <div class="ct">Last Signal</div>
  <div class="m"><span class="k">Confidence</span><span class="v" id="sc">--</span></div>
  <div class="m"><span class="k">Entry</span><span class="v" id="se">--</span></div>
  <div class="m"><span class="k">Stop loss</span><span class="r" id="ss">--</span></div>
  <div class="m"><span class="k">Take profit</span><span class="g" id="st">--</span></div>
  <div class="m"><span class="k">R:R</span><span class="v" id="sr">--</span></div>
  <div class="m"><span class="k">Lots</span><span class="v" id="sl">--</span></div>
  <div class="m"><span class="k">Risk USD</span><span class="v" id="sk">--</span></div>
  <div class="m"><span class="k">SL pips</span><span class="v" id="sp">--</span></div>
  <div style="color:#333;font-size:10px;margin-top:8px;line-height:1.6" id="sr2">--</div>
</div>
<div class="card">
  <div class="ct">Debate</div>
  <div class="m"><span class="k">Bull</span><div class="bw"><div class="bf bb" id="bb" style="width:50%"></div></div><span class="g" id="bp">50%</span></div>
  <div class="m"><span class="k">Bear</span><div class="bw"><div class="bf br" id="rb" style="width:50%"></div></div><span class="r" id="rp">50%</span></div>
  <div class="m"><span class="k">Winner</span><span class="v" id="dw">--</span></div>
  <div class="m"><span class="k">Margin</span><span class="v" id="dm">--</span></div>
  <div class="ct" style="margin-top:14px">Technical</div>
  <div class="m"><span class="k">Trend 20d</span><span class="v" id="tt">--</span></div>
  <div class="m"><span class="k">RSI(14)</span><span class="v" id="tr">--</span></div>
  <div class="m"><span class="k">SMA20</span><span class="v" id="ts">--</span></div>
  <div class="m"><span class="k">Support</span><span class="g" id="tu">--</span></div>
  <div class="m"><span class="k">Resistance</span><span class="r" id="te">--</span></div>
  <div class="m"><span class="k">Macro bias</span><span class="v" id="mb">--</span></div>
</div>
<div class="card">
  <div class="ct">Portfolio FTMO Demo</div>
  <div class="m"><span class="k">Capital</span><span class="v" id="pc">$25,000</span></div>
  <div class="m"><span class="k">Equity</span><span class="v" id="pe">--</span></div>
  <div class="m"><span class="k">Total PnL</span><span class="v" id="pp">--</span></div>
  <div class="m"><span class="k">Open</span><span class="v" id="po">--</span></div>
  <div class="m"><span class="k">Trades</span><span class="v" id="pt">--</span></div>
  <div class="m"><span class="k">Win rate</span><span class="v" id="pw">--</span></div>
  <div class="m"><span class="k">Avg win</span><span class="g" id="pa">--</span></div>
  <div class="m"><span class="k">Avg loss</span><span class="r" id="pl">--</span></div>
  <div class="m"><span class="k">Profit factor</span><span class="v" id="pf">--</span></div>
</div>
</div>
<div class="card" style="margin-bottom:16px">
  <div class="ct">News This Cycle</div>
  <div id="nb" style="max-height:150px;overflow-y:auto"><span style="color:#111">No news yet</span></div>
</div>
<div class="card">
  <div class="ct">Signal History</div>
  <table><thead><tr>
    <th>Time</th><th>Price</th><th>Signal</th><th>Conf</th><th>RR</th>
    <th>RSI</th><th>Trend</th><th>Macro</th><th>Bull</th><th>Bear</th><th>Winner</th><th>Reason</th>
  </tr></thead><tbody id="ht">
    <tr><td colspan="12" style="text-align:center;padding:20px;color:#111">No signals yet</td></tr>
  </tbody></table>
</div>
<div class="footer">AURUM &middot; nicoodec.github.io/aurum-trading &middot; FTMO DEMO $25K</div>
</div>
<script>
const cv=document.getElementById("c"),cx=cv.getContext("2d");
function rz(){cv.width=innerWidth;cv.height=innerHeight}rz();
const ch="$XAU01",nc=()=>Math.floor(cv.width/16);
let dr=[];
function id(){dr=Array.from({length:nc()},()=>Math.random()*cv.height/16)}
id();window.onresize=()=>{rz();id()};
setInterval(()=>{
  cx.fillStyle="rgba(0,0,0,0.05)";cx.fillRect(0,0,cv.width,cv.height);
  cx.fillStyle="#b8860b33";cx.font="13px monospace";
  dr.forEach((y,i)=>{
    cx.fillText(ch[Math.floor(Math.random()*ch.length)],i*16,y*16);
    if(y*16>cv.height&&Math.random()>.97)dr[i]=0;
    dr[i]+=.3;
  });
},65);
function fd(n){return n!=null?"$"+Number(n).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2}):"--"}
function sv(id,v){const e=document.getElementById(id);if(e)e.textContent=v}
const D="""

    p2 = """;
function render(d){
  const l=d.latest||{},st=d.stats||{},h=d.history||[];
  const dec=l.decision||"STAY OUT",dcs=dec.replace(" ","_");
  sv("xp","XAU/USD "+(l.price?Number(l.price).toLocaleString("en-US",{minimumFractionDigits:2}):"--"));
  const chg=l.change_pct,ce=document.getElementById("xc");
  if(ce){ce.textContent=chg?(chg>0?"+":"")+chg+"%":"";ce.style.color=chg>0?"#4ade80":chg<0?"#f87171":"#555";}
  const be=document.getElementById("xb");
  if(be){be.textContent=dec;be.className="badge "+dcs;}
  const rp=l.risk_plan||{};
  sv("sc",(l.confidence||0)+"%");
  sv("se",fd(rp.entry));sv("ss",fd(rp.stop_loss));sv("st",fd(rp.take_profit));
  sv("sr",rp.risk_reward?"1:"+rp.risk_reward:"--");
  sv("sl",rp.contracts||"--");sv("sk",fd(rp.risk_usd));
  sv("sp",rp.sl_distance?rp.sl_distance.toFixed(2)+" usd":"--");
  sv("sr2",l.reason||"--");
  const db=l.debate_summary||{},bl=db.bull_conf||50,br=db.bear_conf||50;
  const bel=document.getElementById("bb"),rel=document.getElementById("rb");
  if(bel)bel.style.width=bl+"%";if(rel)rel.style.width=br+"%";
  sv("bp",bl+"%");sv("rp",br+"%");
  sv("dw",db.winner||"--");sv("dm",db.margin?(db.margin+"pts"):"--");
  const te=l.technical||{},ma=l.macro||{};
  sv("tt",te.trend||"--");
  sv("tr",(te.rsi_value||"--")+" ("+(te.rsi_zone||"--")+")");
  sv("ts",fd(te.sma20));sv("tu",fd(te.support));sv("te",fd(te.resistance));
  sv("mb",(ma.bias||ma.macro_bias||"--")+" "+(ma.confidence?"("+ma.confidence+"%)":""));
  sv("pc",fd(st.capital||25000));sv("pe",fd(st.equity));
  const pn=st.total_pnl||0,pne=document.getElementById("pp");
  if(pne){pne.textContent=(pn>=0?"+":"")+fd(Math.abs(pn));pne.className=pn>=0?"v g":"v r";}
  sv("po",(st.open_positions||0)+" / 3");sv("pt",st.total_trades||0);
  sv("pw",(st.win_rate||0)+"%");sv("pa",fd(st.avg_win));sv("pl",fd(Math.abs(st.avg_loss||0)));
  sv("pf",st.profit_factor||"--");
  const nb=document.getElementById("nb");
  if(nb){
    const ni=l.news_items||[];
    nb.innerHTML=ni.length?ni.map(n=>"<div class=\'ni\'><span class=\'ns\'>["+n.source+"]</span> "+n.title+"</div>").join(""):"<span style=\'color:#111\'>No news this cycle</span>";
  }
  const tb=document.getElementById("ht"),rows=h.slice(-40).reverse();
  if(!rows.length){tb.innerHTML="<tr><td colspan=\'12\' style=\'text-align:center;padding:20px;color:#111\'>No signals yet</td></tr>";return;}
  tb.innerHTML=rows.map(row=>{
    const dc2=(row.decision||"STAY OUT").replace(" ","_");
    const ts2=row.ts?row.ts.substring(0,16).replace("T"," "):"--";
    const te2=row.technical||{},ma2=row.macro||{},db2=row.debate_summary||{},rp2=row.risk_plan||{};
    return "<tr><td>"+ts2+"</td>"
      +"<td>"+(row.price?Number(row.price).toFixed(2):"--")+"</td>"
      +"<td class=\'"+dc2+"\'>"+dc2.replace("_"," ")+"</td>"
      +"<td>"+(row.confidence||0)+"%</td>"
      +"<td>"+(rp2.risk_reward?"1:"+rp2.risk_reward:"--")+"</td>"
      +"<td>"+(te2.rsi_value||"--")+"</td>"
      +"<td>"+(te2.trend||"--")+"</td>"
      +"<td>"+(ma2.bias||ma2.macro_bias||"--")+"</td>"
      +"<td style=\'color:#4ade80\'>"+(db2.bull_conf||"--")+"%</td>"
      +"<td style=\'color:#f87171\'>"+(db2.bear_conf||"--")+"%</td>"
      +"<td>"+(db2.winner||"--")+"</td>"
      +"<td style=\'color:#222;font-size:10px\'>"+(row.reason||"--").substring(0,35)+"</td>"
      +"</tr>";
  }).join("");
  document.getElementById("upd").textContent="Last update: "+new Date().toLocaleString()+" | Auto-refresh 2min";
}
render(D);
setTimeout(()=>window.location.reload(),120000);
</script></body></html>"""

    full_html = p1 + data_json + p2
    os.makedirs("docs", exist_ok=True)
    os.makedirs("dashboard", exist_ok=True)
    with open("docs/index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    with open("dashboard/index.html", "w", encoding="utf-8") as f:
        f.write(full_html)
    print("Dashboard generated OK")

if __name__ == "__main__":
    generate()
'''

files['agents/debate.py'] = '''from utils.ollama_client import chat, extract_confidence
from config import MODEL_HEAVY, DEBATE_ROUNDS

BULL_SYSTEM = """You are a veteran gold bull trader with 20 years experience on XAU/USD.
Your job: build the STRONGEST possible case for gold RISING in the next 24-48 hours.
Use specific data provided. Be decisive and concrete.
Structure your argument:
1. Primary catalyst driving gold up RIGHT NOW
2. Technical confirmation from the price data given
3. Why the bears are wrong
4. Specific price target

CRITICAL: Your final line MUST be exactly:
Confidence: XX%
(where XX is your honest confidence level between 45 and 85)"""

BEAR_SYSTEM = """You are a veteran gold bear trader with 20 years experience on XAU/USD.
Your job: build the STRONGEST possible case for gold FALLING in the next 24-48 hours.
Use specific data provided. Be decisive and concrete.
Structure your argument:
1. Primary catalyst driving gold down RIGHT NOW
2. Technical breakdown signals from the price data given
3. Why the bulls are wrong
4. Specific downside target

CRITICAL: Your final line MUST be exactly:
Confidence: XX%
(where XX is your honest confidence level between 45 and 85)"""

def _ctx(macro, tech, price, news):
    p   = price.get("price", 0)
    chg = price.get("change_pct", 0)
    h   = price.get("high", p)
    l   = price.get("low",  p)
    rsi = tech.get("rsi_value", "N/A")
    s   = tech.get("support", 0)
    r   = tech.get("resistance", 0)
    s20 = tech.get("sma20", "N/A")
    ni  = news.get("news_items", [])
    top_news = [x["title"] for x in ni[:5]] if ni else ["No news available"]
    return (
        "=== PRICE DATA ===\\n"
        "XAU/USD: $" + str(p) + " | Change: " + str(chg) + "% | Range: $" + str(l) + "-$" + str(h) + "\\n"
        "\\n=== TECHNICAL INDICATORS (CALCULATED) ===\\n"
        "RSI(14): " + str(rsi) + " | SMA20: $" + str(s20) + "\\n"
        "Support: $" + str(s) + " | Resistance: $" + str(r) + "\\n"
        "20-day trend: " + str(tech.get("trend", "N/A")) + " | Bias: " + str(tech.get("bias", "N/A")) + "\\n"
        "\\n=== MACRO CONTEXT ===\\n"
        "Macro bias: " + str(macro.get("macro_bias", "N/A")) + " (" + str(macro.get("confidence", 0)) + "%)\\n"
        "Key drivers: " + str(macro.get("key_drivers", [])) + "\\n"
        "Analysis: " + str(macro.get("analysis", "")) + "\\n"
        "\\n=== LATEST NEWS (use these!) ===\\n"
        + "\\n".join(["- " + n for n in top_news])
    )

def run_debate(macro_data, tech_data, price_data, news_data=None):
    if news_data is None:
        news_data = {}
    context = _ctx(macro_data, tech_data, price_data, news_data)
    history, bull_scores, bear_scores = [], [], []

    # Round 1
    bull_msg = chat(
        context + "\\n\\nMake your BULL case. Be specific. Last line must be: Confidence: XX%",
        model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.75
    )
    bear_msg = chat(
        context + "\\n\\nMake your BEAR case. Be specific. Last line must be: Confidence: XX%",
        model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.75
    )
    bs1, br1 = extract_confidence(bull_msg), extract_confidence(bear_msg)
    bull_scores.append(bs1); bear_scores.append(br1)
    history.append({"round": 1, "bull": bull_msg, "bear": bear_msg})
    print("      Round 1 -- Bull: " + str(bs1) + "% | Bear: " + str(br1) + "%")

    # Round 2
    bull_msg2 = chat(
        context + "\\n\\nBEAR argued:\\n" + bear_msg[-600:] +
        "\\n\\nDIRECTLY REFUTE the bear. Strengthen your bull case with NEW points. Last line: Confidence: XX%",
        model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.7
    )
    bear_msg2 = chat(
        context + "\\n\\nBULL argued:\\n" + bull_msg[-600:] +
        "\\n\\nDIRECTLY REFUTE the bull. Strengthen your bear case with NEW points. Last line: Confidence: XX%",
        model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.7
    )
    bs2, br2 = extract_confidence(bull_msg2), extract_confidence(bear_msg2)
    bull_scores.append(bs2); bear_scores.append(br2)
    history.append({"round": 2, "bull": bull_msg2, "bear": bear_msg2})
    print("      Round 2 -- Bull: " + str(bs2) + "% | Bear: " + str(br2) + "%")

    # Round 3 - final verdict
    bull_msg3 = chat(
        context + "\\n\\nFINAL ROUND. Bear\'s best argument was:\\n" + bear_msg2[-400:] +
        "\\n\\nGive your FINAL bull verdict. Be decisive. Last line: Confidence: XX%",
        model=MODEL_HEAVY, system=BULL_SYSTEM, temperature=0.65
    )
    bear_msg3 = chat(
        context + "\\n\\nFINAL ROUND. Bull\'s best argument was:\\n" + bull_msg2[-400:] +
        "\\n\\nGive your FINAL bear verdict. Be decisive. Last line: Confidence: XX%",
        model=MODEL_HEAVY, system=BEAR_SYSTEM, temperature=0.65
    )
    bs3, br3 = extract_confidence(bull_msg3), extract_confidence(bear_msg3)
    bull_scores.append(bs3); bear_scores.append(br3)
    history.append({"round": 3, "bull": bull_msg3, "bear": bear_msg3})
    print("      Round 3 -- Bull: " + str(bs3) + "% | Bear: " + str(br3) + "%")

    avg_bull = round(sum(bull_scores) / 3, 1)
    avg_bear = round(sum(bear_scores) / 3, 1)
    margin   = round(abs(avg_bull - avg_bear), 1)
    is_tie   = margin < 10
    winner   = "TIE" if is_tie else ("BULL" if avg_bull > avg_bear else "BEAR")

    return {
        "history":             history,
        "avg_bull_confidence": avg_bull,
        "avg_bear_confidence": avg_bear,
        "margin":              margin,
        "winner":              winner,
        "is_tie":              is_tie,
        "final_bull":          bull_msg3,
        "final_bear":          bear_msg3,
        "round_scores":        list(zip(bull_scores, bear_scores))
    }
'''

files['backtest.py'] = '''import random
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
'''

for path, content in files.items():
    os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Written: " + path)

print("\nAll files written OK")
