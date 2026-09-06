// Adapter contract and actual Node-to-Python execution, not a live Cline session.
import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp,rm,access} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve,relative} from 'node:path';
import {invoke,plugin} from '../plugin/index.js';
import {fork} from 'node:child_process';
import {fileURLToPath} from 'node:url';

async function workspace(t) {
  const base=resolve(tmpdir());
  const dir=await mkdtemp(join(base,'kch-ops-test-'));
  t.after(async()=>{
    const part=relative(base,dir);
    assert(part.startsWith('kch-ops-test-') && !part.includes('..'));
    await rm(dir,{recursive:true,force:false});
  });
  return dir;
}
test('actual bridge: status is read-only and does not create a database',async t=>{
  const dir=await workspace(t);
  const result=await invoke('status',{},dir);
  assert.equal(result.event_count,0);
  await assert.rejects(access(join(dir,'.kch','operational-supervision','agents.sqlite3')));
});
test('actual bridge: forbidden worker model is rejected',async t=>{
  const dir=await workspace(t);
  await assert.rejects(invoke('dispatch-preflight',{model:'gpt-6-astra'},dir));
});
test('actual bridge: expired SSH lease is rejected before network access',async t=>{
  const dir=await workspace(t);
  await assert.rejects(invoke('vps-ssh',{profile:{host:'fixture.invalid',user:'root',authorization_ref:'test-fixture',expires_at_utc:'2000-01-01T00:00:00Z'}},dir),/SSH_LEASE_EXPIRED/);
});
test('adapter contract: two tools register, status executes through Python',async t=>{
  const dir=await workspace(t);const registered=[];
  plugin.setup({registerTool:tool=>registered.push(tool)},{workspaceInfo:{rootPath:dir}});
  assert.deepEqual(registered.map(x=>x.name),['kch_vps_diagnose','kch_agents_observe']);
  const status=await registered[1].execute({action:'status'});
  assert.equal(status.event_count,0);
});
test('native Cline bootstrap loads both tools and executes status',{
  skip:!process.env.KCH_CLINE_BOOTSTRAP || !process.env.KCH_CODE_EXECUTABLE,
  timeout:100000
},async t=>{
  const dir=await workspace(t);
  const child=fork(process.env.KCH_CLINE_BOOTSTRAP,[],{
    execPath:process.env.KCH_CODE_EXECUTABLE,execArgv:[],cwd:dir,
    env:{...process.env,ELECTRON_RUN_AS_NODE:'1'},windowsHide:true,
    stdio:['ignore','pipe','pipe','ipc']});
  let serial=0,stderr='';const pending=new Map();
  child.stderr.setEncoding('utf8');child.stderr.on('data',b=>stderr=(stderr+b).slice(-4000));
  child.stdout.resume();
  const ended=new Promise(resolve=>{
    child.once('exit',(code,signal)=>{
      for(const item of pending.values()){clearTimeout(item.timer);item.reject(new Error(`Native host exited ${code}: ${stderr}`));}
      pending.clear();resolve({code,signal});
    });
    child.once('error',error=>{
      for(const item of pending.values()){clearTimeout(item.timer);item.reject(error);}
      pending.clear();resolve({code:null,error:String(error)});
    });
  });
  child.on('message',message=>{
    if(message.type!=='response')return;
    const item=pending.get(message.id);if(!item)return;
    pending.delete(message.id);clearTimeout(item.timer);
    message.ok?item.resolve(message.result):item.reject(new Error(JSON.stringify(message.error)));
  });
  function call(method,args){return new Promise((resolve,reject)=>{
    const id=++serial;const timer=setTimeout(()=>{pending.delete(id);reject(new Error(`Native IPC timeout: ${method}`));},30000);
    pending.set(id,{resolve,reject,timer});
    child.send({type:'call',id,method,args},error=>{if(error){clearTimeout(timer);pending.delete(id);reject(error);}});
  });}
  try {
    const init=await call('initialize',{
      pluginPaths:[fileURLToPath(new URL('../plugin/index.js',import.meta.url))],cwd:dir,
      session:{sessionId:'kch-ops-native-integration-test'},client:{name:'kch-ops-verifier'},
      workspaceInfo:{rootPath:dir},loggerEnabled:true});
    assert.equal(init.failures.length,0,JSON.stringify(init.failures));
    assert.equal(init.warnings.length,0,JSON.stringify(init.warnings));
    assert.equal(init.plugins.length,1);
    const entry=init.plugins[0];assert.equal(entry.contributions.tools.length,2);
    const tool=entry.contributions.tools.find(x=>x.name==='kch_agents_observe');assert(tool);
    const result=await call('executeTool',{pluginId:entry.pluginId,contributionId:tool.id,input:{action:'status'}});
    assert.equal(result.event_count,0);
  } finally {
    if(child.connected)child.disconnect();
    const timer=setTimeout(()=>child.kill(),5000);
    const exit=await ended;clearTimeout(timer);
    assert.equal(exit.code,0,JSON.stringify(exit));
  }
});
