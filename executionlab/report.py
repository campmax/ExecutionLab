"""Portable self-contained HTML report: no server or third-party scripts."""
import html
import json
from pathlib import Path


def write_report(path, bundle):
    template = r'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>ExecutionLab | Execution research</title><style>
:root{color-scheme:dark;font-family:Segoe UI,Arial,sans-serif;background:#0b1220;color:#edf3fc}body{max-width:1180px;margin:auto;padding:36px 24px}h1{font-size:48px;margin:10px 0}h2{font-size:21px}p{line-height:1.6;color:#aebdd1}.eyebrow{color:#65dbbd;letter-spacing:3px;font-size:12px}.badge{border:1px solid #e8b861;color:#e8b861;padding:9px 13px;display:inline-block;border-radius:8px}.controls,.cards{display:flex;gap:14px;flex-wrap:wrap;margin:24px 0}select{background:#17243a;color:white;border:1px solid #4b6384;border-radius:7px;padding:10px;max-width:100%}label{display:grid;gap:7px;color:#aebdd1}.card{background:#142035;border:1px solid #263850;border-radius:10px;padding:20px;flex:1;min-width:170px}.value{font-size:28px;margin-top:9px;color:#fff}.sub{font-size:12px;color:#aebdd1}section{background:#111d30;border:1px solid #263850;border-radius:12px;padding:24px;margin:20px 0}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{text-align:right;padding:13px 9px;border-bottom:1px solid #263850}th:first-child,td:first-child{text-align:left}th{color:#aebdd1;font-size:12px}.scroll{overflow:auto}svg{width:100%;height:auto;display:block}button{background:#65dbbd;color:#0b1220;border:0;padding:12px;border-radius:8px;cursor:pointer}a{color:#65dbbd}.note{border-left:3px solid #e8b861;padding-left:15px}code{overflow-wrap:anywhere}footer{color:#8194ae;font-size:12px;margin:30px 0}.legend{display:flex;gap:20px;flex-wrap:wrap;font-size:13px}
p{overflow-wrap:anywhere}section{min-width:0}@media(max-width:600px){body{padding:24px 14px}h1{font-size:38px}section{padding:16px}.card{min-width:140px}.badge{font-size:12px}}
</style><div class="eyebrow">EXECUTION RESEARCH / 01</div><h1>ExecutionLab</h1>
<p>One trading decision. Four ways to execute it. Measure what happens between an idea and a fill.</p>
<div class="badge" id="badge"></div><div class="controls"><label>Replay<select id="dataset"></select></label><label>Execution method<select id="policy"></select></label></div>
<div class="cards" id="cards"></div><section><h2>Completion through time</h2><p>Cumulative filled quantity as a percentage of the parent order. Unfilled quantity stays unfilled at the deadline.</p><div class="legend" id="legend"></div><svg id="chart" viewBox="0 0 1000 290" role="img" aria-label="Execution completion chart"></svg></section>
<section><h2>Execution scorecard</h2><p>Lower shortfall is better for this replay. Negative means favorable execution or price movement, not a profitable trading strategy.</p><div class="scroll"><table><thead><tr><th>Method</th><th>Filled</th><th>Average price</th><th>Fees</th><th>Unfilled cost</th><th>Shortfall (bps)</th></tr></thead><tbody id="scores"></tbody></table></div></section>
<section><h2>Cost decomposition</h2><p id="decomp"></p><p class="note">Execution cost + fees + terminal opportunity cost = implementation shortfall. Opportunity cost marks unfilled quantity to the final midpoint; it is not a liquidation or a guaranteed fill.</p><button id="download">Download selected fill ledger</button><div class="scroll"><table><thead><tr><th>Time</th><th>Type</th><th>Quantity</th><th>Price</th><th>Fee</th></tr></thead><tbody id="fills"></tbody></table></div><p id="fillnote"></p></section>
<section><h2>Model and data</h2><p id="provenance"></p><p id="config"></p><p>Market orders consume at most one displayed touch per event, with an explicit adverse impact charge. Passive orders use a queue proxy, later aggressor-side prints, post-only rejection, and a fixed cancellation timeout. Event timestamps define quote/print observations, not a full exchange feed.</p><p>Replay cannot reconstruct hidden liquidity, precise exchange priority, cancellations ahead of an order, or the market's response to your trading. Depth is assumed refreshed between events. Synthetic fixtures are engineering experiments, not historical evidence. Imported files are user-supplied and are not independently authenticated.</p></section>
<section><h2>Research beyond the demo</h2><p>Run independent days and symbols, separate development from evaluation, and compare paired cost differences with completion rates. The included stress study varies fees, delay, queue assumptions, and order size. None of those parameters are calibrated to an exchange.</p><p>References: <a href="https://www.cmegroup.com/education/files/TCA-4.pdf">CME transaction cost analysis</a> · <a href="https://www.interactivebrokers.com/docs/general/order-types/algorithmic-orders/ib-algorithms/twap">IBKR TWAP</a> · <a href="https://www.interactivebrokers.com/docs/general/order-types/algorithmic-orders/ib-algorithms/percentage-of-volume">IBKR volume participation</a>. The implementations here are educational models, not replicas of broker algorithms.</p></section><footer>ExecutionLab · Python standard library · reproducible fixtures · source and audit ledgers included</footer>
<script id="payload" type="application/json">PAYLOAD</script><script>
const D=JSON.parse(document.getElementById('payload').textContent), $=id=>document.getElementById(id), colors=['#65dbbd','#81adff','#ffc571','#d29eff'];
const fmt=(x,d=2)=>x===null?'—':Number(x).toLocaleString('en-US',{minimumFractionDigits:d,maximumFractionDigits:d});
for(const x of D.datasets){const o=document.createElement('option');o.textContent=x.name;$('dataset').append(o)}
for(const x of D.datasets[0].results){const o=document.createElement('option');o.textContent=x.summary.policy;$('policy').append(o)}
function selected(){const ds=D.datasets[$('dataset').selectedIndex];return [ds,ds.results[$('policy').selectedIndex]]}
function render(){const [ds,r]=selected(),s=r.summary;
$('badge').textContent=D.label;
$('cards').innerHTML=[['Completion',fmt(s.fill_pct)+'%'],['Implementation shortfall',fmt(s.shortfall_bps)+' bps'],['Average fill',fmt(s.average_price,4)],['Parent order',fmt(s.target,0)+' '+s.side]].map(([k,v])=>'<div class="card"><div class="sub">'+k+'</div><div class="value">'+v+'</div></div>').join('');
$('scores').innerHTML=ds.results.map(r=>{const x=r.summary;return '<tr><td>'+x.policy+'</td><td>'+fmt(x.fill_pct)+'%</td><td>'+fmt(x.average_price,4)+'</td><td>'+fmt(x.fees)+'</td><td>'+fmt(x.opportunity_cost)+'</td><td>'+fmt(x.shortfall_bps)+'</td></tr>'}).join('');
$('decomp').textContent=fmt(s.execution_cost)+' execution cost + '+fmt(s.fees)+' fees + '+fmt(s.opportunity_cost)+' opportunity cost = '+fmt(s.shortfall)+' total cost in quote currency.';
$('fills').innerHTML=r.fills.slice(0,60).map(f=>'<tr><td>'+fmt(f.t,1)+'</td><td>'+f.kind+'</td><td>'+fmt(f.quantity)+'</td><td>'+fmt(f.price,4)+'</td><td>'+fmt(f.fee,4)+'</td></tr>').join('');
$('fillnote').textContent='Showing '+Math.min(60,r.fills.length)+' of '+r.fills.length+' fills. Download contains all fills.';
$('provenance').textContent=ds.provenance;
$('config').textContent='Assumptions: '+JSON.stringify(r.config);
$('legend').innerHTML=ds.results.map((r,i)=>'<span style="color:'+colors[i]+'">'+r.summary.policy+'</span>').join('');
let svg='';for(let p=0;p<=100;p+=25){const y=240-p*2;svg+='<line x1="65" x2="970" y1="'+y+'" y2="'+y+'" stroke="#263850"/><text x="12" y="'+(y+4)+'" fill="#aebdd1" font-size="13">'+p+'%</text>'}
const t0=r.curve[0].t,t1=r.curve[r.curve.length-1].t;
for(let i=0;i<ds.results.length;i++){const x=ds.results[i],pts=x.curve.map(v=>(65+905*(v.t-t0)/(t1-t0))+','+(240-200*v.filled/x.summary.target)).join(' ');svg+='<polyline points="'+pts+'" fill="none" stroke="'+colors[i]+'" stroke-width="2.5"/>'}
svg+='<text x="65" y="275" fill="#aebdd1" font-size="13">Start</text><text x="825" y="275" fill="#aebdd1" font-size="13">'+fmt(t1-t0,0)+' seconds</text>';$('chart').innerHTML=svg;
}
$('dataset').onchange=render;$('policy').onchange=render;
$('download').onclick=()=>{const [ds,r]=selected(),keys=['t','decision_t','quantity','price','fee','kind','mid'],txt=[keys.join(','),...r.fills.map(f=>keys.map(k=>f[k]).join(','))].join('\n'),a=document.createElement('a'),u=URL.createObjectURL(new Blob([txt],{type:'text/csv'}));a.href=u;a.download='execution-fills.csv';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000)};render();
</script></html>'''
    # Avoid closing the payload script with imported strings.
    payload = json.dumps(bundle, allow_nan=False).replace("<", "\\u003c")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(template.replace("PAYLOAD", payload), encoding="utf-8")
