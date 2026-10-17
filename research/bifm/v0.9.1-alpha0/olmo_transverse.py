#!/usr/bin/env python3
"""BIFM v0.9.1 — OLMo2 transverse, non-gauge MLP intervention.

Scalar scaling before post-feedforward RMSNorm is nearly a gauge direction in
OLMo2. This successor scales only even-indexed MLP output channels, changing
direction as well as norm so post-RMSNorm cannot globally cancel the perturbation.
"""
from __future__ import annotations
import hashlib,json,os,platform,sys,time
from collections import Counter
from pathlib import Path
import pandas as pd, torch
from huggingface_hub import hf_hub_download
from transformers import AutoModelForCausalLM,AutoTokenizer

MODEL_ID="allenai/OLMo-2-0425-1B-Instruct"
MODEL_REVISION="48d788eca847d4d7548f375ad03d3c9312f6139e"
DATASET_ID="allenai/ai2_arc"; DATASET_REVISION="210d026faf9955653af8916fad021475a3f00453"
DATASET_FILE="ARC-Challenge/validation-00000-of-00001.parquet"
LAYER_INDEX=8; POOL_SIZE=96; OBS_N=12; CF_N=12; BATCH=8
EPS_GRID=(0.02,0.05,0.10,0.20,0.35,0.50,0.75,1.00,1.50,2.00)
OUT=Path(os.environ.get("BIFM_OUT","bifm_v091_olmo_transverse")); OUT.mkdir(parents=True,exist_ok=True)
def sha(s): return hashlib.sha256(s.encode()).hexdigest()
def dump(p,o): Path(p).write_text(json.dumps(o,indent=2,sort_keys=True),encoding="utf-8")
def item_text(row,r):
    texts=list(row["choices"]["text"]); order=[(j+r)%4 for j in range(4)]
    lines="\n".join(f"{'ABCD'[j]}. {texts[order[j]]}" for j in range(4))
    return ("Answer this multiple-choice science question. Return only one letter: A, B, C, or D.\n\n"
            f"Question: {row['question'].strip()}\n{lines}\nAnswer:"),order
def render(tok,t): return tok.apply_chat_template([{"role":"user","content":t}],tokenize=False,add_generation_prompt=True)
def choice_ids(tok):
    d={}
    for lab in "ABCD":
        for s in (" "+lab,lab):
            v=tok.encode(s,add_special_tokens=False)
            if len(v)==1: d[lab]=v[0]; break
        if lab not in d: raise RuntimeError(lab)
    return d
def flatten(tok,rows):
    ps=[]; maps=[]
    for row in rows:
        m=[]
        for r in range(4):
            t,o=item_text(row,r); ps.append(render(tok,t)); m.append(o)
        maps.append(m)
    return ps,maps
def run(model,tok,ps,cids,eps=None,capture=False,full=False):
    cs=[]; fs=[]; hs=[]; hooks=[]; layer=model.model.layers[LAYER_INDEX]
    if eps is not None:
        def hook(module,inputs,output):
            z=output.clone(); z[...,::2]*=(1.0+eps); return z
        hooks.append(layer.mlp.register_forward_hook(hook))
    if capture:
        def lhook(module,inputs,output):
            t=output[0] if isinstance(output,(tuple,list)) else output
            hs.append(t[:,-1,:].detach().float().cpu())
        hooks.append(layer.register_forward_hook(lhook))
    try:
        with torch.inference_mode():
            for s in range(0,len(ps),BATCH):
                enc=tok(ps[s:s+BATCH],return_tensors="pt",padding=True,truncation=True,max_length=384)
                core=model.model(**enc,use_cache=False,return_dict=True)
                logits=model.lm_head(core.last_hidden_state[:,-1,:]).detach().float().cpu()
                cs.append(torch.stack([logits[:,cids[x]] for x in "ABCD"],1))
                if full: fs.append(logits)
    finally:
        for h in hooks:h.remove()
    return {"choice":torch.cat(cs),"full":torch.cat(fs) if fs else None,"hidden":torch.cat(hs) if hs else None}
def agg(flat,maps):
    n=len(maps); x=flat.reshape(n,4,4); a=torch.zeros((n,4))
    rp=[]
    for i in range(n):
        rr=[]
        for r in range(4):
            for shown,orig in enumerate(maps[i][r]): a[i,orig]+=x[i,r,shown]/4
            rr.append(maps[i][r][int(x[i,r].argmax())])
        rp.append(rr)
    v,idx=torch.topk(a,2,1); return a,idx[:,0],v[:,0]-v[:,1],rp
def evalr(model,tok,cids,rows,eps=None,capture=False,full=False):
    ps,m=flatten(tok,rows); z=run(model,tok,ps,cids,eps,capture,full); a,p,mar,rp=agg(z["choice"],m); z.update(scores=a,pred=p,margin=mar,rotpred=rp); return z
def strat(pool,pred,margin,n):
    out=[]; per=max(1,n//4)
    for cls in range(4):
        q=sorted([i for i in pool if int(pred[i])==cls],key=lambda i:(-float(margin[i]),i)); out+=q[:per]
    out=list(dict.fromkeys(out))
    if len(out)<n: out += [i for i in sorted(pool,key=lambda i:(-float(margin[i]),i)) if i not in out][:n-len(out)]
    return out[:n]
def js(a,b):
    la=torch.log_softmax(a,-1); lb=torch.log_softmax(b,-1); pa=la.exp(); pb=lb.exp(); m=(pa+pb)/2; lm=torch.log(m.clamp_min(1e-30))
    return .5*((pa*(la-lm)).sum(-1)+(pb*(lb-lm)).sum(-1))
def main():
    t0=time.time(); torch.manual_seed(0); torch.set_num_threads(max(1,min(4,os.cpu_count() or 1)))
    p=hf_hub_download(repo_id=DATASET_ID,repo_type="dataset",filename=DATASET_FILE,revision=DATASET_REVISION)
    df=pd.read_parquet(p); rows=[r for r in df.to_dict("records") if list(r["choices"]["label"])==["A","B","C","D"]]
    rows=sorted(rows,key=lambda r:sha(str(r["id"])))[:POOL_SIZE]
    tok=AutoTokenizer.from_pretrained(MODEL_ID,revision=MODEL_REVISION); tok.padding_side="left"
    if tok.pad_token_id is None: tok.pad_token=tok.eos_token
    model=AutoModelForCausalLM.from_pretrained(MODEL_ID,revision=MODEL_REVISION,torch_dtype=torch.float32,low_cpu_mem_usage=True); model.eval()
    cids=choice_ids(tok); base=evalr(model,tok,cids,rows); pred,margin=base["pred"],base["margin"]
    oi=strat(range(32,64),pred,margin,OBS_N); ci=sorted(range(64,96),key=lambda i:(float(margin[i]),i))[:CF_N]
    orows=[rows[i] for i in oi]; crows=[rows[i] for i in ci]
    o0=evalr(model,tok,cids,orows,capture=True,full=True); c0=evalr(model,tok,cids,crows,capture=True,full=True)
    trace=[]; valid=[]
    for e in EPS_GRID:
        z=evalr(model,tok,cids,orows,eps=e); f=int((z["pred"]!=o0["pred"]).sum())
        trace.append({"epsilon":e,"flips":f}); 
        if f==0: valid.append(e)
    if not valid: raise SystemExit("no transverse collision")
    e=max(valid); o1=evalr(model,tok,cids,orows,eps=e,capture=True,full=True); c1=evalr(model,tok,cids,crows,eps=e,capture=True,full=True)
    of=int((o1["pred"]!=o0["pred"]).sum()); cf=int((c1["pred"]!=c0["pred"]).sum())
    rel=(o1["hidden"]-o0["hidden"]).norm(dim=1)/(o0["hidden"].norm(dim=1)+1e-12)
    cos=1-torch.nn.functional.cosine_similarity(o1["hidden"],o0["hidden"],dim=1)
    result={"status":"PASS_TRANSVERSE_M3" if of==0 and cf>0 else "PASS_TRANSVERSE_M2" if of==0 else "FAIL",
      "model":{"id":MODEL_ID,"revision":MODEL_REVISION,"layer":LAYER_INDEX,"parameters":sum(p.numel() for p in model.parameters())},
      "intervention":{"kind":"even_channel_mlp_scaling_before_post_rmsnorm","epsilon":e,"scale_even_channels":1+e,"scale_odd_channels":1.0,"search_trace":trace},
      "observation":{"flips":of,"hidden_relative_l2_mean":float(rel.mean()),"hidden_relative_l2_min":float(rel.min()),"hidden_cosine_distance_mean":float(cos.mean()),"js_mean":float(js(o0["full"],o1["full"]).mean())},
      "counterfactual":{"flips":cf,"flip_rate":cf/CF_N,"js_mean":float(js(c0["full"],c1["full"]).mean())},
      "data":{"id":DATASET_ID,"revision":DATASET_REVISION,"file":DATASET_FILE},
      "operator":"four cyclic option permutations remapped to content and averaged before top-1",
      "elapsed_seconds":time.time()-t0,
      "boundary":["This successor removes the scalar post-RMSNorm gauge direction exposed by v0.9.0.","It remains a finite-observation intervention-state claim, not global mechanism identity."] }
    dump(OUT/"olmo_transverse_receipt.json",result); print(json.dumps(result,indent=2,sort_keys=True))
    if of: raise SystemExit(2)
if __name__=="__main__": main()
