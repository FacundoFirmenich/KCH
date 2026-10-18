#!/usr/bin/env python3
"""BIFM v0.10 — development-selected substantive OLMo M4 replication.

Layer and scale are selected only on a disjoint development pool. A candidate
must preserve every development top-1 decision and exceed preregistered hidden
and distributional effect floors. The locked candidate is then evaluated on
independent observation and counterfactual pools.
"""
from __future__ import annotations
import hashlib, json, os, platform, sys, time
from collections import Counter
from pathlib import Path

import pandas as pd
import torch
from huggingface_hub import HfApi, hf_hub_download
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID="allenai/OLMo-2-0425-1B-Instruct"
DATASET_ID="allenai/ai2_arc"
DATASET_FILE="ARC-Challenge/validation-00000-of-00001.parquet"
LAYERS=(2,5,8,11,14)
SCALES=(0.0,0.5,1.5,2.0,3.0,5.0)
POOL_SIZE=96
DEV_N=8
OBS_N=12
CF_N=12
BATCH=8
HIDDEN_REL_L2_FLOOR=0.01
JS_FLOOR=1e-4
OUT=Path(os.environ.get("BIFM_OUT","bifm_v0100_olmo_results"))
OUT.mkdir(parents=True,exist_ok=True)


def sha(s:str)->str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def dump(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True),encoding="utf-8")


def item_text(row,rot):
    labels="ABCD"; texts=list(row["choices"]["text"]); order=[(j+rot)%4 for j in range(4)]
    lines="\n".join(f"{labels[j]}. {texts[order[j]]}" for j in range(4))
    return (
      "Answer this multiple-choice science question. Return only one letter: "
      "A, B, C, or D.\n\n"
      f"Question: {row['question'].strip()}\n{lines}\nAnswer:"
    ),order


def render(tok,text):
    return tok.apply_chat_template(
      [{"role":"user","content":text}],tokenize=False,add_generation_prompt=True
    )


def choice_ids(tok):
    out={}
    for lab in "ABCD":
        for candidate in (" "+lab,lab):
            ids=tok.encode(candidate,add_special_tokens=False)
            if len(ids)==1:
                out[lab]=ids[0]; break
        if lab not in out: raise RuntimeError(f"{lab} is not single-token")
    assert len(set(out.values()))==4
    return out


def flatten(tok,rows):
    prompts=[]; maps=[]
    for row in rows:
        pm=[]
        for r in range(4):
            text,order=item_text(row,r)
            prompts.append(render(tok,text)); pm.append(order)
        maps.append(pm)
    return prompts,maps


def run(model,tok,prompts,cids,layer_idx=None,scale=None,capture=False):
    choices=[]; full=[]; hidden=[]; hooks=[]
    if layer_idx is not None and scale is not None:
        def mlp_hook(module,inputs,output):
            return output*scale
        hooks.append(model.model.layers[layer_idx].mlp.register_forward_hook(mlp_hook))
    if layer_idx is not None and capture:
        def layer_hook(module,inputs,output):
            t=output[0] if isinstance(output,(tuple,list)) else output
            hidden.append(t[:,-1,:].detach().float().cpu())
        hooks.append(model.model.layers[layer_idx].register_forward_hook(layer_hook))
    try:
        with torch.inference_mode():
            for s in range(0,len(prompts),BATCH):
                enc=tok(prompts[s:s+BATCH],return_tensors="pt",padding=True,
                        truncation=True,max_length=384)
                core=model.model(**enc,use_cache=False,return_dict=True)
                logits=model.lm_head(core.last_hidden_state[:,-1,:]).detach().float().cpu()
                choices.append(torch.stack([logits[:,cids[x]] for x in "ABCD"],dim=1))
                full.append(logits)
    finally:
        for h in hooks: h.remove()
    return {"choice":torch.cat(choices),"full":torch.cat(full),
            "hidden":torch.cat(hidden) if hidden else None}


def aggregate(raw,maps):
    n=len(maps); c=raw["choice"].reshape(n,4,4)
    f=raw["full"].reshape(n,4,raw["full"].shape[-1])
    choice=torch.zeros((n,4),dtype=c.dtype)
    for i in range(n):
        for r in range(4):
            for shown,orig in enumerate(maps[i][r]):
                choice[i,orig]+=c[i,r,shown]/4.0
    full=f.mean(dim=1)
    vals,idx=torch.topk(choice,2,dim=1)
    raw.update({"choice_agg":choice,"full_agg":full,"pred":idx[:,0],
                "margin":vals[:,0]-vals[:,1]})
    return raw


def eval_rows(model,tok,cids,rows,layer=None,scale=None,capture=False):
    prompts,maps=flatten(tok,rows)
    return aggregate(run(model,tok,prompts,cids,layer_idx=layer,
                         scale=scale,capture=capture),maps)


def balanced_high(pool,pred,margin,n):
    per=max(1,n//4); out=[]
    for cls in range(4):
        cand=sorted([i for i in pool if int(pred[i])==cls],
                    key=lambda i:(-float(margin[i]),i))
        out.extend(cand[:per])
    out=list(dict.fromkeys(out))
    if len(out)<n:
        rest=[i for i in sorted(pool,key=lambda i:(-float(margin[i]),i)) if i not in out]
        out.extend(rest[:n-len(out)])
    return out[:n]


def js(a,b):
    la=torch.log_softmax(a,dim=-1); lb=torch.log_softmax(b,dim=-1)
    pa=la.exp(); pb=lb.exp(); m=(pa+pb)*0.5; lm=torch.log(m.clamp_min(1e-30))
    return 0.5*((pa*(la-lm)).sum(-1)+(pb*(lb-lm)).sum(-1))


def effect_metrics(base,pert):
    rel=(pert["hidden"]-base["hidden"]).norm(dim=1)/(base["hidden"].norm(dim=1)+1e-12)
    cos=1.0-torch.nn.functional.cosine_similarity(pert["hidden"],base["hidden"],dim=1)
    return {
      "flips":int((pert["pred"]!=base["pred"]).sum().item()),
      "hidden_relative_l2_mean":float(rel.mean().item()),
      "hidden_relative_l2_min":float(rel.min().item()),
      "hidden_cosine_distance_mean":float(cos.mean().item()),
      "js_mean":float(js(base["full_agg"],pert["full_agg"]).mean().item()),
    }


def main():
    t0=time.time(); torch.manual_seed(0)
    torch.set_num_threads(max(1,min(4,os.cpu_count() or 1)))
    api=HfApi(); model_sha=api.model_info(MODEL_ID).sha; dsha=api.dataset_info(DATASET_ID).sha
    parquet=hf_hub_download(repo_id=DATASET_ID,repo_type="dataset",
                            filename=DATASET_FILE,revision=dsha)
    df=pd.read_parquet(parquet)
    rows=[r for r in df.to_dict("records") if list(r["choices"]["label"])==["A","B","C","D"]]
    rows=sorted(rows,key=lambda r:sha(str(r["id"])))[:POOL_SIZE]
    tok=AutoTokenizer.from_pretrained(MODEL_ID,revision=model_sha)
    tok.padding_side="left"
    if tok.pad_token_id is None: tok.pad_token=tok.eos_token
    model=AutoModelForCausalLM.from_pretrained(
      MODEL_ID,revision=model_sha,torch_dtype=torch.float32,low_cpu_mem_usage=True
    ); model.eval(); cids=choice_ids(tok)
    assert model.config.num_hidden_layers==16

    base_all=eval_rows(model,tok,cids,rows)
    pred,margin=base_all["pred"],base_all["margin"]
    dev_idx=balanced_high(list(range(0,32)),pred,margin,DEV_N)
    obs_idx=balanced_high(list(range(32,64)),pred,margin,OBS_N)
    cf_idx=sorted(range(64,96),key=lambda i:(float(margin[i]),i))[:CF_N]
    dev_rows=[rows[i] for i in dev_idx]; obs_rows=[rows[i] for i in obs_idx]; cf_rows=[rows[i] for i in cf_idx]

    candidates=[]
    for layer in LAYERS:
        dev0=eval_rows(model,tok,cids,dev_rows,layer=layer,capture=True)
        for scale in SCALES:
            dev1=eval_rows(model,tok,cids,dev_rows,layer=layer,scale=scale,capture=True)
            m=effect_metrics(dev0,dev1)
            qualifies=(m["flips"]==0 and
                       m["hidden_relative_l2_mean"]>=HIDDEN_REL_L2_FLOOR and
                       m["js_mean"]>=JS_FLOOR)
            candidates.append({"layer":layer,"scale":float(scale),
              "epsilon":float(scale-1.0),"qualifies":bool(qualifies),**m})

    eligible=[c for c in candidates if c["qualifies"]]
    selected=None
    if eligible:
        selected=max(eligible,key=lambda c:(c["js_mean"],c["hidden_relative_l2_mean"],
                                            abs(c["epsilon"]),-c["layer"]))

    result={
      "model":{"id":MODEL_ID,"revision":model_sha,
               "parameters_computed":sum(p.numel() for p in model.parameters()),
               "num_hidden_layers":model.config.num_hidden_layers,
               "hidden_size":model.config.hidden_size},
      "data":{"id":DATASET_ID,"revision":dsha,"file":DATASET_FILE},
      "selection":{
        "layers":list(LAYERS),"scales":list(SCALES),
        "hidden_relative_l2_floor":HIDDEN_REL_L2_FLOOR,"js_floor":JS_FLOOR,
        "criterion":"max development JS among exact-development-collision candidates passing both material-effect floors",
        "candidates":candidates,"selected":selected,
      },
      "split":{"development_ids":[str(rows[i]["id"]) for i in dev_idx],
               "observation_ids":[str(rows[i]["id"]) for i in obs_idx],
               "counterfactual_ids":[str(rows[i]["id"]) for i in cf_idx]},
      "status":"NO_SUBSTANTIVE_DEV_COLLISION",
      "observation":None,"counterfactual":None,
      "software":{"python":sys.version,"torch":torch.__version__,"platform":platform.platform()},
      "claim_boundary":[
        "Candidate selection uses only the development pool.",
        "A successful observation replication requires exact top-1 collision plus preregistered material-effect floors.",
        "No global mechanistic, biological, phenomenal, semantic, or authority conclusion follows."
      ],
    }

    if selected is not None:
        layer=int(selected["layer"]); scale=float(selected["scale"])
        obs0=eval_rows(model,tok,cids,obs_rows,layer=layer,capture=True)
        obs1=eval_rows(model,tok,cids,obs_rows,layer=layer,scale=scale,capture=True)
        cf0=eval_rows(model,tok,cids,cf_rows,layer=layer,capture=True)
        cf1=eval_rows(model,tok,cids,cf_rows,layer=layer,scale=scale,capture=True)
        om=effect_metrics(obs0,obs1); cm=effect_metrics(cf0,cf1)
        observation_pass=(om["flips"]==0 and
                          om["hidden_relative_l2_mean"]>=HIDDEN_REL_L2_FLOOR and
                          om["js_mean"]>=JS_FLOOR)
        if observation_pass:
            result["status"]="PASS_M4_M3_SUBSTANTIVE" if cm["flips"]>0 else "PASS_M4_M2_SUBSTANTIVE"
        else:
            result["status"]="DEV_SELECTED_NOT_REPLICATED"
        result["observation"]={"n":OBS_N,**om,
          "prediction_distribution":dict(sorted(Counter("ABCD"[int(x)] for x in obs0["pred"]).items()))}
        result["counterfactual"]={"n":CF_N,**cm,
          "flip_rate":cm["flips"]/CF_N,
          "prediction_distribution":dict(sorted(Counter("ABCD"[int(x)] for x in cf0["pred"]).items()))}

    result["elapsed_seconds"]=time.time()-t0
    dump(OUT/"olmo_substantive_m4.json",result)
    pd.DataFrame(candidates).to_csv(OUT/"development_candidates.csv",index=False)
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=="__main__": main()
