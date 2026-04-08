import os, json

def generate(latest=None, history=None, stats=None):
    if latest  is None: latest  = {}
    if history is None: history = []
    if stats   is None:
        stats = {"capital":25000,"equity":25000,"total_pnl":0,"total_trades":0,
                 "open_positions":0,"win_rate":0,"wins":0,"losses":0,
                 "avg_win":0,"avg_loss":0,"profit_factor":0}

    data_json = json.dumps({"latest":latest,"history":history[-50:],"stats":stats},
                           indent=2, default=str)

    p1 = """<!DOCTYPE html>
<html lang="es"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AURUM - Gold Trading AI</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#0a0800;color:#e8c84a;font-family:'Courier New',monospace;min-height:100vh}
canvas{position:fixed;top:0;left:0;z-index:0;pointer-events:none;opacity:.2}
.wrap{position:relative;z-index:1;max-width:1500px;margin:0 auto;padding:20px 16px}
pre.ascii{color:#f5d020;font-size:clamp(6px,1.2vw,14px);line-height:1.2;text-align:center;margin-bottom:6px;text-shadow:0 0 15px #f5d02044}
.tag{text-align:center;color:#7a6010;font-size:10px;letter-spacing:6px;margin-bottom:20px;text-transform:uppercase}
.sr{display:flex;align-items:center;justify-content:center;gap:14px;margin-bottom:24px;flex-wrap:wrap}
.dot{width:8px;height:8px;border-radius:50%;background:#22c55e;animation:blink 2s infinite;box-shadow:0 0 6px #22c55e}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
.price{font-size:28px;color:#f5d020;font-weight:bold;text-shadow:0 0 10px #f5d02044}
.chg-up{color:#4ade80;font-size:14px}.chg-dn{color:#f87171;font-size:14px}.chg-neu{color:#8a7020;font-size:14px}
.badge{padding:5px 16px;border-radius:4px;font-size:13px;letter-spacing:2px;font-weight:bold}
.LONG{background:#0a2e0a;color:#4ade80;border:1px solid #4ade80;box-shadow:0 0 8px #4ade8033}
.SHORT{background:#2e0a0a;color:#f87171;border:1px solid #f87171;box-shadow:0 0 8px #f8717133}
.STAY_OUT{display:none}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin-bottom:14px}
.card{background:#0f0c00;border:1px solid #3a2800;border-radius:8px;padding:18px}
.card:hover{border-color:#8a6800;transition:border-color .2s}
.ct{color:#c9a030;font-size:10px;letter-spacing:3px;text-transform:uppercase;
    margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid #2a2000}
.m{display:flex;justify-content:space-between;align-items:center;margin:7px 0;font-size:12px}
.k{color:#8a7020}.v{color:#f0c030}.g{color:#4ade80}.r{color:#f87171}
.bw{background:#1a1500;border-radius:2px;height:6px;flex:1;margin:0 8px}
.bf{height:6px;border-radius:2px;transition:width .8s}
.bb{background:linear-gradient(90deg,#1e4e1e,#4ade80)}
.br{background:linear-gradient(90deg,#4e1e1e,#f87171)}
table{width:100%;border-collapse:collapse;font-size:11px}
th{color:#c9a030;padding:9px 6px;text-align:left;border-bottom:1px solid #2a2000;
   font-size:9px;text-transform:uppercase;letter-spacing:1px}
td{padding:7px 6px;border-bottom:1px solid #150f00;color:#d4a830}
td.LONG{color:#4ade80;font-weight:bold}
td.SHORT{color:#f87171;font-weight:bold}
td.STAY_OUT{color:#4a3808}
.ni{color:#9a8020;font-size:10px;padding:5px 0;border-bottom:1px solid #150f00;line-height:1.5}
.ns{color:#5a4010;margin-right:6px}
#upd{color:#3a2800;font-size:9px;text-align:right;margin-bottom:8px}
.footer{text-align:center;color:#2a1800;font-size:9px;margin-top:24px;letter-spacing:2px}
.pbar{height:2px;background:#1a1500;margin-bottom:12px;border-radius:1px;overflow:hidden}
.pfill{height:100%;background:linear-gradient(90deg,#3a2000,#c9a030);border-radius:1px;transition:width 1s linear}
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
<p class="tag">Multi-Agent Gold Swing Trading &middot; AI Powered</p>
<div class="pbar"><div class="pfill" id="pf" style="width:100%"></div></div>
<div id="upd">--</div>
<div class="sr">
  <div class="dot"></div>
  <span style="font-size:11px;color:#5a4810;letter-spacing:2px">LIVE</span>
  <span class="price" id="xp">XAU/USD --</span>
  <span id="xc" class="chg-neu"></span>
  <span id="xb" class="badge STAY_OUT"></span>
</div>
<div class="grid">
<div class="card">
  <div class="ct">Last Signal</div>
  <div class="m"><span class="k">Confidence</span><span class="v" id="sc">--</span></div>
  <div class="m"><span class="k">Direction</span><span class="v" id="sdir">--</span></div>
  <div class="m"><span class="k">Entry</span><span class="v" id="se">--</span></div>
  <div class="m"><span class="k">Stop loss</span><span class="r" id="ss">--</span></div>
  <div class="m"><span class="k">Take profit</span><span class="g" id="st">--</span></div>
  <div class="m"><span class="k">R:R</span><span class="v" id="srr">--</span></div>
  <div class="m"><span class="k">Lots</span><span class="v" id="sl">--</span></div>
  <div class="m"><span class="k">Risk USD</span><span class="v" id="sk">--</span></div>
  <div style="color:#7a6010;font-size:10px;margin-top:10px;line-height:1.6;border-top:1px solid #1a1500;padding-top:8px" id="sreason">--</div>
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
  <div class="ct" style="margin-top:14px">Macro</div>
  <div class="m"><span class="k">Bias</span><span class="v" id="mb">--</span></div>
  <div class="m"><span class="k">DXY</span><span class="v" id="dxy">--</span></div>
  <div class="m"><span class="k">10Y Treasury</span><span class="v" id="t10">--</span></div>
  <div class="m"><span class="k">FedFunds</span><span class="v" id="fed">--</span></div>
</div>
<div class="card">
  <div class="ct">Portfolio</div>
  <div class="m"><span class="k">Balance</span><span class="v" id="pc">--</span></div>
  <div class="m"><span class="k">Equity</span><span class="v" id="pe">--</span></div>
  <div class="m"><span class="k">Total P&amp;L</span><span class="v" id="pp">--</span></div>
  <div class="m"><span class="k">Open positions</span><span class="v" id="po">--</span></div>
  <div class="m"><span class="k">Total trades</span><span class="v" id="pt">--</span></div>
  <div class="m"><span class="k">Win rate</span><span class="v" id="pw">--</span></div>
  <div class="m"><span class="k">Avg win</span><span class="g" id="pa">--</span></div>
  <div class="m"><span class="k">Avg loss</span><span class="r" id="pal">--</span></div>
  <div class="m"><span class="k">Profit factor</span><span class="v" id="pf2">--</span></div>
  <div class="ct" style="margin-top:14px">FTMO Limits</div>
  <div class="m"><span class="k">Daily remaining</span><span class="v" id="fdr">--</span></div>
  <div class="m"><span class="k">Total remaining</span><span class="v" id="ftr">--</span></div>
</div>
</div>
<div class="card" style="margin-bottom:14px">
  <div class="ct">News This Cycle</div>
  <div id="nb" style="max-height:140px;overflow-y:auto"><span style="color:#2a2000">No news yet</span></div>
</div>
<div class="card">
  <div class="ct">Signal History</div>
  <table><thead><tr>
    <th>Time</th><th>Price</th><th>Signal</th><th>Conf</th><th>RR</th>
    <th>RSI</th><th>Trend</th><th>DXY</th><th>Macro</th><th>Bull</th><th>Bear</th><th>Margin</th><th>Reason</th>
  </tr></thead><tbody id="ht">
    <tr><td colspan="13" style="text-align:center;padding:20px;color:#2a2000">No signals yet</td></tr>
  </tbody></table>
</div>
<div class="footer">AURUM &middot; nicoodec.github.io/aurum-trading &middot; Multi-Agent AI Gold Trading</div>
</div>
<script>
const cv=document.getElementById("c"),cx=cv.getContext("2d");
function rz(){cv.width=innerWidth;cv.height=innerHeight}rz();
const ch="$XAU01GOLD",nc=()=>Math.floor(cv.width/16);
let dr=[];
function id2(){dr=Array.from({length:nc()},()=>Math.random()*cv.height/16)}
id2();window.onresize=()=>{rz();id2()};
setInterval(()=>{
  cx.fillStyle="rgba(10,8,0,0.06)";cx.fillRect(0,0,cv.width,cv.height);
  cx.fillStyle="#c9a03018";cx.font="13px monospace";
  dr.forEach((y,i)=>{
    cx.fillText(ch[Math.floor(Math.random()*ch.length)],i*16,y*16);
    if(y*16>cv.height&&Math.random()>.97)dr[i]=0;
    dr[i]+=.28;
  });
},65);

function fd(n,pre="$"){return n!=null?pre+Number(n).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2}):"--"}
function sv(id,v){const e=document.getElementById(id);if(e)e.textContent=v}
const D="""

    p2 = """;
function render(d){
  const l=d.latest||{},st=d.stats||{},h=d.history||[];
  const dec=l.decision||"STAY OUT",dcs=dec.replace(" ","_");
  const p=l.price;
  sv("xp","XAU/USD "+(p?Number(p).toLocaleString("en-US",{minimumFractionDigits:2}):"--"));
  const chg=l.change_pct,ce=document.getElementById("xc");
  if(ce&&chg!=null){ce.textContent=(chg>0?"+":"")+chg+"%";ce.className=chg>0?"chg-up":chg<0?"chg-dn":"chg-neu";}
  const be=document.getElementById("xb");
  if(be){
    if(dec==="LONG"||dec==="SHORT"){be.textContent=dec;be.className="badge "+dcs;}
    else{be.textContent="";be.className="badge STAY_OUT";}
  }
  const rp=l.risk_plan||{};
  sv("sc",(l.confidence||0)+"%");
  sv("sdir",rp.direction||"--");
  sv("se",fd(rp.entry));sv("ss",fd(rp.stop_loss));sv("st",fd(rp.take_profit));
  sv("srr",rp.risk_reward?"1:"+rp.risk_reward:"--");
  sv("sl",rp.contracts||"--");sv("sk",fd(rp.risk_usd));
  sv("sreason",l.reason||"--");
  const db=l.debate_summary||{},bl=db.bull_conf||50,br2=db.bear_conf||50;
  const bel=document.getElementById("bb"),rel2=document.getElementById("rb");
  if(bel)bel.style.width=bl+"%";if(rel2)rel2.style.width=br2+"%";
  sv("bp",bl+"%");sv("rp",br2+"%");
  sv("dw",db.winner||"--");sv("dm",db.margin!=null?(db.margin+"pts"):"--");
  const te=l.technical||{},ma=l.macro||{},fr=l.fred||{};
  sv("tt",te.trend||"--");
  sv("tr",(te.rsi_value!=null?te.rsi_value:"--")+" ("+(te.rsi_zone||"--")+")");
  sv("ts",fd(te.sma20));sv("tu",fd(te.support));sv("te",fd(te.resistance));
  sv("mb",(ma.bias||ma.macro_bias||"--")+" "+(ma.confidence?"("+ma.confidence+"%)":""));
  sv("dxy",fr.dxy!=null?Number(fr.dxy).toFixed(2):"--");
  sv("t10",fr.t10y!=null?fr.t10y+"%":"--");
  sv("fed",fr.fedfunds!=null?fr.fedfunds+"%":"--");
  sv("pc",fd(st.capital));sv("pe",fd(st.equity));
  const pn=st.total_pnl||0,pne=document.getElementById("pp");
  if(pne){pne.textContent=(pn>=0?"+":"")+fd(Math.abs(pn));pne.className=pn>=0?"v g":"v r";}
  sv("po",(st.open_positions||0)+" / 3");sv("pt",st.total_trades||0);
  sv("pw",(st.win_rate||0)+"%");sv("pa",fd(st.avg_win));sv("pal",fd(Math.abs(st.avg_loss||0)));
  sv("pf2",st.profit_factor||"--");
  const ftmo=l.ftmo_status||{};
  sv("fdr",ftmo.daily_remaining!=null?fd(ftmo.daily_remaining):"--");
  sv("ftr",ftmo.total_remaining!=null?fd(ftmo.total_remaining):"--");
  const nb=document.getElementById("nb");
  if(nb){
    const ni=l.news_items||[];
    nb.innerHTML=ni.length?ni.slice(0,15).map(n=>"<div class=\\'ni\\'><span class=\\'ns\\'>["+n.source+"]</span>"+n.title+"</div>").join(""):"<span style=\\'color:#2a2000\\'>No news this cycle</span>";
  }
  const tb=document.getElementById("ht"),rows=h.slice(-50).reverse();
  if(!rows.length){tb.innerHTML="<tr><td colspan=\\'13\\' style=\\'text-align:center;padding:20px;color:#2a2000\\'>No signals yet</td></tr>";return;}
  tb.innerHTML=rows.map(row=>{
    const dc2=(row.decision||"STAY OUT").replace(" ","_");
    const ts2=row.ts?row.ts.substring(0,16).replace("T"," "):"--";
    const te2=row.technical||{},ma2=row.macro||{},db2=row.debate_summary||{},rp2=row.risk_plan||{},fr2=row.fred||{};
    return "<tr><td>"+ts2+"</td>"
      +"<td style=\\'color:#f0c030\\'>"+(row.price?Number(row.price).toFixed(2):"--")+"</td>"
      +"<td class=\\'"+dc2+"\\'>"+dc2.replace("_"," ")+"</td>"
      +"<td style=\\'color:#c9a030\\'>"+(row.confidence||0)+"%</td>"
      +"<td>"+(rp2.risk_reward?"1:"+rp2.risk_reward:"--")+"</td>"
      +"<td>"+(te2.rsi_value!=null?te2.rsi_value:"--")+"</td>"
      +"<td>"+(te2.trend||"--")+"</td>"
      +"<td>"+(fr2.dxy!=null?Number(fr2.dxy).toFixed(1):"--")+"</td>"
      +"<td>"+(ma2.bias||ma2.macro_bias||"--")+"</td>"
      +"<td style=\\'color:#4ade80\\'>"+(db2.bull_conf!=null?db2.bull_conf:"--")+"%</td>"
      +"<td style=\\'color:#f87171\\'>"+(db2.bear_conf!=null?db2.bear_conf:"--")+"%</td>"
      +"<td style=\\'color:#c9a030\\'>"+(db2.margin!=null?db2.margin:"--")+"pts</td>"
      +"<td style=\\'color:#5a4810;font-size:10px\\'>"+(row.reason||"--").substring(0,30)+"</td>"
      +"</tr>";
  }).join("");
  sv("upd","Last update: "+new Date().toLocaleString()+" | Auto-refresh 2min");
}
render(D);
const REFRESH=120;let cd=REFRESH;
setInterval(()=>{
  cd--;
  const pf=document.getElementById("pf");
  if(pf)pf.style.width=(cd/REFRESH*100)+"%";
  if(cd<=0){cd=REFRESH;window.location.reload();}
},1000);
</script></body></html>"""

    full = p1 + data_json + p2
    os.makedirs("docs", exist_ok=True)
    os.makedirs("dashboard", exist_ok=True)
    with open("docs/index.html","w",encoding="utf-8") as f: f.write(full)
    with open("dashboard/index.html","w",encoding="utf-8") as f: f.write(full)
    print("Dashboard generated OK")

if __name__ == "__main__":
    generate()
