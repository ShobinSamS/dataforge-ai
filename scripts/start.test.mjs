import test from "node:test";
import assert from "node:assert/strict";
import {createServer} from "node:http";
import {identify,portOpen} from "./start.mjs";

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
