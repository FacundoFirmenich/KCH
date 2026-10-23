#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, platform, sys, time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from huggingface_hub import hf_hub_download, snapshot_download
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_ID='Qwen/Qwen3-0.6B'
MODEL_REVISION='c1899de289a04d12100db370d81485cdf75e47ca'
DATASET_ID='allenai/ai2_arc'
DATASET_REVISION='210d026faf9955653af8916fad021475a3f00453'
DATASET_FILE='ARC-Challenge/validation-00000-of-00001.parquet'
EPS_GRID=(None,0.05,0.10,0.20,0.35,0.50,0.75,1.00,1.50,2.00)
POOL_SIZE=96; BATCH=8

def sha_text(s): return hashlib.sha256(s.encode()).hexdigest()
def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,o): Path(p).write_text(json.dumps(o,indent=2,sort_keys=True)+'\n')

def item_text(row,rotation):
    labels='ABCD'; texts=list(row['choices']['text']); order=[(j+rotation)%4 for j in range(4)]
    lines='\n'.join(f'{labels[j]}. {texts[order[j]]}' for j in range(4))
    return ('Answer this multiple-choice science question. Return only one letter: A, B, C, or D.\n\n'
            f"Question: {row['question'].strip()}\n{lines}\nAnswer:"),order

def render(tok,text):
    try:
        return tok.apply_chat_template([{'role':'user','content':text}],tokenize=False,add_generation_prompt=True,enable_thinking=False)
    except TypeError:
        return tok.apply_chat_template([{'role':'user','content':text}],tokenize=False,add_generation_prompt=True)

def choice_ids(tok):
    out={}
    for lab in 'ABCD':
        for candidate in (' '+lab,lab):
            ids=tok.encode(candidate,add_special_tokens=False)
            if len(ids)==1: out[lab]=ids[0]; break
        if lab not in out: raise RuntimeError(f'{lab} not single-token')
    if len(set(out.values()))!=4: raise RuntimeError(out)
    return out

def flatten(tok,rows):
    prompts=[]; maps=[]
    for row in rows:
        per=[]
        for r in range(4):
            text,order=item_text(row,r); prompts.append(render(tok,text)); per.append(order)
        maps.append(per)
    return prompts,maps

def evaluate(model,tok,prompts,maps,cids,layer_idx,scale):
    choices=[]; hidden=[]; hooks=[]; layer=model.model.layers[layer_idx]
    if scale is not None:
        hooks.append(layer.mlp.register_forward_hook(lambda m,i,o:o*scale))
    def layer_hook(module,inputs,output):
        t=output[0] if isinstance(output,(tuple,list)) else output
        hidden.append(t[:,-1,:].detach().float().cpu())
    hooks.append(layer.register_forward_hook(layer_hook)); full_chunks=[]
    try:
        with torch.inference_mode():
            for s in range(0,len(prompts),BATCH):
                enc=tok(prompts[s:s+BATCH],return_tensors='pt',padding=True,truncation=True,max_length=384)
                core=model.model(**enc,use_cache=False,return_dict=True)
                logits=model.lm_head(core.last_hidden_state[:,-1,:]).detach().float().cpu()
                choices.append(torch.stack([logits[:,cids[x]] for x in 'ABCD'],dim=1)); full_chunks.append(logits)
    finally:
        for h in hooks: h.remove()
    flat_choice=torch.cat(choices); flat_full=torch.cat(full_chunks); flat_hidden=torch.cat(hidden)
    n=len(maps); vocab=flat_full.shape[-1]; c=flat_choice.reshape(n,4,4); f=flat_full.reshape(n,4,vocab)
    choice=torch.zeros((n,4),dtype=c.dtype)
    for i in range(n):
        for r in range(4):
            for shown,orig in enumerate(maps[i][r]): choice[i,orig]+=c[i,r,shown]/4.0
    full=f.mean(dim=1); probs=torch.softmax(choice,dim=-1); rank4=torch.argsort(choice,dim=-1,descending=True)
    return {
      'top1':rank4[:,0].numpy().astype(np.int8), 'rank4':rank4.numpy().astype(np.int8),
      'choice_q8':torch.clamp(torch.floor(probs*8+1e-12),max=7).numpy().astype(np.int8),
      'full_top8':torch.topk(full,8,dim=-1).indices.numpy().astype(np.int32),
      'full_top32':torch.topk(full,32,dim=-1).indices.numpy().astype(np.int32),
      'hidden':flat_hidden.numpy().astype(np.float32),
    }

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--layer',type=int,required=True); ap.add_argument('--out',type=Path,required=True); ap.add_argument('--expected',type=Path,required=True); args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True); t_all=time.time(); torch.manual_seed(0); torch.set_num_threads(max(1,min(4,os.cpu_count() or 1)))
    model_path=snapshot_download(MODEL_ID,revision=MODEL_REVISION)
    parquet=hf_hub_download(DATASET_ID,repo_type='dataset',revision=DATASET_REVISION,filename=DATASET_FILE)
    df=pd.read_parquet(parquet); rows=[r for r in df.to_dict('records') if list(r['choices']['label'])==['A','B','C','D']]
    rows=sorted(rows,key=lambda r:sha_text(str(r['id'])))[:POOL_SIZE]
    tok=AutoTokenizer.from_pretrained(model_path,local_files_only=True); tok.padding_side='left'
    if tok.pad_token_id is None: tok.pad_token=tok.eos_token
    model=AutoModelForCausalLM.from_pretrained(model_path,local_files_only=True,dtype=torch.float32,low_cpu_mem_usage=True); model.eval()
    prompts,maps=flatten(tok,rows); cids=choice_ids(tok)
    expected=json.loads(args.expected.read_text()); expected_map={(x['layer'],x['epsilon_index']):x for x in expected['expected_raw_artifacts']}
    results=[]
    for eidx,eps in enumerate(EPS_GRID):
        t0=time.time(); scale=None if eps is None else 1.0+eps
        arrays=evaluate(model,tok,prompts,maps,cids,args.layer,scale)
        arrays.update({'item_ids':np.array([str(r['id']) for r in rows],dtype='U64'),'answer_keys':np.array([str(r['answerKey']) for r in rows],dtype='U4'),'layer':np.array([args.layer],dtype=np.int16),'epsilon_index':np.array([eidx],dtype=np.int16),'epsilon':np.array([0.0 if eps is None else eps],dtype=np.float32),'scale':np.array([1.0 if scale is None else scale],dtype=np.float32)})
        npz=args.out/f'qwen_L{args.layer}_E{eidx}.npz'; np.savez_compressed(npz,**arrays); digest=sha_file(npz); exp=expected_map[(args.layer,eidx)]['npz_sha256']
        receipt={'status':'PASS','layer':args.layer,'epsilon_index':eidx,'epsilon':eps,'scale':1.0 if scale is None else scale,'model':{'id':MODEL_ID,'revision':MODEL_REVISION,'num_hidden_layers':model.config.num_hidden_layers},'data':{'id':DATASET_ID,'revision':DATASET_REVISION,'file':DATASET_FILE,'n_items':POOL_SIZE,'selection':'SHA256(item id), first 96 canonical A-D rows'},'n_prompt_realizations':len(prompts),'operators':['TOP1','RANK4','CHOICE_Q8','FULL_TOP8','FULL_TOP32'],'npz_sha256':digest,'expected_npz_sha256':exp,'raw_hash_match':digest==exp,'software':{'python':sys.version,'torch':torch.__version__,'numpy':np.__version__,'pandas':pd.__version__,'transformers':__import__('transformers').__version__,'platform':platform.platform()},'elapsed_seconds':time.time()-t0}
        dump(args.out/f'qwen_L{args.layer}_E{eidx}_receipt.json',receipt); results.append(receipt); print(json.dumps(receipt,sort_keys=True),flush=True)
    summary={'layer':args.layer,'shards':10,'raw_hash_matches':sum(r['raw_hash_match'] for r in results),'elapsed_seconds':time.time()-t_all,'results':results}; dump(args.out/f'layer_{args.layer}_replay_summary.json',summary)
if __name__=='__main__': main()
