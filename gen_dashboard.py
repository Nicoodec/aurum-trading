import os, json

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
body{background:#000;color:#c9a84c;font-family:'Courier New',monospace;min-height:100vh}
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
.k{color:#333}.v{color:#f0c040}.g{color:#4ade80}.r{color:#f87171}
.bw{background:#0a0a0a;border-radius:2px;height:5px;flex:1;margin:0 8px}
.bf{height:5px;border-radius:2px;transition:width .8s}.bb{background:#4ade80}.br{background:#f87171}
table{width:100%;border-collapse:collapse;font-size:11px}
th{color:#c9a84c;padding:8px 6px;text-align:left;border-bottom:1px solid #0f0f0f;font-size:9px;text-transform:uppercase}
td{padding:6px;border-bottom:1px solid #080808;color:#9a7a30}
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
    nb.innerHTML=ni.length?ni.map(n=>"<div class='ni'><span class='ns'>["+n.source+"]</span> "+n.title+"</div>").join(""):"<span style='color:#111'>No news this cycle</span>";
  }
  const tb=document.getElementById("ht"),rows=h.slice(-40).reverse();
  if(!rows.length){tb.innerHTML="<tr><td colspan='12' style='text-align:center;padding:20px;color:#111'>No signals yet</td></tr>";return;}
  tb.innerHTML=rows.map(row=>{
    const dc2=(row.decision||"STAY OUT").replace(" ","_");
    const ts2=row.ts?row.ts.substring(0,16).replace("T"," "):"--";
    const te2=row.technical||{},ma2=row.macro||{},db2=row.debate_summary||{},rp2=row.risk_plan||{};
    return "<tr><td>"+ts2+"</td>"
      +"<td>"+(row.price?Number(row.price).toFixed(2):"--")+"</td>"
      +"<td class='"+dc2+"'>"+dc2.replace("_"," ")+"</td>"
      +"<td>"+(row.confidence||0)+"%</td>"
      +"<td>"+(rp2.risk_reward?"1:"+rp2.risk_reward:"--")+"</td>"
      +"<td>"+(te2.rsi_value||"--")+"</td>"
      +"<td>"+(te2.trend||"--")+"</td>"
      +"<td>"+(ma2.bias||ma2.macro_bias||"--")+"</td>"
      +"<td style='color:#4ade80'>"+(db2.bull_conf||"--")+"%</td>"
      +"<td style='color:#f87171'>"+(db2.bear_conf||"--")+"%</td>"
      +"<td>"+(db2.winner||"--")+"</td>"
      +"<td style='color:#222;font-size:10px'>"+(row.reason||"--").substring(0,35)+"</td>"
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
