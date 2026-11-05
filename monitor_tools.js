/* Pure execution calculator plus optional browser controls. No order sending. */
(function(root){
function estimate(m, side, quantity, feeBps, sharesPerLot, offline=false){
 if(offline||!m||!m.fresh||!m.quote)throw Error('A fresh eligible quote is required.');
 if(!['buy','sell'].includes(side))throw Error('Choose buy or sell.');
 if(!Number.isFinite(quantity)||quantity<=0||quantity>1e12||!Number.isFinite(feeBps)||feeBps<0||feeBps>1000)throw Error('Enter positive quantity and fees from 0 to 1,000 bps.');
 const q=m.quote,stock=q.size_unit==='reported round lots';
 if(stock&&(!Number.isFinite(sharesPerLot)||sharesPerLot<1||sharesPerLot>1e6||!Number.isInteger(sharesPerLot)))throw Error('Enter the verified shares per reported round lot; no conversion is assumed.');
 const multiplier=stock?sharesPerLot:1,depth=(side==='buy'?q.ask_size:q.bid_size)*multiplier,price=side==='buy'?q.ask:q.bid,covered=Math.min(quantity,depth);
 if(![price,depth,q.mid].every(Number.isFinite)||price<=0||depth<0)throw Error('Invalid quote.');
 const notional=covered*price,fees=notional*feeBps/10000,spreadCost=covered*Math.abs(price-q.mid);
 return {quantity,covered,uncovered:quantity-covered,coveragePct:100*covered/quantity,price,notional,fees,spreadCost,totalCost:fees+spreadCost,cash:side==='buy'?notional+fees:notional-fees};
}
const api={estimate};
if(typeof module!=='undefined'&&module.exports)module.exports=api;
root.ExecutionTools=api;
if(typeof document==='undefined')return;
const $=id=>document.getElementById(id),fmt=(x,d=2)=>Number(x).toLocaleString('en-US',{maximumFractionDigits:d}),esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let state=null,offline=true;
api.markets=markets=>{const search=$('search').value.trim().toUpperCase();let result=markets.filter(m=>m.symbol.includes(search));if($('sort').value==='alerts')result.sort((a,b)=>b.conditions.filter(c=>c.confirmed).length-a.conditions.filter(c=>c.confirmed).length);else if($('sort').value==='symbol')result.sort((a,b)=>a.symbol.localeCompare(b.symbol));return result};
function calculate(){
 try{const m=state?.markets.find(x=>x.symbol===$('calc-market').value);const e=estimate(m,$('calc-side').value,Number($('calc-qty').value),Number($('calc-fees').value),Number($('calc-lot').value),offline);$('calc-result').textContent='Displayed coverage: '+fmt(e.covered,6)+' of '+fmt(e.quantity,6)+' ('+fmt(e.coveragePct)+'%). Uncovered: '+fmt(e.uncovered,6)+'. Touch price: '+fmt(e.price,6)+'. On covered quantity only: spread cost vs midpoint '+fmt(e.spreadCost)+', assumed fees '+fmt(e.fees)+', total '+fmt(e.totalCost)+' in quote currency. No fill is guaranteed.';}
 catch(e){$('calc-result').textContent=e.message;}
}
api.render=(value,disconnected)=>{state=value;offline=disconnected;const symbols=state.markets.map(m=>m.symbol);if(Array.from($('calc-market').options).map(o=>o.value).join()!==symbols.join())$('calc-market').innerHTML=symbols.map(s=>'<option>'+esc(s)+'</option>').join('');$('lot-field').hidden=state.asset!=='stocks';$('qty-label').textContent=state.asset==='stocks'?'Quantity (shares)':'Quantity (base asset)';
 const h=state.health||{};$('health').textContent='Accepted observations: '+Object.values(h).reduce((n,x)=>n+x.accepted,0)+' | rejected: '+Object.values(h).reduce((n,x)=>n+x.rejected,0)+' | quote-processing failures: '+Object.values(h).reduce((n,x)=>n+x.failures,0)+(state.batch_request_ms!=null?' | Last batch request: '+fmt(state.batch_request_ms,0)+' ms':'')+(state.batch_retry_seconds>0?' | Batch retry in '+fmt(state.batch_retry_seconds,0)+'s':'');
 $('retries').textContent=Object.entries(h).filter(([s,x])=>x.retry_seconds>0).map(([s,x])=>s+' retries in '+fmt(x.retry_seconds,0)+'s').join(' | ');
 calculate();};
for(const id of ['calc-market','calc-side','calc-qty','calc-fees','calc-lot'])$(id).addEventListener('input',calculate);
$('alert-csv').onclick=()=>{if(!state)return;const rows=[['time_utc','symbol','condition','explanation','source','mode'],...state.markets.flatMap(m=>m.alerts).sort((a,b)=>b.time-a.time).map(a=>[new Date(a.time*1000).toISOString(),a.symbol,a.kind,a.detail,state.source,state.mode])];const safe=x=>'"'+String(x).replace(/^[=+@-]/,"'$&").replaceAll('"','""')+'"';const blob=new Blob([rows.map(r=>r.map(safe).join(',')).join('\r\n')],{type:'text/csv'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='executionlab-alert-history.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
})(typeof globalThis!=='undefined'?globalThis:this);
