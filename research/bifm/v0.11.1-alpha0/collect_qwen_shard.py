#!/usr/bin/env python3
"""BIFM v0.11.1 — one frozen Qwen (layer, intervention) shard.

The sharded execution is computationally equivalent to the v0.11 collector:
96 real ARC-Challenge items, four cyclic answer permutations, the same frozen
model/data revisions, signatures and internal-state capture. It changes only
parallelization.
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
EIDX=int(os.environ["BIFM_EIDX"])
if EIDX<0 or EIDX>len(EPS_GRID):
    raise RuntimeError(f"invalid EIDX {EIDX}")
EPSILON=None if EIDX==0 else EPS_GRID[EIDX-1]
SCALE=None if EPSILON is None else 1.0+EPSILON
OUT=Path(os.environ.get("BIFM_OUT",f"bifm_v0111_L{LAYER}_E{EIDX}"))
OUT.mkdir(parents=True,exist_ok=True)


def sha(s:str)->str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def dump(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True),encoding="utf-8")


def item_text(row,rotation):
    labels="ABCD"; texts=list(row["choices"]["text"])
    order=[(j+rotation)%4 for j in range(4)]
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


def choice_ids(tok):
    out={}
    for lab in "ABCD":
        for candidate in (" "+lab,lab):
            ids=tok.encode(candidate,add_special_tokens=False)
            if len(ids)==1:
                out[lab]=ids[0]; break
        if lab not in out: raise RuntimeError(f"{lab} is not single-token")
    if len(set(out.values()))!=4: raise RuntimeError(f"non-distinct ids {out}")
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


def evaluate(model,tok,prompts,maps,cids):
    choices=[]; full_top_logits=[]; hidden=[]; hooks=[]
    layer=model.model.layers[LAYER]
    if SCALE is not None:
        def mlp_hook(module,inputs,output):
            return output*SCALE
        hooks.append(layer.mlp.register_forward_hook(mlp_hook))
    def layer_hook(module,inputs,output):
        t=output[0] if isinstance(output,(tuple,list)) else output
        hidden.append(t[:,-1,:].detach().float().cpu())
    hooks.append(layer.register_forward_hook(layer_hook))
    full_chunks=[]
    try:
        with torch.inference_mode():
            for s in range(0,len(prompts),BATCH):
                enc=tok(prompts[s:s+BATCH],return_tensors="pt",padding=True,
                        truncation=True,max_length=384)
                core=model.model(**enc,use_cache=False,return_dict=True)
                logits=model.lm_head(core.last_hidden_state[:,-1,:]).detach().float().cpu()
                choices.append(torch.stack([logits[:,cids[x]] for x in "ABCD"],dim=1))
                full_chunks.append(logits)
    finally:
        for h in hooks: h.remove()
    flat_choice=torch.cat(choices); flat_full=torch.cat(full_chunks); flat_hidden=torch.cat(hidden)
    n=len(maps); vocab=flat_full.shape[-1]
    c=flat_choice.reshape(n,4,4); f=flat_full.reshape(n,4,vocab)
    choice=torch.zeros((n,4),dtype=c.dtype)
    for i in range(n):
        for r in range(4):
            for shown,orig in enumerate(maps[i][r]):
                choice[i,orig]+=c[i,r,shown]/4.0
    full=f.mean(dim=1)
    probs=torch.softmax(choice,dim=-1)
    rank4=torch.argsort(choice,dim=-1,descending=True)
    return {
      "top1":rank4[:,0].numpy().astype(np.int8),
      "rank4":rank4.numpy().astype(np.int8),
      "choice_q8":torch.clamp(torch.floor(probs*8+1e-12),max=7).numpy().astype(np.int8),
      "full_top8":torch.topk(full,8,dim=-1).indices.numpy().astype(np.int32),
      "full_top32":torch.topk(full,32,dim=-1).indices.numpy().astype(np.int32),
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
    prompts,maps=flatten(tok,rows)
    arrays=evaluate(model,tok,prompts,maps,choice_ids(tok))
    arrays.update({
      "item_ids":np.array([str(r["id"]) for r in rows],dtype="U64"),
      "answer_keys":np.array([str(r["answerKey"]) for r in rows],dtype="U4"),
      "layer":np.array([LAYER],dtype=np.int16),
      "epsilon_index":np.array([EIDX],dtype=np.int16),
      "epsilon":np.array([0.0 if EPSILON is None else EPSILON],dtype=np.float32),
      "scale":np.array([1.0 if SCALE is None else SCALE],dtype=np.float32),
    })
    npz=OUT/f"qwen_L{LAYER}_E{EIDX}.npz"
    np.savez_compressed(npz,**arrays)
    receipt={
      "status":"PASS","layer":LAYER,"epsilon_index":EIDX,
      "epsilon":None if EPSILON is None else float(EPSILON),
      "scale":1.0 if SCALE is None else float(SCALE),
      "model":{"id":MODEL_ID,"revision":MODEL_REVISION,
               "num_hidden_layers":model.config.num_hidden_layers},
      "data":{"id":DATASET_ID,"revision":dsha,"file":DATASET_FILE,
              "n_items":POOL_SIZE,
              "selection":"SHA256(item id), first 96 canonical A-D rows"},
      "n_prompt_realizations":len(prompts),
      "operators":["TOP1","RANK4","CHOICE_Q8","FULL_TOP8","FULL_TOP32"],
      "npz_sha256":hashlib.sha256(npz.read_bytes()).hexdigest(),
      "software":{"python":sys.version,"torch":torch.__version__,
                  "numpy":np.__version__,"platform":platform.platform()},
      "elapsed_seconds":time.time()-t0,
    }
    dump(OUT/f"qwen_L{LAYER}_E{EIDX}_receipt.json",receipt)
    print(json.dumps(receipt,indent=2,sort_keys=True))

if __name__=="__main__": main()
