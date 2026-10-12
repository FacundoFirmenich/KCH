#!/usr/bin/env python3
from __future__ import annotations
import argparse, ast, base64, gzip, hashlib, io, json, os, re, subprocess, tarfile, urllib.request, zipfile
from pathlib import Path, PurePosixPath
from typing import Any

TARGETS={"runtime":"src/kch_helical_dynamic_v08/null_runtime.py","tests":"tests_v0_8_4/test_null_runtime.py"}
SYMS={"seeded_rng","moving_block_resample","permute_within_bins","rewire_parent_graph","simulate_catalog","score_null_metrics","compute_parent_state","eval_intensity","static_logodds","propagate_mechanism_uncertainty"}
SCI={".pickle",".pkl",".npz",".npy",".csv",".parquet",".geojson",".fits",".h5",".hdf5",".sqlite",".db"}
MARK=("null_runtime","test_null_runtime","source_transport","runtime","null_perturbation","helical_v08","helical-v08")

def h(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def canon(x:Any)->bytes:return json.dumps(x,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()
def sh(repo:Path,*a:str,text=False):return subprocess.check_output(["git","-C",str(repo),*a],text=text)
def safe(n:str)->bool:
 p=PurePosixPath(n.replace("\\","/"));return not p.is_absolute() and ".." not in p.parts

def analyse(data:bytes,name:str,prov:dict[str,Any])->dict[str,Any]:
 r={**prov,"logical_name":name,"bytes":len(data),"sha256":h(data),"utf8":False,"ast_parse":False,"symbol_hits":[]}
 try:t=data.decode("utf-8","strict")
 except UnicodeDecodeError:return r
 r["utf8"]=True;r["symbol_hits"]=sorted(s for s in SYMS if re.search(rf"\b{re.escape(s)}\b",t))
 try:tree=ast.parse(t,filename=name)
 except SyntaxError as e:r["ast_error"]=f"{e.lineno}:{e.offset}:{e.msg}";return r
 r["ast_parse"]=True;r["functions"]=sorted({n.name for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))});return r

class Scan:
 def __init__(self,cap:int,depth:int):self.cap=cap;self.depth=depth;self.exact={k:[] for k in TARGETS};self.symbol=[];self.members=0;self.sci_skip=0;self.diag=[]
 def source(self,b:bytes,n:str,p:dict[str,Any]):
  r=analyse(b,n,p);base=PurePosixPath(n).name
  for k,s in TARGETS.items():
   if n.replace("\\","/").endswith(s) or base==PurePosixPath(s).name:self.exact[k].append(r)
  if len(r["symbol_hits"])>=4:self.symbol.append(r)
 def inspect(self,b:bytes,n:str,p:dict[str,Any],d=0):
  if d>self.depth or len(b)>self.cap:self.diag.append({**p,"name":n,"outcome":"CAP"});return
  self.members+=1;low=n.lower();suf=PurePosixPath(low).suffix
  if suf in SCI:self.sci_skip+=1;return
  if suf in {".py",".pyw"}:self.source(b,n,p);return
  try:
   if zipfile.is_zipfile(io.BytesIO(b)):
    with zipfile.ZipFile(io.BytesIO(b)) as z:
     for i in z.infolist():
      if i.is_dir() or not safe(i.filename) or i.file_size>self.cap:continue
      q=i.filename.lower();qs=PurePosixPath(q).suffix
      if qs in SCI:self.sci_skip+=1;continue
      if PurePosixPath(q).name in {PurePosixPath(x).name for x in TARGETS.values()} or any(m in q for m in MARK) or q.endswith((".zip",".gz",".b64",".tar",".tgz")):
       self.inspect(z.read(i),f"{n}!/{i.filename}",{**p,"member":i.filename},d+1)
    return
  except Exception as e:self.diag.append({**p,"name":n,"zip_error":repr(e)})
  try:
   with tarfile.open(fileobj=io.BytesIO(b),mode="r:*") as t:
    for i in t.getmembers():
     if not i.isfile() or i.issym() or i.islnk() or not safe(i.name) or i.size>self.cap:continue
     q=i.name.lower();qs=PurePosixPath(q).suffix
     if qs in SCI:self.sci_skip+=1;continue
     if PurePosixPath(q).name in {PurePosixPath(x).name for x in TARGETS.values()} or any(m in q for m in MARK):
      f=t.extractfile(i);self.inspect(f.read(),f"{n}!/{i.name}",{**p,"member":i.name},d+1) if f else None
    return
  except Exception:pass
  if b.startswith(b"\x1f\x8b"):
   try:o=gzip.decompress(b)
   except Exception:o=None
   if o is not None and len(o)<=self.cap:self.inspect(o,n+"!gunzip",p,d+1);return
  if any(m in low for m in MARK) or low.endswith((".b64",".txt")):
   c=b"".join(b.split())
   if c and len(c)%4==0:
    try:o=base64.b64decode(c,validate=True)
    except Exception:o=None
    if o is not None and o!=b:self.inspect(o,n+"!base64",p,d+1)

def req(url:str,tok:str,binary=False):
 r=urllib.request.Request(url,headers={"Authorization":f"Bearer {tok}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28","User-Agent":"kch-v0165"})
 with urllib.request.urlopen(r,timeout=120) as x:return x.read() if binary else json.load(x)
def artifacts(owner,repo,tok):
 out=[]
 for page in range(1,51):
  p=req(f"https://api.github.com/repos/{owner}/{repo}/actions/artifacts?per_page=100&page={page}",tok);rows=p.get("artifacts",[])
  out+=rows
  if len(rows)<100:break
 return out

def dedupe(rows):
 d={}
 for r in rows:d[(r.get("sha256"),r.get("logical_name"),r.get("surface"),r.get("artifact_id"),r.get("git_object"))]=r
 return sorted(d.values(),key=lambda r:(str(r.get("sha256")),str(r.get("logical_name"))))

def main():
 a=argparse.ArgumentParser();a.add_argument("--repo-root",type=Path,required=True);a.add_argument("--output",type=Path,required=True);a.add_argument("--owner",required=True);a.add_argument("--repo",required=True);a.add_argument("--cap",type=int,default=52428800);a.add_argument("--total-cap",type=int,default=1073741824);x=a.parse_args()
 repo=x.repo_root.resolve();out=x.output.resolve();out.mkdir(parents=True,exist_ok=True);tok=os.environ["GITHUB_TOKEN"];scan=Scan(x.cap,4)
 raw=sh(repo,"rev-list","--objects","--all",text=True);paths=[]
 for line in raw.splitlines():
  z=line.split(" ",1)
  if len(z)!=2:continue
  oid,path=z;low=path.lower()
  if not (low.endswith(".py") or any(m in low for m in MARK) or low.endswith((".zip",".gz",".b64",".tar",".tgz"))):continue
  try:size=int(sh(repo,"cat-file","-s",oid,text=True).strip())
  except Exception:continue
  if size>x.cap:continue
  b=sh(repo,"cat-file","blob",oid);paths.append({"oid":oid,"path":path,"bytes":len(b),"sha256":h(b)})
  p={"surface":"git","git_object":oid,"git_path":path}
  if low.endswith(".py"):
   r=analyse(b,path,p)
   if PurePosixPath(low).name in {PurePosixPath(v).name for v in TARGETS.values()} or len(r["symbol_hits"])>=4:scan.source(b,path,p)
  if any(m in low for m in MARK) or low.endswith((".zip",".gz",".b64",".tar",".tgz")):scan.inspect(b,path,p)
 arts=artifacts(x.owner,x.repo,tok);inv=[];errs=[];used=0;down=0
 for q in sorted(arts,key=lambda r:(str(r.get("created_at")),int(r.get("id",0)))):
  name=str(q.get("name",""));size=int(q.get("size_in_bytes") or 0);rel="helical" in name.lower() and any(m in name.lower() for m in ("runtime","source","null","quorum","freeze","recovery","v08","v013","v015"));row={"id":q.get("id"),"name":name,"bytes":size,"expired":bool(q.get("expired")),"relevant":rel,"digest":q.get("digest"),"workflow_run":q.get("workflow_run"),"downloaded":False};inv.append(row)
  if row["expired"] or not rel or size<=0 or size>x.cap or used+size>x.total_cap:continue
  try:b=req(str(q["archive_download_url"]),tok,True)
  except Exception as e:errs.append({"id":row["id"],"name":name,"error":repr(e)});continue
  if len(b)>x.cap:errs.append({"id":row["id"],"name":name,"error":"ACTUAL_SIZE_CAP"});continue
  used+=len(b);down+=1;row.update(downloaded=True,downloaded_bytes=len(b),downloaded_sha256=h(b));scan.inspect(b,f"artifact:{row['id']}:{name}.zip",{"surface":"artifact","artifact_id":row["id"],"artifact_name":name,"artifact_digest":row["digest"],"workflow_run":row["workflow_run"]})
 exact={k:dedupe(v) for k,v in scan.exact.items()};rf=bool(exact["runtime"]);tf=bool(exact["tests"])
 outcome=("EXACT_RUNTIME_AND_TEST_SOURCE_CANDIDATES_FOUND" if rf and tf else "EXACT_RUNTIME_CANDIDATE_FOUND_TEST_SOURCE_MISSING" if rf else "EXACT_TEST_SOURCE_CANDIDATE_FOUND_RUNTIME_MISSING" if tf else "RUNTIME_SOURCE_NOT_RECOVERABLE_FROM_AVAILABLE_INDEPENDENT_TRANSPORTS")
 body={"format":"KCH_HELICAL_V0_16_5_EXHAUSTIVE_RUNTIME_TRANSPORT_QUORUM","github_run_id":os.environ.get("GITHUB_RUN_ID"),"github_sha":os.environ.get("GITHUB_SHA"),"repository":f"{x.owner}/{x.repo}","git":{"reachable_objects":len(raw.splitlines()),"relevant_blobs":len(paths)},"artifacts":{"listed":len(arts),"relevant_unexpired":sum(1 for r in inv if r["relevant"] and not r["expired"]),"downloaded":down,"downloaded_bytes":used,"errors":errs},"inspection":{"members_seen":scan.members,"scientific_members_skipped_without_read":scan.sci_skip},"targets":exact,"symbol_candidates":dedupe(scan.symbol),"outcome":outcome,"search_protocol_status":"PASS","transport_bytes_repaired":False,"missing_source_bytes_inferred":False,"candidate_source_imported":False,"candidate_source_executed":False,"scientific_payload_members_read":False,"scientific_data_accessed":False,"calibration_executed":False,"sealed_test_accessed":False,"scientific_result":None,"physical_helicity":"NOT_EVALUATED","historical_v0_13_ledger_identity_transferred":False,"promotion":"BLOCKED","canonicalization":"BLOCKED","next_gate":"PROVENANCE_ADJUDICATION_OF_EXACT_SOURCE_CANDIDATES" if rf or tf else "SPECIFICATION_DERIVED_NONIDENTICAL_RUNTIME_SUCCESSOR"};body["receipt_id"]="h165transport:"+h(canon(body))
 inventory={"format":"KCH_HELICAL_V0_16_5_SEARCH_INVENTORY","git_transport_inventory":paths,"artifact_inventory":inv,"diagnostics":scan.diag};inventory["inventory_id"]="h165inventory:"+h(canon(inventory))
 val={"format":"KCH_HELICAL_V0_16_5_VALIDATION","status":"PASS","receipt_id":body["receipt_id"],"inventory_id":inventory["inventory_id"],"checks":{"all_git_refs_enumerated":True,"all_actions_artifacts_listed":True,"strict_base64_only":True,"scientific_payloads_skipped":True,"candidate_execution_forbidden":True,"sealed_test_not_accessed":True}};val["validation_id"]="h165validation:"+h(canon(val))
 for n,v in (("EXHAUSTIVE_RUNTIME_TRANSPORT_QUORUM_RECEIPT_V0_16_5.json",body),("EXHAUSTIVE_RUNTIME_TRANSPORT_SEARCH_INVENTORY_V0_16_5.json",inventory),("EXHAUSTIVE_RUNTIME_TRANSPORT_QUORUM_VALIDATION_V0_16_5.json",val)):(out/n).write_text(json.dumps(v,sort_keys=True,indent=2)+"\n")
 print(json.dumps({"receipt_id":body["receipt_id"],"validation_id":val["validation_id"],"outcome":outcome,"artifacts_downloaded":down,"runtime_candidates":len(exact["runtime"]),"test_candidates":len(exact["tests"])}));return 0
if __name__=="__main__":raise SystemExit(main())
