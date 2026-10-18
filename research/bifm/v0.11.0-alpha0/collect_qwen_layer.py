#!/usr/bin/env python3
"""BIFM v0.11 — collect one real-data Qwen layer over the frozen grid.

The script evaluates all 96 frozen ARC-Challenge items under four cyclic answer
permutations for baseline plus nine MLP-scaling interventions. It stores only
machine-checkable observation signatures and realized hidden-state effects.
"""
from __future__ import annotations
import hashlib, json, os, platform, sys, time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from huggingface_hub import HfApi, hf_hub_download
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID="Qwen/Qwen3-0.6B"
MODEL_REVISION="c1899de289a04d12100db370d81485cdf75e47ca"
DATASET_ID="allenai/ai2_arc"
DATASET_FILE="ARC-Challenge/validation-00000-of-00001.parquet"
EPS_GRID=(0.05,0.10,0.20,0.35,0.50,0.75,1.00,1.50,2.00)
POOL_SIZE=96
BATCH=8
LAYER=int(os.environ["BIFM_LAYER"])
OUT=Path(os.environ.get("BIFM_OUT",f"bifm_v011_layer_{LAYER}"))
OUT.mkdir(parents=True,exist_ok=True)


def sha(s:str)->str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def dump(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True),encoding="utf-8")


def item_text(row,rot):
    labels="ABCD"; texts=list(row["choices"]["text"])
    order=[(j+rot)%4 for j in range(4)]
    lines="\n".join(f"{labels[j]}. {texts[order[j]]}" for j in range(4))
    return (
      "Answer this multiple-choice science question. Return only one letter: "
      "A, B, C, or D.\n\n"
      f"Question: {row['question'].strip()}\n{lines}\nAnswer:"
    ),order


def render(tok,text):
    try:
        return tok.apply_chat_template(
          [{"role":"user","content":text}],tokenize=False,
          add_generation_prompt=True,enable_thinking=False
        )
    except TypeError:
        return tok.apply_chat_template(
          [{"role":"user","content":text}],tokenize=False,
          add_generation_prompt=True
        )


def find_choice_ids(tok):
    out={}
    for lab in "ABCD":
        for candidate in (" "+lab,lab):
            ids=tok.encode(candidate,add_special_tokens=False)
            if len(ids)==1:
                out[lab]=ids[0]; break
        if lab not in out:
            raise RuntimeError(f"{lab} not single-token")
    if len(set(out.values()))!=4:
        raise RuntimeError(f"non-distinct choice token ids: {out}")
    return out


def flatten(tok,rows):
    prompts=[]; maps=[]
    for row in rows:
        per=[]
        for r in range(4):
            text,order=item_text(row,r)
            prompts.append(render(tok,text)); per.append(order)
        maps.append(per)
    return prompts,maps


def evaluate(model,tok,prompts,maps,cids,scale=None):
    choice_chunks=[]; full_chunks=[]; hidden_chunks=[]; hooks=[]
    layer=model.model.layers[LAYER]
    if scale is not None:
        def mlp_hook(module,inputs,output):
            return output*scale
        hooks.append(layer.mlp.register_forward_hook(mlp_hook))
    def layer_hook(module,inputs,output):
        t=output[0] if isinstance(output,(tuple,list)) else output
        hidden_chunks.append(t[:,-1,:].detach().float().cpu())
    hooks.append(layer.register_forward_hook(layer_hook))
    try:
        with torch.inference_mode():
            for s in range(0,len(prompts),BATCH):
                enc=tok(prompts[s:s+BATCH],return_tensors="pt",padding=True,
                        truncation=True,max_length=384)
                core=model.model(**enc,use_cache=False,return_dict=True)
                logits=model.lm_head(core.last_hidden_state[:,-1,:]).detach().float().cpu()
                choice_chunks.append(torch.stack([logits[:,cids[x]] for x in "ABCD"],dim=1))
                full_chunks.append(logits)
    finally:
        for h in hooks: h.remove()
    flat_choice=torch.cat(choice_chunks)
    flat_full=torch.cat(full_chunks)
    flat_hidden=torch.cat(hidden_chunks)
    n=len(maps); vocab=flat_full.shape[-1]
    c=flat_choice.reshape(n,4,4)
    f=flat_full.reshape(n,4,vocab)
    choice=torch.zeros((n,4),dtype=c.dtype)
    for i in range(n):
        for r in range(4):
            for shown,orig in enumerate(maps[i][r]):
                choice[i,orig]+=c[i,r,shown]/4.0
    full=f.mean(dim=1)
    probs=torch.softmax(choice,dim=-1)
    rank4=torch.argsort(choice,dim=-1,descending=True)
    top1=rank4[:,0]
    q8=torch.clamp(torch.floor(probs*8+1e-12),max=7).to(torch.int8)
    top8=torch.topk(full,8,dim=-1).indices.to(torch.int32)
    top32=torch.topk(full,32,dim=-1).indices.to(torch.int32)
    return {
      "top1":top1.numpy().astype(np.int8),
      "rank4":rank4.numpy().astype(np.int8),
      "choice_q8":q8.numpy().astype(np.int8),
      "full_top8":top8.numpy().astype(np.int32),
      "full_top32":top32.numpy().astype(np.int32),
      "hidden":flat_hidden.numpy().astype(np.float32),
    }


def main():
    t0=time.time(); torch.manual_seed(0)
    torch.set_num_threads(max(1,min(4,os.cpu_count() or 1)))
    api=HfApi(); dsha=api.dataset_info(DATASET_ID).sha
    parquet=hf_hub_download(repo_id=DATASET_ID,repo_type="dataset",
                            filename=DATASET_FILE,revision=dsha)
    df=pd.read_parquet(parquet)
    rows=[r for r in df.to_dict("records") if list(r["choices"]["label"])==["A","B","C","D"]]
    rows=sorted(rows,key=lambda r:sha(str(r["id"])))[:POOL_SIZE]
    if len(rows)!=POOL_SIZE: raise RuntimeError("insufficient canonical ARC rows")

    tok=AutoTokenizer.from_pretrained(MODEL_ID,revision=MODEL_REVISION)
    tok.padding_side="left"
    if tok.pad_token_id is None: tok.pad_token=tok.eos_token
    model=AutoModelForCausalLM.from_pretrained(
      MODEL_ID,revision=MODEL_REVISION,torch_dtype=torch.float32,
      low_cpu_mem_usage=True
    ); model.eval()
    if LAYER<0 or LAYER>=model.config.num_hidden_layers:
        raise RuntimeError(f"invalid layer {LAYER}")
    cids=find_choice_ids(tok); prompts,maps=flatten(tok,rows)

    baseline=evaluate(model,tok,prompts,maps,cids,scale=None)
    arrays={
      "item_ids":np.array([str(r["id"]) for r in rows],dtype="U64"),
      "answer_keys":np.array([str(r["answerKey"]) for r in rows],dtype="U4"),
      "eps_grid":np.array(EPS_GRID,dtype=np.float32),
    }
    for key in ("top1","rank4","choice_q8","full_top8","full_top32"):
        arrays[f"base_{key}"]=baseline[key]
    base_hidden=baseline["hidden"]
    effects=[]
    for k,eps in enumerate(EPS_GRID):
        pert=evaluate(model,tok,prompts,maps,cids,scale=1.0+eps)
        for key in ("top1","rank4","choice_q8","full_top8","full_top32"):
            arrays[f"e{k}_{key}"]=pert[key]
        rel=np.linalg.norm(pert["hidden"]-base_hidden,axis=1)/(np.linalg.norm(base_hidden,axis=1)+1e-12)
        dot=(pert["hidden"]*base_hidden).sum(axis=1)
        denom=np.linalg.norm(pert["hidden"],axis=1)*np.linalg.norm(base_hidden,axis=1)+1e-12
        cos=1.0-dot/denom
        effects.append({
          "index":k,"epsilon":float(eps),"scale":float(1.0+eps),
          "hidden_relative_l2_mean":float(rel.mean()),
          "hidden_relative_l2_min":float(rel.min()),
          "hidden_relative_l2_median":float(np.median(rel)),
          "hidden_cosine_distance_mean":float(cos.mean()),
          "top1_flips_all96":int((pert["top1"]!=baseline["top1"]).sum()),
        })
        del pert
    del arrays["eps_grid"]
    arrays["eps_grid"]=np.array(EPS_GRID,dtype=np.float32)
    np.savez_compressed(OUT/f"qwen_layer_{LAYER}.npz",**arrays)
    receipt={
      "status":"PASS","layer":LAYER,
      "model":{"id":MODEL_ID,"revision":MODEL_REVISION,
               "num_hidden_layers":model.config.num_hidden_layers},
      "data":{"id":DATASET_ID,"revision":dsha,"file":DATASET_FILE,
              "n_items":POOL_SIZE,"selection":"SHA256(item id), first 96 canonical A-D rows"},
      "operators":["TOP1","RANK4","CHOICE_Q8","FULL_TOP8","FULL_TOP32"],
      "effects":effects,
      "software":{"python":sys.version,"torch":torch.__version__,
                  "platform":platform.platform()},
      "elapsed_seconds":time.time()-t0,
    }
    dump(OUT/f"qwen_layer_{LAYER}_receipt.json",receipt)
    print(json.dumps(receipt,indent=2,sort_keys=True))

if __name__=="__main__": main()
