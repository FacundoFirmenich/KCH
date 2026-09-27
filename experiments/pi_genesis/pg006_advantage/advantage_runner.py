from __future__ import annotations

import argparse, hashlib, importlib, json, os, platform, subprocess, sys, time
from pathlib import Path
from typing import Any
import arviz as az
import numpy as np

CHAINS=4;WARMUP=800;DRAWS=800;TARGET_ACCEPT=0.95;MAX_TREE_DEPTH=12
SEEDS={'pymc':2026092783,'numpyro':2026092784}

def sha(p):
 h=hashlib.sha256();h.update(Path(p).read_bytes());return h.hexdigest()

def canonical(obj):return hashlib.sha256(json.dumps(obj,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def health(samples,extras):
 idata=az.from_dict(posterior=samples);r=az.rhat(idata,method='rank');b=az.ess(idata,method='bulk');t=az.ess(idata,method='tail')
 def vals(ds):
  out=[]
  for n in ds.data_vars:
   a=np.asarray(ds[n]).reshape(-1);out += [(float(v),f'{n}[{i}]' if a.size>1 else n) for i,v in enumerate(a) if np.isfinite(v)]
  return out
 rv,bv,tv=vals(r),vals(b),vals(t)
 return {'max_rank_folded_rhat':max(rv)[0],'max_rhat_parameter':max(rv)[1],'min_bulk_ess':min(bv)[0],'min_bulk_parameter':min(bv)[1],'min_tail_ess':min(tv)[0],'min_tail_parameter':min(tv)[1],'divergences':int(np.asarray(extras.get('diverging',[]),bool).sum())}

def pymc_run(module,data,seed):
 import pymc as pm
 model=module.build_advantage(data)
 with model:
  step=pm.NUTS(target_accept=TARGET_ACCEPT,max_treedepth=MAX_TREE_DEPTH)
  idata=pm.sample(draws=DRAWS,tune=WARMUP,chains=CHAINS,cores=min(CHAINS,os.cpu_count() or 1),random_seed=[seed+1009*i for i in range(CHAINS)],step=step,progressbar=False,compute_convergence_checks=False,return_inferencedata=True)
 samples={n:np.asarray(idata.posterior[n].values,float) for n in idata.posterior.data_vars};extras={}
 for s,d in [('diverging','diverging'),('energy','energy'),('tree_depth','tree_depth'),('acceptance_rate','acceptance_rate')]:
  if s in idata.sample_stats:extras[d]=np.asarray(idata.sample_stats[s].values)
 return samples,extras

def numpyro_run(module,data,seed):
 import jax, jax.numpy as jnp, numpyro
 from numpyro.infer import MCMC,NUTS
 numpyro.enable_x64();k=NUTS(module.advantage_model,target_accept_prob=TARGET_ACCEPT,max_tree_depth=MAX_TREE_DEPTH);m=MCMC(k,num_warmup=WARMUP,num_samples=DRAWS,num_chains=CHAINS,chain_method='sequential',progress_bar=False)
 m.run(jax.random.PRNGKey(seed),extra_fields=('diverging','potential_energy','num_steps','accept_prob'),y=jnp.asarray(data['y']),X=jnp.asarray(data['X']))
 samples={n:np.asarray(v,float) for n,v in m.get_samples(group_by_chain=True).items()};f=m.get_extra_fields(group_by_chain=True);extras={'diverging':np.asarray(f.get('diverging',np.zeros((CHAINS,DRAWS),bool))),'energy':np.asarray(f.get('potential_energy',np.empty(0))),'num_steps':np.asarray(f.get('num_steps',np.empty(0))),'acceptance_rate':np.asarray(f.get('accept_prob',np.empty(0)))}
 return samples,extras

def predict(samples,X):
 g0=np.asarray(samples['gamma0']).reshape(-1);g=np.asarray(samples['gamma']).reshape(-1,np.asarray(samples['gamma']).shape[-1]);return g0[:,None]+g@X.T

def main():
 p=argparse.ArgumentParser();p.add_argument('--backend',choices=['pymc','numpyro'],required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 raw=np.load(a.input,allow_pickle=False);data={k:raw[k] for k in raw.files};module=importlib.import_module('advantage_pymc' if a.backend=='pymc' else 'advantage_numpyro')
 st=time.time();samples,extras=(pymc_run if a.backend=='pymc' else numpyro_run)(module,data,SEEDS[a.backend]);elapsed=time.time()-st
 pred=predict(samples,np.asarray(data['X_final'],float));out=a.output/'advantage.npz';payload={f'sample__{k}':v for k,v in samples.items()};payload.update({f'extra__{k}':v for k,v in extras.items()});payload['pred_advantage__final']=pred;np.savez_compressed(out,**payload)
 receipt={'gate_id':'KCH-PI-GENESIS-PG006-DECISION-COUPLED-AUTHORITY-FIELD-001','backend':a.backend,'backend_family':module.BACKEND_FAMILY,'semantics':module.SEMANTICS,'input_sha256':sha(a.input),'source_sha256':sha(module.__file__),'health':health(samples,extras),'sampling':{'chains':CHAINS,'warmup':WARMUP,'draws':DRAWS,'target_accept':TARGET_ACCEPT,'max_tree_depth':MAX_TREE_DEPTH},'elapsed_seconds':elapsed,'npz_sha256':sha(out),'future_outcomes_visible':False};receipt['receipt_hash']=canonical(receipt);(a.output/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
 try:(a.output/'pip_freeze.txt').write_text(subprocess.check_output([sys.executable,'-m','pip','freeze'],text=True))
 except Exception:pass
 print(json.dumps(receipt,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
