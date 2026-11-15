"use strict";
const http=require("node:http"),fs=require("node:fs"),path=require("node:path");
const root=path.resolve(__dirname,"../dashboard");
const types={".html":"text/html; charset=utf-8",".css":"text/css; charset=utf-8",".js":"text/javascript; charset=utf-8"};
http.createServer((req,res)=>{
 const pathname=decodeURIComponent(new URL(req.url,"http://127.0.0.1").pathname);
 const target=path.resolve(root,"."+pathname);
 if(target!==root&&!target.startsWith(root+path.sep)){res.writeHead(403).end("Forbidden");return;}
 fs.readFile(pathname==="/" ? path.join(root,"index.html"):target,(err,data)=>{
  if(err){res.writeHead(404).end("Not found");return;}
  const contentPath=pathname==="/" ? path.join(root,"index.html") : target;
  res.writeHead(200,{"content-type":types[path.extname(contentPath)]||"application/octet-stream","cache-control":"no-store","x-content-type-options":"nosniff"});res.end(data);
 });
}).listen(4173,"127.0.0.1",()=>process.stdout.write("Dashboard QA server listening on 4173\n"));
