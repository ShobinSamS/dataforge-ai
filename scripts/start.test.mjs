import test from "node:test";
import assert from "node:assert/strict";
import {createServer} from "node:http";
import {identify,portOpen,launch} from "./start.mjs";

test("detects its frontend without disturbing an occupied foreign service",async()=>{
 let known=false;
 const server=createServer((request,response)=>{response.end(known?"<title>DataForge AI — Synthetic data workspace</title>":"Other app");});
 await new Promise(done=>server.listen(0,"127.0.0.1",done));
 const port=server.address().port;
 try {
  assert.equal(await portOpen(port),true);
  await assert.rejects(()=>identify(port),/another service/);
  assert.equal(server.listening,true);
  known=true;assert.equal(await identify(port),true);
 } finally {await new Promise(done=>server.close(done));}
 assert.equal(await portOpen(port),false);
 assert.equal(await identify(port),false);
});

test("identifies the API on a custom port without accepting another service",async()=>{
 let known=false;
 const server=createServer((request,response)=>{response.setHeader("Content-Type","application/json");response.end(JSON.stringify({info:{title:known?"DataForge AI":"Another API"}}));});
 await new Promise(done=>server.listen(0,"127.0.0.1",done));
 try{const port=server.address().port;await assert.rejects(()=>identify(port,"backend"),/another service/);known=true;assert.equal(await identify(port,"backend"),true);}
 finally{await new Promise(done=>server.close(done));}
 for(const apiPort of [0,5173,65536,NaN])await assert.rejects(()=>launch({browser:false,apiPort}),/API port/);
});
