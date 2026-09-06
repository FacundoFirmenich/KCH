import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {dirname,join} from 'node:path';
const root=dirname(dirname(fileURLToPath(import.meta.url)));

export function invoke(action,request,workspace,python=process.env.KCH_OPS_PYTHON || 'python') {
  return new Promise((resolve,reject)=>{
    const child=spawn(python,['-B',join(root,'scripts','kch_ops.py'),action,'--database',join(workspace,'.kch','operational-supervision','agents.sqlite3')],
      {cwd:workspace,env:{...process.env,PYTHONIOENCODING:'utf-8'},windowsHide:true,stdio:['pipe','pipe','pipe']});
    child.stdout.setEncoding('utf8');child.stderr.setEncoding('utf8');
    let output='',error='';let overflow=false;
    const timer=setTimeout(()=>{child.kill();reject(new Error('KCH_OPS_TIMEOUT'));},90000);
    child.stdout.on('data',b=>{output+=b;if(output.length>4_000_000){overflow=true;child.kill();}});
    child.stderr.on('data',b=>{error=(error+b).slice(-3000);});
    child.on('error',e=>{clearTimeout(timer);reject(e);});
    child.on('close',code=>{clearTimeout(timer);if(overflow)return reject(new Error('KCH_OPS_OUTPUT_LIMIT'));
      try { const result=JSON.parse(output);if(code!==0)return reject(new Error(result.error || error || 'KCH_OPS_FAILED'));resolve(result); }
      catch(e){reject(e);}});
    child.stdin.on('error',()=>{});
    child.stdin.end(JSON.stringify(request));
  });
}

export const plugin={name:'kch-operational-supervision',manifest:{capabilities:['tools']},
  setup(api,ctx){
    const workspace=ctx.workspaceInfo?.rootPath || process.cwd();
    api.registerTool({name:'kch_vps_diagnose',description:'Read-only VPS measurements through exact authorized SSH profile. No process inspection unless a UID allowlist is explicitly supplied; no killing or restarting.',
      inputSchema:{type:'object',properties:{profile:{type:'object'},measurement:{type:'object'}},required:['profile'],additionalProperties:false},
      execute:input=>invoke('vps-ssh',input,workspace)});
    api.registerTool({name:'kch_agents_observe',description:'Read or ingest native agent observations, check Luna/Terra dispatch plans, preserve attributed reviews, and preregister dual-branch Construct candidates. Does not create native Cline agents or auto-publish.',
      inputSchema:{type:'object',properties:{action:{type:'string',enum:['status','observe','dispatch-preflight','review','preregister']},request:{type:'object'}},required:['action'],additionalProperties:false},
      execute:input=>invoke(input.action,input.request || {},workspace)});
    ctx.logger?.log?.('KCH Operational Supervision registered',{version:'0.1.0',tools:2,native_cline_agent_dispatch:false});
  }};
export default plugin;
