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
   const errors=[];page.on("pageerror",e=>errors.push(e.message));
   const fixtureRows=Array.from({length:1000},(_,i)=>({symbol:"COIN"+String(i).padStart(4,"0")+"USDT",base_asset:"COIN"+String(i).padStart(4,"0"),quote_asset:"USDT",last_price:(i+1).toFixed(4),quote_volume_24h:String((1000-i)*1250),price_change_percent_24h:String((i%21)-10),status:"TRADING"}));
   await page.route("https://qa.invalid/**",async route=>{
    const url=new URL(route.request().url());
    if(url.pathname==="/health")return route.fulfill({status:200,contentType:"application/json",body:JSON.stringify({status:"ok"})});
    if(url.pathname==="/api/v1/markets/spot/scan")return route.fulfill({status:200,contentType:"application/json",body:JSON.stringify({status:"ok",source:"deterministic QA fixture",eligible_count:1000,scanned_count:1000,failed_count:0,matched_count:1000,symbols:fixtureRows})});
    return route.fulfill({status:404,contentType:"application/json",body:JSON.stringify({detail:"Unmocked QA route"})});
   });
   const start=Date.now();const response=await page.goto("http://127.0.0.1:4173/",{waitUntil:"domcontentloaded"});const loadMs=Date.now()-start;
   const contentType=response&&response.headers()["content-type"];if(!response||!response.ok()||!contentType||!contentType.includes("text/html"))throw new Error("Dashboard root did not return successful HTML (status="+(response&&response.status())+", content-type="+contentType+")");
   await page.locator(".app-shell").waitFor({state:"visible"});
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
   await page.locator('#main-nav .nav-link[data-page="spot-scanner"]').click();
   const scanStart=Date.now();await page.locator("#scan-spot").click();
   await page.waitForFunction(()=>document.querySelector("#spot-count")?.textContent.includes("1000 matching / 1000 returned"));
   const scanRenderMs=Date.now()-scanStart,visibleRows=await page.locator("#spot-rows tr").count();
   const sortStart=Date.now();await page.locator('table[aria-label="Spot market scan results"] thead th').nth(4).click();
   await page.waitForFunction(()=>document.querySelector('table[aria-label="Spot market scan results"] thead th:nth-child(5)')?.getAttribute("aria-sort")==="ascending");
   const sortMs=Date.now()-sortStart;
   const pager=page.locator('.table-pager button[aria-label="Next scanner page"]');
   const pageStart=Date.now();await pager.click();await page.getByText(/page 2\/10/).waitFor();const paginationMs=Date.now()-pageStart;
   await page.locator('.table-pager button[aria-label="Previous scanner page"]').click();await page.getByText(/page 1\/10/).waitFor();
   const searchStart=Date.now();await page.locator("#spot-search").fill("COIN0999USDT");
   await page.waitForFunction(()=>document.querySelector("#spot-count")?.textContent.includes("1 matching / 1000 returned"));
   const searchMs=Date.now()-searchStart,searchRows=await page.locator("#spot-rows tr").count();
   await page.locator("#spot-search").fill("");await page.waitForFunction(()=>document.querySelector("#spot-count")?.textContent.includes("1000 matching / 1000 returned"));
   await cdp.send("HeapProfiler.collectGarbage");
   const readMetrics=async()=>{const m=await cdp.send("Performance.getMetrics");return Object.fromEntries(m.metrics.map(x=>[x.name,x.value]));};
   const baselineMetrics=await readMetrics();
   const captureSnapshot=async name=>{const chunks=[];const listener=({chunk})=>chunks.push(chunk);cdp.on("HeapProfiler.addHeapSnapshotChunk",listener);await cdp.send("HeapProfiler.takeHeapSnapshot",{reportProgress:false});cdp.off("HeapProfiler.addHeapSnapshotChunk",listener);fs.writeFileSync(path.join(out,name),chunks.join(""));};
   await captureSnapshot("heap-cpu-"+rate+"x-baseline.heapsnapshot");
   const cycleStart=Date.now();
   for(let cycle=0;cycle<5;cycle++){
    await page.locator("#spot-search").fill("COIN0999USDT");
    await page.waitForFunction(()=>document.querySelector("#spot-count")?.textContent.includes("1 matching / 1000 returned"));
    await page.locator("#spot-search").fill("");
    await page.waitForFunction(()=>document.querySelector("#spot-count")?.textContent.includes("1000 matching / 1000 returned"));
    await page.locator('table[aria-label="Spot market scan results"] thead th').nth(4).click();
    await page.locator('.table-pager button[aria-label="Next scanner page"]').click();
    await page.getByText(/page 2\/10/).waitFor();
    await page.locator('.table-pager button[aria-label="Previous scanner page"]').click();
    await page.getByText(/page 1\/10/).waitFor();
   }
   const repeatedCyclesMs=Date.now()-cycleStart;
   await cdp.send("HeapProfiler.collectGarbage");
   const finalMetrics=await readMetrics();
   await captureSnapshot("heap-cpu-"+rate+"x-after-5-cycles.heapsnapshot");
   results.samples.push({cpu_throttle:rate,initial_navigation_ms:loadMs,navigation_samples:navSamples,scanner_fixture:{rows:fixtureRows.length,visible_rows_first_page:visibleRows,scan_render_ms:scanRenderMs,sort_ms:sortMs,search_ms:searchMs,search_visible_rows:searchRows,pagination_ms:paginationMs,repeated_5_cycle_ms:repeatedCyclesMs,heap_used_before_cycles_bytes:baselineMetrics.JSHeapUsedSize,heap_used_after_cycles_bytes:finalMetrics.JSHeapUsedSize,heap_delta_bytes:finalMetrics.JSHeapUsedSize-baselineMetrics.JSHeapUsedSize,dom_nodes_after_cycles:finalMetrics.Nodes},heap_used_bytes:finalMetrics.JSHeapUsedSize,heap_total_bytes:finalMetrics.JSHeapTotalSize,dom_nodes:finalMetrics.Nodes,page_errors:errors});
   await context.close();
  }
  fs.writeFileSync(path.join(out,"browser-profile.json"),JSON.stringify(results,null,2));process.stdout.write(JSON.stringify(results,null,2)+"\n");
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e.stack||e)+"\n");process.exitCode=1;});
