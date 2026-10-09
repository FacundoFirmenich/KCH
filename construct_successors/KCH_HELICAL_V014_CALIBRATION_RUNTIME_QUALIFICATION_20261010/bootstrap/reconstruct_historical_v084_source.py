from __future__ import annotations
import argparse, base64, gzip, hashlib, io, json, os, shutil, subprocess, tarfile, tempfile, zipfile
from pathlib import Path, PurePosixPath
COMMIT="e458afe20b8172db5a04194224cf21df5ec00dc4"
FILES={
  ".github/helical_v08_4/source_transport/chunk_00":"da9a691447b022087063b132a03ad1d4399cadd1",
  ".github/helical_v08_4/source_transport/chunk_01":"3082e6ee37ad74319195d37dea59d495fe90f490",
  ".github/helical_v08_4/source_transport/chunk_02":"6449dfb0065b3fd8347cb83bb1b9f07236e6fb89",
}
REQUIRED=("src/kch_helical_dynamic_v08/null_runtime.py","tests_v0_8_4/test_null_runtime.py","tools/freeze_null_perturbation_runtime.py")
def sha(b):return hashlib.sha256(b).hexdigest()
def git(repo,*args):return subprocess.check_output(["git","-C",str(repo),*args])
def safe_name(name):
    p=PurePosixPath(name);return bool(name) and not p.is_absolute() and ".." not in p.parts

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--repo-root",type=Path,required=True);ap.add_argument("--output",type=Path,required=True);ap.add_argument("--receipt",type=Path,required=True);a=ap.parse_args()
    repo=a.repo_root.resolve();out=a.output.resolve();receipt=a.receipt.resolve();git(repo,"cat-file","-e",f"{COMMIT}^{{commit}}")
    chunks=[];source=[]
    for path,blob in FILES.items():
        observed=git(repo,"rev-parse",f"{COMMIT}:{path}").decode().strip()
        if observed!=blob:raise RuntimeError(f"blob mismatch {path}: {observed}")
        data=git(repo,"show",f"{COMMIT}:{path}");chunks.append(data);source.append({"path":path,"git_blob_sha1":observed,"bytes":len(data),"sha256":sha(data)})
    b64=b"".join(chunks);compressed=base64.b64decode(b"".join(b64.split()),validate=True);payload=gzip.decompress(compressed)
    out.parent.mkdir(parents=True,exist_ok=True);tmp=Path(tempfile.mkdtemp(prefix=out.name+".tmp.",dir=out.parent));archive_type=None
    try:
        bio=io.BytesIO(payload)
        try:
            with tarfile.open(fileobj=bio,mode="r:*") as tf:
                members=tf.getmembers()
                if any(not safe_name(m.name) or m.issym() or m.islnk() for m in members):raise RuntimeError("unsafe tar member")
                tf.extractall(tmp,filter="data");archive_type="tar"
        except tarfile.ReadError:
            bio.seek(0)
            if not zipfile.is_zipfile(bio):raise RuntimeError("decoded payload is neither safe tar nor zip")
            bio.seek(0)
            with zipfile.ZipFile(bio) as z:
                if any(not safe_name(n) for n in z.namelist()):raise RuntimeError("unsafe zip member")
                z.extractall(tmp);archive_type="zip"
        found=[]
        for req in REQUIRED:
            exact=[m for m in tmp.rglob(Path(req).name) if m.as_posix().endswith(req)]
            if len(exact)!=1:raise RuntimeError(f"required source not uniquely found: {req}")
            found.append({"required_path":req,"materialized_path":exact[0].relative_to(tmp).as_posix(),"bytes":exact[0].stat().st_size,"sha256":sha(exact[0].read_bytes())})
        if out.exists():shutil.rmtree(out)
        os.replace(tmp,out);tmp=None
    finally:
        if tmp is not None and tmp.exists():shutil.rmtree(tmp)
    body={"format":"KCH_HELICAL_V0_14_HISTORICAL_V084_SOURCE_RECONSTRUCTION_RECEIPT","source_commit":COMMIT,"source_files":source,"concatenated_base64_sha256":sha(b64),"compressed_sha256":sha(compressed),"decoded_archive_sha256":sha(payload),"archive_type":archive_type,"required_files":found,"scientific_execution_performed":False,"sealed_test_accessed":False,"authority":"SOFTWARE_CANDIDATE_LOCAL_SHADOW"}
    body["receipt_id"]="h14v084source:"+sha(json.dumps(body,sort_keys=True,separators=(",",":")).encode());receipt.parent.mkdir(parents=True,exist_ok=True);receipt.write_text(json.dumps(body,indent=2,sort_keys=True)+"\n");print(json.dumps(body,sort_keys=True))
if __name__=="__main__":main()
