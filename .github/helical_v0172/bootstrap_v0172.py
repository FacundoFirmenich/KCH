#!/usr/bin/env python3
from __future__ import annotations
import argparse,base64,gzip,hashlib,io,json,os,py_compile,shutil,stat,subprocess,sys,tarfile,zipfile
from pathlib import Path,PurePosixPath

ALLOWED={'AUTHORITY_LEASE_V0_17.json','README.md','contracts/CONNECTOR_ARTIFACT_SURFACE_ADJUDICATION_V0_16_6.json','contracts/SPEC_DERIVATION_CONTRACT_V0_17.json','freeze_runtime_v017.py','src/kch_helical_null_v017/__init__.py','src/kch_helical_null_v017/runtime.py','tests/test_runtime_v017.py'}
H13='h13nullledger:6abcf3c64273d25a52d75fd423b6b825ee0b1a1b800aaf5d38acf98795179c2a'
def h(b):return hashlib.sha256(b).hexdigest()
def hf(p):return h(Path(p).read_bytes())
def c(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False).encode()
def load(p):
 v=json.loads(Path(p).read_text());
 if not isinstance(v,dict):raise RuntimeError(f'object required: {p}')
 return v
def write(p,v):Path(p).parent.mkdir(parents=True,exist_ok=True);Path(p).write_text(json.dumps(v,sort_keys=True,indent=2)+'\n')
def blob(repo,rel):return subprocess.check_output(['git','-C',str(repo),'rev-parse',f'HEAD:{rel}'],text=True).strip()
def tree(root):return [{'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':hf(p)} for p in sorted(x for x in root.rglob('*') if x.is_file())]
def cmd(argv,cwd,env,log):
 r=subprocess.run(argv,cwd=cwd,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT);Path(log).write_text(r.stdout)
 if r.returncode:raise RuntimeError(f'command {r.returncode}: {argv}; {log}')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo-root',type=Path,required=True);ap.add_argument('--manifest',type=Path,required=True);ap.add_argument('--root',type=Path,required=True);ap.add_argument('--work',type=Path,required=True);a=ap.parse_args()
 repo=a.repo_root.resolve();root=a.root.resolve();work=a.work.resolve();m=load(a.manifest.resolve());root.mkdir(parents=True,exist_ok=True);work.mkdir(parents=True,exist_ok=True)
 if m.get('format')!='KCH_HELICAL_V0_17_2_TEXT_CHUNK_MANIFEST':raise RuntimeError('manifest format')
 parts=[];obs=[]
 for i,row in enumerate(m['chunks']):
  p=repo/row['path'];d=p.read_bytes();s=h(d);g=blob(repo,row['path'])
  if len(d)!=row['bytes'] or s!=row['sha256'] or g!=row['git_blob_sha1']:raise RuntimeError(f'chunk identity {i}: {p}')
  parts.append(d);obs.append({'index':i,'path':row['path'],'bytes':len(d),'sha256':s,'git_blob_sha1':g})
 joined=b''.join(parts)
 if len(joined)!=m['chunk_bytes_total'] or h(joined)!=m['concatenated_base64_sha256']:raise RuntimeError('joined identity')
 gz=base64.b64decode(joined,validate=True)
 if len(gz)!=m['decoded_gzip_bytes'] or h(gz)!=m['decoded_gzip_sha256']:raise RuntimeError('gzip identity')
 raw=gzip.decompress(gz)
 if len(raw)!=m['decompressed_tar_bytes'] or h(raw)!=m['decompressed_tar_sha256']:raise RuntimeError('tar identity')
 rows=[]
 with tarfile.open(fileobj=io.BytesIO(raw),mode='r:') as tf:
  ms=tf.getmembers();names={x.name for x in ms}
  if names!=ALLOWED or len(ms)!=m['source_member_count']:raise RuntimeError(f'members {sorted(names^ALLOWED)}')
  for x in ms:
   q=PurePosixPath(x.name)
   if q.is_absolute() or '..' in q.parts or not x.isfile() or x.issym() or x.islnk():raise RuntimeError(f'unsafe {x.name}')
   f=tf.extractfile(x);d=f.read() if f else None
   if d is None:raise RuntimeError(f'unreadable {x.name}')
   p=root/x.name;p.parent.mkdir(parents=True,exist_ok=True)
   if p.exists():p.unlink()
   fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o644)
   with os.fdopen(fd,'wb') as o:o.write(d);o.flush();os.fsync(o.fileno())
   if p.read_bytes()!=d:raise RuntimeError(f'post-write {x.name}')
   rows.append({'path':x.name,'bytes':len(d),'sha256':h(d)})
 transport={'format':'KCH_HELICAL_V0_17_2_TEXT_CAPSULE_MATERIALIZATION_RECEIPT','manifest_path':a.manifest.resolve().relative_to(repo).as_posix(),'manifest_git_blob_sha1':blob(repo,a.manifest.resolve().relative_to(repo).as_posix()),'chunks':obs,'chunk_count':len(obs),'concatenated_base64_sha256':h(joined),'decoded_gzip_sha256':h(gz),'decompressed_tar_sha256':h(raw),'materialized_members':sorted(rows,key=lambda x:x['path']),'materialized_member_count':len(rows),'source_bytes_modified':False,'scientific_data_included':False,'calibration_executed':False,'sealed_test_accessed':False,'scientific_result':None,'status':'PASS'};transport['receipt_id']='h172transport:'+h(c(transport));write(root/'TEXT_CAPSULE_MATERIALIZATION_RECEIPT_V0_17_2.json',transport)
 py=[root/'src/kch_helical_null_v017/__init__.py',root/'src/kch_helical_null_v017/runtime.py',root/'tests/test_runtime_v017.py',root/'freeze_runtime_v017.py'];bc=work/'bytecode';bc.mkdir(exist_ok=True)
 for i,p in enumerate(py):py_compile.compile(str(p),doraise=True,cfile=str(bc/f'{i}.pyc'))
 env={'PATH':os.environ.get('PATH',''),'HOME':str(work/'home'),'TMPDIR':str(work/'tmp'),'PYTHONPATH':str(root/'src'),'PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1','PYTHONHASHSEED':'0','LC_ALL':'C.UTF-8','LANG':'C.UTF-8'};Path(env['HOME']).mkdir(exist_ok=True);Path(env['TMPDIR']).mkdir(exist_ok=True)
 logs=[]
 for tag in ('a','b'):
  log=work/f'unittest-{tag}.log';cmd([sys.executable,'-m','unittest','discover','-s',str(root/'tests'),'-v'],repo,env,log);t=log.read_text()
  if 'Ran 44 tests' not in t or not t.rstrip().endswith('OK'):raise RuntimeError(f'test census {tag}')
  logs.append(log)
 gen=root/'generated';rep=work/'generated-replay';shutil.rmtree(gen,ignore_errors=True);shutil.rmtree(rep,ignore_errors=True)
 for out,log,tag in ((gen,logs[0],'a'),(rep,logs[1],'b')):cmd([sys.executable,str(root/'freeze_runtime_v017.py'),'--repo-root',str(repo),'--root',str(root),'--unittest-log',str(log),'--output',str(out)],repo,env,work/f'freeze-{tag}.log')
 if tree(gen)!=tree(rep):raise RuntimeError('double freeze identity')
 status=load(gen/'STATUS_V0_17.json');proof=load(gen/'NONIDENTITY_PROOF_V0_17.json');val=load(gen/'RUNTIME_VALIDATION_REPORT_V0_17.json');summary=load(gen/'NULL_PERTURBATION_JOB_LEDGER_SUMMARY_V0_17.json');freeze=load(gen/'RUNTIME_FREEZE_RECEIPT_V0_17.json');ledger=(gen/'NULL_PERTURBATION_JOB_LEDGER_V0_17.jsonl').read_text()
 checks=[status['state']=='SPECIFICATION_DERIVED_NONIDENTICAL_RUNTIME_FROZEN',status['scheduled_job_count']==6376,status['historical_identity_transferred'] is False,status['calibration_runtime_qualification_executed'] is False,status['scientific_data_accessed'] is False,status['sealed_test_accessed'] is False,status['scientific_result'] is None,proof['contract_ids_distinct'] is True,proof['ledger_ids_distinct'] is True,proof['ledger_bytes_distinct'] is True,proof['byte_identity_claim']=='FORBIDDEN',proof['historical_hash_reuse'] is False,val['all_pass'] is True,val['unittest_count']>=44,val['structural_fixture_is_scientific_execution'] is False,summary['job_count']==6376,summary['job_id_unique_count']==6376,summary['seed_unique_count']==6376,summary['historical_identity_transferred'] is False,summary['runtime_contract_id'].startswith('h17nullspec:'),summary['ledger_id'].startswith('h17nullledger:'),freeze['historical_ledger_hash_reused'] is False,freeze['calibration_runtime_qualification_executed'] is False,freeze['sealed_test_accessed'] is False,freeze['scientific_result'] is None,freeze['promotion']=='BLOCKED',freeze['canonicalization']=='BLOCKED',H13 not in ledger,'"TEST"' not in ledger]
 if not all(checks):raise RuntimeError(f'freeze firewall {[(i,x) for i,x in enumerate(checks) if not x]}')
 rel=root/'release';rel.mkdir(exist_ok=True);z=rel/'KCH_HELICAL_V0172_SPEC_DERIVED_NONIDENTICAL_RUNTIME.zip';files=[p for p in root.rglob('*') if p.is_file() and 'release' not in p.relative_to(root).parts and '__pycache__' not in p.parts];zr=[]
 for p in files:zr.append({'path':p.relative_to(root).as_posix(),'bytes':p.stat().st_size,'sha256':hf(p)})
 zr.sort(key=lambda x:x['path'])
 with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as out:
  for r in zr:
   info=zipfile.ZipInfo(r['path'],(1980,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=(stat.S_IFREG|0o644)<<16;out.writestr(info,(root/r['path']).read_bytes())
 with zipfile.ZipFile(z) as src:
  if src.testzip() is not None or src.namelist()!=[r['path'] for r in zr]:raise RuntimeError('zip membership/crc')
  for r in zr:
   if h(src.read(r['path']))!=r['sha256']:raise RuntimeError(f'zip hash {r["path"]}')
 manifest={'format':'KCH_HELICAL_V0_17_2_RELEASE_MANIFEST','members':zr,'member_count':len(zr),'member_tree_sha256':h(c(zr))};manifest['manifest_id']='h172manifest:'+h(c(manifest));write(rel/'RELEASE_MANIFEST_V0_17_2.json',manifest)
 release={'format':'KCH_HELICAL_V0_17_2_RELEASE_RECEIPT','archive_name':z.name,'archive_bytes':z.stat().st_size,'archive_sha256':hf(z),'manifest_id':manifest['manifest_id'],'member_count':len(zr),'zip_crc':'PASS','member_hash_identity':'PASS','scientific_data_included':False,'calibration_executed':False,'sealed_test_accessed':False,'scientific_result':None,'promotion':'BLOCKED','canonicalization':'BLOCKED','status':'PASS'};release['receipt_id']='h172release:'+h(c(release));write(rel/'RELEASE_RECEIPT_V0_17_2.json',release);(rel/(z.name+'.sha256')).write_text(f"{release['archive_sha256']}  {z.name}\n")
 body={'format':'KCH_HELICAL_V0_17_2_BOOTSTRAP_RECEIPT','github_run_id':os.environ.get('GITHUB_RUN_ID'),'github_run_attempt':os.environ.get('GITHUB_RUN_ATTEMPT'),'github_sha':os.environ.get('GITHUB_SHA'),'transport_receipt_id':transport['receipt_id'],'unit_test_count_each':44,'unit_test_total_executions':88,'double_freeze_identity':'PASS','freeze_tree_sha256':h(c(tree(gen))),'runtime_contract_id':summary['runtime_contract_id'],'job_ledger_id':summary['ledger_id'],'job_ledger_sha256':hf(gen/'NULL_PERTURBATION_JOB_LEDGER_V0_17.jsonl'),'scheduled_job_count':summary['job_count'],'release_manifest_id':manifest['manifest_id'],'release_receipt_id':release['receipt_id'],'release_archive_sha256':release['archive_sha256'],'historical_identity_transferred':False,'scientific_data_accessed':False,'calibration_runtime_qualification_executed':False,'sealed_test_accessed':False,'scientific_result':None,'physical_helicity':'NOT_EVALUATED','promotion':'BLOCKED','canonicalization':'BLOCKED','status':'PASS','next_gate':'CALIBRATION_ONLY_FULL_RUNTIME_QUALIFICATION_6376_JOBS_NO_TEST_ACCESS'};body['receipt_id']='h172bootstrap:'+h(c(body));write(root/'BOOTSTRAP_RECEIPT_V0_17_2.json',body);print(json.dumps({'receipt_id':body['receipt_id'],'transport_receipt_id':body['transport_receipt_id'],'runtime_contract_id':body['runtime_contract_id'],'job_ledger_id':body['job_ledger_id'],'scheduled_job_count':body['scheduled_job_count'],'release_receipt_id':body['release_receipt_id'],'release_archive_sha256':body['release_archive_sha256']},sort_keys=True));return 0
if __name__=='__main__':raise SystemExit(main())
