#!/usr/bin/env python3
"""BIFM v0.8 — real open-weight behavior-to-mechanism collision gate.

Real system: Qwen/Qwen3-0.6B at a frozen model revision.
Real stimuli: ARC-Challenge validation examples from a frozen HF dataset revision
resolved and recorded before execution.

Primary observation O_B: top-1 answer choice among A/B/C/D under a frozen prompt
and decoder/scoring rule.

Two distinct intervention families:
1) fixed pre-softmax choice-token bias;
2) mid-layer MLP output scaling via a forward hook.

The experiment is constructive, not a prevalence estimate.
"""
from __future__ import annotations
import hashlib, json, math, os, platform, statistics, sys, time
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
LOGIT_ALPHA_GRID=(0.10,0.25,0.50,1.0,2.0,4.0,8.0)
MLP_EPS_GRID=(0.005,0.01,0.02,0.05,0.10,0.20)

OUT=Path(os.environ.get("BIFM_OUT","bifm_v080_results"))
OUT.mkdir(parents=True,exist_ok=True)

def sha_text(s:str)->str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def json_dump(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True),encoding="utf-8")

def prompt_text(row):
    labels=list(row["choices"]["label"])
    texts=list(row["choices"]["text"])
    stem=row["question"].strip()
    body="\n".join(f"{lab}. {txt}" for lab,txt in zip(labels,texts))
    return (
        "Answer this multiple-choice science question. "
        "Return only one letter: A, B, C, or D.\n\n"
        f"Question: {stem}\n{body}\nAnswer:"
    )

def render_chat(tok,content):
    try:
        return tok.apply_chat_template(
            [{"role":"user","content":content}],
            tokenize=False, add_generation_prompt=True, enable_thinking=False
        )
    except TypeError:
        return tok.apply_chat_template(
            [{"role":"user","content":content}],
            tokenize=False, add_generation_prompt=True
        )

def find_choice_token_ids(tok):
    ids={}
    for lab in "ABCD":
        candidates=(" "+lab,lab)
        found=None
        for s in candidates:
            v=tok.encode(s,add_special_tokens=False)
            if len(v)==1:
                found=v[0]; break
        if found is None:
            raise RuntimeError(f"Choice label {lab!r} is not single-token in tested forms")
        ids[lab]=found
    if len(set(ids.values()))!=4:
        raise RuntimeError(f"Choice token IDs are not distinct: {ids}")
    return ids

def run_model(model,tok,prompts,choice_ids,mlp_scale=None,capture_layer=False):
    logits_all=[]; hidden_all=[]; layer_norms=[]
    hooks=[]
    if mlp_scale is not None:
        layer=model.model.layers[LAYER_INDEX]
        def mlp_hook(module,inputs,output):
            t=output
            layer_norms.append(float(t.detach().float().norm().cpu()))
            return t*mlp_scale
        hooks.append(layer.mlp.register_forward_hook(mlp_hook))
    if capture_layer:
        layer=model.model.layers[LAYER_INDEX]
        def layer_hook(module,inputs,output):
            t=output[0] if isinstance(output,(tuple,list)) else output
            hidden_all.append(t[:,-1,:].detach().float().cpu())
        hooks.append(layer.register_forward_hook(layer_hook))
    try:
        with torch.inference_mode():
            for start in range(0,len(prompts),BATCH):
                batch=prompts[start:start+BATCH]
                enc=tok(batch,return_tensors="pt",padding=True,truncation=True,max_length=384)
                out=model(**enc,use_cache=False)
                logits_all.append(out.logits[:,-1,:].detach().float().cpu())
    finally:
        for h in hooks: h.remove()
    logits=torch.cat(logits_all,dim=0)
    choice=torch.stack([logits[:,choice_ids[c]] for c in "ABCD"],dim=1)
    hidden=torch.cat(hidden_all,dim=0) if hidden_all else None
    return logits,choice,hidden,layer_norms

def top_and_margin(choice):
    vals,idx=torch.topk(choice,2,dim=1)
    return idx[:,0], (vals[:,0]-vals[:,1])

def js_divergence(logits0,logits1):
    logp=torch.log_softmax(logits0,dim=-1)
    logq=torch.log_softmax(logits1,dim=-1)
    p=logp.exp(); q=logq.exp(); m=0.5*(p+q)
    logm=torch.log(m.clamp_min(1e-30))
    return 0.5*((p*(logp-logm)).sum(-1)+(q*(logq-logm)).sum(-1))

def select_largest_preserving(grid,base_choice,intervene):
    valid=[]
    traces=[]
    for value in grid:
        c=intervene(value)
        pred=c.argmax(dim=1)
        agree=float((pred==base_choice).float().mean().item())
        traces.append({"value":float(value),"agreement":agree,"flips":int((pred!=base_choice).sum().item())})
        if bool(torch.equal(pred,base_choice)):
            valid.append(value)
    return (max(valid) if valid else None), traces

def main():
    t0=time.time()
    torch.manual_seed(0)
    torch.set_num_threads(max(1,min(4,os.cpu_count() or 1)))

    api=HfApi()
    dataset_sha=api.dataset_info(DATASET_ID).sha
    parquet=hf_hub_download(repo_id=DATASET_ID,repo_type="dataset",filename=DATASET_FILE,revision=dataset_sha)
    df=pd.read_parquet(parquet)
    rows=[]
    for rec in df.to_dict("records"):
        labels=list(rec["choices"]["label"])
        if labels==["A","B","C","D"]:
            rows.append(rec)
    rows=sorted(rows,key=lambda r:sha_text(str(r["id"])))
    if len(rows)<POOL_SIZE:
        raise RuntimeError(f"Need {POOL_SIZE} canonical A-D ARC rows, got {len(rows)}")
    rows=rows[:POOL_SIZE]

    tok=AutoTokenizer.from_pretrained(MODEL_ID,revision=MODEL_REVISION)
    tok.padding_side="left"
    if tok.pad_token_id is None:
        tok.pad_token=tok.eos_token
    model=AutoModelForCausalLM.from_pretrained(
        MODEL_ID, revision=MODEL_REVISION, torch_dtype=torch.float32,
        low_cpu_mem_usage=True
    )
    model.eval()
    choice_ids=find_choice_token_ids(tok)

    prompts=[render_chat(tok,prompt_text(r)) for r in rows]
    base_logits,base_choice_logits,_,_=run_model(model,tok,prompts,choice_ids)
    pred,margin=top_and_margin(base_choice_logits)

    # Three disjoint real-data pools fixed by hash order before any intervention.
    dev_idx=list(range(0,32))
    obs_pool=list(range(32,64))
    cf_pool=list(range(64,96))

    # Choose target choice token only from development pool baseline scores.
    target_stats={}
    for j,lab in enumerate("ABCD"):
        req=[]
        for i in dev_idx:
            scores=base_choice_logits[i]
            top=float(scores.max().item())
            r=max(0.0,top-float(scores[j].item())+1e-6)
            if int(pred[i])!=j: req.append(r)
        target_stats[lab]=statistics.median(req) if req else float("inf")
    target_label=min(target_stats,key=lambda x:(target_stats[x],x))
    target_j="ABCD".index(target_label)
    target_token_id=choice_ids[target_label]

    # Observation B: highest-margin real ARC items from its disjoint pool.
    obs_idx=sorted(obs_pool,key=lambda i:(-float(margin[i]),str(rows[i]["id"])))[:OBS_N]
    # Counterfactual B': lowest-margin items from its disjoint pool, selected
    # before seeing either intervention.
    cf_idx=sorted(cf_pool,key=lambda i:(float(margin[i]),str(rows[i]["id"])))[:CF_N]

    obs_base_full=base_logits[obs_idx]
    obs_base_choice=base_choice_logits[obs_idx]
    obs_base_pred=obs_base_choice.argmax(1)
    cf_base_full=base_logits[cf_idx]
    cf_base_choice=base_choice_logits[cf_idx]
    cf_base_pred=cf_base_choice.argmax(1)

    # ---- Family 1: fixed pre-softmax bias ----
    def bias_choice(alpha,choice=obs_base_choice):
        c=choice.clone(); c[:,target_j]+=float(alpha); return c
    logit_alpha,logit_trace=select_largest_preserving(LOGIT_ALPHA_GRID,obs_base_pred,bias_choice)
    logit_result={"selected_alpha":None,"observation_collision":False}
    if logit_alpha is not None:
        obs_l1=obs_base_full.clone(); obs_l1[:,target_token_id]+=float(logit_alpha)
        cf_l1=cf_base_full.clone(); cf_l1[:,target_token_id]+=float(logit_alpha)
        obs_c1=obs_base_choice.clone(); obs_c1[:,target_j]+=float(logit_alpha)
        cf_c1=cf_base_choice.clone(); cf_c1[:,target_j]+=float(logit_alpha)
        obs_pred1=obs_c1.argmax(1); cf_pred1=cf_c1.argmax(1)
        logit_result={
            "target_label":target_label,
            "target_token_id":int(target_token_id),
            "selected_alpha":float(logit_alpha),
            "observation_collision":bool(torch.equal(obs_pred1,obs_base_pred)),
            "observation_flips":int((obs_pred1!=obs_base_pred).sum().item()),
            "counterfactual_flips":int((cf_pred1!=cf_base_pred).sum().item()),
            "counterfactual_flip_rate":float((cf_pred1!=cf_base_pred).float().mean().item()),
            "observation_js_mean":float(js_divergence(obs_base_full,obs_l1).mean().item()),
            "counterfactual_js_mean":float(js_divergence(cf_base_full,cf_l1).mean().item()),
            "q_intervention":{"kind":"pre_softmax_choice_bias","label":target_label,"alpha":float(logit_alpha)},
        }
    logit_result["search_trace"]=logit_trace

    # Free the large all-pool logits before repeated model passes.
    del base_logits
    torch.cuda.empty_cache() if torch.cuda.is_available() else None

    # ---- Family 2: mid-layer MLP scaling ----
    obs_prompts=[prompts[i] for i in obs_idx]
    cf_prompts=[prompts[i] for i in cf_idx]
    # Baseline re-run with hidden capture.
    obs0_full,obs0_choice,obs0_hidden,_=run_model(model,tok,obs_prompts,choice_ids,capture_layer=True)
    cf0_full,cf0_choice,cf0_hidden,_=run_model(model,tok,cf_prompts,choice_ids,capture_layer=True)
    obs0_pred=obs0_choice.argmax(1); cf0_pred=cf0_choice.argmax(1)

    mlp_trace=[]; valid=[]
    for eps in MLP_EPS_GRID:
        _,c,_,_=run_model(model,tok,obs_prompts,choice_ids,mlp_scale=1.0+eps)
        p=c.argmax(1); agree=float((p==obs0_pred).float().mean().item())
        mlp_trace.append({"epsilon":float(eps),"agreement":agree,"flips":int((p!=obs0_pred).sum().item())})
        if bool(torch.equal(p,obs0_pred)): valid.append(eps)
    mlp_eps=max(valid) if valid else None
    mlp_result={"selected_epsilon":None,"observation_collision":False,"search_trace":mlp_trace}
    if mlp_eps is not None:
        obs1_full,obs1_choice,obs1_hidden,norms_obs=run_model(
            model,tok,obs_prompts,choice_ids,mlp_scale=1.0+mlp_eps,capture_layer=True
        )
        cf1_full,cf1_choice,cf1_hidden,norms_cf=run_model(
            model,tok,cf_prompts,choice_ids,mlp_scale=1.0+mlp_eps,capture_layer=True
        )
        op=obs1_choice.argmax(1); cp=cf1_choice.argmax(1)
        rel=((obs1_hidden-obs0_hidden).norm(dim=1)/(obs0_hidden.norm(dim=1)+1e-12))
        cos=1.0-torch.nn.functional.cosine_similarity(obs1_hidden,obs0_hidden,dim=1)
        mlp_result.update({
            "selected_epsilon":float(mlp_eps),
            "mlp_scale":float(1.0+mlp_eps),
            "layer_index":LAYER_INDEX,
            "observation_collision":bool(torch.equal(op,obs0_pred)),
            "observation_flips":int((op!=obs0_pred).sum().item()),
            "counterfactual_flips":int((cp!=cf0_pred).sum().item()),
            "counterfactual_flip_rate":float((cp!=cf0_pred).float().mean().item()),
            "observation_js_mean":float(js_divergence(obs0_full,obs1_full).mean().item()),
            "counterfactual_js_mean":float(js_divergence(cf0_full,cf1_full).mean().item()),
            "hidden_relative_l2_mean":float(rel.mean().item()),
            "hidden_relative_l2_min":float(rel.min().item()),
            "hidden_cosine_distance_mean":float(cos.mean().item()),
            "intervened_mlp_norm_receipts":len(norms_obs)+len(norms_cf),
            "q_intervention":{"kind":"mlp_output_scaling","layer":LAYER_INDEX,"scale":float(1.0+mlp_eps)},
        })

    def item_record(i):
        return {
            "id":str(rows[i]["id"]),
            "id_sha256":sha_text(str(rows[i]["id"])),
            "answer_key":str(rows[i]["answerKey"]),
            "baseline_prediction":"ABCD"[int(pred[i])],
            "baseline_margin":float(margin[i]),
            "prompt_sha256":sha_text(prompts[i]),
        }

    provenance={
        "model_id":MODEL_ID,
        "model_revision":MODEL_REVISION,
        "model_parameter_count_from_hf":751632384,
        "dataset_id":DATASET_ID,
        "dataset_revision":dataset_sha,
        "dataset_file":DATASET_FILE,
        "arc_filtered_abcd_rows_available":len([r for r in df.to_dict("records") if list(r["choices"]["label"])==["A","B","C","D"]]),
        "pool_size":POOL_SIZE,
        "prompt_selection":"SHA256(id) sort; first 96 canonical A-D validation rows; disjoint 32/32/32 dev-observation-counterfactual pools",
        "choice_token_ids":choice_ids,
        "target_label_selection":{"development_pool_only":True,"median_required_bias":target_stats,"selected":target_label},
        "software":{
            "python":sys.version,
            "platform":platform.platform(),
            "torch":torch.__version__,
        },
    }
    result={
        "status":"PASS" if (logit_result.get("observation_collision") and mlp_result.get("observation_collision")) else "PARTIAL",
        "primary_claim":"Frozen multiple-choice behavior on B does not identify the declared intervention state when a nonzero intervention preserves every observed top-1 choice.",
        "observation_operator":"top-1 A/B/C/D choice on 12 preregistered high-margin ARC-Challenge validation items",
        "counterfactual_operator":"same top-1 choice rule on 12 disjoint low-margin ARC-Challenge validation items selected before intervention",
        "observation_items":[item_record(i) for i in obs_idx],
        "counterfactual_items":[item_record(i) for i in cf_idx],
        "pre_softmax":logit_result,
        "mlp_internal":mlp_result,
        "provenance":provenance,
        "elapsed_seconds":time.time()-t0,
        "claim_boundary":[
            "This identifies only the intervention-state property defined here.",
            "It does not infer consciousness, biology, semantic understanding, or global mechanism identity.",
            "The ARC labels are used as real benchmark stimuli; this experiment is not an ARC accuracy claim.",
        ],
    }
    json_dump(OUT/"mechanistic_gate_receipt.json",result)
    pd.DataFrame(result["observation_items"]).to_csv(OUT/"observation_items.csv",index=False)
    pd.DataFrame(result["counterfactual_items"]).to_csv(OUT/"counterfactual_items.csv",index=False)
    print(json.dumps(result,indent=2,sort_keys=True))
    if not logit_result.get("observation_collision"):
        raise SystemExit("FAIL: no pre-softmax collision witness")
    if not mlp_result.get("observation_collision"):
        raise SystemExit("FAIL: no internal MLP collision witness")

if __name__=="__main__":
    main()
