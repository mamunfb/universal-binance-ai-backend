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
  const state = {base:"", token:"", market:"SPOT", symbol:"BTCUSDT", timeframe:"1h", lastScan:null, lastHealth:null, lastAnalysis:null};
  let activeScanSequence=0;
  const esc = (value) => String(value ?? "—").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const setText = (id, value) => { const el=$(id); if(el) el.textContent = value == null || value === "" ? "—" : String(value); };
  const toast = (message, type="info") => { const el=document.createElement("div"); el.className="toast "+(type==="error"?"error":type==="success"?"success":""); el.textContent=message; $("toast-region").append(el); window.setTimeout(()=>el.remove(),4500); };
  const formatNumber = (value) => value===null || value===undefined || value==="" ? "—" : (Number.isFinite(Number(value)) ? new Intl.NumberFormat(undefined,{maximumFractionDigits:2}).format(Number(value)) : "—");
  const json = (value) => JSON.stringify(value,null,2);
  const showJson = (id, value) => { const el=$(id); if(el) el.textContent=json(value); };
  const safeArray = (obj, keys=[]) => { if(Array.isArray(obj)) return obj; for(const key of keys) if(Array.isArray(obj?.[key])) return obj[key]; return []; };
  const setConnection = (ok, label) => { const dot=$("connection-dot"); dot.className="status-dot "+(ok?"good":"bad"); setText("connection-label",label); $("connection-banner").querySelector(".status-dot").className="status-dot "+(ok?"good":"bad"); $("connection-banner").querySelector("span:nth-child(2)").textContent=label; };
  function navigate(page) {
    const known = PAGE_TITLES[page] ? page : "overview";
    document.querySelectorAll(".page-view").forEach(p=>p.classList.toggle("active",p.id==="page-"+known || (known!=="overview" && !document.getElementById("page-"+known) && p.id==="page-placeholder")));
    document.querySelectorAll(".nav-link").forEach(a=>a.classList.toggle("active",a.dataset.page===known));
    const title=PAGE_TITLES[known] || known;
    setText("page-crumb",title);
    if(!document.getElementById("page-"+known)) { setText("placeholder-title",title); setText("placeholder-description", "This research area is included in the approved dashboard scope. Its API capability must be verified before live data is shown."); }
    if(known==="coin-analysis") syncAnalysisHeader();
    document.querySelector(".sidebar").classList.remove("open");
  }
  function apiHeaders() { const h={"Accept":"application/json"}; if(state.token) h.Authorization="Bearer "+state.token; return h; }
  async function api(path, {method="GET", body, timeout=20000}={}) {
    if(!state.base) throw new Error("Configure the private backend URL in Settings first.");
    const controller=new AbortController(); const timer=window.setTimeout(()=>controller.abort(),timeout);
    try {
      const response=await fetch(state.base.replace(/\/$/,"")+path,{method,headers:{...apiHeaders(),...(body?{"Content-Type":"application/json"}:{})},body:body?JSON.stringify(body):undefined,signal:controller.signal,credentials:"omit",cache:"no-store"});
      const raw=await response.text(); let data=null; try{data=raw?JSON.parse(raw):null;}catch{throw new Error("Backend returned a non-JSON response (HTTP "+response.status+").");}
      if(!response.ok){const detail=data?.detail||data?.message||("HTTP "+response.status);throw new Error(typeof detail==="string"?detail:json(detail));}
      return data;
    } catch(error) { if(error.name==="AbortError") throw new Error("Request timed out."); throw error; }
    finally { window.clearTimeout(timer); }
  }
  async function withButton(button, task, busyText="Loading…") {
    const el=$(button); if(!el) return; const original=el.textContent; el.disabled=true; el.textContent=busyText;
    try { await task(); } catch(error) { toast(error.message,"error"); } finally { el.disabled=false; el.textContent=original; }
  }
  function setMetric(key,value){setText("metric-"+key,formatNumber(value));}
  function extractCount(data, names) { for(const name of names){ const value=data?.[name]; if(value!==null && value!==undefined && value!=="" && !(typeof value==="string"&&value.trim()==="") && typeof value!=="boolean" && Number.isFinite(Number(value)) && Number(value)>=0) return Number(value); } return null; }
  function renderScanSummary(data) {
    state.lastScan=data;
    const eligible=extractCount(data,["eligible_count","eligible_symbols","eligible","total_eligible","total_symbols"]);
    const scanned=extractCount(data,["scanned_count","scanned_symbols","scanned","attempted_count"]);
    const failed=extractCount(data,["failed_count","failed_symbols","failed"]);
    setMetric("eligible",eligible); setMetric("scanned",scanned); setMetric("failed",failed);
    setMetric("qualified",extractCount(data,["qualified_count","matched_count","candidate_count"]));
    const summary=$("scan-summary"); summary.innerHTML="";
    const rows=[
      ["Market",state.market],["Eligible",eligible],["Scanned",scanned],["Matched",extractCount(data,["matched_count","match_count"])],
      ["Failed",failed],["Status",data.status||data.scan_status||"Returned"],["Source",data.source||"Backend response"],["Updated",data.generated_at||data.timestamp||data.updated_at||"Not supplied"]
    ];
    rows.forEach(([label,value])=>{const line=document.createElement("div");line.className="status-list";const row=document.createElement("div");const a=document.createElement("span");a.textContent=label;const b=document.createElement("b");b.textContent=value==null?"Not supplied":String(value);row.append(a,b);line.append(row);summary.append(line);});
    setText("scan-state",data.status||data.scan_status||"Response received");
    setText("overview-updated",data.generated_at||data.timestamp||data.updated_at||"Timestamp not supplied");
  }
  async function loadHealth() {
    try { const result=await api("/health"); state.lastHealth=result; setText("health-status",result.status||"Healthy response"); setConnection(true,"Backend reachable"); return result; }
    catch(error){setText("health-status","Unavailable");setConnection(false,"Backend unavailable: "+error.message);throw error;}
  }
  function invalidateScanRequests(){activeScanSequence++;}
  async function scanMarket(market) {
    const requestSequence=++activeScanSequence;
    const marketChanged=state.market!==market; state.market=market; $("global-market").value=market; if(marketChanged) invalidateChartView(); document.querySelectorAll(".market-tab").forEach(b=>b.classList.toggle("active",b.dataset.market===market));
    let path;
    if(market==="SPOT") { const quote=($("spot-quote")?.value||"").trim().toUpperCase(); path="/api/v1/markets/spot/scan"+(quote?"?quote_asset="+encodeURIComponent(quote):""); }
    else if(market==="USD_M") path="/api/v1/markets/futures/usdm/scan";
    else path="/api/v1/markets/futures/coinm/scan";
    let data; try{data=await api(path);}catch(error){if(requestSequence!==activeScanSequence)return{status:"SUPERSEDED",market};throw error;}
    if(requestSequence!==activeScanSequence)return{status:"SUPERSEDED",market};
    renderScanSummary(data);
    const rows=safeArray(data,["symbols","markets","results","data"]);
    if(market==="SPOT") renderRows("spot-rows",rows,6);
    if(market==="USD_M") renderRows("usdm-rows",rows,5);
    if(market==="COIN_M") renderRows("coinm-rows",rows,5);
    renderScannerMeta(market,data,rows);
    toast(market+" scan response received. Check coverage and failure counts.","success");
    return data;
  }
  function renderScannerMeta(market,data,rows) {
    const prefix=market==="USD_M"?"usdm":market==="COIN_M"?"coinm":"spot";
    const countNames={
      eligible:["eligible_count","eligible_symbols","eligible","total_eligible","total_symbols"],
      scanned:["scanned_count","scanned_symbols","scanned","attempted_count"],
      failed:["failed_count","failed_symbols","failed"],
      matched:["matched_count","match_count","qualified_count","candidate_count"]
    };
    const details=[
      "Returned rows: "+rows.length,
      "Status: "+(data.status||data.scan_status||"Not supplied"),
      "Eligible: "+(extractCount(data,countNames.eligible)??"Not supplied"),
      "Scanned: "+(extractCount(data,countNames.scanned)??"Not supplied"),
      "Failed: "+(extractCount(data,countNames.failed)??"Not supplied"),
      "Matched: "+(extractCount(data,countNames.matched)??"Not supplied"),
      "Source: "+(data.source||"Not supplied"),
      "Timestamp: "+(data.generated_at||data.timestamp||data.updated_at||"Not supplied")
    ];
    setText(prefix+"-coverage",details.join(" · "));
    if(market!=="SPOT") setText(prefix+"-count",rows.length.toLocaleString()+" returned");
  }
  const tableViews = {};
  function renderRows(target, rows, columns) {
    const body=$(target); if(!body) return;
    const keys=columns===6?["symbol","base_asset","quote_asset","last_price","quote_volume_24h","status"]:["symbol","last_price","quote_volume_24h","price_change_percent_24h","status"];
    const view=tableViews[target]||(tableViews[target]={page:0,pageSize:100,sortKey:"symbol",direction:1,rows:[],query:""});
    view.rows=Array.isArray(rows)?rows.slice():[];
    const filtered=view.rows.filter(item=>!view.query||keys.some(key=>String(item?.[key]??"").toUpperCase().includes(view.query)));
    filtered.sort((a,b)=>{const av=a?.[view.sortKey],bv=b?.[view.sortKey];const numericValue=v=>v!==null&&v!==undefined&&!(typeof v==="string"&&v.trim()==="")&&typeof v!=="boolean"&&Number.isFinite(Number(v))?Number(v):null;const an=numericValue(av),bn=numericValue(bv);const numeric=an!==null&&bn!==null;const cmp=numeric?an-bn:String(av??"").localeCompare(String(bv??""),undefined,{numeric:true,sensitivity:"base"});return cmp*view.direction;});
    const pages=Math.max(1,Math.ceil(filtered.length/view.pageSize));view.page=Math.min(view.page,pages-1);
    body.replaceChildren();
    const visible=filtered.slice(view.page*view.pageSize,(view.page+1)*view.pageSize);
    if(!visible.length){const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=columns;td.className="empty-cell";td.textContent=view.rows.length?"No rows match the current filter.":"No market rows were returned. Inspect the raw response and scan status.";tr.append(td);body.append(tr);}
    visible.forEach(item=>{const tr=document.createElement("tr");keys.forEach(key=>{const td=document.createElement("td");td.textContent=item?.[key]===undefined?"—":String(item[key]);tr.append(td);});body.append(tr);});
    const table=body.closest("table"),headers=table?.querySelectorAll("thead th")||[];
    headers.forEach((th,index)=>{th.title="Sort by "+keys[index];th.setAttribute("aria-sort",keys[index]===view.sortKey?(view.direction===1?"ascending":"descending"):"none");th.style.cursor="pointer";});
    let pager=table?.parentElement?.parentElement?.querySelector(".table-pager");
    if(table&&!pager){pager=document.createElement("div");pager.className="table-pager";pager.style.cssText="display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 14px;color:var(--muted,#9aa);font-size:12px";table.parentElement.parentElement.append(pager);}
    if(pager){pager.replaceChildren();const info=document.createElement("span");info.textContent=filtered.length.toLocaleString()+" matching / "+view.rows.length.toLocaleString()+" returned · page "+(view.page+1)+"/"+pages+" · "+view.pageSize+" per page";const controls=document.createElement("span");const prev=document.createElement("button"),next=document.createElement("button");prev.type=next.type="button";prev.textContent="Previous";next.textContent="Next";prev.disabled=view.page===0;next.disabled=view.page>=pages-1;prev.addEventListener("click",()=>{view.page--;renderRows(target,view.rows,columns);});next.addEventListener("click",()=>{view.page++;renderRows(target,view.rows,columns);});controls.append(prev,next);pager.append(info,controls);}
    if(target==="spot-rows")setText("spot-count",filtered.length.toLocaleString()+" matching / "+view.rows.length.toLocaleString()+" returned");
    if(!view.headersBound&&table){view.headersBound=true;headers.forEach((th,index)=>th.addEventListener("click",()=>{const key=keys[index];view.direction=view.sortKey===key?-view.direction:1;view.sortKey=key;view.page=0;renderRows(target,view.rows,columns);}));}
  }
  function syncAnalysisHeader(){state.symbol=$("global-symbol").value.trim().toUpperCase()||"BTCUSDT";state.market=$("global-market").value;state.timeframe=$("global-timeframe").value;setText("analysis-title",state.symbol+" · "+state.market);setText("analysis-subtitle","Timeframe "+state.timeframe+" · "+state.market+" · Research-only analysis");}
  function invalidateChartView(message="Selection changed. Run analysis to load matching candles.") {
    window.DashboardCharts.invalidate();
    const host=$("chart-placeholder"); if(host) host.replaceChildren(document.createTextNode(message));
    setText("chart-state","Awaiting analysis"); setText("technical-summary","Run analysis to load indicators for the current selection.");
    setText("analysis-output","No chart response for the current selection.");
  }
  async function loadMarketEvidence() {
    syncAnalysisHeader(); invalidateChartView("Market evidence endpoint does not provide candle chart data."); const path="/api/v1/analysis/market-evidence/"+encodeURIComponent(state.symbol);
    const data=await api(path);state.lastAnalysis=data;showJson("analysis-output",data);setText("chart-state","Evidence loaded; candle chart not provided by this endpoint");setText("technical-summary",data.summary||data.status||"Market evidence returned. Inspect evidence payload.");
    toast("Market evidence loaded.","success");return data;
  }
  async function loadTechnical() {
    syncAnalysisHeader();
    const data=await window.DashboardCharts.load(api,state.market,state.symbol,state.timeframe);
    state.lastAnalysis=data;toast("Verified candle chart and descriptive indicators loaded.","success");return data;
  }
  function initTimeframes() {
    ["global-timeframe","default-timeframe","quality-interval"].forEach(id=>{const select=$(id);select.replaceChildren();TIMEFRAMES.forEach(tf=>{const option=document.createElement("option");option.value=tf;option.textContent=tf;select.append(option);});});
    $("global-timeframe").value="1h";$("default-timeframe").value="1h";const qualitySelect=$("quality-interval");qualitySelect.replaceChildren();["1m","3m","5m","15m","30m","1h","2h","4h","6h","8h","12h","1d"].forEach(tf=>{const option=document.createElement("option");option.value=tf;option.textContent=tf;qualitySelect.append(option);});qualitySelect.value="1h";
    const strip=$("analysis-timeframes");TIMEFRAMES.forEach(tf=>{const button=document.createElement("button");button.className="timeframe-btn"+(tf==="1h"?" active":"");button.type="button";button.textContent=tf;button.addEventListener("click",()=>{state.timeframe=tf;$("global-timeframe").value=tf;strip.querySelectorAll("button").forEach(b=>b.classList.toggle("active",b===button));syncAnalysisHeader();withButton("load-coin-analysis",loadTechnical,"Loading…");});strip.append(button);});
  }
  async function loadQuality() {
    const market=$("quality-market").value,symbol=$("quality-symbol").value.trim().toUpperCase(),interval=$("quality-interval").value,lookback=Number($("quality-lookback").value);
    if(!symbol) throw new Error("Enter a symbol.");if(!Number.isInteger(lookback)||lookback<1||lookback>2160)throw new Error("Lookback must be 1–2160 hours.");
    const q=new URLSearchParams({interval,lookback_hours:String(lookback)});
    const data=await api("/api/v1/quality/market-data/"+encodeURIComponent(market)+"/"+encodeURIComponent(symbol)+"?"+q);
    showJson("quality-output",data);setText("quality-state",data.status||"Report received");toast("Data quality report loaded.","success");return data;
  }
  function connectSettings() {
    const url=$("backend-url").value.trim().replace(/\/$/,"");if(!/^https:\/\//i.test(url) && !/^http:\/\/localhost(?::\d+)?$/i.test(url) && !/^http:\/\/127\.0\.0\.1(?::\d+)?$/i.test(url))throw new Error("Use HTTPS for remote backends. HTTP is allowed only for localhost.");
    state.base=url;state.token=$("backend-token").value.trim();setText("settings-status","Connection details held in page memory only.");toast("Connection settings applied for this page session.","success");
  }
  function bind() {
    document.querySelectorAll(".nav-link").forEach(a=>a.addEventListener("click",e=>{e.preventDefault();const page=a.dataset.page; if(PAGE_TITLES[page] && document.getElementById("page-"+page)) navigate(page); else navigate(page); history.replaceState(null,"","#"+page);}));
    $("mobile-menu").addEventListener("click",()=>$("sidebar").classList.toggle("open"));
    $("open-settings").addEventListener("click",()=>{navigate("settings");history.replaceState(null,"","#settings");});
    $("banner-settings").addEventListener("click",()=>navigate("settings"));
    $("refresh-page").addEventListener("click",()=>{const page=location.hash.slice(1)||"overview";if(page==="overview")withButton("refresh-page",async()=>{await loadHealth();await scanMarket(state.market);},"Refreshing");else if(page==="reliability")withButton("refresh-page",loadQuality,"Refreshing");else if(page==="coin-analysis")withButton("refresh-page",loadTechnical,"Refreshing");else toast("No verified refresh action is mapped for this page yet.");});
    $("global-market").addEventListener("change",e=>{invalidateScanRequests();state.market=e.target.value;document.querySelectorAll(".market-tab").forEach(b=>b.classList.toggle("active",b.dataset.market===state.market));invalidateChartView();});
    $("global-symbol").addEventListener("change",()=>{state.symbol=$("global-symbol").value.trim().toUpperCase();syncAnalysisHeader();invalidateChartView();});
    $("global-timeframe").addEventListener("change",()=>{state.timeframe=$("global-timeframe").value;syncAnalysisHeader();invalidateChartView();});
    document.querySelectorAll(".market-tab").forEach(b=>b.addEventListener("click",()=>{invalidateScanRequests();state.market=b.dataset.market;document.querySelectorAll(".market-tab").forEach(x=>x.classList.toggle("active",x===b));$("global-market").value=state.market;invalidateChartView();}));
    $("run-market-scan").addEventListener("click",()=>withButton("run-market-scan",()=>scanMarket(state.market),"Scanning…"));
    $("scan-spot").addEventListener("click",()=>withButton("scan-spot",()=>scanMarket("SPOT"),"Scanning…"));
    $("scan-usdm").addEventListener("click",()=>withButton("scan-usdm",()=>scanMarket("USD_M"),"Scanning…"));
    $("scan-coinm").addEventListener("click",()=>withButton("scan-coinm",()=>scanMarket("COIN_M"),"Scanning…"));
    [["spot-search","spot-rows",6],["usdm-search","usdm-rows",5],["coinm-search","coinm-rows",5]].forEach(([input,target,columns])=>{
      $(input).addEventListener("input",e=>{const view=tableViews[target]||(tableViews[target]={page:0,pageSize:100,sortKey:"symbol",direction:1,rows:[],query:""});view.query=e.target.value.trim().toUpperCase();view.page=0;renderRows(target,view.rows,columns);});
    });
    $("load-preflight").addEventListener("click",()=>withButton("load-preflight",async()=>showJson("readiness-output",await api("/api/v1/research/preflight")),"Checking…"));
    $("load-readiness").addEventListener("click",()=>withButton("load-readiness",async()=>showJson("readiness-output",await api("/api/v1/research/phase-readiness")),"Checking…"));
    $("load-coin-analysis").addEventListener("click",()=>withButton("load-coin-analysis",loadTechnical,"Loading…"));
    $("load-technical").addEventListener("click",()=>withButton("load-technical",loadTechnical,"Loading…"));
    $("load-market-evidence").addEventListener("click",()=>withButton("load-market-evidence",loadMarketEvidence,"Loading…"));
    $("load-quality").addEventListener("click",()=>withButton("load-quality",loadQuality,"Checking…"));
    $("test-connection").addEventListener("click",()=>withButton("test-connection",async()=>{connectSettings();await loadHealth();setText("settings-status","Backend health endpoint responded successfully.");},"Testing…"));
    $("clear-credentials").addEventListener("click",()=>{state.base="";state.token="";$("backend-url").value="";$("backend-token").value="";setConnection(false,"Not connected");setText("settings-status","Credentials cleared from page memory.");toast("Connection credentials cleared.","success");});
    $("default-market").addEventListener("change",e=>{invalidateScanRequests();$("global-market").value=e.target.value;state.market=e.target.value;invalidateChartView();});
    $("default-timeframe").addEventListener("change",e=>{$("global-timeframe").value=e.target.value;state.timeframe=e.target.value;invalidateChartView();});
    window.addEventListener("hashchange",()=>navigate(location.hash.slice(1)||"overview"));
  }
  initTimeframes();bind();navigate(location.hash.slice(1)||"overview");setConnection(false,"Backend not configured");
})();