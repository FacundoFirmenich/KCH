#!/usr/bin/env python3
"""BIFM v0.9 — inter-model M4 replication on OLMo 2 1B Instruct.

Replicates the v0.8.1 permutation-averaged internal MLP collision protocol on
an independently developed open-weight model family.
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
LAYER_INDEX=8
POOL_SIZE=96
OBS_N=12
CF_N=12
BATCH=8
EPS_GRID=(0.02,0.05,0.10,0.20,0.35,0.50,0.75,1.00,1.50,2.00)
OUT=Path(os.environ.get("BIFM_OUT","bifm_v090_olmo_results"))
OUT.mkdir(parents=True,exist_ok=True)

def sha(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()
def dump(path,obj): Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True),encoding="utf-8")

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
        if lab not in out: raise RuntimeError(f"{lab} not single-token")
    assert len(set(out.values()))==4
    return out

def run_flat(model,tok,prompts,cids,scale=None,capture=False,full=False):
    choice=[]; fulls=[]; hids=[]; receipts=[]; hooks=[]
    layer=model.model.layers[LAYER_INDEX]
    if scale is not None:
        def mlp_hook(module,inputs,output):
            receipts.append(float(output.detach().float().norm().cpu()))
            return output*scale
        hooks.append(layer.mlp.register_forward_hook(mlp_hook))
    if capture:
        def layer_hook(module,inputs,output):
            t=output[0] if isinstance(output,(tuple,list)) else output
            hids.append(t[:,-1,:].detach().float().cpu())
        hooks.append(layer.register_forward_hook(layer_hook))
    try:
        with torch.inference_mode():
            for s in range(0,len(prompts),BATCH):
                enc=tok(prompts[s:s+BATCH],return_tensors="pt",padding=True,truncation=True,max_length=384)
                core=model.model(**enc,use_cache=False,return_dict=True)
                logits=model.lm_head(core.last_hidden_state[:,-1,:]).detach().float().cpu()
                choice.append(torch.stack([logits[:,cids[x]] for x in "ABCD"],dim=1))
                if full: fulls.append(logits)
    finally:
        for h in hooks: h.remove()
    return {
      "choice":torch.cat(choice),
      "full":torch.cat(fulls) if fulls else None,
      "hidden":torch.cat(hids) if hids else None,
      "receipts":receipts,
    }

def flatten(tok,rows):
    prompts=[]; maps=[]
    for row in rows:
        per=[]
        for r in range(4):
            text,order=item_text(row,r)
            prompts.append(render(tok,text)); per.append(order)
        maps.append(per)
    return prompts,maps

def aggregate(flat_choice,maps):
    n=len(maps); x=flat_choice.reshape(n,4,4)
    agg=torch.zeros((n,4),dtype=x.dtype); rotpred=[]
    for i in range(n):
        rp=[]
        for r in range(4):
            for shown,orig in enumerate(maps[i][r]):
                agg[i,orig]+=x[i,r,shown]/4.0
            rp.append(maps[i][r][int(x[i,r].argmax())])
        rotpred.append(rp)
    return agg,rotpred

def eval_items(model,tok,cids,rows,scale=None,capture=False,full=False):
    prompts,maps=flatten(tok,rows)
    raw=run_flat(model,tok,prompts,cids,scale=scale,capture=capture,full=full)
    agg,rotpred=aggregate(raw["choice"],maps)
    vals,idx=torch.topk(agg,2,dim=1)
    raw.update({"agg":agg,"pred":idx[:,0],"margin":vals[:,0]-vals[:,1],"rotpred":rotpred})
    return raw

def stratified(pool,pred,margin,n):
    per=max(1,n//4); out=[]
    for cls in range(4):
        cand=sorted([i for i in pool if int(pred[i])==cls],key=lambda i:(-float(margin[i]),i))
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

def main():
    t0=time.time(); torch.manual_seed(0); torch.set_num_threads(max(1,min(4,os.cpu_count() or 1)))
    api=HfApi()
    model_sha=api.model_info(MODEL_ID).sha
    dataset_sha=api.dataset_info(DATASET_ID).sha
    parquet=hf_hub_download(repo_id=DATASET_ID,repo_type="dataset",filename=DATASET_FILE,revision=dataset_sha)
    df=pd.read_parquet(parquet)
    rows=[r for r in df.to_dict("records") if list(r["choices"]["label"])==["A","B","C","D"]]
    rows=sorted(rows,key=lambda r:sha(str(r["id"])))[:POOL_SIZE]
    assert len(rows)==POOL_SIZE

    tok=AutoTokenizer.from_pretrained(MODEL_ID,revision=model_sha)
    tok.padding_side="left"
    if tok.pad_token_id is None: tok.pad_token=tok.eos_token
    model=AutoModelForCausalLM.from_pretrained(
      MODEL_ID,revision=model_sha,torch_dtype=torch.float32,low_cpu_mem_usage=True
    )
    model.eval()
    assert model.config.num_hidden_layers==16
    cids=choice_ids(tok)
    parameter_count=sum(p.numel() for p in model.parameters())

    base=eval_items(model,tok,cids,rows)
    pred,margin=base["pred"],base["margin"]
    obs_pool=list(range(32,64)); cf_pool=list(range(64,96))
    obs_idx=stratified(obs_pool,pred,margin,OBS_N)
    cf_idx=sorted(cf_pool,key=lambda i:(float(margin[i]),i))[:CF_N]
    obs_rows=[rows[i] for i in obs_idx]; cf_rows=[rows[i] for i in cf_idx]

    obs0=eval_items(model,tok,cids,obs_rows,capture=True,full=True)
    cf0=eval_items(model,tok,cids,cf_rows,capture=True,full=True)

    trace=[]; valid=[]
    for eps in EPS_GRID:
        e=eval_items(model,tok,cids,obs_rows,scale=1.0+eps)
        flips=int((e["pred"]!=obs0["pred"]).sum().item())
        trace.append({"epsilon":float(eps),"flips":flips,"agreement":1.0-flips/OBS_N})
        if flips==0: valid.append(eps)
    if not valid: raise SystemExit("FAIL_M1: no nonzero collision")
    selected=max(valid)

    obs1=eval_items(model,tok,cids,obs_rows,scale=1.0+selected,capture=True,full=True)
    cf1=eval_items(model,tok,cids,cf_rows,scale=1.0+selected,capture=True,full=True)
    of=int((obs1["pred"]!=obs0["pred"]).sum().item())
    cf=int((cf1["pred"]!=cf0["pred"]).sum().item())
    rel=(obs1["hidden"]-obs0["hidden"]).norm(dim=1)/(obs0["hidden"].norm(dim=1)+1e-12)
    cos=1.0-torch.nn.functional.cosine_similarity(obs1["hidden"],obs0["hidden"],dim=1)

    def consistency(x):
        n=sum(len(set(p))==1 for p in x)
        return {"all_four_rotations_agree":n,"n":len(x),"rate":n/len(x)}
    def dist(p): return dict(sorted(Counter("ABCD"[int(x)] for x in p).items()))
    def item(i): return {
       "id":str(rows[i]["id"]),"answer_key":str(rows[i]["answerKey"]),
       "baseline_prediction":"ABCD"[int(pred[i])],"baseline_margin":float(margin[i]),
       "id_sha256":sha(str(rows[i]["id"]))
    }

    status="PASS_M4_M3" if of==0 and cf>0 else "PASS_M4_M2" if of==0 else "FAIL"
    result={
      "status":status,
      "model":{"id":MODEL_ID,"revision":model_sha,"parameters_computed":parameter_count,
               "num_hidden_layers":model.config.num_hidden_layers,"hidden_size":model.config.hidden_size,
               "intervention_layer":LAYER_INDEX},
      "data":{"id":DATASET_ID,"revision":dataset_sha,"file":DATASET_FILE,"pool_size":POOL_SIZE},
      "operator":"four cyclic answer permutations, remapped to original content, mean score, content-level top-1",
      "intervention":{"kind":"mlp_output_scaling","selected_epsilon":float(selected),
                      "scale":float(1+selected),"search_trace":trace},
      "observation":{"n":OBS_N,"flips":of,"exact_collision":of==0,
        "hidden_relative_l2_mean":float(rel.mean()),"hidden_relative_l2_min":float(rel.min()),
        "hidden_cosine_distance_mean":float(cos.mean()),
        "js_mean":float(js(obs0["full"],obs1["full"]).mean()),
        "prediction_distribution":dist(obs0["pred"]),
        "rotation_consistency":consistency(obs0["rotpred"]),
        "items":[item(i) for i in obs_idx]},
      "counterfactual":{"n":CF_N,"flips":cf,"flip_rate":cf/CF_N,
        "js_mean":float(js(cf0["full"],cf1["full"]).mean()),
        "prediction_distribution":dist(cf0["pred"]),
        "rotation_consistency":consistency(cf0["rotpred"]),
        "items":[item(i) for i in cf_idx]},
      "replication_claim":"M4 requires an internal intervention collision on an independently developed open-weight family under the same observation logic.",
      "software":{"python":sys.version,"torch":torch.__version__,"platform":platform.platform()},
      "elapsed_seconds":time.time()-t0,
      "claim_boundary":[
        "This is a replication of intervention-state non-identifiability relative to a frozen finite observation operator.",
        "It is not a claim of global mechanistic equivalence.",
        "No biological, phenomenal, semantic-understanding, or authority claim is inherited."
      ],
    }
    dump(OUT/"olmo_m4_receipt.json",result)
    pd.DataFrame(result["observation"]["items"]).to_csv(OUT/"observation_items.csv",index=False)
    pd.DataFrame(result["counterfactual"]["items"]).to_csv(OUT/"counterfactual_items.csv",index=False)
    print(json.dumps(result,indent=2,sort_keys=True))
    if of!=0: raise SystemExit(2)

if __name__=="__main__": main()
