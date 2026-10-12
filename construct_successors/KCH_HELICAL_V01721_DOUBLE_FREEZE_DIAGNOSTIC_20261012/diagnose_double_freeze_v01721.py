#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
from typing import Any

def c(v:Any)->bytes:return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def h(v:Any)->str:return hashlib.sha256(c(v)).hexdigest()
def write(p:Path,v:Any):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,sort_keys=True,indent=2)+'\n')
def loadmod(p:Path):
 s=importlib.util.spec_from_file_location('kch_v0172_bootstrap',p)
 if s is None or s.loader is None:raise RuntimeError('bootstrap import specification unavailable')
 m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def json_diff(a:Any,b:Any,path:str='$',out:list|None=None)->list:
 out=[] if out is None else out
 if type(a) is not type(b):out.append({'path':path,'left':a,'right':b,'kind':'TYPE'});return out
 if isinstance(a,dict):
  for k in sorted(set(a)|set(b)):
   if k not in a:out.append({'path':f'{path}.{k}','left':'<MISSING>','right':b[k],'kind':'MISSING_LEFT'})
   elif k not in b:out.append({'path':f'{path}.{k}','left':a[k],'right':'<MISSING>','kind':'MISSING_RIGHT'})
   else:json_diff(a[k],b[k],f'{path}.{k}',out)
 elif isinstance(a,list):
  if len(a)!=len(b):out.append({'path':path+'.length','left':len(a),'right':len(b),'kind':'LENGTH'})
  for i,(x,y) in enumerate(zip(a,b)):json_diff(x,y,f'{path}[{i}]',out)
 elif a!=b:out.append({'path':path,'left':a,'right':b,'kind':'VALUE'})
 return out

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument('--repo-root',type=Path,required=True);ap.add_argument('--bootstrap',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--work',type=Path,required=True);ap.add_argument('--lineage',type=Path,required=True);a=ap.parse_args()
 repo=a.repo_root.resolve();bootstrap=a.bootstrap.resolve();root=a.root.resolve();work=a.work.resolve();lineage=a.lineage.resolve();lineage.mkdir(parents=True,exist_ok=True)
 module=loadmod(bootstrap);original_tree=module.tree;calls=[];report_holder={}
 def diagnostic_tree(directory:Path):
  rows=original_tree(directory);calls.append({'root':str(Path(directory).resolve()),'rows':rows})
  if len(calls)==2:
   left={r['path']:r for r in calls[0]['rows']};right={r['path']:r for r in rows};diffs=[]
   for name in sorted(set(left)|set(right)):
    x=left.get(name);y=right.get(name)
    if x==y:continue
    item={'path':name,'generated':x,'replay':y,'classification':'CONTENT_MISMATCH' if x and y else 'MEMBERSHIP_MISMATCH'}
    lp=Path(calls[0]['root'])/name;rp=Path(calls[1]['root'])/name
    if x and y and name.endswith('.json'):
     try:item['json_differences']=json_diff(json.loads(lp.read_text()),json.loads(rp.read_text()))[:200]
     except Exception as exc:item['json_diff_error']=repr(exc)
    diffs.append(item)
   report={'format':'KCH_HELICAL_V0_17_2_1_DOUBLE_FREEZE_DIFFERENCE_REPORT','generated_root':calls[0]['root'],'replay_root':calls[1]['root'],'generated_member_count':len(left),'replay_member_count':len(right),'divergent_member_count':len(diffs),'divergences':diffs,'scientific_data_accessed':False,'calibration_executed':False,'sealed_test_accessed':False,'scientific_result':None,'status':'DIAGNOSTIC_COMPLETE'}
   report['report_id']='h1721diff:'+h(report);write(lineage/'DOUBLE_FREEZE_DIFFERENCE_REPORT_V0_17_2_1.json',report);report_holder['report']=report
  return rows
 module.tree=diagnostic_tree
 old=sys.argv[:]
 try:
  sys.argv=[str(bootstrap),'--repo-root',str(repo),'--manifest',str(a.manifest.resolve()),'--root',str(root),'--work',str(work)]
  try:module.main()
  except RuntimeError as exc:
   if 'double freeze identity' not in str(exc):raise
   error=str(exc)
  else:raise RuntimeError('predecessor double-freeze mismatch did not reproduce')
 finally:sys.argv=old
 report=report_holder.get('report')
 if not isinstance(report,dict) or report['divergent_member_count']<1:raise RuntimeError('no diagnostic difference report produced')
 transport=json.loads((root/'TEXT_CAPSULE_MATERIALIZATION_RECEIPT_V0_17_2.json').read_text())
 body={'format':'KCH_HELICAL_V0_17_2_1_DOUBLE_FREEZE_DIAGNOSTIC_RECEIPT','predecessor_failed_run_id':38191524484,'predecessor_failed_job_id':114625098990,'predecessor_error':error,'transport_receipt_id':transport['receipt_id'],'unit_test_runs_completed':2,'unit_tests_each':44,'freeze_runs_completed':2,'difference_report_id':report['report_id'],'divergent_member_count':report['divergent_member_count'],'freeze_accepted':False,'release_built':False,'scientific_data_accessed':False,'calibration_executed':False,'sealed_test_accessed':False,'scientific_result':None,'physical_helicity':'NOT_EVALUATED','promotion':'BLOCKED','canonicalization':'BLOCKED','status':'PASS','next_gate':'DOUBLE_FREEZE_VOLATILE_FIELD_ADJUDICATION'};body['receipt_id']='h1721diagnostic:'+h(body);write(lineage/'DOUBLE_FREEZE_DIAGNOSTIC_RECEIPT_V0_17_2_1.json',body)
 print(json.dumps({'receipt_id':body['receipt_id'],'report_id':report['report_id'],'divergent_member_count':report['divergent_member_count'],'divergent_paths':[x['path'] for x in report['divergences']]},sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
