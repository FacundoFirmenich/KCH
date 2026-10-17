#!/usr/bin/env python3
"""BIFM v0.9 — empirical invisibility frontier on Qwen3-0.6B.

Estimates a grid approximation to
  epsilon*(B, layer, n) = sup{epsilon: O_B(m_epsilon)=O_B(m_0)}
for nested, permutation-averaged ARC observation sets.
"""
from __future__ import annotations
import hashlib, json, os, platform, sys, time
from pathlib import Path

import pandas as pd
import torch
from huggingface_hub import HfApi, hf_hub_download
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID="Qwen/Qwen3-0.6B"
MODEL_REVISION="c1899de289a04d12100db370d81485cdf75e47ca"
DATASET_ID="allenai/ai2_arc"
DATASET_FILE="ARC-Challenge/validation-00000-of-00001.parquet"
LAYERS=(4,14,24)
OBS_SIZES=(4,8,12,16)
EPS_GRID=(0.05,0.10,0.20,0.35,0.50,0.75,1.00,1.50,2.00)
POOL_SIZE=96
MAX_OBS=max(OBS_SIZES)
CF_N=12
BATCH=8
OUT=Path(os.environ.get("BIFM_OUT","bifm_v090_frontier_results"))
OUT.mkdir(parents=True,exist_ok=True)

def sha(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()
def dump(path,obj): Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True),encoding="utf-8")

def item_text(row,rot):
    labels="ABCD"; texts=list(row["choices"]["text"]); order=[(j+rot)%4 for j in range(4)]
    lines="\n".join(f"{labels[j]}. {texts[order[j]]}" for j in range(4))
    return ("Answer this multiple-choice science question. Return only one letter: "
            "A, B, C, or D.\n\n"
            f"Question: {row['question'].strip()}\n{lines}\nAnswer:"),order

def render(tok,text):
    try:
        return tok.apply_chat_template([{"role":"user","content":text}],tokenize=False,
          add_generation_prompt=True,enable_thinking=False)
    except TypeError:
        return tok.apply_chat_template([{"role":"user","content":text}],tokenize=False,
          add_generation_prompt=True)

def choice_ids(tok):
    out={}
    for lab in "ABCD":
        for candidate in (" "+lab,lab):
            ids=tok.encode(candidate,add_special_tokens=False)
            if len(ids)==1: out[lab]=ids[0]; break
        if lab not in out: raise RuntimeError(f"{lab} not single-token")
    return out

def flatten(tok,rows):
    prompts=[]; maps=[]
    for row in rows:
        pm=[]
        for r in range(4):
            text,order=item_text(row,r); prompts.append(render(tok,text)); pm.append(order)
        maps.append(pm)
    return prompts,maps

def run(model,tok,prompts,cids,layer_idx=None,scale=None,capture=False,full=False):
    choices=[]; fulls=[]; hidden=[]; hooks=[]
    if layer_idx is not None and scale is not None:
        layer=model.model.layers[layer_idx]
        def mlp_hook(module,inputs,output): return output*scale
        hooks.append(layer.mlp.register_forward_hook(mlp_hook))
    if layer_idx is not None and capture:
        layer=model.model.layers[layer_idx]
        def layer_hook(module,inputs,output):
            t=output[0] if isinstance(output,(tuple,list)) else output
            hidden.append(t[:,-1,:].detach().float().cpu())
        hooks.append(layer.register_forward_hook(layer_hook))
    try:
        with torch.inference_mode():
            for s in range(0,len(prompts),BATCH):
                enc=tok(prompts[s:s+BATCH],return_tensors="pt",padding=True,truncation=True,max_length=384)
                core=model.model(**enc,use_cache=False,return_dict=True)
                logits=model.lm_head(core.last_hidden_state[:,-1,:]).detach().float().cpu()
                choices.append(torch.stack([logits[:,cids[x]] for x in "ABCD"],dim=1))
                if full: fulls.append(logits)
    finally:
        for h in hooks: h.remove()
    return {"choice":torch.cat(choices),"full":torch.cat(fulls) if fulls else None,
            "hidden":torch.cat(hidden) if hidden else None}

def aggregate(flat,maps):
    n=len(maps); x=flat.reshape(n,4,4); agg=torch.zeros((n,4),dtype=x.dtype)
    for i in range(n):
        for r in range(4):
            for shown,orig in enumerate(maps[i][r]): agg[i,orig]+=x[i,r,shown]/4.0
    vals,idx=torch.topk(agg,2,dim=1)
    return {"scores":agg,"pred":idx[:,0],"margin":vals[:,0]-vals[:,1]}

def eval_rows(model,tok,cids,rows,layer=None,scale=None,capture=False,full=False):
    prompts,maps=flatten(tok,rows)
    raw=run(model,tok,prompts,cids,layer_idx=layer,scale=scale,capture=capture,full=full)
    raw.update(aggregate(raw["choice"],maps))
    return raw

def nested_balanced(pool,pred,margin,nmax):
    queues={}
    for cls in range(4):
        queues[cls]=sorted([i for i in pool if int(pred[i])==cls],key=lambda i:(-float(margin[i]),i))
    out=[]; rank=0
    while len(out)<nmax and rank<100:
        for cls in range(4):
            if rank<len(queues[cls]) and queues[cls][rank] not in out:
                out.append(queues[cls][rank])
                if len(out)==nmax: break
        rank+=1
    if len(out)<nmax:
        rest=[i for i in sorted(pool,key=lambda i:(-float(margin[i]),i)) if i not in out]
        out.extend(rest[:nmax-len(out)])
    return out[:nmax]

def js(a,b):
    la=torch.log_softmax(a,dim=-1); lb=torch.log_softmax(b,dim=-1)
    pa=la.exp(); pb=lb.exp(); m=(pa+pb)*0.5; lm=torch.log(m.clamp_min(1e-30))
    return 0.5*((pa*(la-lm)).sum(-1)+(pb*(lb-lm)).sum(-1))

def main():
    t0=time.time(); torch.manual_seed(0); torch.set_num_threads(max(1,min(4,os.cpu_count() or 1)))
    api=HfApi(); dsha=api.dataset_info(DATASET_ID).sha
    parquet=hf_hub_download(repo_id=DATASET_ID,repo_type="dataset",filename=DATASET_FILE,revision=dsha)
    df=pd.read_parquet(parquet)
    rows=[r for r in df.to_dict("records") if list(r["choices"]["label"])==["A","B","C","D"]]
    rows=sorted(rows,key=lambda r:sha(str(r["id"])))[:POOL_SIZE]
    tok=AutoTokenizer.from_pretrained(MODEL_ID,revision=MODEL_REVISION); tok.padding_side="left"
    if tok.pad_token_id is None: tok.pad_token=tok.eos_token
    model=AutoModelForCausalLM.from_pretrained(MODEL_ID,revision=MODEL_REVISION,
      torch_dtype=torch.float32,low_cpu_mem_usage=True); model.eval()
    cids=choice_ids(tok)

    base=eval_rows(model,tok,cids,rows)
    pred,margin=base["pred"],base["margin"]
    obs_rank=nested_balanced(list(range(32,64)),pred,margin,MAX_OBS)
    cf_idx=sorted(range(64,96),key=lambda i:(float(margin[i]),i))[:CF_N]
    obs_rows=[rows[i] for i in obs_rank]; cf_rows=[rows[i] for i in cf_idx]
    obs0=eval_rows(model,tok,cids,obs_rows)
    cf0=eval_rows(model,tok,cids,cf_rows)

    layer_results=[]
    for layer in LAYERS:
        traces=[]; star={n:None for n in OBS_SIZES}
        for eps in EPS_GRID:
            r=eval_rows(model,tok,cids,obs_rows,layer=layer,scale=1.0+eps)
            flips={}
            for n in OBS_SIZES:
                f=int((r["pred"][:n]!=obs0["pred"][:n]).sum().item())
                flips[str(n)]=f
                if f==0: star[n]=eps
            traces.append({"epsilon":float(eps),"flips_by_n":flips})
        # Nested sets imply non-increasing invisibility threshold with n.
        seq=[-1.0 if star[n] is None else float(star[n]) for n in OBS_SIZES]
        assert all(seq[i]>=seq[i+1] for i in range(len(seq)-1)), (layer,seq)

        star16=star[MAX_OBS]
        diagnostic=None
        if star16 is not None:
            b0=eval_rows(model,tok,cids,obs_rows,layer=layer,capture=True,full=True)
            b1=eval_rows(model,tok,cids,obs_rows,layer=layer,scale=1.0+star16,capture=True,full=True)
            c1=eval_rows(model,tok,cids,cf_rows,layer=layer,scale=1.0+star16)
            rel=(b1["hidden"]-b0["hidden"]).norm(dim=1)/(b0["hidden"].norm(dim=1)+1e-12)
            diagnostic={
              "epsilon_star_n16":float(star16),"scale":float(1+star16),
              "hidden_relative_l2_mean":float(rel.mean()),"hidden_relative_l2_min":float(rel.min()),
              "js_mean":float(js(b0["full"],b1["full"]).mean()),
              "counterfactual_flips":int((c1["pred"]!=cf0["pred"]).sum().item()),
              "counterfactual_flip_rate":float((c1["pred"]!=cf0["pred"]).float().mean().item())
            }
        layer_results.append({
          "layer":layer,
          "epsilon_star_grid":{str(n):(None if star[n] is None else float(star[n])) for n in OBS_SIZES},
          "search_trace":traces,
          "n16_diagnostic":diagnostic,
        })

    result={
      "status":"PASS",
      "definition":"epsilon_star_grid(B,layer,n) is the largest tested epsilon whose MLP-output scaling leaves all nested observation decisions unchanged.",
      "model":{"id":MODEL_ID,"revision":MODEL_REVISION,"layers":model.config.num_hidden_layers},
      "data":{"id":DATASET_ID,"revision":dsha,"file":DATASET_FILE},
      "operator":"permutation-averaged content-level top-1 over four cyclic answer orders",
      "layers":list(LAYERS),"observation_sizes":list(OBS_SIZES),"epsilon_grid":list(EPS_GRID),
      "observation_order":[{"rank":k+1,"id":str(rows[i]["id"]),"baseline_prediction":"ABCD"[int(pred[i])],
         "margin":float(margin[i])} for k,i in enumerate(obs_rank)],
      "counterfactual_ids":[str(rows[i]["id"]) for i in cf_idx],
      "results":layer_results,
      "software":{"python":sys.version,"torch":torch.__version__,"platform":platform.platform()},
      "elapsed_seconds":time.time()-t0,
      "claim_boundary":[
        "epsilon_star is grid-limited, model-specific, layer-specific, and observation-operator-specific.",
        "The experiment estimates a local invisibility frontier, not global mechanistic equivalence.",
        "Nested-set monotonicity is a design invariant, not an empirical discovery."
      ],
    }
    dump(OUT/"qwen_invisibility_frontier.json",result)
    pd.DataFrame(result["observation_order"]).to_csv(OUT/"observation_order.csv",index=False)
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=="__main__": main()
