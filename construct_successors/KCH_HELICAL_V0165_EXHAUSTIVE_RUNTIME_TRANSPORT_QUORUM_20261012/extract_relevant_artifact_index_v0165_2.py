#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os
from pathlib import Path
from typing import Any

EXPECTED_RECEIPT_ID="h1651transport:a45d1b835cca51a25d736cba638c01ac0b094c49c4af41491cde3c2f04f7b08b"

def canonical(v:Any)->bytes:
 return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()
def sha(v:Any)->str:return hashlib.sha256(canonical(v)).hexdigest()
def load(p:Path)->dict[str,Any]:
 v=json.loads(p.read_text(encoding="utf-8"))
 if not isinstance(v,dict):raise RuntimeError(f"expected object: {p}")
 return v

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument("--root",type=Path,required=True);args=ap.parse_args()
 root=args.root.resolve();receipts=root/"receipts"
 inventory_path=receipts/"EXHAUSTIVE_RUNTIME_TRANSPORT_SEARCH_INVENTORY_V0_16_5.json"
 receipt_path=receipts/"EXHAUSTIVE_RUNTIME_TRANSPORT_QUORUM_RECEIPT_V0_16_5.json"
 inv=load(inventory_path);pred=load(receipt_path)
 if pred.get("receipt_id")!=EXPECTED_RECEIPT_ID:raise RuntimeError("unexpected predecessor receipt")
 rows=inv.get("artifact_inventory")
 if not isinstance(rows,list):raise RuntimeError("artifact_inventory missing")
 compact=[]
 for row in rows:
  if not isinstance(row,dict) or row.get("relevant") is not True:continue
  compact.append({
   "id":int(row["id"]),"name":str(row["name"]),"bytes":int(row["bytes"]),
   "digest":row.get("digest"),"expired":bool(row.get("expired")),
   "workflow_run":row.get("workflow_run"),"predecessor_downloaded":bool(row.get("downloaded")),
  })
 compact.sort(key=lambda r:(r["name"],r["id"]))
 expected=int(pred["artifacts"]["relevant_unexpired"])
 observed=sum(not r["expired"] for r in compact)
 if observed!=expected:raise RuntimeError(f"unexpired relevant count mismatch {observed}!={expected}")
 body={
  "format":"KCH_HELICAL_V0_16_5_2_RELEVANT_ARTIFACT_INDEX",
  "github_run_id":os.environ.get("GITHUB_RUN_ID"),"github_sha":os.environ.get("GITHUB_SHA"),
  "predecessor_receipt_id":pred["receipt_id"],"artifact_count":len(compact),
  "unexpired_artifact_count":observed,"artifacts":compact,
  "artifact_payloads_downloaded":False,"records_modified":False,
  "scientific_data_accessed":False,"calibration_executed":False,
  "sealed_test_accessed":False,"scientific_result":None,
  "promotion":"BLOCKED","canonicalization":"BLOCKED","status":"PASS",
 }
 body["index_id"]="h1652artifactindex:"+sha(body)
 out=receipts/"RELEVANT_ARTIFACT_INDEX_V0_16_5_2.json"
 out.write_text(json.dumps(body,sort_keys=True,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"index_id":body["index_id"],"artifact_count":len(compact),"unexpired_artifact_count":observed},sort_keys=True))
 return 0
if __name__=="__main__":raise SystemExit(main())
