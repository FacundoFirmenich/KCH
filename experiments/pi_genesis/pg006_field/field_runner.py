from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import arviz as az
import numpy as np

CHAINS = 4
WARMUP = 800
DRAWS = 800
TARGET_ACCEPT = 0.95
MAX_TREE_DEPTH = 12
SEEDS = {"pymc": 2026092781, "numpyro": 2026092782}


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def versions() -> dict[str, str]:
    import importlib.metadata as md
    out = {"python": platform.python_version()}
    for name in ("numpy", "scipy", "pandas", "arviz", "pymc", "pytensor", "jax", "jaxlib", "numpyro"):
        try: out[name] = md.version(name)
        except md.PackageNotFoundError: pass
    return out


def health(samples: dict[str, np.ndarray], extras: dict[str, np.ndarray]) -> dict[str, Any]:
    idata = az.from_dict(posterior=samples)
    r = az.rhat(idata, method="rank"); eb = az.ess(idata, method="bulk"); et = az.ess(idata, method="tail")
    def flat(ds: Any) -> list[tuple[float,str]]:
        out=[]
        for name in ds.data_vars:
            arr=np.asarray(ds[name].values).reshape(-1)
            out.extend((float(v),f"{name}[{i}]" if arr.size>1 else name) for i,v in enumerate(arr) if np.isfinite(v))
        return out
    rr=flat(r); bb=flat(eb); tt=flat(et)
    return {"max_rank_folded_rhat": max(rr)[0], "max_rhat_parameter": max(rr)[1], "min_bulk_ess": min(bb)[0], "min_bulk_parameter": min(bb)[1], "min_tail_ess": min(tt)[0], "min_tail_parameter": min(tt)[1], "divergences": int(np.asarray(extras.get("diverging",[]),dtype=bool).sum())}


def run_pymc(module: Any, data: dict[str,np.ndarray], seed: int):
    import pymc as pm
    model=module.build_regret_field(data)
    with model:
        step=pm.NUTS(target_accept=TARGET_ACCEPT,max_treedepth=MAX_TREE_DEPTH)
        idata=pm.sample(draws=DRAWS,tune=WARMUP,chains=CHAINS,cores=min(CHAINS,os.cpu_count() or 1),random_seed=[seed+1009*i for i in range(CHAINS)],step=step,progressbar=False,compute_convergence_checks=False,return_inferencedata=True)
    samples={n:np.asarray(idata.posterior[n].values,dtype=float) for n in idata.posterior.data_vars}
    extras={}
    for s,t in (("diverging","diverging"),("energy","energy"),("tree_depth","tree_depth"),("acceptance_rate","acceptance_rate")):
        if s in idata.sample_stats: extras[t]=np.asarray(idata.sample_stats[s].values)
    return samples,extras


def run_numpyro(module: Any, data: dict[str,np.ndarray], seed: int):
    import jax
    import jax.numpy as jnp
    import numpyro
    from numpyro.infer import MCMC,NUTS
    numpyro.enable_x64()
    kernel=NUTS(module.regret_field_model,target_accept_prob=TARGET_ACCEPT,max_tree_depth=MAX_TREE_DEPTH)
    mcmc=MCMC(kernel,num_warmup=WARMUP,num_samples=DRAWS,num_chains=CHAINS,chain_method="sequential",progress_bar=False)
    kwargs={"z":jnp.asarray(data["z"]),"X":jnp.asarray(data["X"]),"model_idx":jnp.asarray(data["model_idx"]),"subject_idx":jnp.asarray(data["subject_idx"]),"basis":jnp.asarray(data["basis"]),"n_models":int(data["n_models"])}
    mcmc.run(jax.random.PRNGKey(seed),extra_fields=("diverging","potential_energy","num_steps","accept_prob"),**kwargs)
    samples={n:np.asarray(v,dtype=float) for n,v in mcmc.get_samples(group_by_chain=True).items()}
    fields=mcmc.get_extra_fields(group_by_chain=True)
    extras={"diverging":np.asarray(fields.get("diverging",np.zeros((CHAINS,DRAWS),bool))),"energy":np.asarray(fields.get("potential_energy",np.empty(0))),"num_steps":np.asarray(fields.get("num_steps",np.empty(0))),"acceptance_rate":np.asarray(fields.get("accept_prob",np.empty(0)))}
    return samples,extras


def predict_z(samples: dict[str,np.ndarray], X: np.ndarray, model_idx: np.ndarray, subject_idx: np.ndarray) -> np.ndarray:
    alpha=np.asarray(samples["alpha"]).reshape(-1,np.asarray(samples["alpha"]).shape[-1])
    beta=np.asarray(samples["beta"]).reshape(-1,*np.asarray(samples["beta"]).shape[-2:])
    se=np.asarray(samples["subject_effect"]).reshape(-1,*np.asarray(samples["subject_effect"]).shape[-2:])
    return alpha[:,model_idx] + np.sum(beta[:,model_idx,:]*X[None,:,:],axis=-1) + se[:,model_idx,subject_idx]


def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument("--backend",choices=("pymc","numpyro"),required=True); p.add_argument("--input",type=Path,required=True); p.add_argument("--output",type=Path,required=True); args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    raw=np.load(args.input,allow_pickle=False)
    data={k:raw[k] for k in raw.files}
    module=importlib.import_module("regret_field_pymc" if args.backend=="pymc" else "regret_field_numpyro")
    start=time.time(); samples,extras=(run_pymc if args.backend=="pymc" else run_numpyro)(module,data,SEEDS[args.backend]); elapsed=time.time()-start
    predictions={}
    for split in ("calibration","final"):
        predictions[split]=predict_z(samples,np.asarray(data[f"X_{split}"]),np.asarray(data[f"model_idx_{split}"],int),np.asarray(data[f"subject_idx_{split}"],int))
    payload={f"sample__{k}":v for k,v in samples.items()}; payload.update({f"extra__{k}":v for k,v in extras.items()}); payload.update({f"pred_z__{k}":v for k,v in predictions.items()})
    npz=args.output/"regret_field.npz"; np.savez_compressed(npz,**payload)
    receipt={"gate_id":"KCH-PI-GENESIS-PG006-DECISION-COUPLED-AUTHORITY-FIELD-001","backend":args.backend,"backend_family":module.BACKEND_FAMILY,"field_semantics":module.FIELD_SEMANTICS,"input":args.input.name,"input_sha256":sha256_file(args.input),"generated_source":module.__file__,"generated_source_sha256":sha256_file(module.__file__),"sampling":{"chains":CHAINS,"warmup":WARMUP,"draws":DRAWS,"target_accept":TARGET_ACCEPT,"max_tree_depth":MAX_TREE_DEPTH},"health":health({k:v for k,v in samples.items() if k in {"alpha","beta","sigma","tau_subject","subject_effect"}},extras),"elapsed_seconds":elapsed,"npz":npz.name,"npz_sha256":sha256_file(npz),"versions":versions(),"future_outcomes_visible":False}
    receipt["receipt_hash"]=canonical_hash(receipt); (args.output/"receipt.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    try:(args.output/"pip_freeze.txt").write_text(subprocess.check_output([sys.executable,"-m","pip","freeze"],text=True))
    except Exception:pass
    print(json.dumps({"receipt_hash":receipt["receipt_hash"],"health":receipt["health"]},indent=2)); return 0


if __name__=="__main__": raise SystemExit(main())
