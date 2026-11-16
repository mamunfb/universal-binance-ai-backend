(function(){
"use strict";
const ns="http://www.w3.org/2000/svg";
const MAX_SOURCE_CANDLES=1000;
let activeLoadSequence=0,activeLoadController=null;
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
function finiteBlend(previous,current,weight){
 if(!Number.isFinite(previous)||!Number.isFinite(current)||!Number.isFinite(weight)||weight<0||weight>1)return null;
 const scale=Math.max(Math.abs(previous),Math.abs(current));if(scale===0)return 0;
 const normalized=previous/scale*(1-weight)+current/scale*weight;
 if(!Number.isFinite(normalized))return null;
 return Math.min(1,Math.max(-1,normalized))*scale;
}
function finiteMean(values){
 if(!values.length||!values.every(Number.isFinite))return null;
 const scale=Math.max(...values.map(Math.abs));if(!Number.isFinite(scale))return null;if(scale===0)return 0;
 let sum=0,correction=0;
 for(const value of values){const adjusted=value/scale-correction,next=sum+adjusted;correction=(next-sum)-adjusted;sum=next;}
 const mean=(sum/values.length)*scale;
 return Number.isFinite(mean)?mean:null;
}
function ema(a,n){if(a.length<n||!a.every(Number.isFinite))return null;const k=2/(n+1);let v=finiteMean(a.slice(0,n));if(v===null)return null;for(let i=n;i<a.length;i++){v=finiteBlend(v,a[i],k);if(v===null)return null;}return v;}
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
 for(let i=n+1;i<a.length;i++){const d=a[i]-a[i-1];if(!Number.isFinite(d))return null;g=g*((n-1)/n)+Math.max(d,0)/n;l=l*((n-1)/n)+Math.max(-d,0)/n;}
 if(!Number.isFinite(g)||!Number.isFinite(l))return null;
 if(g===0&&l===0)return 50;if(l===0)return 100;if(g===0)return 0;return 100-100/(1+g/l);
}
function atrWilder(c,n=14){
 const tr=c.slice(1).map((x,i)=>Math.max(x.high-x.low,Math.abs(x.high-c[i].close),Math.abs(x.low-c[i].close)));
 if(tr.length<n||!tr.every(Number.isFinite))return null;
 let value=finiteMean(tr.slice(0,n));if(value===null)return null;
 for(let i=n;i<tr.length;i++)value=value*((n-1)/n)+tr[i]/n;
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
  value=finiteBlend(value,values[i],k);if(value===null){runLength=0;continue;}out[i]=value;
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
  averageGain=averageGain*((n-1)/n)+gain/n;averageLoss=averageLoss*((n-1)/n)+loss/n;
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
  const validCurrent=cur&&typeof cur==="object"&&[cur.high,cur.low,cur.close].every(Number.isFinite)&&cur.high>0&&cur.low>0&&cur.close>0&&cur.high>=Math.max(cur.low,cur.close)&&cur.low<=Math.min(cur.high,cur.close),validPrevious=prev&&typeof prev==="object"&&[prev.high,prev.low,prev.close].every(Number.isFinite)&&prev.high>0&&prev.low>0&&prev.close>0&&prev.high>=Math.max(prev.low,prev.close)&&prev.low<=Math.min(prev.high,prev.close);const tr=validCurrent&&validPrevious?Math.max(cur.high-cur.low,Math.abs(cur.high-prev.close),Math.abs(cur.low-prev.close)):null;
  if(!Number.isFinite(tr)){seed=[];value=null;continue;}
  if(value===null){seed.push(tr);if(seed.length===n){value=finiteMean(seed);seed=[];if(value!==null)out[i]=value;else value=null;}continue;}
  value=value*((n-1)/n)+tr/n;if(!Number.isFinite(value)){seed=[];value=null;continue;}out[i]=value;
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
 if(!Array.isArray(values))return{upper:[],middle:[],lower:[]};
 const middle=Array(values.length).fill(null),upper=Array(values.length).fill(null),lower=Array(values.length).fill(null);
 if(!Number.isSafeInteger(n)||n<1||!Number.isFinite(multiplier)||multiplier<0)return{upper,middle,lower};
 for(let i=n-1;i<values.length;i++){const window=values.slice(i-n+1,i+1),mean=finiteMean(window),sd=scaledDeviation(window,mean);if(mean===null||sd===null)continue;middle[i]=mean;const upperValue=mean+multiplier*sd,lowerValue=mean-multiplier*sd;if(Number.isFinite(upperValue))upper[i]=upperValue;if(Number.isFinite(lowerValue))lower[i]=lowerValue;}
 return{upper,middle,lower};
}
function adxSegment(c,n,out,offset){
 if(c.length<2*n)return;
 const tr=[],plus=[],minus=[];
 for(let i=1;i<c.length;i++){const cur=c[i],prev=c[i-1],up=cur.high-prev.high,down=prev.low-cur.low;
  tr.push(Math.max(cur.high-cur.low,Math.abs(cur.high-prev.close),Math.abs(cur.low-prev.close)));
  plus.push(up>down&&up>0?up:0);minus.push(down>up&&down>0?down:0);
 }
 let scale=1;for(let i=0;i<tr.length;i++)scale=Math.max(scale,tr[i],plus[i],minus[i]);
 if(!Number.isFinite(scale))return;
 for(let i=0;i<tr.length;i++){tr[i]/=scale;plus[i]/=scale;minus[i]/=scale;}
 let trSm=tr.slice(0,n).reduce((sum,x)=>sum+x,0),pSm=plus.slice(0,n).reduce((sum,x)=>sum+x,0),mSm=minus.slice(0,n).reduce((sum,x)=>sum+x,0);
 const dx=[];
 for(let i=n-1;i<tr.length;i++){
  if(i>=n){trSm=trSm-trSm/n+tr[i];pSm=pSm-pSm/n+plus[i];mSm=mSm-mSm/n+minus[i];}
  const pdi=trSm?pSm/trSm*100:0,mdi=trSm?mSm/trSm*100:0,den=pdi+mdi;
  dx.push(den?Math.abs(pdi-mdi)/den*100:0);
  if(dx.length===n){let value=dx.reduce((sum,x)=>sum+x,0)/n;out[offset+i+1]=value;
   for(let j=i+1;j<tr.length;j++){trSm=trSm-trSm/n+tr[j];pSm=pSm-pSm/n+plus[j];mSm=mSm-mSm/n+minus[j];const pp=trSm?pSm/trSm*100:0,mm=trSm?mSm/trSm*100:0,d=pp+mm?Math.abs(pp-mm)/(pp+mm)*100:0;value=(value*(n-1)+d)/n;out[offset+j+1]=Number.isFinite(value)?value:null;}break;
  }
 }
}
function adxSeries(c,n=14){
 if(!Array.isArray(c))return[];const out=Array(c.length).fill(null);if(!Number.isSafeInteger(n)||n<1)return out;
 let segment=[],segmentStart=0;
 const flush=()=>{if(segment.length>=2*n)adxSegment(segment,n,out,segmentStart);segment=[];};
 for(let i=0;i<c.length;i++){
  const candle=c[i],valid=candle&&typeof candle==="object"&&[candle.high,candle.low,candle.close].every(Number.isFinite)&&candle.high>0&&candle.low>0&&candle.close>0&&candle.high>=Math.max(candle.low,candle.close)&&candle.low<=Math.min(candle.high,candle.close);
  if(!valid){flush();segmentStart=i+1;continue;}
  if(!segment.length)segmentStart=i;
  segment.push(candle);
 }
 flush();
 return out;
}
function stochRsiSeries(values,rsiPeriod=14,stochPeriod=14,smoothK=3,smoothD=3){
 const length=Array.isArray(values)?values.length:0,raw=Array(length).fill(null),k=Array(length).fill(null),d=Array(length).fill(null);
 if(!Array.isArray(values)||![rsiPeriod,stochPeriod,smoothK,smoothD].every(Number.isSafeInteger)||rsiPeriod<1||stochPeriod<1||smoothK<1||smoothD<1||!Number.isSafeInteger(rsiPeriod+stochPeriod)||!Number.isSafeInteger(smoothK+smoothD))return{k,d};
 const rsi=rsiSeries(values,rsiPeriod),minDeque=[],maxDeque=[];let minHead=0,maxHead=0,validRun=0;
 for(let i=0;i<rsi.length;i++){
  const current=rsi[i];if(!Number.isFinite(current)){minDeque.length=0;maxDeque.length=0;minHead=0;maxHead=0;validRun=0;continue;}
  validRun++;
  while(minHead<minDeque.length&&minDeque[minHead]<=i-stochPeriod)minHead++;
  while(maxHead<maxDeque.length&&maxDeque[maxHead]<=i-stochPeriod)maxHead++;
  while(minDeque.length>minHead&&rsi[minDeque[minDeque.length-1]]>=current)minDeque.pop();
  while(maxDeque.length>maxHead&&rsi[maxDeque[maxDeque.length-1]]<=current)maxDeque.pop();
  minDeque.push(i);maxDeque.push(i);
  if(validRun>=stochPeriod){const lo=rsi[minDeque[minHead]],hi=rsi[maxDeque[maxHead]];raw[i]=hi===lo?50:Math.min(100,Math.max(0,(current-lo)/(hi-lo)*100));}
 }
 let kRun=0,kSum=0,dRun=0,dSum=0;
 for(let i=0;i<length;i++){
  if(Number.isFinite(raw[i])){
   kRun++;kSum+=raw[i];if(kRun>smoothK)kSum-=raw[i-smoothK];
   if(kRun>=smoothK)k[i]=Math.min(100,Math.max(0,kSum/smoothK));
  }else{kRun=0;kSum=0;}
  if(Number.isFinite(k[i])){
   dRun++;dSum+=k[i];if(dRun>smoothD)dSum-=k[i-smoothD];
   if(dRun>=smoothD)d[i]=Math.min(100,Math.max(0,dSum/smoothD));
  }else{dRun=0;dSum=0;}
 }
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
 const a=c.slice(-120),w=1000,h=330,top=18,bottom=238,volTop=260,volBottom=310,closeAll=c.map(x=>x.close),bands=bollingerSeries(closeAll),bandValues=[...bands.upper.slice(-a.length),...bands.lower.slice(-a.length)].filter(Number.isFinite),hi=Math.max(...a.map(x=>x.high),...bandValues),lo=Math.min(...a.map(x=>x.low),...bandValues),priceScale=Math.max(Math.abs(hi),Math.abs(lo),1),scaledLo=lo/priceScale,scaledSpan=hi/priceScale-scaledLo||1,maxVol=Math.max(...a.map(x=>x.volume));
 const svg=document.createElementNS(ns,"svg");svg.setAttribute("viewBox","0 0 "+w+" "+h);svg.setAttribute("role","img");svg.setAttribute("aria-label","Candlestick and volume chart from verified backend OHLCV data");svg.style.width="100%";
 const svgContent=document.createDocumentFragment();const add=(tag,attrs)=>{const e=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,String(v)));svgContent.append(e);};
 for(let i=0;i<5;i++){const y=top+i*(bottom-top)/4;add("line",{x1:20,y1:y,x2:980,y2:y,stroke:"#243650","stroke-width":1});}
 const step=960/a.length,cw=Math.max(2,step*.58),y=v=>bottom-(v/priceScale-scaledLo)/scaledSpan*(bottom-top);
 a.forEach((x,i)=>{const cx=20+i*step+step/2,color=x.close>=x.open?"#48c99a":"#ef737e";add("line",{x1:cx,y1:y(x.high),x2:cx,y2:y(x.low),stroke:color,"stroke-width":1.2});add("rect",{x:cx-cw/2,y:Math.min(y(x.open),y(x.close)),width:cw,height:Math.max(1,Math.abs(y(x.open)-y(x.close))),fill:color});const vh=maxVol>0?x.volume/maxVol*(volBottom-volTop):0;add("rect",{x:cx-cw/2,y:volBottom-vh,width:cw,height:vh,fill:color,opacity:.4});});
 const closes=closeAll,ema20=emaSeries(closes,20),offset=c.length-a.length;
 const linePoints=series=>{const segments=[];let segment=[];series.slice(offset).forEach((v,i)=>{if(!Number.isFinite(v)){if(segment.length>1)segments.push(segment);segment=[];return;}const point=(20+i*step+step/2)+","+y(v);if(point.includes("NaN")||point.includes("Infinity")){if(segment.length>1)segments.push(segment);segment=[];return;}segment.push(point);});if(segment.length>1)segments.push(segment);return segments;};
 for(const [series,color,width] of [[bands.upper,"#8b9db8",1.2],[bands.middle,"#8b9db8",1],[bands.lower,"#8b9db8",1],[ema20,"#f4c46a",2]]){for(const pts of linePoints(series))add("polyline",{points:pts.join(" "),fill:"none",stroke:color,"stroke-width":width,"stroke-linejoin":"round","stroke-dasharray":color==="#8b9db8"?"5 4":"none"});}
 svg.append(svgContent);
 const caption=document.createElement("div");caption.className="chart-caption";caption.textContent=a.length+" candles · actual backend OHLCV · EMA20 + Bollinger(20,2) overlays · "+(c[0].time?new Date(c[0].time).toISOString():"");host.append(svg,caption);
 const valuesClose=c.map(x=>x.close);
 host.append(drawLinePanel("RSI (14) · Wilder",rsiSeries(valuesClose),{min:0,max:100}));
 const stoch=stochRsiSeries(valuesClose);host.append(drawLinePanel("Stochastic RSI · %K",stoch.k,{min:0,max:100}));host.append(drawLinePanel("Stochastic RSI · %D",stoch.d,{min:0,max:100}));
 host.append(drawLinePanel("ADX (14) · Wilder",adxSeries(c),{min:0,max:100}));
 const macd=macdComponents(valuesClose);host.append(drawLinePanel("MACD line · EMA12 − EMA26",macd.line,{zero:true}));host.append(drawLinePanel("MACD signal · EMA9 of MACD",macd.signal,{zero:true}));host.append(drawLinePanel("MACD histogram · line − signal",macd.histogram,{zero:true}));
 host.append(drawLinePanel("ATR (14) · Wilder",atrSeries(c)));
}
function invalidate(){activeLoadSequence++;if(activeLoadController){activeLoadController.abort();activeLoadController=null;}}
async function load(api,market,symbol,timeframe){
 const tf=timeframe,route=routeFor(market);
 if(!route)throw new Error("Unsupported market type: "+market);
 const supportedTimeframes=["1s","1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1D","3D","1W","1M"];
 if(!supportedTimeframes.includes(tf))throw new Error("Unsupported chart timeframe: "+tf);
 if(typeof symbol!=="string"||!symbol.trim())throw new Error("Enter a valid trading symbol.");
 const interval=intervalFor(tf),requestSequence=++activeLoadSequence;
 if(activeLoadController)activeLoadController.abort();
 const controller=new AbortController();activeLoadController=controller;
 let response;try{response=await api(route+encodeURIComponent(symbol)+"?interval="+encodeURIComponent(interval)+"&limit=1000",{signal:controller.signal});}catch(error){if(requestSequence!==activeLoadSequence)return{status:"SUPERSEDED",market,symbol,requested_timeframe:tf};throw error;}finally{if(activeLoadController===controller)activeLoadController=null;}
 if(requestSequence!==activeLoadSequence)return{status:"SUPERSEDED",market,symbol,requested_timeframe:tf};
 if(response===null||typeof response!=="object"||Array.isArray(response))throw new Error("Candle endpoint returned an invalid response shape. Expected a JSON object; previous chart was preserved.");
 if(!Array.isArray(response.klines))throw new Error("Candle endpoint did not provide a klines array; previous chart was preserved.");
 const sourceRows=response.klines.length>MAX_SOURCE_CANDLES?response.klines.slice(-MAX_SOURCE_CANDLES):response.klines;let candles=parse(sourceRows);if(tf==="3h")candles=aggregate3h(candles);if(!candles.length)throw new Error("Backend returned no valid complete candle rows; previous chart was preserved.");
 const values=indicators(candles);render(candles);
 const result={status:response.status||"RESPONSE_RECEIVED",market,symbol,requested_timeframe:tf,source_interval:interval,aggregation:tf==="3h"?"UTC-aligned groups of exactly three consecutive 1h candles; incomplete groups discarded":"Exchange-native interval",source:response.source||"Configured backend",candle_count:candles.length,source_rows_received:response.klines.length,source_rows_processed:sourceRows.length,latest_candle_time_utc:new Date(candles[candles.length-1].time).toISOString(),indicators:values,warning:"Descriptive frontend calculations only; not a validated trade signal."};
 const summary=Object.entries(values).filter(([k,v])=>k!=="method"&&v!==null&&typeof v!=="object").map(([k,v])=>k.replaceAll("_"," ")+": "+(typeof v==="number"?new Intl.NumberFormat(undefined,{maximumFractionDigits:4}).format(v):String(v))).join(" · ");
 document.getElementById("technical-summary").textContent=summary||"Insufficient history for indicator calculations.";
 document.getElementById("analysis-output").textContent=JSON.stringify(result,null,2);
 document.getElementById("chart-state").textContent=tf==="3h"?"3h aggregated from complete 1h candles":candles.length+" candles loaded";
 return result;
}
window.DashboardCharts={load,invalidate,parse,aggregate3h,indicators,intervalFor,routeFor,emaSeries,rsiSeries,atrSeries,macdSeries,macdComponents,bollingerSeries,adxSeries,stochRsiSeries};
})();