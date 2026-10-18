#!/usr/bin/env python3
"""BIFM v0.10 — empirical observation-lattice frontier on Qwen3-0.6B.

The experiment holds model, data, intervention family and nested observation
sets fixed while refining the observation operator. Each finer signature
contains the preceding signature, so equality is monotone by construction.
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
BATCH=8
OUT=Path(os.environ.get("BIFM_OUT","bifm_v0100_lattice_results"))
OUT.mkdir(parents=True,exist_ok=True)

LEVELS=(
    "L0_TOP1",
    "L1_RANK4",
    "L2_CHOICE_Q4",
    "L3_CHOICE_Q8",
    "L4_CHOICE_Q16",
    "L5_CHOICE_Q32",
    "L6_FULL_TOP8",
    "L7_FULL_TOP32",
)


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
        if lab not in out:
            raise RuntimeError(f"{lab} is not single-token")
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


def run(model,tok,prompts,cids,layer=None,scale=None):
    choice=[]; full=[]; hooks=[]
    if layer is not None and scale is not None:
        def mlp_hook(module,inputs,output):
            return output*scale
        hooks.append(model.model.layers[layer].mlp.register_forward_hook(mlp_hook))
    try:
        with torch.inference_mode():
            for s in range(0,len(prompts),BATCH):
                enc=tok(prompts[s:s+BATCH],return_tensors="pt",padding=True,
                        truncation=True,max_length=384)
                core=model.model(**enc,use_cache=False,return_dict=True)
                logits=model.lm_head(core.last_hidden_state[:,-1,:]).detach().float().cpu()
                choice.append(torch.stack([logits[:,cids[x]] for x in "ABCD"],dim=1))
                full.append(logits)
    finally:
        for h in hooks: h.remove()
    return torch.cat(choice),torch.cat(full)


def aggregate(choice_flat,full_flat,maps):
    n=len(maps); c=choice_flat.reshape(n,4,4); vocab=full_flat.shape[-1]
    f=full_flat.reshape(n,4,vocab)
    choice=torch.zeros((n,4),dtype=c.dtype)
    full=f.mean(dim=1)
    for i in range(n):
        for r in range(4):
            for shown,orig in enumerate(maps[i][r]):
                choice[i,orig]+=c[i,r,shown]/4.0
    return choice,full


def nested_balanced(pool,pred,margin,nmax):
    queues={}
    for cls in range(4):
        queues[cls]=sorted([i for i in pool if int(pred[i])==cls],
                           key=lambda i:(-float(margin[i]),i))
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


def quantize_probs(probs,bins):
    q=torch.floor(probs*bins+1e-12).to(torch.int16)
    return torch.clamp(q,max=bins-1)


def signatures(choice_logits,full_logits):
    probs=torch.softmax(choice_logits,dim=-1)
    rank=torch.argsort(choice_logits,dim=-1,descending=True)
    top1=rank[:,0]
    top8=torch.topk(full_logits,8,dim=-1).indices
    top32=torch.topk(full_logits,32,dim=-1).indices
    q4=quantize_probs(probs,4); q8=quantize_probs(probs,8)
    q16=quantize_probs(probs,16); q32=quantize_probs(probs,32)
    # Each tuple is cumulative, hence every later level refines every earlier one.
    return {
      "L0_TOP1":(top1,),
      "L1_RANK4":(top1,rank),
      "L2_CHOICE_Q4":(top1,rank,q4),
      "L3_CHOICE_Q8":(top1,rank,q4,q8),
      "L4_CHOICE_Q16":(top1,rank,q4,q8,q16),
      "L5_CHOICE_Q32":(top1,rank,q4,q8,q16,q32),
      "L6_FULL_TOP8":(top1,rank,q4,q8,q16,q32,top8),
      "L7_FULL_TOP32":(top1,rank,q4,q8,q16,q32,top8,top32),
    }


def prefix_equal(base,pert,n):
    return all(torch.equal(a[:n],b[:n]) for a,b in zip(base,pert))


def main():
    t0=time.time(); torch.manual_seed(0)
    torch.set_num_threads(max(1,min(4,os.cpu_count() or 1)))
    api=HfApi(); dsha=api.dataset_info(DATASET_ID).sha
    parquet=hf_hub_download(repo_id=DATASET_ID,repo_type="dataset",
                            filename=DATASET_FILE,revision=dsha)
    df=pd.read_parquet(parquet)
    rows=[r for r in df.to_dict("records") if list(r["choices"]["label"])==["A","B","C","D"]]
    rows=sorted(rows,key=lambda r:sha(str(r["id"])))[:POOL_SIZE]
    tok=AutoTokenizer.from_pretrained(MODEL_ID,revision=MODEL_REVISION)
    tok.padding_side="left"
    if tok.pad_token_id is None: tok.pad_token=tok.eos_token
    model=AutoModelForCausalLM.from_pretrained(
      MODEL_ID,revision=MODEL_REVISION,torch_dtype=torch.float32,
      low_cpu_mem_usage=True
    ); model.eval(); cids=choice_ids(tok)

    all_prompts,all_maps=flatten(tok,rows)
    bchoice,bfull=run(model,tok,all_prompts,cids)
    base_choice_all,base_full_all=aggregate(bchoice,bfull,all_maps)
    vals,idx=torch.topk(base_choice_all,2,dim=1)
    obs_idx=nested_balanced(list(range(32,64)),idx[:,0],vals[:,0]-vals[:,1],MAX_OBS)
    obs_rows=[rows[i] for i in obs_idx]
    prompts,maps=flatten(tok,obs_rows)
    base_choice_flat,base_full_flat=run(model,tok,prompts,cids)
    base_choice,base_full=aggregate(base_choice_flat,base_full_flat,maps)
    base_sig=signatures(base_choice,base_full)

    results=[]
    for layer in LAYERS:
        traces=[]
        frontier={level:{n:None for n in OBS_SIZES} for level in LEVELS}
        for eps in EPS_GRID:
            cflat,fflat=run(model,tok,prompts,cids,layer=layer,scale=1.0+eps)
            choice,full=aggregate(cflat,fflat,maps)
            sig=signatures(choice,full)
            visible={}
            for level in LEVELS:
                visible[level]={}
                for n in OBS_SIZES:
                    eq=prefix_equal(base_sig[level],sig[level],n)
                    visible[level][str(n)]=not eq
                    if eq: frontier[level][n]=eps
            traces.append({"epsilon":float(eps),"visible":visible})

        # Refinement invariants: frontier cannot increase at finer levels.
        for n in OBS_SIZES:
            seq=[]
            for level in LEVELS:
                v=frontier[level][n]
                seq.append(-1.0 if v is None else float(v))
            assert all(seq[i]>=seq[i+1] for i in range(len(seq)-1)),(layer,n,seq)
        # Sample nesting invariant within each operator.
        for level in LEVELS:
            seq=[]
            for n in OBS_SIZES:
                v=frontier[level][n]
                seq.append(-1.0 if v is None else float(v))
            assert all(seq[i]>=seq[i+1] for i in range(len(seq)-1)),(layer,level,seq)

        results.append({
          "layer":layer,
          "epsilon_star_grid":{
            level:{str(n):(None if frontier[level][n] is None else float(frontier[level][n]))
                   for n in OBS_SIZES}
            for level in LEVELS
          },
          "trace":traces,
        })

    result={
      "status":"PASS",
      "model":{"id":MODEL_ID,"revision":MODEL_REVISION,"layers":model.config.num_hidden_layers},
      "data":{"id":DATASET_ID,"revision":dsha,"file":DATASET_FILE},
      "intervention":"MLP-output scaling by 1+epsilon",
      "layers":list(LAYERS),"observation_sizes":list(OBS_SIZES),
      "epsilon_grid":list(EPS_GRID),"operator_levels":list(LEVELS),
      "operator_definition":{
        "L0_TOP1":"content-level top-1",
        "L1_RANK4":"L0 plus full rank of four answer contents",
        "L2_CHOICE_Q4":"L1 plus choice probabilities quantized into 4 bins",
        "L3_CHOICE_Q8":"L2 plus 8-bin choice probabilities",
        "L4_CHOICE_Q16":"L3 plus 16-bin choice probabilities",
        "L5_CHOICE_Q32":"L4 plus 32-bin choice probabilities",
        "L6_FULL_TOP8":"L5 plus ordered top-8 full-vocabulary token ids",
        "L7_FULL_TOP32":"L6 plus ordered top-32 full-vocabulary token ids",
      },
      "observation_order":[{
        "rank":k+1,"id":str(rows[i]["id"]),
        "baseline_prediction":"ABCD"[int(idx[i,0])],
        "baseline_margin":float(vals[i,0]-vals[i,1])
      } for k,i in enumerate(obs_idx)],
      "results":results,
      "software":{"python":sys.version,"torch":torch.__version__,"platform":platform.platform()},
      "elapsed_seconds":time.time()-t0,
      "claim_boundary":[
        "The lattice is a declared hierarchy of machine-observable signatures, not a universal hierarchy of cognition.",
        "Quantized and top-k operators are exact only relative to their specified discretization.",
        "The result maps practical observability of a known intervention; it does not establish global mechanism identity."
      ],
    }
    dump(OUT/"qwen_observation_lattice.json",result)
    pd.DataFrame(result["observation_order"]).to_csv(OUT/"observation_order.csv",index=False)
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=="__main__": main()
