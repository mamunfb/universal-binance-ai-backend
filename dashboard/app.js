(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const TIMEFRAMES = ["1m","3m","5m","15m","30m","1h","2h","3h","4h","6h","8h","12h","1D","3D","1W","1M"];
  const PAGE_TITLES = {
    overview:"Overview","daily-research":"Daily AI Research","selected-coins":"AI Selected Coins",bullish:"Bullish Candidates",bearish:"Bearish Candidates",
    "spot-scanner":"Spot Scanner","usdm-scanner":"USDⓈ-M Scanner","coinm-scanner":"COIN-M Scanner","coin-analysis":"Coin Analysis","coin-comparison":"Coin Comparison",
    "historical-research":"Historical Research","technical-analysis":"Technical Analysis",derivatives:"Derivatives Intelligence","order-flow":"Order Flow & Liquidity",
    liquidations:"Liquidation Intelligence",news:"News & Catalysts",onchain:"On-Chain Intelligence",performance:"Signals & Performance",risk:"Risk Monitoring",reports:"Reports",reliability:"Data Reliability",settings:"Settings"
  };
  const state = {base:"", token:"", market:"SPOT", symbol:"BTCUSDT", timeframe:"1h", displayTimezone:"Asia/Dhaka", lastScan:null, lastScanDetails:null, lastHealth:null, lastAnalysis:null};
  let activeScanSequence=0;
  let activeScanController=null;
  let activeEvidenceSequence=0;
  let activeQualitySequence=0;
  let activeQualityController=null;
  let activeReadinessSequence=0;
  let activeReadinessController=null;
  let activeHealthSequence=0;
  let activeHealthController=null;
  let activeMarketEvidenceController=null;
  const esc = (value) => String(value ?? "—").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const setText = (id, value) => { const el=$(id); if(el) el.textContent = value == null || value === "" ? "—" : String(value); };
  const toast = (message, type="info") => { const el=document.createElement("div"); el.className="toast "+(type==="error"?"error":type==="success"?"success":""); el.textContent=message; $("toast-region").append(el); window.setTimeout(()=>el.remove(),4500); };
  const formatNumber = (value) => value===null || value===undefined || value==="" ? "—" : (Number.isFinite(Number(value)) ? new Intl.NumberFormat(undefined,{maximumFractionDigits:2}).format(Number(value)) : "—");
  const json = (value) => JSON.stringify(value,null,2);
  const showJson = (id, value) => { const el=$(id); if(el) el.textContent=json(value); };
  const setConnection = (ok, label) => { const dot=$("connection-dot"); dot.className="status-dot "+(ok?"good":"bad"); setText("connection-label",label); $("connection-banner").querySelector(".status-dot").className="status-dot "+(ok?"good":"bad"); $("connection-banner").querySelector("span:nth-child(2)").textContent=label; };
  function setSidebarOpen(open){
    const sidebar=$("sidebar"),menu=$("mobile-menu"),mobile=window.matchMedia("(max-width:760px)").matches;
    if(!open&&mobile&&sidebar.contains(document.activeElement))menu.focus();
    sidebar.classList.toggle("open",Boolean(open&&mobile));
    menu.setAttribute("aria-expanded",String(Boolean(open&&mobile)));
    menu.setAttribute("aria-label",open&&mobile?"Close navigation":"Open navigation");
    sidebar.inert=mobile&&!open;
    if(open&&mobile)sidebar.querySelector(".nav-link")?.focus();
  }
  function navigate(page) {
    const known = PAGE_TITLES[page] ? page : "overview";
    if(known!=="coin-analysis")cancelAnalysisRequests();
    document.querySelectorAll(".page-view").forEach(p=>p.classList.toggle("active",p.id==="page-"+known || (known!=="overview" && !document.getElementById("page-"+known) && p.id==="page-placeholder")));
    document.querySelectorAll(".nav-link").forEach(a=>{const active=a.dataset.page===known;a.classList.toggle("active",active);if(active)a.setAttribute("aria-current","page");else a.removeAttribute("aria-current");});
    const title=PAGE_TITLES[known] || known;
    setText("page-crumb",title);
    if(!document.getElementById("page-"+known)) { setText("placeholder-title",title); setText("placeholder-description", "This research area is included in the approved dashboard scope. Its API capability must be verified before live data is shown."); }
    if(known==="coin-analysis") syncAnalysisHeader();
    setSidebarOpen(false);
    if(document.activeElement!==document.body){
      const target=(document.getElementById("page-"+known)||$("page-placeholder"))?.querySelector("h1");
      if(target){target.setAttribute("tabindex","-1");target.focus({preventScroll:true});}
    }
  }
  function apiHeaders() { const h={"Accept":"application/json"}; if(state.token) h.Authorization="Bearer "+state.token; return h; }
  async function api(path, {method="GET", body, timeout=20000, signal:externalSignal}={}) {
    if(!state.base) throw new Error("Configure the private backend URL in Settings first.");
    if(!Number.isFinite(timeout)||timeout<=0)throw new Error("Request timeout must be a positive finite number.");
    const hasBody=body!==undefined; const controller=new AbortController(); let timedOut=false; const abortFromCaller=()=>controller.abort(); if(externalSignal?.aborted)controller.abort();else externalSignal?.addEventListener("abort",abortFromCaller,{once:true}); const timer=window.setTimeout(()=>{timedOut=true;controller.abort();},timeout);
    try {
      const response=await fetch(state.base.replace(/\/$/,"")+path,{method,headers:{...apiHeaders(),...(hasBody?{"Content-Type":"application/json"}:{})},body:hasBody?JSON.stringify(body):undefined,signal:controller.signal,credentials:"omit",cache:"no-store"});
      const raw=await response.text(); let data=null; try{data=raw?JSON.parse(raw):null;}catch{throw new Error("Backend returned a non-JSON response (HTTP "+response.status+").");}
      if(response.ok&&data===null)throw new Error("Backend returned an empty JSON response (HTTP "+response.status+").");
      if(!response.ok){const detail=data?.detail??data?.message;const safeDetail=typeof detail==="string"?detail.replace(/[\x00-\x1f\x7f]/g," ").replace(/\s+/g," ").trim().slice(0,300):"";throw new Error(safeDetail||("Backend request failed (HTTP "+response.status+")."));}
      return data;
    } catch(error) {
      if(error.name==="AbortError") throw new Error(timedOut?"Request timed out.":externalSignal?.aborted?"Request cancelled.":"Request aborted.");
      if(error instanceof TypeError) throw new Error("Network connection failed. Check your connection and backend availability.");
      throw error;
    }
    finally { window.clearTimeout(timer); externalSignal?.removeEventListener("abort",abortFromCaller); }
  }
  async function withButton(button, task, busyText="Loading…") {
    const el=$(button); if(!el) return; const original=el.textContent; el.disabled=true; el.textContent=busyText;
    try { await task(); } catch(error) { toast(error.message,"error"); } finally { el.disabled=false; el.textContent=original; }
  }
  function setMetric(key,value){setText("metric-"+key,formatNumber(value));}
  function extractCount(data, names) { for(const name of names){ const value=data?.[name]; if(typeof value!=="number" && typeof value!=="string") continue; if(typeof value==="string" && value.trim()==="") continue; const parsed=Number(value); if(Number.isSafeInteger(parsed)&&parsed>=0) return parsed; } return null; }
  function metadataText(value,fallback="Not supplied",maxLength=160) { let textValue=null; if(typeof value==="string"&&value.trim()!=="")textValue=value.trim(); else if(typeof value==="number"&&Number.isFinite(value))textValue=String(value); if(textValue===null)return fallback; return textValue.length>maxLength?textValue.slice(0,maxLength-1)+"…":textValue; }
  function metadataFieldName(data,names) { return names.find(name=>metadataText(data?.[name],null,160)!==null)||null; }
  function formatTimestamp(value) {
    if(typeof value!=="string"||!value.trim())return metadataText(value,"Not supplied",80);
    const raw=value.trim();
    if(!/^\d{4}-\d{2}-\d{2}(?:[Tt ]|$)/.test(raw))return metadataText(raw,"Not supplied",80);
    const parsed=Date.parse(raw);if(!Number.isFinite(parsed))return metadataText(raw,"Not supplied",80);
    try{return new Intl.DateTimeFormat(undefined,{dateStyle:"medium",timeStyle:"medium",timeZone:state.displayTimezone}).format(parsed);}
    catch{return metadataText(raw,"Not supplied",80);}
  }
  function scanTimestamp(data) { return formatTimestamp(data.generated_at??data.timestamp??data.updated_at??"Not supplied"); }
  function renderScanSummary(data,market=state.market) {
    state.lastScan=data;
    const eligible=extractCount(data,["eligible_count","eligible_symbols","eligible","total_eligible","total_symbols"]);
    const scanned=extractCount(data,["scanned_count","scanned_symbols","scanned","attempted_count"]);
    const failed=extractCount(data,["failed_count","failed_symbols","failed"]);
    setMetric("eligible",eligible); setMetric("scanned",scanned); setMetric("failed",failed);
    setMetric("qualified",extractCount(data,["qualified_count","matched_count","candidate_count"]));
    const summary=$("scan-summary"); summary.innerHTML="";
    const rows=[
      ["Market",market],["Eligible",eligible],["Scanned",scanned],["Matched",extractCount(data,["matched_count","match_count"])],
      ["Failed",failed],["Status",metadataText(data.status,metadataText(data.scan_status,"Returned",80),80)],["Source",metadataText(data.source,"Backend response",120)],["Updated",scanTimestamp(data)]
    ];
    rows.forEach(([label,value])=>{const line=document.createElement("div");line.className="status-list";const row=document.createElement("div");const a=document.createElement("span");a.textContent=label;const b=document.createElement("b");b.textContent=value==null?"Not supplied":String(value);row.append(a,b);line.append(row);summary.append(line);});
    setText("scan-state",metadataText(data.status,metadataText(data.scan_status,"Response received",80),80));
    setText("overview-updated",scanTimestamp(data));
  }
  function invalidateHealthRequests(){activeHealthSequence++;if(activeHealthController){activeHealthController.abort();activeHealthController=null;}}
  async function loadHealth() {
    invalidateHealthRequests();const requestSequence=activeHealthSequence;const controller=new AbortController();activeHealthController=controller;
    setText("health-status","Checking backend health · previous status retained");
    try { const result=await api("/health",{signal:controller.signal}); if(requestSequence!==activeHealthSequence)return{status:"SUPERSEDED"}; if(result===null||typeof result!=="object"||Array.isArray(result))throw new Error("Health endpoint returned an invalid response shape. Expected a JSON object."); state.lastHealth=result; setText("health-status",metadataText(result.status,"Healthy response",80)); setConnection(true,"Backend reachable"); return result; }
    catch(error){if(requestSequence!==activeHealthSequence)return{status:"SUPERSEDED"};setText("health-status","Unavailable");setConnection(false,"Backend unavailable: "+metadataText(error?.message,"Request failed",160));throw error;}
    finally{if(activeHealthController===controller)activeHealthController=null;}
  }
  function invalidateScanRequests(){activeScanSequence++;if(activeScanController){activeScanController.abort();activeScanController=null;}}
  async function scanMarket(market) {
    if(!["SPOT","USD_M","COIN_M"].includes(market))throw new Error("Unsupported scanner market selection.");
    invalidateScanRequests();const requestSequence=activeScanSequence;const controller=new AbortController();activeScanController=controller;
    setText("scan-state","Refreshing · previous results retained");
    const marketChanged=state.market!==market; state.market=market; $("global-market").value=market; if(marketChanged) invalidateChartView(); document.querySelectorAll(".market-tab").forEach(b=>b.classList.toggle("active",b.dataset.market===market));
    let path,quoteFilter=null;
    if(market==="SPOT") { quoteFilter=($("spot-quote")?.value||"").trim().toUpperCase(); path="/api/v1/markets/spot/scan"+(quoteFilter?"?quote_asset="+encodeURIComponent(quoteFilter):""); }
    else if(market==="USD_M") path="/api/v1/markets/futures/usdm/scan";
    else path="/api/v1/markets/futures/coinm/scan";
    let data; try{data=await api(path,{signal:controller.signal});}catch(error){if(requestSequence!==activeScanSequence)return{status:"SUPERSEDED",market};setText("scan-state","Refresh failed · previous results retained");throw error;}finally{if(activeScanController===controller)activeScanController=null;}
    if(requestSequence!==activeScanSequence)return{status:"SUPERSEDED",market};
    if(data===null||typeof data!=="object"||Array.isArray(data)){setText("scan-state","Invalid response · previous results retained");throw new Error("Scanner endpoint returned an invalid response shape. Expected a JSON object; previous results were preserved.");}
    const rowKey=["symbols","markets","results","data"].find(key=>Array.isArray(data[key]));
    if(rowKey===undefined){setText("scan-state","Incomplete response · previous results and coverage retained");toast(market+" scan response incomplete. No recognized result array was supplied; previous results and coverage were preserved.","info");return{status:"INCOMPLETE_RESPONSE",market};}
    const additionalRowKeys=["symbols","markets","results","data"].filter(key=>key!==rowKey&&Array.isArray(data[key]));
    const responseRows=data[rowKey];
    const rows=responseRows.filter(item=>item!==null&&typeof item==="object"&&!Array.isArray(item));
    const rejectedRows=responseRows.length-rows.length;
    if(responseRows.length>0&&rows.length===0){setText("scan-state","Invalid rows · previous results and coverage retained");throw new Error("Scanner response contained no valid row objects; previous results and coverage were preserved.");}
    renderScanSummary(data,market);
    if(market==="SPOT") renderRows("spot-rows",rows,6);
    if(market==="USD_M") renderRows("usdm-rows",rows,5);
    if(market==="COIN_M") renderRows("coinm-rows",rows,5);
    renderScannerMeta(market,data,rows,rejectedRows,rowKey,additionalRowKeys,quoteFilter);
    state.lastScanDetails={market,data,rows,rejectedRows,rowKey,additionalRowKeys,quoteFilter};
    toast(market+" scan response received."+(rejectedRows?" "+rejectedRows+" malformed rows were excluded.":" Check coverage and failure counts."),rejectedRows?"info":"success");
    return data;
  }
  function scannerCountAliasConflicts(data,countNames) {
    return Object.entries(countNames).flatMap(([label,names])=>{
      const supplied=names.map(name=>({name,value:extractCount(data,[name])})).filter(entry=>entry.value!==null);
      const distinct=new Set(supplied.map(entry=>entry.value));
      return distinct.size>1?[label+": "+supplied.map(entry=>entry.name+"="+entry.value).join(", ")]:[];
    });
  }
  function scannerDuplicateSymbolStats(rows) {
    const counts=new Map();
    for(const row of Array.isArray(rows)?rows:[]){
      const symbol=typeof row?.symbol==="string"?row.symbol.trim().toUpperCase():"";
      if(!symbol)continue;
      counts.set(symbol,(counts.get(symbol)||0)+1);
    }
    let duplicateSymbols=0,duplicateRows=0;
    for(const count of counts.values())if(count>1){duplicateSymbols++;duplicateRows+=count-1;}
    return{uniqueSymbols:counts.size,duplicateSymbols,duplicateRows};
  }
  function renderScannerMeta(market,data,rows,rejectedRows=0,rowKey=null,additionalRowKeys=[],quoteFilter=null) {
    const prefix=market==="USD_M"?"usdm":market==="COIN_M"?"coinm":"spot";
    const duplicateStats=scannerDuplicateSymbolStats(rows);
    const countNames={
      eligible:["eligible_count","eligible_symbols","eligible","total_eligible","total_symbols"],
      scanned:["scanned_count","scanned_symbols","scanned","attempted_count"],
      failed:["failed_count","failed_symbols","failed"],
      matched:["matched_count","match_count","qualified_count","candidate_count"]
    };
    const details=[
      "Result field: "+(rowKey||"Not supplied"),
      "Additional array fields: "+(additionalRowKeys.length?additionalRowKeys.join(", "):"None"),
      "Returned rows: "+rows.length,
      "Unique symbols: "+duplicateStats.uniqueSymbols,
      "Duplicate symbols: "+duplicateStats.duplicateSymbols,
      "Duplicate rows: "+duplicateStats.duplicateRows,
      "Rejected malformed rows: "+rejectedRows,
      "Status field: "+(metadataFieldName(data,["status","scan_status"])||"Not supplied"),
      "Status: "+metadataText(data.status,metadataText(data.scan_status,"Not supplied",80),80),
      "Eligible: "+(extractCount(data,countNames.eligible)??"Not supplied"),
      "Scanned: "+(extractCount(data,countNames.scanned)??"Not supplied"),
      "Failed: "+(extractCount(data,countNames.failed)??"Not supplied"),
      "Matched: "+(extractCount(data,countNames.matched)??"Not supplied"),
      "Count alias conflicts: "+(scannerCountAliasConflicts(data,countNames).join("; ")||"None detected"),
      "Source field: "+(metadataFieldName(data,["source"])||"Not supplied"),
      "Source: "+metadataText(data.source,"Not supplied",120),
      "Timestamp field: "+(metadataFieldName(data,["generated_at","timestamp","updated_at"])||"Not supplied"),
      "Timestamp: "+scanTimestamp(data),
      ...(market==="SPOT"?["Requested quote filter: "+metadataText(quoteFilter,"All quote assets",40)]:[])
    ];
    setText(prefix+"-coverage",details.join(" · "));
    if(market!=="SPOT") setText(prefix+"-count",rows.length.toLocaleString()+" returned");
  }
  const tableViews = {};
  const scannerSearchTimers = {};
  const scannerSearchTextCaches = {};
  const scannerCollator = new Intl.Collator(undefined,{numeric:true,sensitivity:"base"});
  function focusPagerControl(table,label){
    const buttons=Array.from(table?.parentElement?.parentElement?.querySelectorAll(".table-pager button")||[]);
    const preferred=buttons.find(button=>button.getAttribute("aria-label")===label&&!button.disabled);
    (preferred||buttons.find(button=>!button.disabled))?.focus();
  }
  function scannerSearchText(target,item,keys){
    let cache=scannerSearchTextCaches[target];
    if(!cache)cache=scannerSearchTextCaches[target]=new WeakMap();
    if(!cache.has(item))cache.set(item,keys.map(key=>String(item?.[key]??"").toUpperCase()).join("\u0000"));
    return cache.get(item);
  }
  function scannerCellText(key,value) {
    if(value===null||value===undefined||value==="")return"—";
    const numericKey=["last_price","quote_volume_24h","price_change_percent_24h"].includes(key);
    if(numericKey){
      if(typeof value!=="number"&&typeof value!=="string")return"Invalid number";
      if(typeof value==="string"&&value.trim()==="")return"—";
      return Number.isFinite(Number(value))?String(value):"Invalid number";
    }
    if(typeof value==="number")return Number.isFinite(value)?String(value):"Invalid number";
    if(typeof value==="string")return value.trim()===""?"—":value;
    if(typeof value==="boolean")return String(value);
    return"Invalid value";
  }
  function renderRows(target, rows, columns) {
    if(scannerSearchTimers[target]!==undefined){window.clearTimeout(scannerSearchTimers[target]);delete scannerSearchTimers[target];}
    const body=$(target); if(!body) return;
    const keys=columns===6?["symbol","base_asset","quote_asset","last_price","quote_volume_24h","status"]:["symbol","last_price","quote_volume_24h","price_change_percent_24h","status"];
    const view=tableViews[target]||(tableViews[target]={page:0,pageSize:100,sortKey:"symbol",direction:1,rows:[],query:""});
    const incomingRows=Array.isArray(rows)?rows:[];
    if(incomingRows!==view.rows){view.rows=incomingRows;view.page=0;view.sortedCache=null;scannerSearchTextCaches[target]=new WeakMap();}
    const cached=view.sortedCache;
    let filteredCount,sortedRows;
    if(cached&&cached.rows===view.rows&&cached.query===view.query&&cached.sortKey===view.sortKey&&cached.direction===view.direction){
      filteredCount=cached.filteredCount;sortedRows=cached.sortedRows;
    }else{
      const numericValue=value=>{if(typeof value==="number")return Number.isFinite(value)?value:null;if(typeof value!=="string"||value.trim()==="")return null;const parsed=Number(value);return Number.isFinite(parsed)?parsed:null;};
      sortedRows=[];
      for(const item of view.rows){
        if(view.query&&!scannerSearchText(target,item,keys).includes(view.query))continue;
        sortedRows.push(item);
      }
      const sortKey=view.sortKey,direction=view.direction;
      const numericCache=new WeakMap();
      const numericFor=item=>{
        if(!numericCache.has(item))numericCache.set(item,numericValue(item?.[sortKey]));
        return numericCache.get(item);
      };
      sortedRows.sort((a,b)=>{
        const av=a?.[sortKey],bv=b?.[sortKey];
        const aMissing=av===null||av===undefined||(typeof av==="string"&&av.trim()==="");
        const bMissing=bv===null||bv===undefined||(typeof bv==="string"&&bv.trim()==="");
        if(aMissing!==bMissing)return aMissing?1:-1;
        const an=numericFor(a),bn=numericFor(b);
        if((an!==null)!==(bn!==null))return an!==null?-1:1;
        let cmp=an!==null&&bn!==null?an-bn:scannerCollator.compare(String(av??""),String(bv??""));
        if(cmp===0)cmp=scannerCollator.compare(String(a?.symbol??""),String(b?.symbol??""));
        return cmp===0?0:cmp*direction;
      });
      filteredCount=sortedRows.length;
      view.sortedCache={rows:view.rows,query:view.query,sortKey,direction,filteredCount,sortedRows};
    }
    const pages=Math.max(1,Math.ceil(sortedRows.length/view.pageSize));view.page=Math.min(view.page,pages-1);
    body.replaceChildren();
    const rowFragment=document.createDocumentFragment();
    const visible=sortedRows.slice(view.page*view.pageSize,(view.page+1)*view.pageSize);
    if(!visible.length){const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=columns;td.className="empty-cell";td.textContent=view.rows.length?"No rows match the current filter.":"No market rows were returned. Inspect the raw response and scan status.";tr.append(td);rowFragment.append(tr);}
    visible.forEach(item=>{const tr=document.createElement("tr");keys.forEach(key=>{const td=document.createElement("td");td.textContent=scannerCellText(key,item?.[key]);tr.append(td);});rowFragment.append(tr);});
    body.append(rowFragment);
    const table=body.closest("table"),headers=table?.querySelectorAll("thead th")||[];
    headers.forEach((th,index)=>{th.title="Sort by "+keys[index];th.setAttribute("aria-sort",keys[index]===view.sortKey?(view.direction===1?"ascending":"descending"):"none");th.style.cursor="pointer";});
    let pager=table?.parentElement?.parentElement?.querySelector(".table-pager");
    if(table&&!pager){pager=document.createElement("div");pager.className="table-pager";pager.style.cssText="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 14px;color:var(--muted,#9aa);font-size:12px";table.parentElement.parentElement.append(pager);}
    if(pager){pager.replaceChildren();const info=document.createElement("span");info.setAttribute("aria-live","polite");info.textContent=filteredCount.toLocaleString()+" matching / "+view.rows.length.toLocaleString()+" returned · page "+(view.page+1)+"/"+pages+" · "+view.pageSize+" per page";const controls=document.createElement("span");const prev=document.createElement("button"),next=document.createElement("button");prev.type=next.type="button";prev.textContent="Previous";next.textContent="Next";prev.setAttribute("aria-label","Previous scanner page");next.setAttribute("aria-label","Next scanner page");prev.setAttribute("aria-controls",target);next.setAttribute("aria-controls",target);prev.disabled=view.page===0;next.disabled=view.page>=pages-1;prev.addEventListener("click",()=>{view.page--;renderRows(target,view.rows,columns);focusPagerControl(table,"Previous scanner page");});next.addEventListener("click",()=>{view.page++;renderRows(target,view.rows,columns);focusPagerControl(table,"Next scanner page");});controls.append(prev,next);pager.append(info,controls);}
    if(target==="spot-rows")setText("spot-count",filteredCount.toLocaleString()+" matching / "+view.rows.length.toLocaleString()+" returned");
    if(!view.headersBound&&table){view.headersBound=true;headers.forEach((th,index)=>{const sort=()=>{const key=keys[index];view.direction=view.sortKey===key?-view.direction:1;view.sortKey=key;view.page=0;renderRows(target,view.rows,columns);};th.tabIndex=0;th.setAttribute("aria-keyshortcuts","Enter Space");th.setAttribute("aria-label","Sort by "+keys[index]);th.addEventListener("click",sort);th.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();sort();}});});}
  }
  function syncAnalysisHeader(){state.symbol=$("global-symbol").value.trim().toUpperCase()||"BTCUSDT";state.market=$("global-market").value;state.timeframe=$("global-timeframe").value;setText("analysis-title",state.symbol+" · "+state.market);setText("analysis-subtitle","Timeframe "+state.timeframe+" · "+state.market+" · Research-only analysis");}
  function cancelAnalysisRequests(){
    activeEvidenceSequence++;window.DashboardCharts.invalidate();
    if(activeMarketEvidenceController){activeMarketEvidenceController.abort();activeMarketEvidenceController=null;}
  }
  function invalidateChartView(message="Selection changed. Run analysis to load matching candles.") {
    cancelAnalysisRequests();
    const host=$("chart-placeholder"); if(host) host.replaceChildren(document.createTextNode(message));
    setText("chart-state","Awaiting analysis"); setText("technical-summary","Run analysis to load indicators for the current selection.");
    setText("analysis-output","No chart response for the current selection.");
  }
  async function loadMarketEvidence() {
    syncAnalysisHeader();const requestSequence=++activeEvidenceSequence;window.DashboardCharts.invalidate();
    if(activeMarketEvidenceController)activeMarketEvidenceController.abort();
    const controller=new AbortController();activeMarketEvidenceController=controller;
    setText("chart-state","Loading market evidence · previous chart and evidence retained");
    const path="/api/v1/analysis/market-evidence/"+encodeURIComponent(state.symbol);let data;
    try{data=await api(path,{signal:controller.signal});}
    catch(error){if(requestSequence!==activeEvidenceSequence)return{status:"SUPERSEDED"};setText("chart-state","Evidence request failed · previous chart and evidence retained");throw error;}
    finally{if(activeMarketEvidenceController===controller)activeMarketEvidenceController=null;}
    if(requestSequence!==activeEvidenceSequence)return{status:"SUPERSEDED"};
    if(data===null||typeof data!=="object"||Array.isArray(data)){setText("chart-state","Invalid evidence response · previous chart and evidence retained");throw new Error("Market evidence endpoint returned an invalid response shape. Expected a JSON object; previous evidence was preserved.");}
    const chartHost=$("chart-placeholder");if(chartHost)chartHost.replaceChildren(document.createTextNode("Market evidence endpoint does not provide candle chart data."));
    state.lastAnalysis=data;showJson("analysis-output",data);setText("chart-state","Evidence loaded; candle chart not provided by this endpoint");setText("technical-summary",metadataText(data.summary,metadataText(data.status,"Market evidence returned. Inspect evidence payload.",120),120));
    toast("Market evidence loaded.","success");return data;
  }
  async function loadTechnical() {
    syncAnalysisHeader();const requestSequence=++activeEvidenceSequence;
    if(activeMarketEvidenceController){activeMarketEvidenceController.abort();activeMarketEvidenceController=null;}
    setText("chart-state","Loading candles · previous chart retained");
    let data;try{data=await window.DashboardCharts.load(api,state.market,state.symbol,state.timeframe);}
    catch(error){if(requestSequence!==activeEvidenceSequence)return{status:"SUPERSEDED"};setText("chart-state","Chart request failed · previous chart retained");setText("technical-summary","Request failed: "+metadataText(error?.message,"Unknown error",160));throw error;}
    if(requestSequence!==activeEvidenceSequence||data?.status==="SUPERSEDED")return{status:"SUPERSEDED"};
    state.lastAnalysis=data;toast("Verified candle chart and descriptive indicators loaded.","success");return data;
  }
  function initTimeframes() {
    ["global-timeframe","default-timeframe","quality-interval"].forEach(id=>{const select=$(id);select.replaceChildren();TIMEFRAMES.forEach(tf=>{const option=document.createElement("option");option.value=tf;option.textContent=tf;select.append(option);});});
    $("global-timeframe").value="1h";$("default-timeframe").value="1h";const qualitySelect=$("quality-interval");qualitySelect.replaceChildren();["1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d"].forEach(tf=>{const option=document.createElement("option");option.value=tf;option.textContent=tf;qualitySelect.append(option);});qualitySelect.value="1h";
    const strip=$("analysis-timeframes");TIMEFRAMES.forEach(tf=>{const button=document.createElement("button");button.className="timeframe-btn"+(tf==="1h"?" active":"");button.type="button";button.textContent=tf;button.addEventListener("click",()=>{state.timeframe=tf;$("global-timeframe").value=tf;strip.querySelectorAll("button").forEach(b=>b.classList.toggle("active",b===button));syncAnalysisHeader();withButton("load-coin-analysis",loadTechnical,"Loading…");});strip.append(button);});
  }
  function applyDisplayPreferences() {
    state.displayTimezone=$("display-timezone").value;
    state.market=$("default-market").value;
    state.timeframe=$("default-timeframe").value;
    $("global-market").value=state.market;$("global-timeframe").value=state.timeframe;
    document.querySelectorAll(".market-tab").forEach(b=>b.classList.toggle("active",b.dataset.market===state.market));
    $("analysis-timeframes").querySelectorAll("button").forEach(b=>b.classList.toggle("active",b.textContent===state.timeframe));
    syncAnalysisHeader();
  }
  function invalidateQualityRequest(){activeQualitySequence++;if(activeQualityController){activeQualityController.abort();activeQualityController=null;}}
  async function loadQuality() {
    invalidateQualityRequest();const requestSequence=activeQualitySequence;const controller=new AbortController();activeQualityController=controller;
    const market=$("quality-market").value,symbolInput=$("quality-symbol"),symbol=symbolInput.value.trim().toUpperCase(),interval=$("quality-interval").value,lookbackInput=$("quality-lookback"),lookback=Number(lookbackInput.value);
    symbolInput.setCustomValidity("");lookbackInput.setCustomValidity("");
    if(!symbol){symbolInput.setCustomValidity("Enter a market symbol.");symbolInput.reportValidity();throw new Error("Enter a market symbol.");}
    if(!/^[A-Z0-9]{1,40}$/.test(symbol)){symbolInput.setCustomValidity("Use 1–40 letters or digits only.");symbolInput.reportValidity();throw new Error("Market symbol must contain 1–40 letters or digits only.");}
    if(!Number.isInteger(lookback)||lookback<1||lookback>2160){lookbackInput.setCustomValidity("Enter a whole number from 1 to 2160.");lookbackInput.reportValidity();throw new Error("Lookback must be a whole number from 1–2160 hours.");}
    const q=new URLSearchParams({interval,lookback_hours:String(lookback)});
    setText("quality-state","Loading "+symbol+" · "+interval+" · previous report retained");
    let data;try{data=await api("/api/v1/quality/market-data/"+encodeURIComponent(market)+"/"+encodeURIComponent(symbol)+"?"+q,{signal:controller.signal});}catch(error){if(requestSequence!==activeQualitySequence)return{status:"SUPERSEDED"};setText("quality-state","Load failed · previous report retained · "+metadataText(error?.message,"Unknown error",120));throw error;}finally{if(activeQualityController===controller)activeQualityController=null;}
    if(requestSequence!==activeQualitySequence)return{status:"SUPERSEDED"};
    if(data===null||typeof data!=="object"||Array.isArray(data)){setText("quality-state","Invalid response · previous report retained");throw new Error("Data quality endpoint returned an invalid response shape. Expected a JSON object; previous report was preserved.");}
    showJson("quality-output",data);setText("quality-state",metadataText(data.status,"Report received",80));toast("Data quality report loaded.","success");return data;
  }
  function invalidateReadinessRequests() {
    activeReadinessSequence++;
    if(activeReadinessController){activeReadinessController.abort();activeReadinessController=null;}
  }
  async function loadReadiness(path) {
    const requestSequence=++activeReadinessSequence;
    if(activeReadinessController)activeReadinessController.abort();
    const controller=new AbortController();activeReadinessController=controller;
    setText("readiness-state","Loading · previous response retained");
    try {
      const data=await api(path,{signal:controller.signal});
      if(requestSequence!==activeReadinessSequence)return{status:"SUPERSEDED"};
      if(data===null||typeof data!=="object"||Array.isArray(data))throw new Error("Research readiness endpoint returned an invalid response shape.");
      showJson("readiness-output",data);setText("readiness-state",metadataText(data.status,"Response received",80));return data;
    } catch(error) {
      if(requestSequence!==activeReadinessSequence)return{status:"SUPERSEDED"};
      setText("readiness-state","Request failed · previous response retained");throw error;
    } finally {
      if(requestSequence===activeReadinessSequence&&activeReadinessController===controller)activeReadinessController=null;
    }
  }
  function clearConnectionScopedData(reason="Connection changed · previous backend data cleared") {
    state.lastScan=null;state.lastScanDetails=null;state.lastHealth=null;state.lastAnalysis=null;
    ["eligible","scanned","failed","qualified"].forEach(key=>setMetric(key,null));
    setText("overview-updated",reason);setText("scan-state",reason);setText("scan-summary",reason);
    const scanners=[["spot-rows","spot-search","spot-count","spot-coverage",6],["usdm-rows","usdm-search","usdm-count","usdm-coverage",5],["coinm-rows","coinm-search","coinm-count","coinm-coverage",5]];
    scanners.forEach(([target,searchId,countId,coverageId,columns])=>{
      const view=tableViews[target]||(tableViews[target]={page:0,pageSize:100,sortKey:"symbol",direction:1,rows:[],query:""});
      if(scannerSearchTimers[target]!==undefined){window.clearTimeout(scannerSearchTimers[target]);delete scannerSearchTimers[target];}
      view.rows=[];view.page=0;view.query="";view.sortedCache=null;scannerSearchTextCaches[target]=new WeakMap();
      const search=$(searchId);if(search)search.value="";
      renderRows(target,[],columns);setText(countId,reason);setText(coverageId,reason);
    });
    setText("readiness-state",reason);setText("readiness-output",reason);
    setText("quality-state",reason);setText("quality-output",reason);
    window.DashboardCharts.invalidate();
    const chartHost=$("chart-placeholder");if(chartHost)chartHost.replaceChildren(document.createTextNode(reason));
    setText("chart-state",reason);setText("technical-summary",reason);setText("analysis-output",reason);
  }
  function refreshDisplayedTimestamps() {
    if(!state.lastScan)return;
    const cached=state.lastScanDetails;
    renderScanSummary(cached?.data??state.lastScan,cached?.market??state.market);
    if(cached)renderScannerMeta(cached.market,cached.data,cached.rows,cached.rejectedRows,cached.rowKey,cached.additionalRowKeys,cached.quoteFilter);
  }
  function connectSettings() {
    const urlInput=$("backend-url"),rawUrl=urlInput.value.trim(),url=rawUrl.replace(/\/$/,"");
    const rejectUrl=(message)=>{urlInput.setCustomValidity(message);urlInput.reportValidity();throw new Error(message);};
    urlInput.setCustomValidity("");
    if(!url)rejectUrl("Enter the private backend base URL.");
    let parsed;try{parsed=new URL(url);}catch{rejectUrl("Enter a valid absolute backend URL.");}
    const localHttp=parsed.protocol==="http:"&&(parsed.hostname==="localhost"||parsed.hostname==="127.0.0.1");
    if(parsed.protocol!=="https:"&&!localHttp)rejectUrl("Use HTTPS for remote backends. HTTP is allowed only for localhost or 127.0.0.1.");
    if(!parsed.hostname||parsed.username||parsed.password||parsed.search||parsed.hash)rejectUrl("Backend URL must include a host and must not contain embedded credentials, query parameters or a fragment.");
    invalidateScanRequests();invalidateQualityRequest();invalidateReadinessRequests();cancelAnalysisRequests();invalidateHealthRequests();state.base=url;state.token=$("backend-token").value.trim();clearConnectionScopedData("Connection settings changed · previous backend data cleared");setText("health-status","Not checked · test the new connection");setConnection(false,"Connection settings changed · test connection");setText("scan-state","Connection settings changed · run a new scan");setText("quality-state","Connection settings changed · run a new quality check");setText("settings-status","Connection details held in page memory only.");toast("Connection settings applied for this page session.","success");
  }
  function bind() {
    document.querySelectorAll(".nav-link").forEach(a=>a.addEventListener("click",e=>{e.preventDefault();const page=a.dataset.page; if(PAGE_TITLES[page] && document.getElementById("page-"+page)) navigate(page); else navigate(page); history.replaceState(null,"","#"+page);}));
    setSidebarOpen(false);
    $("mobile-menu").addEventListener("click",()=>setSidebarOpen(!$("sidebar").classList.contains("open")));
    document.addEventListener("keydown",event=>{
      const sidebar=$("sidebar"),menu=$("mobile-menu");
      if(!sidebar.classList.contains("open")||!window.matchMedia("(max-width:760px)").matches)return;
      if(event.key==="Escape"){event.preventDefault();setSidebarOpen(false);return;}
      if(event.key!=="Tab")return;
      const focusable=Array.from(sidebar.querySelectorAll('a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])'))
        .filter(element=>!element.closest("[inert]")&&element.getClientRects().length>0);
      if(!focusable.length){event.preventDefault();menu.focus();return;}
      const first=focusable[0],last=focusable[focusable.length-1],active=document.activeElement;
      if(event.shiftKey&&(active===first||!sidebar.contains(active))){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&(active===last||!sidebar.contains(active))){event.preventDefault();first.focus();}
    });
    window.addEventListener("resize",()=>setSidebarOpen(false));
    $("open-settings").addEventListener("click",()=>{navigate("settings");history.replaceState(null,"","#settings");});
    $("banner-settings").addEventListener("click",()=>navigate("settings"));
    $("refresh-page").addEventListener("click",()=>{const page=location.hash.slice(1)||"overview";if(page==="overview")withButton("refresh-page",async()=>{const results=await Promise.allSettled([loadHealth(),scanMarket(state.market)]);const failures=results.filter(result=>result.status==="rejected").map(result=>metadataText(result.reason?.message,"Request failed",120));if(failures.length)throw new Error("Overview refresh partially failed: "+failures.join(" · "));},"Refreshing");else if(page==="reliability")withButton("refresh-page",loadQuality,"Refreshing");else if(page==="coin-analysis")withButton("refresh-page",loadTechnical,"Refreshing");else toast("No verified refresh action is mapped for this page yet.");});
    $("global-market").addEventListener("change",e=>{invalidateScanRequests();state.market=e.target.value;document.querySelectorAll(".market-tab").forEach(b=>b.classList.toggle("active",b.dataset.market===state.market));invalidateChartView();});
    $("global-symbol").addEventListener("change",()=>{state.symbol=$("global-symbol").value.trim().toUpperCase();syncAnalysisHeader();invalidateChartView();});
    $("global-timeframe").addEventListener("change",()=>{state.timeframe=$("global-timeframe").value;syncAnalysisHeader();invalidateChartView();});
    ["quality-market","quality-symbol","quality-interval","quality-lookback"].forEach(id=>{const invalidate=()=>{invalidateQualityRequest();setText("quality-state","Selection changed · run a new quality check");};$(id).addEventListener("change",invalidate);if(id==="quality-symbol"||id==="quality-lookback")$(id).addEventListener("input",invalidate);});
    document.querySelectorAll(".market-tab").forEach(b=>b.addEventListener("click",()=>{invalidateScanRequests();setText("scan-state","Market selection changed · run a new scan");state.market=b.dataset.market;document.querySelectorAll(".market-tab").forEach(x=>x.classList.toggle("active",x===b));$("global-market").value=state.market;invalidateChartView();}));
    $("run-market-scan").addEventListener("click",()=>withButton("run-market-scan",()=>scanMarket(state.market),"Scanning…"));
    $("scan-spot").addEventListener("click",()=>withButton("scan-spot",()=>scanMarket("SPOT"),"Scanning…"));
    $("scan-usdm").addEventListener("click",()=>withButton("scan-usdm",()=>scanMarket("USD_M"),"Scanning…"));
    $("scan-coinm").addEventListener("click",()=>withButton("scan-coinm",()=>scanMarket("COIN_M"),"Scanning…"));
    $("spot-quote").addEventListener("input",()=>{invalidateScanRequests();setText("scan-state","Spot quote filter changed · previous results retained; run a new scan");setText("spot-coverage","Quote filter changed · run a new Spot scan");});
    [["spot-search","spot-rows",6],["usdm-search","usdm-rows",5],["coinm-search","coinm-rows",5]].forEach(([input,target,columns])=>{
      $(input).addEventListener("input",e=>{
        const view=tableViews[target]||(tableViews[target]={page:0,pageSize:100,sortKey:"symbol",direction:1,rows:[],query:""});
        view.query=e.target.value.trim().toUpperCase();view.page=0;
        if(scannerSearchTimers[target]!==undefined)window.clearTimeout(scannerSearchTimers[target]);
        scannerSearchTimers[target]=window.setTimeout(()=>{
          delete scannerSearchTimers[target];
          renderRows(target,view.rows,columns);
        },150);
      });
    });
    $("load-preflight").addEventListener("click",()=>withButton("load-preflight",()=>loadReadiness("/api/v1/research/preflight"),"Checking…"));
    $("load-readiness").addEventListener("click",()=>withButton("load-readiness",()=>loadReadiness("/api/v1/research/phase-readiness"),"Checking…"));
    $("load-coin-analysis").addEventListener("click",()=>withButton("load-coin-analysis",loadTechnical,"Loading…"));
    $("load-technical").addEventListener("click",()=>withButton("load-technical",loadTechnical,"Loading…"));
    $("load-market-evidence").addEventListener("click",()=>withButton("load-market-evidence",loadMarketEvidence,"Loading…"));
    $("load-quality").addEventListener("click",()=>withButton("load-quality",loadQuality,"Checking…"));
    $("backend-url").addEventListener("input",()=> $("backend-url").setCustomValidity(""));
    $("test-connection").addEventListener("click",()=>withButton("test-connection",async()=>{connectSettings();const result=await loadHealth();if(result?.status==="SUPERSEDED")return result;setText("settings-status","Backend health endpoint responded successfully.");return result;},"Testing…"));
    $("clear-credentials").addEventListener("click",()=>{invalidateScanRequests();invalidateQualityRequest();invalidateReadinessRequests();cancelAnalysisRequests();invalidateHealthRequests();state.base="";state.token="";clearConnectionScopedData("Backend credentials cleared · previous backend data removed");$("backend-url").value="";$("backend-url").setCustomValidity("");$("backend-token").value="";setText("health-status","Not checked · backend credentials cleared");setText("scan-state","Backend credentials cleared · scan unavailable");setText("quality-state","Backend credentials cleared · quality check unavailable");setConnection(false,"Not connected");setText("settings-status","Credentials cleared from page memory.");toast("Connection credentials cleared.","success");});
    $("display-timezone").addEventListener("change",e=>{state.displayTimezone=e.target.value;refreshDisplayedTimestamps();setText("settings-status","Display timezone applied for this page session.");});
    $("default-market").addEventListener("change",e=>{invalidateScanRequests();setText("scan-state","Market selection changed · run a new scan");$("global-market").value=e.target.value;state.market=e.target.value;document.querySelectorAll(".market-tab").forEach(b=>b.classList.toggle("active",b.dataset.market===state.market));invalidateChartView();});
    $("default-timeframe").addEventListener("change",e=>{$("global-timeframe").value=e.target.value;state.timeframe=e.target.value;$("analysis-timeframes").querySelectorAll("button").forEach(b=>b.classList.toggle("active",b.textContent===state.timeframe));invalidateChartView();});
    window.addEventListener("hashchange",()=>navigate(location.hash.slice(1)||"overview"));
  }
  initTimeframes();applyDisplayPreferences();bind();navigate(location.hash.slice(1)||"overview");setConnection(false,"Backend not configured");
})();