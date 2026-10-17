#!/usr/bin/env python3
"""BIFM v0.9 — cross-model identifiability frontier on real ARC stimuli.

Measures the grid frontier
  eps*_G(B_n, layer) = max{eps in G : O_{B_n}(m_eps)=O_{B_n}(m_0)}
for nested B_4 subset B_8 subset B_12 subset B_16 under permutation-averaged
content-level multiple-choice scoring.

The intervention is causal and internal: scale one decoder-layer MLP output by
1+eps. This is a constructive identifiability experiment, not a prevalence or
leaderboard claim.
"""
from __future__ import annotations
import hashlib, json, os, platform, sys, time
from collections import Counter
from pathlib import Path

import pandas as pd
import torch
from huggingface_hub import hf_hub_download
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID=os.environ["MODEL_ID"]
MODEL_REVISION=os.environ["MODEL_REVISION"]
LAYER_SPEC=[int(x) for x in os.environ["LAYER_SPEC"].split(",") if x.strip()]
MODEL_TAG=os.environ.get("MODEL_TAG","model")
DATASET_ID="allenai/ai2_arc"
DATASET_REVISION="210d026faf9955653af8916fad021475a3f00453"
DATASET_FILE="ARC-Challenge/validation-00000-of-00001.parquet"

POOL_SIZE=96
OBS_POOL=range(32,64)
CF_POOL=range(64,96)
OBS_MAX=16
CF_N=12
SIZES=(4,8,12,16)
EPS_GRID=(0.02,0.05,0.10,0.20,0.35,0.50,0.75,1.00,1.50,2.00,3.00,4.00,6.00,8.00)
BATCH=int(os.environ.get("BATCH","8"))
OUT=Path(os.environ.get("BIFM_OUT",f"bifm_v090_{MODEL_TAG}"))
OUT.mkdir(parents=True,exist_ok=True)

def h(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()
def dump(path,obj): Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True),encoding="utf-8")

def item_text(row,rot):
    texts=list(row["choices"]["text"])
    order=[(j+rot)%4 for j in range(4)]
    lines="\n".join(f"{'ABCD'[j]}. {texts[order[j]]}" for j in range(4))
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

def get_choice_ids(tok):
    out={}
    for lab in "ABCD":
        for s in (" "+lab,lab):
            ids=tok.encode(s,add_special_tokens=False)
            if len(ids)==1:
                out[lab]=ids[0]; break
        if lab not in out: raise RuntimeError(f"No single token for {lab}")
    if len(set(out.values()))!=4: raise RuntimeError(str(out))
    return out

def flatten(tok,rows):
    prompts=[]; maps=[]
    for row in rows:
        per=[]
        for r in range(4):
            t,m=item_text(row,r); prompts.append(render(tok,t)); per.append(m)
        maps.append(per)
    return prompts,maps

def run_flat(model,tok,prompts,cids,layer_idx=None,scale=None,capture=False,full=False):
    choices=[]; fulls=[]; hidden=[]; receipts=[]
    hooks=[]
    if layer_idx is not None:
        layer=model.model.layers[layer_idx]
        if scale is not None:
            def mh(module,inputs,output):
                receipts.append(float(output.detach().float().norm().cpu()))
                return output*scale
            hooks.append(layer.mlp.register_forward_hook(mh))
        if capture:
            def lh(module,inputs,output):
                t=output[0] if isinstance(output,(tuple,list)) else output
                hidden.append(t[:,-1,:].detach().float().cpu())
            hooks.append(layer.register_forward_hook(lh))
    try:
        with torch.inference_mode():
            for s in range(0,len(prompts),BATCH):
                enc=tok(prompts[s:s+BATCH],return_tensors="pt",padding=True,truncation=True,max_length=384)
                core=model.model(**enc,use_cache=False,return_dict=True)
                logits=model.lm_head(core.last_hidden_state[:,-1,:]).detach().float().cpu()
                choices.append(torch.stack([logits[:,cids[x]] for x in "ABCD"],dim=1))
                if full: fulls.append(logits)
    finally:
        for hk in hooks: hk.remove()
    return {"choice":torch.cat(choices),"full":torch.cat(fulls) if fulls else None,
            "hidden":torch.cat(hidden) if hidden else None,"receipts":receipts}

def aggregate(flat_choice,maps):
    n=len(maps); x=flat_choice.reshape(n,4,4); agg=torch.zeros((n,4),dtype=x.dtype)
    for i in range(n):
        for r in range(4):
            for shown,orig in enumerate(maps[i][r]): agg[i,orig]+=x[i,r,shown]/4.0
    vals,idx=torch.topk(agg,2,dim=1)
    return agg,idx[:,0],vals[:,0]-vals[:,1]

def eval_items(model,tok,cids,rows,layer=None,scale=None,capture=False,full=False):
    prompts,maps=flatten(tok,rows)
    raw=run_flat(model,tok,prompts,cids,layer_idx=layer,scale=scale,capture=capture,full=full)
    agg,pred,margin=aggregate(raw["choice"],maps)
    raw.update({"agg":agg,"pred":pred,"margin":margin})
    return raw

def nested_balanced_order(pool,pred,margin,nmax):
    buckets={c:sorted([i for i in pool if int(pred[i])==c],key=lambda i:(-float(margin[i]),i)) for c in range(4)}
    out=[]; rank=0
    while len(out)<nmax and any(rank<len(buckets[c]) for c in range(4)):
        for c in range(4):
            if rank<len(buckets[c]) and len(out)<nmax: out.append(buckets[c][rank])
        rank+=1
    if len(out)<nmax:
        rest=[i for i in sorted(pool,key=lambda i:(-float(margin[i]),i)) if i not in out]
        out.extend(rest[:nmax-len(out)])
    return out[:nmax]

def js(a,b):
    la=torch.log_softmax(a,dim=-1); lb=torch.log_softmax(b,dim=-1)
    pa=la.exp(); pb=lb.exp(); m=(pa+pb)*.5; lm=torch.log(m.clamp_min(1e-30))
    return .5*((pa*(la-lm)).sum(-1)+(pb*(lb-lm)).sum(-1))

def dist(pred): return dict(sorted(Counter("ABCD"[int(x)] for x in pred).items()))

def main():
    t0=time.time(); torch.manual_seed(0); torch.set_num_threads(max(1,min(4,os.cpu_count() or 1)))
    pq=hf_hub_download(repo_id=DATASET_ID,repo_type="dataset",filename=DATASET_FILE,revision=DATASET_REVISION)
    df=pd.read_parquet(pq)
    rows=[r for r in df.to_dict("records") if list(r["choices"]["label"])==["A","B","C","D"]]
    rows=sorted(rows,key=lambda r:h(str(r["id"])))[:POOL_SIZE]
    assert len(rows)==POOL_SIZE

    tok=AutoTokenizer.from_pretrained(MODEL_ID,revision=MODEL_REVISION)
    tok.padding_side="left"
    if tok.pad_token_id is None: tok.pad_token=tok.eos_token
    model=AutoModelForCausalLM.from_pretrained(MODEL_ID,revision=MODEL_REVISION,
        torch_dtype=torch.float32,low_cpu_mem_usage=True)
    model.eval(); cids=get_choice_ids(tok)
    n_layers=len(model.model.layers)
    if any(l<0 or l>=n_layers for l in LAYER_SPEC): raise RuntimeError((LAYER_SPEC,n_layers))
    param_count=sum(p.numel() for p in model.parameters())

    base=eval_items(model,tok,cids,rows)
    obs_order=nested_balanced_order(list(OBS_POOL),base["pred"],base["margin"],OBS_MAX)
    cf_idx=sorted(list(CF_POOL),key=lambda i:(float(base["margin"][i]),i))[:CF_N]
    obs_rows=[rows[i] for i in obs_order]; cf_rows=[rows[i] for i in cf_idx]
    obs_base=eval_items(model,tok,cids,obs_rows,full=True)
    cf_base=eval_items(model,tok,cids,cf_rows,full=True)

    layer_results=[]
    for layer_idx in LAYER_SPEC:
        baseline_hidden=eval_items(model,tok,cids,obs_rows,layer=layer_idx,capture=True)["hidden"]
        eps_records=[]
        pred_by_eps={}
        for eps in EPS_GRID:
            r=eval_items(model,tok,cids,obs_rows,layer=layer_idx,scale=1.0+eps)
            pred_by_eps[eps]=r["pred"]
            eps_records.append({
                "epsilon":eps,
                "flips_by_n":{str(n):int((r["pred"][:n]!=obs_base["pred"][:n]).sum().item()) for n in SIZES}
            })

        frontiers={}
        selected_eps=set()
        for n in SIZES:
            valid=[eps for eps in EPS_GRID if int((pred_by_eps[eps][:n]!=obs_base["pred"][:n]).sum().item())==0]
            e=max(valid) if valid else None
            if e is not None: selected_eps.add(e)
            frontiers[str(n)]={
                "epsilon_star_grid":e,
                "scale_star_grid":None if e is None else 1.0+e,
                "right_censored":bool(e==max(EPS_GRID)) if e is not None else False,
                "valid_grid_values":valid,
            }

        seq=[frontiers[str(n)]["epsilon_star_grid"] if frontiers[str(n)]["epsilon_star_grid"] is not None else -1 for n in SIZES]
        nested_monotone=all(seq[i]>=seq[i+1] for i in range(len(seq)-1))

        cf_cache={}
        for eps in sorted(selected_eps):
            rr=eval_items(model,tok,cids,cf_rows,layer=layer_idx,scale=1.0+eps)
            cf_cache[eps]={
                "flips":int((rr["pred"]!=cf_base["pred"]).sum().item()),
                "flip_rate":float((rr["pred"]!=cf_base["pred"]).float().mean().item()),
            }
        for n in SIZES:
            e=frontiers[str(n)]["epsilon_star_grid"]
            frontiers[str(n)]["counterfactual_at_epsilon_star"]=None if e is None else cf_cache[e]

        e16=frontiers[str(OBS_MAX)]["epsilon_star_grid"]
        internal=None
        if e16 is not None:
            rr=eval_items(model,tok,cids,obs_rows,layer=layer_idx,scale=1.0+e16,capture=True,full=True)
            rel=(rr["hidden"]-baseline_hidden).norm(dim=1)/(baseline_hidden.norm(dim=1)+1e-12)
            cos=1.0-torch.nn.functional.cosine_similarity(rr["hidden"],baseline_hidden,dim=1)
            internal={
                "epsilon":e16,
                "hidden_relative_l2_mean":float(rel.mean().item()),
                "hidden_relative_l2_min":float(rel.min().item()),
                "hidden_cosine_distance_mean":float(cos.mean().item()),
                "observation_full_vocab_js_mean":float(js(obs_base["full"],rr["full"]).mean().item()),
                "observation_exact_collision_n16":bool(torch.equal(rr["pred"][:OBS_MAX],obs_base["pred"][:OBS_MAX])),
            }

        layer_results.append({
            "layer":layer_idx,
            "frontier":frontiers,
            "nested_frontier_monotonicity":nested_monotone,
            "epsilon_scan":eps_records,
            "internal_at_n16_frontier":internal,
        })

    result={
        "status":"PASS_M4_CANDIDATE",
        "model":{"id":MODEL_ID,"revision":MODEL_REVISION,"tag":MODEL_TAG,
                 "parameter_count_runtime":param_count,"num_layers":n_layers,"tested_layers":LAYER_SPEC},
        "data":{"id":DATASET_ID,"revision":DATASET_REVISION,"file":DATASET_FILE,"pool_size":POOL_SIZE},
        "observation":{
            "definition":"permutation-averaged original-option score over four cyclic answer orders, then content top-1",
            "nested_sizes":list(SIZES),
            "max_observation_order":[str(rows[i]["id"]) for i in obs_order],
            "baseline_distribution":dist(obs_base["pred"]),
        },
        "counterfactual":{
            "n":CF_N,"items":[str(rows[i]["id"]) for i in cf_idx],
            "baseline_distribution":dist(cf_base["pred"]),
        },
        "epsilon_grid":list(EPS_GRID),
        "layers":layer_results,
        "checks":{
            "all_nested_monotone":all(x["nested_frontier_monotonicity"] for x in layer_results),
            "at_least_one_n16_collision":any(x["frontier"][str(OBS_MAX)]["epsilon_star_grid"] is not None for x in layer_results),
            "at_least_one_counterfactual_flip_at_n16_frontier":any(
                (x["frontier"][str(OBS_MAX)]["counterfactual_at_epsilon_star"] or {}).get("flips",0)>0
                for x in layer_results
            ),
        },
        "software":{"python":sys.version,"torch":torch.__version__,"platform":platform.platform()},
        "elapsed_seconds":time.time()-t0,
        "claim_boundary":[
            "epsilon_star is exact only on the frozen discrete grid.",
            "right_censored means the true invisible frontier exceeds the largest tested epsilon.",
            "the claim concerns the declared MLP-scaling state relative to the declared finite observation operator.",
            "no biological, phenomenal, semantic-understanding, or global mechanism identity claim follows."
        ],
    }
    if not result["checks"]["all_nested_monotone"] or not result["checks"]["at_least_one_n16_collision"]:
        result["status"]="FAIL"
    elif result["checks"]["at_least_one_counterfactual_flip_at_n16_frontier"]:
        result["status"]="PASS_M4_STRONG_LOCAL"
    dump(OUT/"frontier_receipt.json",result)
    print(json.dumps(result,indent=2,sort_keys=True))
    if result["status"]=="FAIL": raise SystemExit(2)

if __name__=="__main__": main()
