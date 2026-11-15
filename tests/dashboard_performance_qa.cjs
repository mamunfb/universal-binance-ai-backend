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
   const start=Date.now();await page.goto("http://127.0.0.1:4173",{waitUntil:"networkidle"});const loadMs=Date.now()-start;
   const nav=page.locator("#main-nav .nav-link"),count=await nav.count(),navSamples=[];
   for(let i=0;i<Math.min(count,12);i++){
    const link=nav.nth(i),pageName=await link.getAttribute("data-page");
    if(await page.locator("#mobile-menu").isVisible())await page.locator("#mobile-menu").click();
    const t=Date.now();await link.click();await page.waitForFunction(name=>document.querySelector("#page-crumb")?.textContent?.trim()!=="",pageName);await page.waitForTimeout(30);
    navSamples.push({page:pageName,duration_ms:Date.now()-t,sidebar_closed:!(await page.locator("#sidebar").evaluate(el=>el.classList.contains("open")))});
   }
   await cdp.send("HeapProfiler.collectGarbage");
   const metrics=await cdp.send("Performance.getMetrics"),metricMap=Object.fromEntries(metrics.metrics.map(x=>[x.name,x.value]));
   const chunks=[];cdp.on("HeapProfiler.addHeapSnapshotChunk",({chunk})=>chunks.push(chunk));
   await cdp.send("HeapProfiler.takeHeapSnapshot",{reportProgress:false});
   fs.writeFileSync(path.join(out,"heap-cpu-"+rate+"x.heapsnapshot"),chunks.join(""));
   results.samples.push({cpu_throttle:rate,initial_navigation_ms:loadMs,navigation_samples:navSamples,heap_used_bytes:metricMap.JSHeapUsedSize,heap_total_bytes:metricMap.JSHeapTotalSize,dom_nodes:metricMap.Nodes,page_errors:errors});
   await context.close();
  }
  fs.writeFileSync(path.join(out,"browser-profile.json"),JSON.stringify(results,null,2));process.stdout.write(JSON.stringify(results,null,2)+"\n");
 }finally{await browser.close();}
})().catch(e=>{process.stderr.write(String(e.stack||e)+"\n");process.exitCode=1;});
