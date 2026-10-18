#!/usr/bin/env python3
"""Dependence-preserving Bayesian bootstrap for BIFM v0.11.

The same Dirichlet weights are applied to every jurisdictional cell, preserving
all within-block dependence across epsilon, sample size, operator and layer.
The bootstrap is a posterior over the empirical six-block distribution; it is
not a population model over arbitrary prompts or domains.
"""
from __future__ import annotations
import json, os, platform, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

INROOT=Path(os.environ.get("BIFM_INPUT","bifm_v011_summary"))
OUT=Path(os.environ.get("BIFM_OUT","bifm_v011_bootstrap"))
OUT.mkdir(parents=True,exist_ok=True)
DRAWS=50000
SEED=20261018


def dump(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True),encoding="utf-8")


def summarize_draws(x):
    q=np.quantile(x,[0.025,0.05,0.5,0.95,0.975])
    return {
      "posterior_mean":float(x.mean()),
      "posterior_sd":float(x.std(ddof=0)),
      "posterior_q025":float(q[0]),
      "posterior_q05":float(q[1]),
      "posterior_median":float(q[2]),
      "posterior_q95":float(q[3]),
      "posterior_q975":float(q[4]),
      "posterior_p_gt_0_5":float((x>0.5).mean()),
    }


def main():
    t0=time.time(); rng=np.random.default_rng(SEED)
    exact=pd.read_csv(INROOT/"exact_sample_cells.csv")
    frontier=pd.read_csv(INROOT/"frontier_samples.csv")
    samples=sorted(exact["sample"].unique())
    if samples!=list(range(6)):
        raise AssertionError(f"expected samples 0..5, got {samples}")
    weights=rng.dirichlet(np.ones(len(samples)),size=DRAWS)

    cell_rows=[]
    cell_keys=["layer","operator","n","epsilon","epsilon_index",
               "hidden_relative_l2_mean_all96"]
    for key,g in exact.groupby(cell_keys,sort=True):
        g=g.sort_values("sample")
        if list(g["sample"])!=samples:
            raise AssertionError(f"incomplete cell {key}")
        y=g["invisible"].to_numpy(dtype=float)
        draws=weights@y
        cell_rows.append({
          **{k:(int(v) if k in ("layer","n","epsilon_index") else float(v) if k in ("epsilon","hidden_relative_l2_mean_all96") else v)
             for k,v in zip(cell_keys,key)},
          "observed_invisible_count":int(y.sum()),
          "sample_count":len(samples),
          **summarize_draws(draws),
        })
    cells=pd.DataFrame(cell_rows)

    frontier_rows=[]
    for key,g in frontier.groupby(["layer","operator","n"],sort=True):
        g=g.sort_values("sample")
        if list(g["sample"])!=samples:
            raise AssertionError(f"incomplete frontier {key}")
        eps_raw=g["epsilon_star"].to_numpy(dtype=float)
        delta_raw=g["delta_star_hidden_l2"].to_numpy(dtype=float)
        eps=np.nan_to_num(eps_raw,nan=0.0)
        delta=np.nan_to_num(delta_raw,nan=0.0)
        eps_draws=weights@eps; delta_draws=weights@delta
        layer,op,n=key
        er=summarize_draws(eps_draws); dr=summarize_draws(delta_draws)
        frontier_rows.append({
          "layer":int(layer),"operator":op,"n":int(n),
          "zero_censored_epsilon_samples":int(np.isnan(eps_raw).sum()),
          "zero_censored_delta_samples":int(np.isnan(delta_raw).sum()),
          **{f"epsilon_star_{k}":v for k,v in er.items()},
          **{f"delta_star_{k}":v for k,v in dr.items()},
        })
    frontiers=pd.DataFrame(frontier_rows)

    # The same weights induce a joint posterior over all cells. Verify exact
    # operator and sample monotonicity on every draw using posterior means as a
    # compact diagnostic; exact per-sample checks remain in the primary summary.
    violations=[]
    op_order=["O0_TOP1","O1_RANK4","O2_CHOICE_Q8","O3_FULL_TOP8","O4_FULL_TOP32"]
    n_order=[4,8,12,16]
    for layer in sorted(cells.layer.unique()):
        for eps in sorted(cells.epsilon_index.unique()):
            for n in n_order:
                vals=[]
                for op in op_order:
                    vals.append(float(cells[(cells.layer==layer)&(cells.epsilon_index==eps)&
                                             (cells.n==n)&(cells.operator==op)].posterior_mean.iloc[0]))
                if any(vals[i]<vals[i+1]-1e-12 for i in range(len(vals)-1)):
                    violations.append(["operator",int(layer),int(eps),int(n),vals])
            for op in op_order:
                vals=[]
                for n in n_order:
                    vals.append(float(cells[(cells.layer==layer)&(cells.epsilon_index==eps)&
                                             (cells.n==n)&(cells.operator==op)].posterior_mean.iloc[0]))
                if any(vals[i]<vals[i+1]-1e-12 for i in range(len(vals)-1)):
                    violations.append(["sample",int(layer),int(eps),op,vals])
    if violations:
        raise AssertionError(f"bootstrap mean monotonicity violation: {violations[:5]}")

    cells.to_csv(OUT/"bayesian_bootstrap_cells.csv",index=False)
    frontiers.to_csv(OUT/"bayesian_bootstrap_frontiers.csv",index=False)
    result={
      "status":"PASS","draws":DRAWS,"seed":SEED,"samples":len(samples),
      "same_dirichlet_weights_used_for_all_cells":True,
      "n_cell_posteriors":int(len(cells)),"n_frontier_posteriors":int(len(frontiers)),
      "monotonicity_violations":len(violations),
      "interpretation":"Dependence-preserving posterior over the frozen empirical six-block distribution.",
      "claim_boundary":[
        "The Bayesian bootstrap does not create new empirical observations.",
        "Zero replaces a grid-censored frontier below the smallest tested nonzero epsilon only for numerical summaries.",
        "The posterior is conditional on one model, one domain, one item pool and the frozen block construction."
      ],
      "software":{"python":sys.version,"numpy":np.__version__,"pandas":pd.__version__,
                  "platform":platform.platform()},
      "elapsed_seconds":time.time()-t0,
    }
    dump(OUT/"bayesian_bootstrap_summary.json",result)
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=="__main__": main()
