#!/usr/bin/env python3
"""BIFM v0.8.1 — permutation-invariant internal mechanistic collision.

Corrects the label/position sensitivity exposed by v0.8 by evaluating each ARC
item under all four cyclic answer permutations, remapping displayed A/B/C/D
logits back to the original answer contents, and averaging before top-1
selection. The only intervention is internal: scaling layer-14 MLP output.
"""
from __future__ import annotations
import hashlib, json, os, platform, sys, time
from collections import Counter
from pathlib import Path

import pandas as pd
import torch
from huggingface_hub import HfApi, hf_hub_download
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID="Qwen/Qwen3-0.6B"
MODEL_REVISION="c1899de289a04d12100db370d81485cdf75e47ca"
DATASET_ID="allenai/ai2_arc"
DATASET_FILE="ARC-Challenge/validation-00000-of-00001.parquet"
LAYER_INDEX=14
POOL_SIZE=96
OBS_N=12
CF_N=12
BATCH=4
EPS_GRID=(0.02,0.05,0.10,0.20,0.35,0.50,0.75,1.00)
OUT=Path(os.environ.get("BIFM_OUT","bifm_v081_results"))
OUT.mkdir(parents=True,exist_ok=True)

def sha(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()
def dump(path,obj): Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True),encoding="utf-8")

def item_text(row,rotation):
    labels="ABCD"
    texts=list(row["choices"]["text"])
    order=[(j+rotation)%4 for j in range(4)]
    lines="\n".join(f"{labels[j]}. {texts[order[j]]}" for j in range(4))
    body=(
      "Answer this multiple-choice science question. Return only one letter: "
      "A, B, C, or D.\n\n"
      f"Question: {row['question'].strip()}\n{lines}\nAnswer:"
    )
    return body,order

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
            if len(ids)==1:
                out[lab]=ids[0]; break
        if lab not in out: raise RuntimeError(f"{lab} is not single-token")
    assert len(set(out.values()))==4
    return out

def run_flat(model,tok,prompts,cids,scale=None,capture=False,full=False):
    choice=[]; fulls=[]; hids=[]; receipts=[]
    hooks=[]
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

def flatten_prompts(tok,rows):
    prompts=[]; maps=[]
    for row in rows:
        per=[]
        for r in range(4):
            text,order=item_text(row,r)
            prompts.append(render(tok,text))
            per.append(order)
        maps.append(per)
    return prompts,maps

def aggregate_choice(flat_choice,maps):
    n=len(maps)
    x=flat_choice.reshape(n,4,4)
    agg=torch.zeros((n,4),dtype=x.dtype)
    mapped_rotation_preds=[]
    for i in range(n):
        preds=[]
        for r in range(4):
            for shown_j,orig_j in enumerate(maps[i][r]):
                agg[i,orig_j]+=x[i,r,shown_j]/4.0
            shown_pred=int(x[i,r].argmax())
            preds.append(maps[i][r][shown_pred])
        mapped_rotation_preds.append(preds)
    return agg,mapped_rotation_preds

def top_margin(scores):
    vals,idx=torch.topk(scores,2,dim=1)
    return idx[:,0],vals[:,0]-vals[:,1]

def js(logits0,logits1):
    lp=torch.log_softmax(logits0,dim=-1); lq=torch.log_softmax(logits1,dim=-1)
    p=lp.exp(); q=lq.exp(); m=(p+q)*0.5; lm=torch.log(m.clamp_min(1e-30))
    return 0.5*((p*(lp-lm)).sum(-1)+(q*(lq-lm)).sum(-1))

def select_stratified(pool,pred,margin,n):
    per=max(1,n//4); selected=[]
    for cls in range(4):
        cand=[i for i in pool if int(pred[i])==cls]
        cand=sorted(cand,key=lambda i:(-float(margin[i]),i))
        selected.extend(cand[:per])
    selected=list(dict.fromkeys(selected))
    if len(selected)<n:
        rest=[i for i in sorted(pool,key=lambda i:(-float(margin[i]),i)) if i not in selected]
        selected.extend(rest[:n-len(selected)])
    return selected[:n]

def eval_items(model,tok,cids,rows,scale=None,capture=False,full=False):
    prompts,maps=flatten_prompts(tok,rows)
    raw=run_flat(model,tok,prompts,cids,scale=scale,capture=capture,full=full)
    agg,rotpred=aggregate_choice(raw["choice"],maps)
    pred,margin=top_margin(agg)
    raw.update({"agg":agg,"pred":pred,"margin":margin,"rotpred":rotpred,"prompts":prompts})
    return raw

def main():
    t0=time.time(); torch.manual_seed(0); torch.set_num_threads(max(1,min(4,os.cpu_count() or 1)))
    dsha=HfApi().dataset_info(DATASET_ID).sha
    parquet=hf_hub_download(repo_id=DATASET_ID,repo_type="dataset",filename=DATASET_FILE,revision=dsha)
    df=pd.read_parquet(parquet)
    rows=[r for r in df.to_dict("records") if list(r["choices"]["label"])==["A","B","C","D"]]
    rows=sorted(rows,key=lambda r:sha(str(r["id"])))[:POOL_SIZE]
    assert len(rows)==POOL_SIZE

    tok=AutoTokenizer.from_pretrained(MODEL_ID,revision=MODEL_REVISION)
    tok.padding_side="left"
    if tok.pad_token_id is None: tok.pad_token=tok.eos_token
    model=AutoModelForCausalLM.from_pretrained(MODEL_ID,revision=MODEL_REVISION,
      torch_dtype=torch.float32,low_cpu_mem_usage=True)
    model.eval(); cids=choice_ids(tok)

    base=eval_items(model,tok,cids,rows)
    pred,margin=base["pred"],base["margin"]
    obs_pool=list(range(32,64)); cf_pool=list(range(64,96))
    obs_idx=select_stratified(obs_pool,pred,margin,OBS_N)
    cf_idx=sorted(cf_pool,key=lambda i:(float(margin[i]),i))[:CF_N]
    obs_rows=[rows[i] for i in obs_idx]; cf_rows=[rows[i] for i in cf_idx]

    obs0=eval_items(model,tok,cids,obs_rows,capture=True,full=True)
    cf0=eval_items(model,tok,cids,cf_rows,capture=True,full=True)

    trace=[]; valid=[]
    for eps in EPS_GRID:
        r=eval_items(model,tok,cids,obs_rows,scale=1.0+eps)
        agree=float((r["pred"]==obs0["pred"]).float().mean().item())
        flips=int((r["pred"]!=obs0["pred"]).sum().item())
        trace.append({"epsilon":float(eps),"agreement":agree,"flips":flips})
        if flips==0: valid.append(eps)
    selected=max(valid) if valid else None
    if selected is None: raise SystemExit("FAIL: no nonzero internal collision")

    obs1=eval_items(model,tok,cids,obs_rows,scale=1.0+selected,capture=True,full=True)
    cf1=eval_items(model,tok,cids,cf_rows,scale=1.0+selected,capture=True,full=True)
    obs_flips=int((obs1["pred"]!=obs0["pred"]).sum().item())
    cf_flips=int((cf1["pred"]!=cf0["pred"]).sum().item())

    rel=(obs1["hidden"]-obs0["hidden"]).norm(dim=1)/(obs0["hidden"].norm(dim=1)+1e-12)
    cos=1.0-torch.nn.functional.cosine_similarity(obs1["hidden"],obs0["hidden"],dim=1)
    obs_js=js(obs0["full"],obs1["full"])
    cf_js=js(cf0["full"],cf1["full"])

    def consistency(rotpred):
        allsame=sum(len(set(p))==1 for p in rotpred)
        return {"all_four_rotations_agree":allsame,"n":len(rotpred),"rate":allsame/len(rotpred)}
    def dist(p): return dict(sorted(Counter("ABCD"[int(x)] for x in p).items()))
    def item(i):
        return {"id":str(rows[i]["id"]),"answer_key":str(rows[i]["answerKey"]),
          "baseline_prediction":"ABCD"[int(pred[i])],"baseline_margin":float(margin[i]),
          "id_sha256":sha(str(rows[i]["id"]))}

    result={
      "status":"PASS_M3" if (obs_flips==0 and cf_flips>0) else "PASS_M2" if obs_flips==0 else "FAIL",
      "primary_claim":"Permutation-averaged multiple-choice behavior on B does not identify the known layer-14 MLP scaling state.",
      "model":{"id":MODEL_ID,"revision":MODEL_REVISION,"parameters":751632384,"layer":LAYER_INDEX},
      "data":{"id":DATASET_ID,"revision":dsha,"file":DATASET_FILE,"pool_size":POOL_SIZE},
      "observation_operator":"mean original-option score over four cyclic A/B/C/D permutations, then content-level top-1",
      "permutation_control":{
         "baseline_pool_rotation_consistency":consistency(base["rotpred"]),
         "observation_rotation_consistency":consistency(obs0["rotpred"]),
         "counterfactual_rotation_consistency":consistency(cf0["rotpred"]),
         "observation_prediction_distribution":dist(obs0["pred"]),
         "counterfactual_prediction_distribution":dist(cf0["pred"]),
      },
      "intervention":{"kind":"mlp_output_scaling","layer":LAYER_INDEX,"selected_epsilon":float(selected),"scale":float(1.0+selected),"search_trace":trace},
      "observation":{
         "n":len(obs_rows),"flips":obs_flips,"exact_collision":obs_flips==0,
         "js_mean_over_rotations":float(obs_js.mean().item()),
         "hidden_relative_l2_mean_over_rotations":float(rel.mean().item()),
         "hidden_relative_l2_min_over_rotations":float(rel.min().item()),
         "hidden_cosine_distance_mean_over_rotations":float(cos.mean().item()),
         "items":[item(i) for i in obs_idx],
      },
      "counterfactual":{
         "n":len(cf_rows),"flips":cf_flips,"flip_rate":cf_flips/len(cf_rows),
         "js_mean_over_rotations":float(cf_js.mean().item()),
         "items":[item(i) for i in cf_idx],
      },
      "software":{"python":sys.version,"torch":torch.__version__,"platform":platform.platform()},
      "elapsed_seconds":time.time()-t0,
      "claim_boundary":[
         "This identifies only the declared intervention-state property relative to the frozen observation operator.",
         "Permutation averaging addresses label/position sensitivity but is not a universal semantic-equivalence guarantee.",
         "No biological, phenomenal, semantic-understanding, or global mechanism claim follows from this result."
      ],
    }
    dump(OUT/"permutation_mechanistic_receipt.json",result)
    pd.DataFrame(result["observation"]["items"]).to_csv(OUT/"observation_items.csv",index=False)
    pd.DataFrame(result["counterfactual"]["items"]).to_csv(OUT/"counterfactual_items.csv",index=False)
    print(json.dumps(result,indent=2,sort_keys=True))
    if result["status"]=="FAIL": raise SystemExit(2)

if __name__=="__main__": main()
