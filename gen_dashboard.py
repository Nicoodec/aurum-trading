# gen_dashboard.py — genera dashboard/index.html
import os
os.makedirs('dashboard', exist_ok=True)
os.makedirs('docs', exist_ok=True)

html = r'''<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AURUM - Gold Trading System</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#000;color:#c9a84c;font-family:'Courier New',monospace;min-height:100vh}
canvas{position:fixed;top:0;left:0;z-index:0;pointer-events:none;opacity:.4}
.wrap{position:relative;z-index:1;max-width:1400px;margin:0 auto;padding:24px 16px}
pre.ascii{color:#f0c040;font-size:clamp(6px,1.1vw,13px);line-height:1.15;text-align:center;margin-bottom:8px}
.tagline{text-align:center;color:#555;font-size:11px;letter-spacing:5px;margin-bottom:32px}
.status-row{display:flex;align-items:center;justify-content:center;gap:12px;margin-bottom:32px;flex-wrap:wrap}
.dot{width:8px;height:8px;border-radius:50%;background:#22c55e;animation:blink 2s infinite}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.badge{display:inline-flex;align-items:center;padding:3px 12px;border-radius:3px;font-size:12px;letter-spacing:2px;font-weight:bold}
.LONG{background:#052e16;color:#4ade80;border:1px solid #166534}
.SHORT{background:#2d0a0a;color:#f87171;border:1px solid #7f1d1d}
.STAY_OUT{background:#111;color:#666;border:1px solid #333}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px;margin-bottom:20px}
.card{background:#050505;border:1px solid #d4a01722;border-radius:6px;padding:18px}
.card-title{color:#888;font-size:10px;letter-spacing:3px;text-transform:uppercase;margin-bottom:14px;border-bottom:1px solid #1a1a1a;padding-bottom:8px}
.metric{display:flex;justify-content:space-between;align-items:center;margin:7px 0;font-size:12px}
.metric .k{color:#555}
.metric .v{color:#e8c46a}
.metric .v.green{color:#4ade80}
.metric .v.red{color:#f87171}
.bar-wrap{background:#111;border-radius:2px;height:6px;flex:1;margin:0 10px}
.bar-fill{height:6px;border-radius:2px;transition:width .5s}
.bar-bull{background:#4ade80}
.bar-bear{background:#f87171}
table{width:100%;border-collapse:collapse;font-size:11px}
th{color:#444;padding:8px 6px;text-align:left;border-bottom:1px solid #111;letter-spacing:1px;font-size:10px}
td{padding:7px 6px;border-bottom:1px solid #0a0a0a;color:#888}
td.LONG{color:#4ade80} td.SHORT{color:#f87171} td.STAY_OUT{color:#444}
.footer{text-align:center;color:#222;font-size:10px;margin-top:32px;letter-spacing:2px}
.refresh-bar{height:2px;background:#d4a01733;margin-bottom:16px;border-radius:1px;overflow:hidden}
.refresh-fill{height:100%;background:#d4a017;border-radius:1px;transition:width 1s linear}
#last-update{color:#333;font-size:10px;text-align:right;margin-bottom:8px}
</style>
</head>
<body>
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
<p class="tagline">MULTI-AGENT GOLD TRADING &middot; AI POWERED &middot; PAPER TRADING</p>
<div class="refresh-bar"><div class="refresh-fill" id="rf" style="width:100%"></div></div>
<div id="last-update">Loading...</div>
<div class="status-row">
  <div class="dot"></div>
  <span style="font-size:11px;color:#555;letter-spacing:2px">LIVE</span>
  <span id="current-price" style="font-size:18px;color:#f0c040">XAU/USD &mdash;</span>
  <span id="price-change" style="font-size:12px;color:#555"></span>
  <span id="decision-badge" class="badge STAY_OUT">STAY OUT</span>
</div>
<div class="grid">
  <div class="card">
    <div class="card-title">Last Signal</div>
    <div class="metric"><span class="k">Confidence</span><span class="v" id="sig-conf">-</span></div>
    <div class="metric"><span class="k">Entry</span><span class="v" id="sig-entry">-</span></div>
    <div class="metric"><span class="k">Stop loss</span><span class="v red" id="sig-sl">-</span></div>
    <div class="metric"><span class="k">Take profit</span><span class="v green" id="sig-tp">-</span></div>
    <div class="metric"><span class="k">R:R</span><span class="v" id="sig-rr">-</span></div>
    <div class="metric"><span class="k">Risk USD</span><span class="v" id="sig-risk">-</span></div>
    <div class="metric"><span class="k">Reason</span></div>
    <div style="color:#555;font-size:10px;margin-top:4px;line-height:1.5" id="sig-reason">-</div>
  </div>
  <div class="card">
    <div class="card-title">Debate Result</div>
    <div class="metric">
      <span class="k">Bull</span>
      <div class="bar-wrap"><div class="bar-fill bar-bull" id="bull-bar" style="width:50%"></div></div>
      <span class="v green" id="bull-pct">50%</span>
    </div>
    <div class="metric">
      <span class="k">Bear</span>
      <div class="bar-wrap"><div class="bar-fill bar-bear" id="bear-bar" style="width:50%"></div></div>
      <span class="v red" id="bear-pct">50%</span>
    </div>
    <div class="metric"><span class="k">Winner</span><span class="v" id="debate-winner">-</span></div>
    <div class="metric"><span class="k">Margin</span><span class="v" id="debate-margin">-</span></div>
    <div class="card-title" style="margin-top:14px">Market Context</div>
    <div class="metric"><span class="k">Macro bias</span><span class="v" id="macro-bias">-</span></div>
    <div class="metric"><span class="k">Trend</span><span class="v" id="tech-trend">-</span></div>
    <div class="metric"><span class="k">RSI zone</span><span class="v" id="rsi-zone">-</span></div>
    <div class="metric"><span class="k">Support</span><span class="v" id="support">-</span></div>
    <div class="metric"><span class="k">Resistance</span><span class="v" id="resistance">-</span></div>
  </div>
  <div class="card">
    <div class="card-title">Portfolio</div>
    <div class="metric"><span class="k">Capital</span><span class="v" id="p-capital">,000</span></div>
    <div class="metric"><span class="k">Equity</span><span class="v" id="p-equity">-</span></div>
    <div class="metric"><span class="k">Total P&amp;L</span><span class="v" id="p-pnl">-</span></div>
    <div class="metric"><span class="k">Open positions</span><span class="v" id="p-open">-</span></div>
    <div class="metric"><span class="k">Total trades</span><span class="v" id="p-trades">-</span></div>
    <div class="metric"><span class="k">Win rate</span><span class="v" id="p-winrate">-</span></div>
    <div class="metric"><span class="k">Avg win</span><span class="v green" id="p-avgwin">-</span></div>
    <div class="metric"><span class="k">Avg loss</span><span class="v red" id="p-avgloss">-</span></div>
    <div class="metric"><span class="k">Profit factor</span><span class="v" id="p-pf">-</span></div>
  </div>
</div>
<div class="card">
  <div class="card-title">Signal History</div>
  <table>
    <thead><tr><th>TIME</th><th>PRICE</th><th>SIGNAL</th><th>CONF</th><th>TREND</th><th>MACRO</th><th>BULL%</th><th>BEAR%</th><th>WINNER</th></tr></thead>
    <tbody id="htable"><tr><td colspan="9" style="text-align:center;color:#222;padding:20px">No signals yet</td></tr></tbody>
  </table>
</div>
<div class="footer">AURUM &middot; MULTI-AGENT AI TRADING &middot; github.com/Nicoodec/aurum-trading</div>
</div>
<script>
const canvas=document.getElementById("c"),ctx=canvas.getContext("2d");
function resize(){canvas.width=innerWidth;canvas.height=innerHeight}
resize();
const chars="",cols=()=>Math.floor(canvas.width/16);
let drops=[];
function initDrops(){drops=Array.from({length:cols()},()=>Math.random()*canvas.height/16)}
initDrops();
window.onresize=()=>{resize();initDrops()};
setInterval(()=>{
  ctx.fillStyle="rgba(0,0,0,0.05)";ctx.fillRect(0,0,canvas.width,canvas.height);
  ctx.fillStyle="#b8860b55";ctx.font="13px monospace";
  drops.forEach((y,i)=>{
    ctx.fillText(chars[Math.floor(Math.random()*chars.length)],i*16,y*16);
    if(y*16>canvas.height&&Math.random()>.97)drops[i]=0;
    drops[i]+=.4;
  });
},60);

const REFRESH=60;let countdown=REFRESH;
function fmt(n){return n!=null?"$"+Number(n).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2}):"--"}
function set(id,val){const el=document.getElementById(id);if(el)el.textContent=val}

async function loadState(){
  try{
    const r=await fetch("state.json?t="+Date.now());
    if(!r.ok)return;
    const d=await r.json();
    const l=d.latest||{},s=d.stats||{},h=d.history||[];
    const dec=(l.decision||"STAY OUT").replace(" ","_");

    set("current-price","XAU/USD "+(l.price?Number(l.price).toLocaleString("en-US",{minimumFractionDigits:2}):"--"));
    const chg=l.change_pct;
    set("price-change",chg?(chg>0?"+":"")+chg+"%":"");
    const badge=document.getElementById("decision-badge");
    badge.textContent=l.decision||"STAY OUT";
    badge.className="badge "+(l.decision==="LONG"?"LONG":l.decision==="SHORT"?"SHORT":"STAY_OUT");

    const rp=l.risk_plan||{};
    set("sig-conf",(l.confidence||0)+"%");
    set("sig-entry",rp.entry?fmt(rp.entry):"--");
    set("sig-sl",rp.stop_loss?fmt(rp.stop_loss):"--");
    set("sig-tp",rp.take_profit?fmt(rp.take_profit):"--");
    set("sig-rr",rp.risk_reward?"1:"+rp.risk_reward:"--");
    set("sig-risk",rp.risk_usd?fmt(rp.risk_usd):"--");
    set("sig-reason",l.reason||"--");

    const db=l.debate_summary||{};
    const bull=db.bull_conf||50,bear=db.bear_conf||50;
    document.getElementById("bull-bar").style.width=bull+"%";
    document.getElementById("bear-bar").style.width=bear+"%";
    set("bull-pct",bull+"%");set("bear-pct",bear+"%");
    set("debate-winner",db.winner||"--");
    set("debate-margin",db.margin?(db.margin+"pts"):"--");

    const tech=l.technical||{},mac=l.macro||{};
    set("macro-bias",mac.bias||"--");
    set("tech-trend",tech.trend||"--");
    set("rsi-zone",tech.rsi_zone||"--");
    set("support",tech.support?fmt(tech.support):"--");
    set("resistance",tech.resistance?fmt(tech.resistance):"--");

    set("p-capital",fmt(s.capital));
    set("p-equity",fmt(s.equity));
    const pnl=s.total_pnl||0;
    const pnlEl=document.getElementById("p-pnl");
    pnlEl.textContent=(pnl>=0?"+":"")+fmt(Math.abs(pnl));
    pnlEl.className="v "+(pnl>=0?"green":"red");
    set("p-open",(s.open_positions||0)+" / 3");
    set("p-trades",s.total_trades||0);
    set("p-winrate",(s.win_rate||0)+"%");
    set("p-avgwin",fmt(s.avg_win));
    set("p-avgloss",fmt(Math.abs(s.avg_loss)));
    set("p-pf",s.profit_factor||"--");

    const tbody=document.getElementById("htable");
    const rows=h.slice(-30).reverse();
    if(!rows.length){
      tbody.innerHTML="<tr><td colspan='9' style='text-align:center;color:#222;padding:20px'>No signals yet</td></tr>";
      return;
    }
    tbody.innerHTML=rows.map(row=>{
      const dec2=(row.decision||"STAY OUT").replace(" ","_");
      const ts=row.ts?row.ts.substring(0,16).replace("T"," "):row.ts||"";
      const tech2=row.technical||{};
      const mac2=row.macro||{};
      const db2=row.debate_summary||{};
      return "<tr>"
        +"<td>"+ts+"</td>"
        +"<td>"+(row.price?Number(row.price).toFixed(2):"--")+"</td>"
        +"<td class='"+dec2+"'>"+(row.decision||"--")+"</td>"
        +"<td>"+(row.confidence||0)+"%</td>"
        +"<td>"+(tech2.trend||"--")+"</td>"
        +"<td>"+(mac2.bias||"--")+"</td>"
        +"<td style='color:#4ade80'>"+(db2.bull_conf||"--")+"%</td>"
        +"<td style='color:#f87171'>"+(db2.bear_conf||"--")+"%</td>"
        +"<td>"+(db2.winner||"--")+"</td>"
        +"</tr>";
    }).join("");

    document.getElementById("last-update").textContent="Last update: "+new Date().toLocaleTimeString();
  }catch(e){console.log("state load:",e)}
}

setInterval(()=>{
  countdown--;
  document.getElementById("rf").style.width=(countdown/REFRESH*100)+"%";
  if(countdown<=0){countdown=REFRESH;loadState();}
},1000);
loadState();
</script>
</body>
</html>'''

with open('dashboard/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
with open('docs/index.html', 'w', encoding='utf-8') as f:
    f.write(html)
print('Dashboard generated OK')
