"use strict";
const fs=require("node:fs"),path=require("node:path");
const {chromium}=require("playwright");
(async()=>{
 const out=path.resolve("artifacts/performance");fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,args:["--no-sandbox"]});
 const results={metadata:{commit:process.env.GITHUB_SHA||"local",node:process.version,browser:browser.version(),viewport:{width:390,height:844}},samples:[]};
 try{
  for(const rate of [1,4]){
   const context=await browser.newContext({viewport:{width:390,height:844}}),page=await context.newPage();
   const cdp=await context.newCDPSession(page);await cdp.send("Performance.enable");await cdp.send("HeapProfiler.enable");await cdp.send("Emulation.setCPUThrottlingRate",{rate});
   const errors=[],apiEvents=[];page.on("pageerror",e=>errors.push(e.message));page.on("requestfailed",r=>apiEvents.push({type:"requestfailed",url:r.url(),error:r.failure()?.errorText}));page.on("response",r=>{if(r.url().startsWith("https://qa.invalid/"))apiEvents.push({type:"response",url:r.url(),status:r.status()});});
   const fixtureRows=Array.from({length:1000},(_,i)=>({symbol:"COIN"+String(i).padStart(4,"0")+"USDT",base_asset:"COIN"+String(i).padStart(4,"0"),quote_asset:"USDT",last_price:(i+1).toFixed(4),quote_volume_24h:String((1000-i)*1250),price_change_percent_24h:String((i%21)-10),status:"TRADING"}));
   const candleStart=Date.UTC(2025,0,1),candleRows=Array.from({length:250},(_,i)=>{const open=100+i*0.1,close=open+0.2;return[candleStart+i*3600000,String(open),String(Math.max(open,close)+0.5),String(open-0.5),String(close),String(1000+i),candleStart+i*3600000+3599999];});
   await page.route("https://qa.invalid/**",async route=>{
    const url=new URL(route.request().url());
    if(url.pathname==="/health")return route.fulfill({status:200,contentType:"application/json",body:JSON.stringify({status:"ok"})});
    if(url.pathname==="/api/v1/markets/spot/scan")return route.fulfill({status:200,contentType:"application/json",body:JSON.stringify({status:"ok",source:"deterministic QA fixture",eligible_count:1000,scanned_count:1000,failed_count:0,matched_count:1000,symbols:fixtureRows})});
    if(url.pathname.startsWith("/api/v1/markets/spot/klines/"))return route.fulfill({status:200,contentType:"application/json",body:JSON.stringify({status:"ok",source:"deterministic QA fixture",klines:candleRows})});
    return route.fulfill({status:404,contentType:"application/json",body:JSON.stringify({detail:"Unmocked QA route"})});
   });
   const start=Date.now();const response=await page.goto("http://127.0.0.1:4173/",{waitUntil:"domcontentloaded"});const loadMs=Date.now()-start;
   const contentType=response&&response.headers()["content-type"];if(!response||!response.ok()||!contentType||!contentType.includes("text/html"))throw new Error("Dashboard root did not return successful HTML (status="+(response&&response.status())+", content-type="+contentType+")");
   await page.locator(".app-shell").waitFor({state:"visible"});
   const initialScriptResources=await page.evaluate(()=>performance.getEntriesByType("resource").filter(entry=>entry.initiatorType==="script"&&new URL(entry.name).origin===location.origin).map(entry=>({name:new URL(entry.name).pathname.split("/").pop(),duration_ms:Math.round(entry.duration*100)/100,encoded_body_bytes:entry.encodedBodySize,decoded_body_bytes:entry.decodedBodySize,transfer_bytes:entry.transferSize})).sort((a,b)=>a.name.localeCompare(b.name)));
   if(!initialScriptResources.some(resource=>resource.name==="app.js"&&resource.decoded_body_bytes>0))throw new Error("Dashboard app.js cold-load resource timing missing or empty: "+JSON.stringify(initialScriptResources));
   if(initialScriptResources.some(resource=>resource.name==="chart.js"))throw new Error("Technical chart bundle was eagerly loaded during the initial dashboard cold load: "+JSON.stringify(initialScriptResources));
   const nav=page.locator("#main-nav .nav-link"),count=await nav.count(),navSamples=[];
   for(let i=0;i<Math.min(count,12);i++){
    const link=nav.nth(i),pageName=await link.getAttribute("data-page");
    if(await page.locator("#mobile-menu").isVisible())await page.locator("#mobile-menu").click();
    const t=Date.now();await link.click();await page.waitForFunction(name=>location.hash==="#"+name,pageName);await page.waitForTimeout(30);
    navSamples.push({page:pageName,duration_ms:Date.now()-t,sidebar_closed:!(await page.locator("#sidebar").evaluate(el=>el.classList.contains("open")))});
   }
   await page.locator("#mobile-menu").click();
   await page.locator('#main-nav .nav-link[data-page="settings"]').click();
   await page.locator("#backend-url").fill("https://qa.invalid");
   await page.locator("#test-connection").click();
   await page.getByText("Backend health endpoint responded successfully.").waitFor();
   await page.locator("#mobile-menu").click();
   await page.locator('#main-nav .nav-link[data-page="coin-analysis"]').click();
   await page.locator("#load-coin-analysis").click();
   await page.waitForFunction("typeof window.DashboardCharts === 'object'");
   await page.waitForFunction(()=>performance.getEntriesByType("resource").some(entry=>entry.initiatorType==="script"&&new URL(entry.name).origin===location.origin&&new URL(entry.name).pathname.endsWith("/chart.js")&&entry.decodedBodySize>0));
   const onDemandChartResource=await page.evaluate(()=>{const entry=performance.getEntriesByType("resource").find(item=>item.initiatorType==="script"&&new URL(item.name).origin===location.origin&&new URL(item.name).pathname.endsWith("/chart.js"));return entry?{name:new URL(entry.name).pathname.split("/").pop(),duration_ms:Math.round(entry.duration*100)/100,encoded_body_bytes:entry.encodedBodySize,decoded_body_bytes:entry.decodedBodySize,transfer_bytes:entry.transferSize}:null;});
   if(!onDemandChartResource||onDemandChartResource.decoded_body_bytes<=0)throw new Error("On-demand chart bundle did not produce a measurable resource entry.");
   await page.locator("#mobile-menu").click();
   await page.locator('#main-nav .nav-link[data-page="spot-scanner"]').click();
   const scanStart=Date.now();await page.locator("#scan-spot").click();
   try{await page.waitForFunction(()=>document.querySelector("#spot-count")?.textContent.replace(/,/g,"").includes("1000 matching / 1000 returned"),null,{timeout:10000});}catch(error){const diagnostic=await page.evaluate(()=>({scanState:document.querySelector("#scan-state")?.textContent,spotCount:document.querySelector("#spot-count")?.textContent,coverage:document.querySelector("#spot-coverage")?.textContent,toast:document.querySelector("#toast-container")?.textContent,buttonDisabled:document.querySelector("#scan-spot")?.disabled,settingsStatus:document.querySelector("#settings-status")?.textContent,hash:location.hash}));throw new Error("1000-row scanner fixture did not render. UI="+JSON.stringify(diagnostic)+" API="+JSON.stringify(apiEvents)+" pageErrors="+JSON.stringify(errors)+"; "+error.message);}
   const settleScannerDom=async()=>{const state=await page.evaluate(()=>{const rows=Array.from(document.querySelectorAll("#spot-rows tr"));let cells=0;for(const row of rows){for(const cell of row.cells){void cell.textContent;cell.getBoundingClientRect();cells++;}}return{rows:rows.length,cells};});if(state.rows!==100||state.cells!==600)throw new Error("Scanner DOM did not settle to 100 rows / 600 cells before GC metrics: "+JSON.stringify(state));};
   const scanRenderMs=Date.now()-scanStart,visibleRows=await page.locator("#spot-rows tr").count();
   const sortStart=Date.now();await page.locator('table[aria-label="Spot market scan results"] thead th').nth(4).click();
   await page.waitForFunction(()=>document.querySelector('table[aria-label="Spot market scan results"] thead th:nth-child(5)')?.getAttribute("aria-sort")==="ascending");
   const sortMs=Date.now()-sortStart;
   const pager=page.locator('#page-spot-scanner .table-pager button[aria-label="Next scanner page"]');
   const pageStart=Date.now();await pager.click();await page.getByText(/page 2\/10/).waitFor();const paginationMs=Date.now()-pageStart;
   await page.locator('#page-spot-scanner .table-pager button[aria-label="Previous scanner page"]').click();await page.getByText(/page 1\/10/).waitFor();
   const searchStart=Date.now();await page.locator("#spot-search").fill("COIN0999USDT");
   await page.waitForFunction(()=>document.querySelector("#spot-count")?.textContent.replace(/,/g,"").includes("1 matching / 1000 returned"));
   const searchMs=Date.now()-searchStart,searchRows=await page.locator("#spot-rows tr").count();
   await page.locator("#spot-search").fill("");await page.waitForFunction(()=>document.querySelector("#spot-count")?.textContent.replace(/,/g,"").includes("1000 matching / 1000 returned"));await settleScannerDom();
   await cdp.send("HeapProfiler.collectGarbage");
   const readMetrics=async()=>{const m=await cdp.send("Performance.getMetrics");return Object.fromEntries(m.metrics.map(x=>[x.name,x.value]));};
   const baselineMetrics=await readMetrics();
   const cycleStart=Date.now();
   for(let cycle=0;cycle<5;cycle++){
    await page.locator("#spot-search").fill("COIN0999USDT");
    await page.waitForFunction(()=>document.querySelector("#spot-count")?.textContent.replace(/,/g,"").includes("1 matching / 1000 returned"));
    await page.locator("#spot-search").fill("");
    await page.waitForFunction(()=>document.querySelector("#spot-count")?.textContent.replace(/,/g,"").includes("1000 matching / 1000 returned"));await settleScannerDom();
    await page.locator('table[aria-label="Spot market scan results"] thead th').nth(4).click();
    await page.locator('#page-spot-scanner .table-pager button[aria-label="Next scanner page"]').click();
    await page.getByText(/page 2\/10/).waitFor();
    await page.locator('#page-spot-scanner .table-pager button[aria-label="Previous scanner page"]').click();
    await page.getByText(/page 1\/10/).waitFor();await settleScannerDom();
   }
   const repeatedCyclesMs=Date.now()-cycleStart;
   await page.locator('table[aria-label="Spot market scan results"] thead th').nth(4).click();await page.waitForFunction(()=>document.querySelector('table[aria-label="Spot market scan results"] thead th:nth-child(5)')?.getAttribute("aria-sort")==="ascending");await settleScannerDom();
   await cdp.send("HeapProfiler.collectGarbage");
   const finalMetrics=await readMetrics();
   const failedApiEvents=apiEvents.filter(event=>event.type==="requestfailed"||(event.type==="response"&&event.status!==200));
   if(errors.length)throw new Error("Browser page errors during performance QA: "+JSON.stringify(errors));
   if(failedApiEvents.length)throw new Error("Mock API request failures or non-200 responses: "+JSON.stringify(failedApiEvents));
   const openSidebarNavigations=navSamples.filter(sample=>!sample.sidebar_closed);
   if(openSidebarNavigations.length)throw new Error("Sidebar remained open after navigation: "+JSON.stringify(openSidebarNavigations));
   if(visibleRows!==100||searchRows!==1)throw new Error("Scanner row-count regression: visible="+visibleRows+", search="+searchRows);
   results.samples.push({cpu_throttle:rate,initial_navigation_ms:loadMs,initial_script_resources:initialScriptResources,on_demand_chart_resource:onDemandChartResource,navigation_samples:navSamples,scanner_fixture:{rows:fixtureRows.length,visible_rows_first_page:visibleRows,scan_render_ms:scanRenderMs,sort_ms:sortMs,search_ms:searchMs,search_visible_rows:searchRows,pagination_ms:paginationMs,repeated_5_cycle_ms:repeatedCyclesMs,heap_used_before_cycles_bytes:baselineMetrics.JSHeapUsedSize,heap_used_after_cycles_bytes:finalMetrics.JSHeapUsedSize,gc_heap_delta_bytes:finalMetrics.JSHeapUsedSize-baselineMetrics.JSHeapUsedSize,dom_nodes_before_cycles:baselineMetrics.Nodes,dom_nodes_after_cycles:finalMetrics.Nodes,dom_nodes_delta:finalMetrics.Nodes-baselineMetrics.Nodes},heap_used_bytes:finalMetrics.JSHeapUsedSize,heap_total_bytes:finalMetrics.JSHeapTotalSize,dom_nodes:finalMetrics.Nodes,page_errors:errors});
   await context.close();
  }
  fs.writeFileSync(path.join(out,"browser-profile.json"),JSON.stringify(results,null,2));process.stdout.write(JSON.stringify(results,null,2)+"\n");
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e.stack||e)+"\n");process.exitCode=1;});
