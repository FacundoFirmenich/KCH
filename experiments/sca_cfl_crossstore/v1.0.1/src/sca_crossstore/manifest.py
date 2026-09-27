from __future__ import annotations
from pathlib import Path
from .canonical import file_sha256,digest

EXCLUDED={"RELEASE_MANIFEST.json","PERSISTENCE_LEDGER.json"}

def build_manifest(root:Path,parent_manifest_digest:str,parent_release:str="0.9.0"):
    files=[]
    for p in sorted(root.rglob("*")):
        if not p.is_file():continue
        rel=p.relative_to(root).as_posix()
        if rel in EXCLUDED or rel.startswith("evidence/") or "/__pycache__/" in "/"+rel or rel.startswith(".pytest_cache/"):continue
        files.append({"path":rel,"sha256":file_sha256(p),"size":p.stat().st_size})
    body={"schema":"SCA_CFL_RELEASE_MANIFEST_V1","release":"1.0.1","parent_release":parent_release,"parent_manifest_digest":parent_manifest_digest,"files":files}
    body["content_digest"]=digest({k:v for k,v in body.items() if k!="content_digest"})
    return body

def verify_manifest(root:Path,m):
    if m.get("schema")!="SCA_CFL_RELEASE_MANIFEST_V1":raise ValueError("SCHEMA")
    observed=[]
    for x in m["files"]:
        p=root/x["path"]
        if not p.is_file():raise FileNotFoundError(x["path"])
        observed.append({"path":x["path"],"sha256":file_sha256(p),"size":p.stat().st_size})
    if observed!=m["files"]:raise ValueError("CONTENT_MISMATCH")
    d=digest({k:v for k,v in m.items() if k!="content_digest"})
    if d!=m["content_digest"]:raise ValueError("MANIFEST_DIGEST")
    return True
