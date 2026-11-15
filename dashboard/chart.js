(function(){
"use strict";
const ns="http://www.w3.org/2000/svg";
const number=v=>v!==null&&v!==undefined&&v!==""&&typeof v!=="boolean"&&Number.isFinite(Number(v))?Number(v):null;
function parse(rows){
 if(!Array.isArray(rows))return[];
 return rows.filter(r=>Array.isArray(r)&&r.length>=7).map(r=>({time:number(r[0]),open:number(r[1]),high:number(r[2]),low:number(r[3]),close:number(r[4]),volume:number(r[5]),closeTime:number(r[6])}))
  .filter(c=>Object.values(c).every(Number.isFinite)&&Number.isInteger(c.time)&&Number.isInteger(c.closeTime)&&c.time>=0&&c.closeTime>=c.time&&c.open>0&&c.high>0&&c.low>0&&c.close>0&&c.volume>=0&&c.high>=Math.max(c.open,c.close,c.low)&&c.low<=Math.min(c.open,c.close,c.high))
  .sort((a,b)=>a.time-b.time);
}
function aggregate3h(rows){
 const map=new Map();rows.forEach(c=>{const start=Math.floor(c.time/10800000)*10800000;if(!map.has(start))map.set(start,[]);map.get(start).push(c);});
 return [...map.entries()].sort((a,b)=>a[0]-b[0]).flatMap(([start,a])=>{a.sort((x,y)=>x.time-y.time);if(a.length!==3||a[0].time!==start||a[1].time!==start+3600000||a[2].time!==start+7200000)return[];return[{time:start,open:a[0].open,high:Math.max(...a.map(x=>x.high)),low:Math.min(...a.map(x=>x.low)),close:a[2].close,volume:a.reduce((s,x)=>s+x.volume,0),closeTime:a[2].closeTime}];});
}
function ema(a,n){if(a.length<n)return null;const k=2/(n+1);let v=a.slice(0,n).reduce((s,x)=>s+x,0)/n;for(let i=n;i<a.length;i++)v=a[i]*k+v*(1-k);return v;}
function sma(a,n){return a.length<n?null:a.slice(-n).reduce((s,x)=>s+x,0)/n;}
function rsi(a,n=14){if(a.length<=n)return null;let g=0,l=0;for(let i=1;i<=n;i++){const d=a[i]-a[i-1];g+=Math.max(d,0);l+=Math.max(-d,0);}g/=n;l/=n;for(let i=n+1;i<a.length;i++){const d=a[i]-a[i-1];g=(g*(n-1)+Math.max(d,0))/n;l=(l*(n-1)+Math.max(-d,0))/n;}if(g===0&&l===0)return 50;if(l===0)return 100;if(g===0)return 0;return 100-100/(1+g/l);}
function atrWilder(c,n=14){
 const tr=c.slice(1).map((x,i)=>Math.max(x.high-x.low,Math.abs(x.high-c[i].close),Math.abs(x.low-c[i].close)));
 if(tr.length<n)return null;
 let value=tr.slice(0,n).reduce((s,x)=>s+x,0)/n;
 for(let i=n;i<tr.length;i++)value=(value*(n-1)+tr[i])/n;
 return value;
}
function macd(a){
 const fast=ema(a,12),slow=ema(a,26);if(fast===null||slow===null)return null;
 const line=fast-slow;return{line,signal:null,histogram:null,method:"MACD line from EMA12 minus EMA26; signal and histogram unavailable without a full aligned MACD series"};
}
function indicators(c){
 if(!Array.isArray(c)||!c.length)return{candle_count:0,method:"Insufficient candle data"};
 const close=c.map(x=>x.close),last=c[c.length-1],m=sma(close,20),sd=m===null?null:Math.sqrt(close.slice(-20).reduce((s,x)=>s+(x-m)**2,0)/20);
 const vol=c.reduce((s,x)=>s+x.volume,0),vwap=vol?c.reduce((s,x)=>s+((x.high+x.low+x.close)/3)*x.volume,0)/vol:null;
 return{last_close:last.close,ema_20:ema(close,20),ema_50:ema(close,50),ema_200:ema(close,200),sma_20:m,rsi_14_wilder:rsi(close),macd_12_26:macd(close),bollinger_20_2:m!==null&&sd!==null?{upper:m+2*sd,middle:m,lower:m-2*sd}:null,atr_14_wilder:atrWilder(c),vwap,candle_count:c.length,method:"Client-side descriptive OHLCV calculations; not a validated trading signal"};
}
function intervalFor(tf){return tf==="3h"?"1h":({"1D":"1d","3D":"3d","1W":"1w"}[tf]||tf);}
function routeFor(market){return market==="SPOT"?"/api/v1/markets/spot/klines/":market==="USD_M"?"/api/v1/markets/futures/usdm/klines/":market==="COIN_M"?"/api/v1/markets/futures/coinm/klines/":null;}
function emaSeries(values,n){
 const out=Array(values.length).fill(null);if(values.length<n)return out;
 const k=2/(n+1);let value=values.slice(0,n).reduce((s,x)=>s+x,0)/n;out[n-1]=value;
 for(let i=n;i<values.length;i++){value=values[i]*k+value*(1-k);out[i]=value;}return out;
}
function rsiSeries(values,n=14){
 const out=Array(values.length).fill(null);if(values.length<=n)return out;
 let gains=0,losses=0;for(let i=1;i<=n;i++){const d=values[i]-values[i-1];gains+=Math.max(d,0);losses+=Math.max(-d,0);}
 gains/=n;losses/=n;out[n]=gains===0&&losses===0?50:losses===0?100:gains===0?0:100-100/(1+gains/losses);
 for(let i=n+1;i<values.length;i++){const d=values[i]-values[i-1];gains=(gains*(n-1)+Math.max(d,0))/n;losses=(losses*(n-1)+Math.max(-d,0))/n;out[i]=gains===0&&losses===0?50:losses===0?100:gains===0?0:100-100/(1+gains/losses);}
 return out;
}
function atrSeries(c,n=14){
 const out=Array(c.length).fill(null),tr=c.slice(1).map((x,i)=>Math.max(x.high-x.low,Math.abs(x.high-c[i].close),Math.abs(x.low-c[i].close)));
 if(tr.length<n)return out;let value=tr.slice(0,n).reduce((s,x)=>s+x,0)/n;out[n]=value;
 for(let i=n+1;i<c.length;i++){value=(value*(n-1)+tr[i-1])/n;out[i]=value;}return out;
}
function macdComponents(values){
 const fast=emaSeries(values,12),slow=emaSeries(values,26);
 const line=values.map((_,i)=>fast[i]===null||slow[i]===null?null:fast[i]-slow[i]);
 const first=line.findIndex(Number.isFinite),compact=first<0?[]:line.slice(first);
 const signalCompact=emaSeries(compact,9),signal=Array(values.length).fill(null);
 signalCompact.forEach((v,i)=>{signal[first+i]=v;});
 const histogram=line.map((v,i)=>v===null||signal[i]===null?null:v-signal[i]);
 return{line,signal,histogram};
}
function macdSeries(values){return macdComponents(values).line;}
function drawLinePanel(title,values,{min=null,max=null,zero=false}={}){
 const valid=values.filter(Number.isFinite);const panel=document.createElement("section");panel.className="indicator-pane";
 const heading=document.createElement("div");heading.className="indicator-pane-heading";const label=document.createElement("strong");label.textContent=title;const latest=document.createElement("span");latest.textContent=valid.length?new Intl.NumberFormat(undefined,{maximumFractionDigits:4}).format(valid[valid.length-1]):"Insufficient history";heading.append(label,latest);panel.append(heading);
 if(!valid.length){const empty=document.createElement("div");empty.className="indicator-pane-empty";empty.textContent="Insufficient candle history for this indicator.";panel.append(empty);return panel;}
 const lo=min===null?Math.min(...valid):min,hi=max===null?Math.max(...valid):max,span=hi-lo||1,w=1000,h=104,pad=8;
 const svg=document.createElementNS(ns,"svg");svg.setAttribute("viewBox","0 0 "+w+" "+h);svg.setAttribute("role","img");svg.setAttribute("aria-label",title+" indicator pane");
 const add=(tag,attrs)=>{const e=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,String(v)));svg.append(e);};
 if(zero&&lo<0&&hi>0){const zy=pad+(hi/span)* (h-pad*2);add("line",{x1:0,y1:zy,x2:w,y2:zy,stroke:"#40516b","stroke-dasharray":"4 4"});}
 let segment=[];const flush=()=>{if(segment.length>1)add("polyline",{points:segment.join(" "),fill:"none",stroke:"#63a7ff","stroke-width":2,"stroke-linejoin":"round","stroke-linecap":"round"});segment=[];};
 const step=w/Math.max(1,values.length-1);
 values.forEach((v,i)=>{if(!Number.isFinite(v)){flush();return;}const x=i*step,y=h-pad-(v-lo)/span*(h-pad*2);segment.push(x+","+y);});flush();
 panel.append(svg);return panel;
}
function render(c){
 const host=document.getElementById("chart-placeholder");host.replaceChildren();if(!c.length){host.textContent="No complete candle data returned.";return;}
 const a=c.slice(-120),w=1000,h=330,top=18,bottom=238,volTop=260,volBottom=310,hi=Math.max(...a.map(x=>x.high)),lo=Math.min(...a.map(x=>x.low)),span=hi-lo||1,maxVol=Math.max(...a.map(x=>x.volume),1);
 const svg=document.createElementNS(ns,"svg");svg.setAttribute("viewBox","0 0 "+w+" "+h);svg.setAttribute("role","img");svg.setAttribute("aria-label","Candlestick and volume chart from verified backend OHLCV data");svg.style.width="100%";
 const add=(tag,attrs)=>{const e=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,String(v)));svg.append(e);};
 for(let i=0;i<5;i++){const y=top+i*(bottom-top)/4;add("line",{x1:20,y1:y,x2:980,y2:y,stroke:"#243650","stroke-width":1});}
 const step=960/a.length,cw=Math.max(2,step*.58),y=v=>bottom-(v-lo)/span*(bottom-top);
 a.forEach((x,i)=>{const cx=20+i*step+step/2,color=x.close>=x.open?"#48c99a":"#ef737e";add("line",{x1:cx,y1:y(x.high),x2:cx,y2:y(x.low),stroke:color,"stroke-width":1.2});add("rect",{x:cx-cw/2,y:Math.min(y(x.open),y(x.close)),width:cw,height:Math.max(1,Math.abs(y(x.open)-y(x.close))),fill:color});const vh=x.volume/maxVol*(volBottom-volTop);add("rect",{x:cx-cw/2,y:volBottom-vh,width:cw,height:vh,fill:color,opacity:.4});});
 const closes=c.map(x=>x.close),ema20=emaSeries(closes,20).slice(-a.length),emaPoints=ema20.map((v,i)=>v===null?null:(20+i*step+step/2)+","+y(v)).filter(Boolean);
 if(emaPoints.length>1)add("polyline",{points:emaPoints.join(" "),fill:"none",stroke:"#f4c46a","stroke-width":2,"stroke-linejoin":"round"});
 const caption=document.createElement("div");caption.className="chart-caption";caption.textContent=a.length+" candles · actual backend OHLCV · EMA20 overlay · "+(c[0].time?new Date(c[0].time).toISOString():"");host.append(svg,caption);
 const valuesClose=c.map(x=>x.close);
 host.append(drawLinePanel("RSI (14) · Wilder",rsiSeries(valuesClose),{min:0,max:100}));
 const macd=macdComponents(valuesClose);host.append(drawLinePanel("MACD line · EMA12 − EMA26",macd.line,{zero:true}));host.append(drawLinePanel("MACD signal · EMA9 of MACD",macd.signal,{zero:true}));host.append(drawLinePanel("MACD histogram · line − signal",macd.histogram,{zero:true}));
 host.append(drawLinePanel("ATR (14) · Wilder",atrSeries(c)));
}
async function load(api,market,symbol,timeframe){
 const tf=timeframe,interval=intervalFor(tf),route=routeFor(market);if(!route)throw new Error("Unsupported market type: "+market);
 const response=await api(route+encodeURIComponent(symbol)+"?interval="+encodeURIComponent(interval)+"&limit=1000");
 let candles=parse(response?.klines);if(tf==="3h")candles=aggregate3h(candles);if(!candles.length)throw new Error("Backend returned no valid complete candle rows.");
 const values=indicators(candles);render(candles);
 const result={status:response.status||"RESPONSE_RECEIVED",market,symbol,requested_timeframe:tf,source_interval:interval,aggregation:tf==="3h"?"UTC-aligned groups of exactly three consecutive 1h candles; incomplete groups discarded":"Exchange-native interval",source:response.source||"Configured backend",candle_count:candles.length,latest_candle_time_utc:new Date(candles[candles.length-1].time).toISOString(),indicators:values,warning:"Descriptive frontend calculations only; not a validated trade signal."};
 const summary=Object.entries(values).filter(([k,v])=>k!=="method"&&v!==null&&typeof v!=="object").map(([k,v])=>k.replaceAll("_"," ")+": "+(typeof v==="number"?new Intl.NumberFormat(undefined,{maximumFractionDigits:4}).format(v):String(v))).join(" · ");
 document.getElementById("technical-summary").textContent=summary||"Insufficient history for indicator calculations.";
 document.getElementById("analysis-output").textContent=JSON.stringify(result,null,2);
 document.getElementById("chart-state").textContent=tf==="3h"?"3h aggregated from complete 1h candles":candles.length+" candles loaded";
 return result;
}
window.DashboardCharts={load,parse,aggregate3h,indicators,intervalFor,routeFor,emaSeries,rsiSeries,atrSeries,macdSeries,macdComponents};
})();