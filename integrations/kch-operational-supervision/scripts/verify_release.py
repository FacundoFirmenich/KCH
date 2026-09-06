"""Run bounded local checks and preserve an exclusive, hash-bound private receipt."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--receipt',required=True)
    parser.add_argument('--validator',required=True)
    parser.add_argument('--node',default='node')
    parser.add_argument('--require-native-cline',action='store_true')
    args=parser.parse_args()
    output=Path(args.receipt).resolve()
    if output.exists():raise FileExistsError('REFUSING_TO_OVERWRITE_VERIFICATION')
    if args.require_native_cline and not all(os.environ.get(k) for k in ('KCH_CLINE_BOOTSTRAP','KCH_CODE_EXECUTABLE')):
        raise ValueError('NATIVE_CLINE_PATHS_REQUIRED')
    commands=[('python_tests',[sys.executable,'-B','-m','unittest','discover','-s','tests','-v']),
              ('node_bridge',[args.node,'--test','tests/test_bridge.mjs']),
              ('plugin_manifest',[sys.executable,'-B',args.validator,str(ROOT)])]
    receipt={'schema':'kch.ops-verification.v0.1.0','timestamp_utc':datetime.now(timezone.utc).isoformat(),
             'model_calls':0,'native_cline_required':args.require_native_cline,'checks':[],
             'interactive_cline_session_verified':False,'codex_hook_delivery_verified':False}
    for name,command in commands:
        try:
            result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=150,
                                  env={**os.environ,'PYTHONIOENCODING':'utf-8'})
            receipt['checks'].append({'name':name,'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
        except subprocess.TimeoutExpired:
            receipt['checks'].append({'name':name,'exit_code':None,'gate':'TIMEOUT'})
    receipt['files']=[{'path':str(p.relative_to(ROOT)).replace('\\','/'),'bytes':p.stat().st_size,
                       'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                      for p in sorted(ROOT.rglob('*')) if p.is_file() and '__pycache__' not in p.parts]
    receipt['gate']='PASS' if all(c['exit_code']==0 for c in receipt['checks']) else 'FAIL'
    with output.open('x',encoding='utf-8') as handle:json.dump(receipt,handle,ensure_ascii=False,indent=2)
    print(json.dumps({'gate':receipt['gate'],'receipt':str(output),'checks':[{k:c.get(k) for k in ('name','exit_code','gate')} for c in receipt['checks']]}))
    return 0 if receipt['gate']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
