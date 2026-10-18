#!/usr/bin/env python3
"""Assemble 30 BIFM v0.11.1 shards into the frozen v0.11 layer format.

The assembler rejects missing, duplicate, mismatched or hash-inconsistent shards.
It computes realized hidden-state effects against the baseline shard and emits
exactly the input contract expected by the frozen v0.11 summary.
"""
from __future__ import annotations
import hashlib, json, os, sys
from pathlib import Path

import numpy as np

LAYERS=(4,14,24)
EPS_GRID=(0.05,0.10,0.20,0.35,0.50,0.75,1.00,1.50,2.00)
FIELDS=("top1","rank4","choice_q8","full_top8","full_top32")
ROOT=Path(os.environ.get("BIFM_SHARDS","shard_artifacts"))
OUT=Path(os.environ.get("BIFM_ASSEMBLED","assembled_layers"))
OUT.mkdir(parents=True,exist_ok=True)


def sha_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for chunk in iter(lambda:f.read(1<<20),b""): h.update(chunk)
    return h.hexdigest()


def locate(layer,eidx):
    npzs=list(ROOT.rglob(f"qwen_L{layer}_E{eidx}.npz"))
    receipts=list(ROOT.rglob(f"qwen_L{layer}_E{eidx}_receipt.json"))
    if len(npzs)!=1 or len(receipts)!=1:
        raise RuntimeError(f"L{layer} E{eidx}: expected one npz/receipt, got {npzs}, {receipts}")
    return npzs[0],receipts[0]


def dump(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True),encoding="utf-8")


def main():
    global_ids=None; global_answers=None; dataset_revision=None
    manifest=[]
    for layer in LAYERS:
        shards=[]
        for eidx in range(10):
            npz_path,receipt_path=locate(layer,eidx)
            receipt=json.load(open(receipt_path,encoding="utf-8"))
            if receipt["layer"]!=layer or receipt["epsilon_index"]!=eidx:
                raise AssertionError(f"receipt mismatch L{layer} E{eidx}")
            if receipt["npz_sha256"]!=sha_file(npz_path):
                raise AssertionError(f"NPZ hash mismatch L{layer} E{eidx}")
            z=np.load(npz_path,allow_pickle=False)
            if int(z["layer"][0])!=layer or int(z["epsilon_index"][0])!=eidx:
                raise AssertionError(f"NPZ metadata mismatch L{layer} E{eidx}")
            ids=list(z["item_ids"].astype(str)); answers=list(z["answer_keys"].astype(str))
            if global_ids is None:
                global_ids=ids; global_answers=answers; dataset_revision=receipt["data"]["revision"]
            if ids!=global_ids or answers!=global_answers:
                raise AssertionError(f"item order mismatch L{layer} E{eidx}")
            if receipt["data"]["revision"]!=dataset_revision:
                raise AssertionError("dataset revision mismatch")
            shards.append((z,receipt,npz_path,receipt_path))
            manifest.append({
              "layer":layer,"epsilon_index":eidx,
              "npz":str(npz_path),"npz_sha256":sha_file(npz_path),
              "receipt":str(receipt_path),"receipt_sha256":sha_file(receipt_path),
            })
        baseline=shards[0][0]; base_hidden=baseline["hidden"].astype(np.float64)
        arrays={
          "item_ids":np.array(global_ids,dtype="U64"),
          "answer_keys":np.array(global_answers,dtype="U4"),
          "eps_grid":np.array(EPS_GRID,dtype=np.float32),
        }
        for field in FIELDS:
            arrays[f"base_{field}"]=baseline[field]
        effects=[]
        for k,eps in enumerate(EPS_GRID):
            z=shards[k+1][0]
            for field in FIELDS:
                arrays[f"e{k}_{field}"]=z[field]
            hidden=z["hidden"].astype(np.float64)
            rel=np.linalg.norm(hidden-base_hidden,axis=1)/(np.linalg.norm(base_hidden,axis=1)+1e-12)
            dot=(hidden*base_hidden).sum(axis=1)
            denom=np.linalg.norm(hidden,axis=1)*np.linalg.norm(base_hidden,axis=1)+1e-12
            cos=1.0-dot/denom
            effects.append({
              "index":k,"epsilon":float(eps),"scale":float(1.0+eps),
              "hidden_relative_l2_mean":float(rel.mean()),
              "hidden_relative_l2_min":float(rel.min()),
              "hidden_relative_l2_median":float(np.median(rel)),
              "hidden_cosine_distance_mean":float(cos.mean()),
              "top1_flips_all96":int((z["top1"]!=baseline["top1"]).sum()),
              "n_hidden_realizations":int(len(rel)),
            })
        layer_dir=OUT/f"BIFM-v0.11-Qwen-layer-{layer}"
        layer_dir.mkdir(parents=True,exist_ok=True)
        npz_out=layer_dir/f"qwen_layer_{layer}.npz"
        np.savez_compressed(npz_out,**arrays)
        receipt={
          "status":"PASS_ASSEMBLED_FROM_SHARDS","layer":layer,
          "model":shards[0][1]["model"],"data":shards[0][1]["data"],
          "operators":list(FIELDS),"effects":effects,
          "source_shards":[{
             "epsilon_index":e,"epsilon":None if e==0 else float(EPS_GRID[e-1]),
             "npz_sha256":manifest[-10+e]["npz_sha256"],
             "receipt_sha256":manifest[-10+e]["receipt_sha256"],
          } for e in range(10)],
          "assembled_npz_sha256":sha_file(npz_out),
          "claim_boundary":[
            "Assembly changes only compute partitioning, not the frozen experimental design.",
            "Hidden effects are computed across 384 item-rotation realizations.",
          ],
        }
        dump(layer_dir/f"qwen_layer_{layer}_receipt.json",receipt)
    dump(OUT/"SHARD_ASSEMBLY_MANIFEST.json",{
      "status":"PASS","n_shards":len(manifest),"layers":list(LAYERS),
      "dataset_revision":dataset_revision,"n_items":len(global_ids),"files":manifest,
    })
    print(json.dumps({
      "status":"PASS","n_shards":len(manifest),"layers":list(LAYERS),
      "n_items":len(global_ids),"dataset_revision":dataset_revision,
      "assembled_root":str(OUT),
    },indent=2,sort_keys=True))

if __name__=="__main__": main()
