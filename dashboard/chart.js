(function(){
"use strict";
const ns="http://www.w3.org/2000/svg";
let activeLoadSequence=0;
const number=v=>{if(typeof v==="number")return Number.isFinite(v)?v:null;if(typeof v!=="string")return null;const text=v.trim();if(!/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$/.test(text))return null;const parsed=Number(text);return Number.isFinite(parsed)?parsed:null;};
function parse(rows){
 if(!Array.isArray(rows))return[];
 const parsed=rows.filter(r=>Array.isArray(r)&&r.length>=7).map(r=>({time:number(r[0]),open:number(r[1]),high:number(r[2]),low:number(r[3]),close:number(r[4]),volume:number(r[5]),closeTime:number(r[6])}))
  .filter(c=>Object.values(c).every(Number.isFinite)&&Number.isSafeInteger(c.time)&&Number.isSafeInteger(c.closeTime)&&c.time>=0&&c.closeTime>=c.time&&c.time<=8640000000000000&&c.closeTime<=8640000000000000&&c.open>0&&c.high>0&&c.low>0&&c.close>0&&c.volume>=0&&c.high>=Math.max(c.open,c.close,c.low)&&c.low<=Math.min(c.open,c.close,c.high))
  .sort((a,b)=>a.time-b.time);
 const counts=new Map();for(const candle of parsed)counts.set(candle.time,(counts.get(candle.time)||0)+1);
 return parsed.filter(candle=>counts.get(candle.time)===1);
}
function aggregate3h(rows){
 if(!Array.isArray(rows))return[];
 const valid=rows.filter(c=>c&&typeof c==="object"&&[c.time,c.open,c.high,c.low,c.close,c.volume,c.closeTime].every(Number.isFinite)&&Number.isSafeInteger(c.time)&&Number.isSafeInteger(c.closeTime)&&c.time>=0&&c.closeTime>=c.time&&c.time<=8640000000000000&&c.closeTime<=8640000000000000&&c.open>0&&c.high>0&&c.low>0&&c.close>0&&c.volume>=0&&c.high>=Math.max(c.open,c.close,c.low)&&c.low<=Math.min(c.open,c.close,c.high));
 const map=new Map();valid.forEach(c=>{const start=Math.floor(c.time/10800000)*10800000;if(!map.has(start))map.set(start,[]);map.get(start).push(c);});
 return [...map.entries()].sort((a,b)=>a[0]-b[0]).flatMap(([start,a])=>{a.sort((x,y)=>x.time-y.time);if(a.length!==3||a[0].time!==start||a[1].time!==start+3600000||a[2].time!==start+7200000||a.some(x=>x.closeTime!==x.time+3599999))return[];const volume=a.reduce((sum,x)=>sum+x.volume,0);if(!Number.isFinite(volume))return[];return[{time:start,open:a[0].open,high:Math.max(...a.map(x=>x.high)),low:Math.min(...a.map(x=>x.low)),close:a[2].close,volume,closeTime:a[2].closeTime}];});
}
function finiteMean(values){
 if(!values.length||!values.every(Number.isFinite))return null;
 let mean=values[0];
 for(let i=1;i<values.length;i++){const weight=1/(i+1);mean=mean*(1-weight)+values[i]*weight;}
 return Number.isFinite(mean)?mean:null;
}
function ema(a,n){if(a.length<n||!a.every(Number.isFinite))return null;const k=2/(n+1);let v=finiteMean(a.slice(0,n));if(v===null)return null;for(let i=n;i<a.length;i++){v=a[i]*k+v*(1-k);if(!Number.isFinite(v))return null;}return v;}
function sma(a,n){return a.length<n?null:finiteMean(a.slice(-n));}
function scaledDeviation(values,mean){
 if(!values.length||mean===null||!Number.isFinite(mean))return null;
 const scale=Math.max(...values.map(Math.abs));if(!Number.isFinite(scale))return null;if(scale===0)return 0;
 const normalizedMean=mean/scale;
 const variance=values.reduce((sum,value)=>{const delta=value/scale-normalizedMean;return sum+delta*delta;},0)/values.length;
 const deviation=scale*Math.sqrt(variance);
 return Number.isFinite(deviation)?deviation:null;
}
function rsi(a,n=14){
 if(a.length<=n||!a.every(Number.isFinite))return null;
 const gains=[],losses=[];for(let i=1;i<=n;i++){const d=a[i]-a[i-1];if(!Number.isFinite(d))return null;gains.push(Math.max(d,0));losses.push(Math.max(-d,0));}
 let g=finiteMean(gains),l=finiteMean(losses);if(g===null||l===null)return null;
 for(let i=n+1;i<a.length;i++){const d=a[i]-a[i-1];if(!Number.isFinite(d))return null;g=(g*(n-1)+Math.max(d,0))/n;l=(l*(n-1)+Math.max(-d,0))/n;}
 if(!Number.isFinite(g)||!Number.isFinite(l))return null;
 if(g===0&&l===0)return 50;if(l===0)return 100;if(g===0)return 0;return 100-100/(1+g/l);
}
function atrWilder(c,n=14){
 const tr=c.slice(1).map((x,i)=>Math.max(x.high-x.low,Math.abs(x.high-c[i].close),Math.abs(x.low-c[i].close)));
 if(tr.length<n||!tr.every(Number.isFinite))return null;
 let value=finiteMean(tr.slice(0,n));if(value===null)return null;
 for(let i=n;i<tr.length;i++)value=(value*(n-1)+tr[i])/n;
 return Number.isFinite(value)?value:null;
}
function macd(a){
 if(a.length<34)return null;
 const series=macdComponents(a),i=a.length-1;
 return{line:series.line[i],signal:series.signal[i],histogram:series.histogram[i],method:"EMA12 minus EMA26; signal is EMA9 of the aligned MACD line"};
}
function indicators(c){
 if(!Array.isArray(c)||!c.length)return{candle_count:0,method:"Insufficient candle data"};
 const close=c.map(x=>x.close),last=c[c.length-1],m=sma(close,20),sd=m===null?null:scaledDeviation(close.slice(-20),m),bandUpper=m!==null&&sd!==null?m+2*sd:null,bandLower=m!==null&&sd!==null?m-2*sd:null;
 const maxVolume=Math.max(...c.map(x=>x.volume)),vwap=maxVolume>0?c.reduce((state,x)=>{const weight=x.volume/maxVolume;if(!weight)return state;const price=x.high/3+x.low/3+x.close/3,total=state.weight+weight;return{weight:total,value:state.weight?state.value*(state.weight/total)+price*(weight/total):price};},{weight:0,value:0}).value:null;
 return{last_close:last.close,ema_20:ema(close,20),ema_50:ema(close,50),ema_200:ema(close,200),sma_20:m,rsi_14_wilder:rsi(close),macd_12_26:macd(close),bollinger_20_2:Number.isFinite(bandUpper)&&Number.isFinite(bandLower)?{upper:bandUpper,middle:m,lower:bandLower}:null,atr_14_wilder:atrWilder(c),vwap,candle_count:c.length,method:"Client-side descriptive OHLCV calculations; not a validated trading signal"};
}
function intervalFor(tf){return tf==="3h"?"1h":({"1D":"1d","3D":"3d","1W":"1w"}[tf]||tf);}
function routeFor(market){return market==="SPOT"?"/api/v1/markets/spot/klines/":market==="USD_M"?"/api/v1/markets/futures/usdm/klines/":market==="COIN_M"?"/api/v1/markets/futures/coinm/klines/":null;}
function emaSeries(values,n){
 if(!Array.isArray(values))return[];const out=Array(values.length).fill(null);if(!Number.isSafeInteger(n)||n<1||values.length<n)return out;
 const k=2/(n+1);let runLength=0,value=null;
 for(let i=0;i<values.length;i++){
  if(!Number.isFinite(values[i])){runLength=0;value=null;continue;}
  runLength++;
  if(runLength<n)continue;
  if(runLength===n){value=finiteMean(values.slice(i-n+1,i+1));if(value!==null)out[i]=value;continue;}
  value=values[i]*k+value*(1-k);if(!Number.isFinite(value)){runLength=0;value=null;continue;}out[i]=value;
 }
 return out;
}
function rsiSeries(values,n=14){
 if(!Array.isArray(values))return[];const out=Array(values.length).fill(null);if(!Number.isSafeInteger(n)||n<1||values.length<=n)return out;
 let gains=[],losses=[],averageGain=null,averageLoss=null;
 const value=()=>averageGain===0&&averageLoss===0?50:averageLoss===0?100:averageGain===0?0:100-100/(1+averageGain/averageLoss);
 for(let i=1;i<values.length;i++){
  const delta=values[i]-values[i-1];
  if(!Number.isFinite(delta)){gains=[];losses=[];averageGain=null;averageLoss=null;continue;}
  const gain=Math.max(delta,0),loss=Math.max(-delta,0);
  if(averageGain===null||averageLoss===null){
   gains.push(gain);losses.push(loss);
   if(gains.length===n){averageGain=finiteMean(gains);averageLoss=finiteMean(losses);gains=[];losses=[];if(averageGain!==null&&averageLoss!==null)out[i]=value();else{averageGain=null;averageLoss=null;}}
   continue;
  }
  averageGain=(averageGain*(n-1)+gain)/n;averageLoss=(averageLoss*(n-1)+loss)/n;
  if(!Number.isFinite(averageGain)||!Number.isFinite(averageLoss)){gains=[];losses=[];averageGain=null;averageLoss=null;continue;}
  out[i]=value();
 }
 return out;
}
function atrSeries(c,n=14){
 if(!Array.isArray(c))return[];const out=Array(c.length).fill(null);if(!Number.isSafeInteger(n)||n<1)return out;
 let seed=[],value=null;
 for(let i=1;i<c.length;i++){
  const cur=c[i],prev=c[i-1];
  const tr=cur&&prev&&[cur.high,cur.low,prev.close].every(Number.isFinite)?Math.max(cur.high-cur.low,Math.abs(cur.high-prev.close),Math.abs(cur.low-prev.close)):null;
  if(!Number.isFinite(tr)){seed=[];value=null;continue;}
  if(value===null){seed.push(tr);if(seed.length===n){value=finiteMean(seed);seed=[];if(value!==null)out[i]=value;else value=null;}continue;}
  value=(value*(n-1)+tr)/n;if(!Number.isFinite(value)){seed=[];value=null;continue;}out[i]=value;
 }
 return out;
}
function macdComponents(values){
 const fast=emaSeries(values,12),slow=emaSeries(values,26);
 const line=values.map((_,i)=>{if(fast[i]===null||slow[i]===null)return null;const value=fast[i]-slow[i];return Number.isFinite(value)?value:null;});
 const first=line.findIndex(Number.isFinite),compact=first<0?[]:line.slice(first);
 const signalCompact=emaSeries(compact,9),signal=Array(values.length).fill(null);
 signalCompact.forEach((v,i)=>{signal[first+i]=Number.isFinite(v)?v:null;});
 const histogram=line.map((v,i)=>{if(!Number.isFinite(v)||!Number.isFinite(signal[i]))return null;const value=v-signal[i];return Number.isFinite(value)?value:null;});
 return{line,signal,histogram};
}
function macdSeries(values){return macdComponents(values).line;}
function bollingerSeries(values,n=20,multiplier=2){
 const middle=Array(values.length).fill(null),upper=Array(values.length).fill(null),lower=Array(values.length).fill(null);
 if(!Number.isSafeInteger(n)||n<1||!Number.isFinite(multiplier)||multiplier<0)return{upper,middle,lower};
 for(let i=n-1;i<values.length;i++){const window=values.slice(i-n+1,i+1),mean=finiteMean(window),sd=scaledDeviation(window,mean);if(mean===null||sd===null)continue;const upperValue=mean+multiplier*sd,lowerValue=mean-multiplier*sd;if(!Number.isFinite(upperValue)||!Number.isFinite(lowerValue))continue;middle[i]=mean;upper[i]=upperValue;lower[i]=lowerValue;}
 return{upper,middle,lower};
}
function adxSeries(c,n=14){
 if(!Array.isArray(c))return[];const out=Array(c.length).fill(null);if(!Number.isSafeInteger(n)||n<1||c.length<2*n)return out;
 const tr=[],plus=[],minus=[];
 for(let i=1;i<c.length;i++){const cur=c[i],prev=c[i-1],up=cur.high-prev.high,down=prev.low-cur.low;
  tr.push(Math.max(cur.high-cur.low,Math.abs(cur.high-prev.close),Math.abs(cur.low-prev.close)));
  plus.push(up>down&&up>0?up:0);minus.push(down>up&&down>0?down:0);
 }
 let scale=1;for(let i=0;i<tr.length;i++){scale=Math.max(scale,tr[i],plus[i],minus[i]);}
 if(!Number.isFinite(scale))return out;
 for(let i=0;i<tr.length;i++){tr[i]/=scale;plus[i]/=scale;minus[i]/=scale;}
 let trSm=tr.slice(0,n).reduce((s,x)=>s+x,0),pSm=plus.slice(0,n).reduce((s,x)=>s+x,0),mSm=minus.slice(0,n).reduce((s,x)=>s+x,0);
 const dx=[];
 for(let i=n-1;i<tr.length;i++){
  if(i>=n){trSm=trSm-trSm/n+tr[i];pSm=pSm-pSm/n+plus[i];mSm=mSm-mSm/n+minus[i];}
  const pdi=trSm?pSm/trSm*100:0,mdi=trSm?mSm/trSm*100:0,den=pdi+mdi;
  dx.push(den?Math.abs(pdi-mdi)/den*100:0);
  if(dx.length===n){let value=dx.reduce((s,x)=>s+x,0)/n;out[i+1]=value;
   for(let j=i+1;j<tr.length;j++){trSm=trSm-trSm/n+tr[j];pSm=pSm-pSm/n+plus[j];mSm=mSm-mSm/n+minus[j];const pp=trSm?pSm/trSm*100:0,mm=trSm?mSm/trSm*100:0,d=pp+mm?Math.abs(pp-mm)/(pp+mm)*100:0;value=(value*(n-1)+d)/n;out[j+1]=value;}break;
  }
 }
 return out;
}
function stochRsiSeries(values,rsiPeriod=14,stochPeriod=14,smoothK=3,smoothD=3){
 const length=Array.isArray(values)?values.length:0,raw=Array(length).fill(null),k=Array(length).fill(null),d=Array(length).fill(null);
 if(!Array.isArray(values)||![rsiPeriod,stochPeriod,smoothK,smoothD].every(Number.isSafeInteger)||rsiPeriod<1||stochPeriod<1||smoothK<1||smoothD<1||!Number.isSafeInteger(rsiPeriod+stochPeriod)||!Number.isSafeInteger(smoothK+smoothD))return{k,d};
 const rsi=rsiSeries(values,rsiPeriod);
 for(let i=0;i<rsi.length;i++){if(i<rsiPeriod+stochPeriod-1||!Number.isFinite(rsi[i]))continue;const w=rsi.slice(i-stochPeriod+1,i+1);if(!w.every(Number.isFinite))continue;const lo=Math.min(...w),hi=Math.max(...w);raw[i]=hi===lo?50:(rsi[i]-lo)/(hi-lo)*100;}
 for(let i=0;i<raw.length;i++){if(i>=smoothK-1&&raw.slice(i-smoothK+1,i+1).every(Number.isFinite))k[i]=raw.slice(i-smoothK+1,i+1).reduce((s,x)=>s+x,0)/smoothK;
  if(i>=smoothK+smoothD-2&&k.slice(i-smoothD+1,i+1).every(Number.isFinite))d[i]=k.slice(i-smoothD+1,i+1).reduce((s,x)=>s+x,0)/smoothD;}
 return{k,d};
}
function drawLinePanel(title,values,{min=null,max=null,zero=false}={}){
 const valid=values.filter(Number.isFinite);const panel=document.createElement("section");panel.className="indicator-pane";
 const heading=document.createElement("div");heading.className="indicator-pane-heading";const label=document.createElement("strong");label.textContent=title;const latest=document.createElement("span");latest.textContent=valid.length?new Intl.NumberFormat(undefined,{maximumFractionDigits:4}).format(valid[valid.length-1]):"Insufficient history";heading.append(label,latest);panel.append(heading);
 if(!valid.length){const empty=document.createElement("div");empty.className="indicator-pane-empty";empty.textContent="Insufficient candle history for this indicator.";panel.append(empty);return panel;}
 let lo=min===null?valid[0]:min,hi=max===null?valid[0]:max;if(min===null||max===null){for(const value of valid){if(min===null&&value<lo)lo=value;if(max===null&&value>hi)hi=value;}}const scale=Math.max(Math.abs(lo),Math.abs(hi),1),scaledLo=lo/scale,scaledSpan=hi/scale-scaledLo||1,w=1000,h=104,pad=8;
 const svg=document.createElementNS(ns,"svg");svg.setAttribute("viewBox","0 0 "+w+" "+h);svg.setAttribute("role","img");svg.setAttribute("aria-label",title+" indicator pane");
 const add=(tag,attrs)=>{const e=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,String(v)));svg.append(e);};
 if(zero&&lo<0&&hi>0){const zy=h-pad-(0/scale-scaledLo)/scaledSpan*(h-pad*2);add("line",{x1:0,y1:zy,x2:w,y2:zy,stroke:"#40516b","stroke-dasharray":"4 4"});}
 let segment=[];const flush=()=>{if(segment.length>1)add("polyline",{points:segment.join(" "),fill:"none",stroke:"#63a7ff","stroke-width":2,"stroke-linejoin":"round","stroke-linecap":"round"});segment=[];};
 const step=w/Math.max(1,values.length-1);
 values.forEach((v,i)=>{if(!Number.isFinite(v)){flush();return;}const x=i*step,y=h-pad-(v/scale-scaledLo)/scaledSpan*(h-pad*2);if(Number.isFinite(x)&&Number.isFinite(y))segment.push(x+","+y);else flush();});flush();
 panel.append(svg);return panel;
}
function render(c){
 const host=document.getElementById("chart-placeholder");host.replaceChildren();if(!c.length){host.textContent="No complete candle data returned.";return;}
 const a=c.slice(-120),w=1000,h=330,top=18,bottom=238,volTop=260,volBottom=310,closeAll=c.map(x=>x.close),bands=bollingerSeries(closeAll),bandValues=[...bands.upper.slice(-a.length),...bands.lower.slice(-a.length)].filter(Number.isFinite),hi=Math.max(...a.map(x=>x.high),...bandValues),lo=Math.min(...a.map(x=>x.low),...bandValues),priceScale=Math.max(Math.abs(hi),Math.abs(lo),1),scaledLo=lo/priceScale,scaledSpan=hi/priceScale-scaledLo||1,maxVol=Math.max(...a.map(x=>x.volume),1);
 const svg=document.createElementNS(ns,"svg");svg.setAttribute("viewBox","0 0 "+w+" "+h);svg.setAttribute("role","img");svg.setAttribute("aria-label","Candlestick and volume chart from verified backend OHLCV data");svg.style.width="100%";
 const add=(tag,attrs)=>{const e=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,String(v)));svg.append(e);};
 for(let i=0;i<5;i++){const y=top+i*(bottom-top)/4;add("line",{x1:20,y1:y,x2:980,y2:y,stroke:"#243650","stroke-width":1});}
 const step=960/a.length,cw=Math.max(2,step*.58),y=v=>bottom-(v/priceScale-scaledLo)/scaledSpan*(bottom-top);
 a.forEach((x,i)=>{const cx=20+i*step+step/2,color=x.close>=x.open?"#48c99a":"#ef737e";add("line",{x1:cx,y1:y(x.high),x2:cx,y2:y(x.low),stroke:color,"stroke-width":1.2});add("rect",{x:cx-cw/2,y:Math.min(y(x.open),y(x.close)),width:cw,height:Math.max(1,Math.abs(y(x.open)-y(x.close))),fill:color});const vh=x.volume/maxVol*(volBottom-volTop);add("rect",{x:cx-cw/2,y:volBottom-vh,width:cw,height:vh,fill:color,opacity:.4});});
 const closes=closeAll,ema20=emaSeries(closes,20),offset=c.length-a.length;
 const linePoints=series=>{const segments=[];let segment=[];series.slice(offset).forEach((v,i)=>{if(!Number.isFinite(v)){if(segment.length>1)segments.push(segment);segment=[];return;}const point=(20+i*step+step/2)+","+y(v);if(point.includes("NaN")||point.includes("Infinity")){if(segment.length>1)segments.push(segment);segment=[];return;}segment.push(point);});if(segment.length>1)segments.push(segment);return segments;};
 for(const [series,color,width] of [[bands.upper,"#8b9db8",1.2],[bands.middle,"#8b9db8",1],[bands.lower,"#8b9db8",1],[ema20,"#f4c46a",2]]){for(const pts of linePoints(series))add("polyline",{points:pts.join(" "),fill:"none",stroke:color,"stroke-width":width,"stroke-linejoin":"round","stroke-dasharray":color==="#8b9db8"?"5 4":"none"});}
 const caption=document.createElement("div");caption.className="chart-caption";caption.textContent=a.length+" candles · actual backend OHLCV · EMA20 + Bollinger(20,2) overlays · "+(c[0].time?new Date(c[0].time).toISOString():"");host.append(svg,caption);
 const valuesClose=c.map(x=>x.close);
 host.append(drawLinePanel("RSI (14) · Wilder",rsiSeries(valuesClose),{min:0,max:100}));
 const stoch=stochRsiSeries(valuesClose);host.append(drawLinePanel("Stochastic RSI · %K",stoch.k,{min:0,max:100}));host.append(drawLinePanel("Stochastic RSI · %D",stoch.d,{min:0,max:100}));
 host.append(drawLinePanel("ADX (14) · Wilder",adxSeries(c),{min:0,max:100}));
 const macd=macdComponents(valuesClose);host.append(drawLinePanel("MACD line · EMA12 − EMA26",macd.line,{zero:true}));host.append(drawLinePanel("MACD signal · EMA9 of MACD",macd.signal,{zero:true}));host.append(drawLinePanel("MACD histogram · line − signal",macd.histogram,{zero:true}));
 host.append(drawLinePanel("ATR (14) · Wilder",atrSeries(c)));
}
function invalidate(){activeLoadSequence++;}
async function load(api,market,symbol,timeframe){
 const tf=timeframe,route=routeFor(market);
 if(!route)throw new Error("Unsupported market type: "+market);
 const supportedTimeframes=["1m","3m","5m","15m","30m","1h","2h","3h","4h","6h","8h","12h","1D","3D","1W","1M"];
 if(!supportedTimeframes.includes(tf))throw new Error("Unsupported chart timeframe: "+tf);
 if(typeof symbol!=="string"||!symbol.trim())throw new Error("Enter a valid trading symbol.");
 const interval=intervalFor(tf),requestSequence=++activeLoadSequence;
 let response;try{response=await api(route+encodeURIComponent(symbol)+"?interval="+encodeURIComponent(interval)+"&limit=1000");}catch(error){if(requestSequence!==activeLoadSequence)return{status:"SUPERSEDED",market,symbol,requested_timeframe:tf};throw error;}
 if(requestSequence!==activeLoadSequence)return{status:"SUPERSEDED",market,symbol,requested_timeframe:tf};
 if(response===null||typeof response!=="object"||Array.isArray(response))throw new Error("Candle endpoint returned an invalid response shape. Expected a JSON object; previous chart was preserved.");
 if(!Array.isArray(response.klines))throw new Error("Candle endpoint did not provide a klines array; previous chart was preserved.");
 let candles=parse(response.klines);if(tf==="3h")candles=aggregate3h(candles);if(!candles.length)throw new Error("Backend returned no valid complete candle rows; previous chart was preserved.");
 const values=indicators(candles);render(candles);
 const result={status:response.status||"RESPONSE_RECEIVED",market,symbol,requested_timeframe:tf,source_interval:interval,aggregation:tf==="3h"?"UTC-aligned groups of exactly three consecutive 1h candles; incomplete groups discarded":"Exchange-native interval",source:response.source||"Configured backend",candle_count:candles.length,latest_candle_time_utc:new Date(candles[candles.length-1].time).toISOString(),indicators:values,warning:"Descriptive frontend calculations only; not a validated trade signal."};
 const summary=Object.entries(values).filter(([k,v])=>k!=="method"&&v!==null&&typeof v!=="object").map(([k,v])=>k.replaceAll("_"," ")+": "+(typeof v==="number"?new Intl.NumberFormat(undefined,{maximumFractionDigits:4}).format(v):String(v))).join(" · ");
 document.getElementById("technical-summary").textContent=summary||"Insufficient history for indicator calculations.";
 document.getElementById("analysis-output").textContent=JSON.stringify(result,null,2);
 document.getElementById("chart-state").textContent=tf==="3h"?"3h aggregated from complete 1h candles":candles.length+" candles loaded";
 return result;
}
window.DashboardCharts={load,invalidate,parse,aggregate3h,indicators,intervalFor,routeFor,emaSeries,rsiSeries,atrSeries,macdSeries,macdComponents,bollingerSeries,adxSeries,stochRsiSeries};
})();