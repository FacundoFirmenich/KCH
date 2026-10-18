#!/usr/bin/env python3
"""BIFM v0.11 — exact multisample audit plus local hierarchical Bayes.

Inputs are three Qwen layer artifacts evaluated on the same 96 real ARC items.
The script forms six disjoint 16-item blocks, nested prefixes, cumulative
observation operators, exact collision certificates, effect-normalized
frontiers, and locally pooled Beta-Binomial posteriors.
"""
from __future__ import annotations
import hashlib, json, math, os, platform, sys, time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import betaln, betainc, digamma, expit, logsumexp
from scipy.stats import beta as beta_dist

LAYERS=(4,14,24)
OPS=("O0_TOP1","O1_RANK4","O2_CHOICE_Q8","O3_FULL_TOP8","O4_FULL_TOP32")
NS=(4,8,12,16)
SAMPLES=6
MATERIAL_HIDDEN_L2=0.10
INROOT=Path(os.environ.get("BIFM_INPUT","layer_artifacts"))
OUT=Path(os.environ.get("BIFM_OUT","bifm_v011_summary"))
OUT.mkdir(parents=True,exist_ok=True)


def dump(path,obj):
    Path(path).write_text(json.dumps(obj,indent=2,sort_keys=True),encoding="utf-8")


def load_layer(layer):
    paths=list(INROOT.rglob(f"qwen_layer_{layer}.npz"))
    receipts=list(INROOT.rglob(f"qwen_layer_{layer}_receipt.json"))
    if len(paths)!=1 or len(receipts)!=1:
        raise RuntimeError(f"layer {layer}: expected one npz and one receipt, got {paths}, {receipts}")
    z=np.load(paths[0],allow_pickle=False)
    receipt=json.load(open(receipts[0],encoding="utf-8"))
    return z,receipt


def cumulative_signature(z,prefix,nidx):
    parts=[z[f"{prefix}_top1"][nidx]]
    if prefix is None: raise AssertionError
    return parts


def equal_operator(z,prefix,indices,op):
    fields={
      "O0_TOP1":("top1",),
      "O1_RANK4":("top1","rank4"),
      "O2_CHOICE_Q8":("top1","rank4","choice_q8"),
      "O3_FULL_TOP8":("top1","rank4","choice_q8","full_top8"),
      "O4_FULL_TOP32":("top1","rank4","choice_q8","full_top8","full_top32"),
    }[op]
    for field in fields:
        a=z[f"base_{field}"][indices]
        b=z[f"{prefix}_{field}"][indices]
        if not np.array_equal(a,b): return False
    return True


def make_stratified_order(ids,pred):
    queues={c:[] for c in range(4)}
    for i,(item,p) in enumerate(zip(ids,pred)):
        queues[int(p)].append((hashlib.sha256(item.encode()).hexdigest(),i))
    for c in queues: queues[c].sort()
    order=[]; rank=0
    while len(order)<len(ids):
        progressed=False
        for c in range(4):
            if rank<len(queues[c]):
                order.append(queues[c][rank][1]); progressed=True
        if not progressed: break
        rank+=1
    if len(order)!=len(ids): raise AssertionError("incomplete stratified order")
    return order


def log_beta_binom(y,n,a,b):
    # combinatorial constants are retained for completeness but cancel within a cell.
    from math import lgamma
    return (lgamma(n+1)-lgamma(y+1)-lgamma(n-y+1)
            + betaln(y+a,n-y+b)-betaln(a,b))


def bern_entropy(p):
    p=float(np.clip(p,1e-15,1-1e-15))
    return -p*math.log(p)-(1-p)*math.log(1-p)


def fit_group(group,mu_grid,logk_grid,rng):
    # group contains 36 cells for one layer/operator jurisdiction.
    ys=group["invisible_count"].to_numpy(dtype=int)
    ns=group["sample_count"].to_numpy(dtype=int)
    mus,klogs=np.meshgrid(mu_grid,logk_grid,indexing="ij")
    flat_mu=mus.ravel(); flat_logk=klogs.ravel(); kappas=np.exp(flat_logk)
    alphas=flat_mu*kappas; betas=(1-flat_mu)*kappas
    logw=-0.5*(flat_logk/2.0)**2  # prior log(kappa) ~ Normal(0,2), mu ~ Uniform
    for y,n in zip(ys,ns):
        logw += np.array([log_beta_binom(int(y),int(n),float(a),float(b))
                          for a,b in zip(alphas,betas)])
    logw-=logsumexp(logw); w=np.exp(logw)
    hyper={
      "mu_mean":float(np.sum(w*flat_mu)),
      "kappa_mean":float(np.sum(w*kappas)),
      "mu_q05":float(np.quantile(rng.choice(flat_mu,size=10000,p=w),0.05)),
      "mu_q95":float(np.quantile(rng.choice(flat_mu,size=10000,p=w),0.95)),
    }
    rows=[]
    for row in group.itertuples(index=False):
        y=int(row.invisible_count); n=int(row.sample_count)
        aa=alphas+y; bb=betas+n-y
        means=aa/(aa+bb)
        post_mean=float(np.sum(w*means))
        p_gt_half=float(np.sum(w*(1-betainc(aa,bb,0.5))))
        idx=rng.choice(len(w),size=6000,p=w)
        draws=rng.beta(aa[idx],bb[idx])
        q025,q50,q975=np.quantile(draws,[0.025,0.5,0.975])
        # Mutual information between p and one future Bernoulli outcome.
        ep_logp=aa/(aa+bb)*(digamma(aa+1)-digamma(aa+bb+1))
        eq_logq=bb/(aa+bb)*(digamma(bb+1)-digamma(aa+bb+1))
        expected_entropy=float(np.sum(w*(-ep_logp-eq_logq)))
        eig=max(0.0,bern_entropy(post_mean)-expected_entropy)
        rows.append({
          **row._asdict(),
          "posterior_mean":post_mean,"posterior_median":float(q50),
          "posterior_q025":float(q025),"posterior_q975":float(q975),
          "posterior_p_gt_0_5":p_gt_half,"next_sample_eig_nats":eig,
          "group_mu_mean":hyper["mu_mean"],"group_kappa_mean":hyper["kappa_mean"],
        })
    return rows,hyper


def main():
    t0=time.time(); rng=np.random.default_rng(20261018)
    loaded={layer:load_layer(layer) for layer in LAYERS}
    ids=list(loaded[14][0]["item_ids"].astype(str))
    for layer,(z,r) in loaded.items():
        if list(z["item_ids"].astype(str))!=ids: raise AssertionError("item order mismatch")
    order=make_stratified_order(ids,loaded[14][0]["base_top1"])
    blocks=[order[s*16:(s+1)*16] for s in range(SAMPLES)]
    if len({i for b in blocks for i in b})!=96: raise AssertionError("blocks not disjoint/exhaustive")

    rows=[]; frontiers=[]; violations=[]
    for layer,(z,receipt) in loaded.items():
        eps=[float(x) for x in z["eps_grid"]]
        effect={int(e["index"]):e for e in receipt["effects"]}
        for s,block in enumerate(blocks):
            for n in NS:
                idx=np.array(block[:n],dtype=int)
                invisible_by_op={op:[] for op in OPS}
                for k,e in enumerate(eps):
                    prefix=f"e{k}"
                    for op in OPS:
                        inv=equal_operator(z,prefix,idx,op)
                        invisible_by_op[op].append(inv)
                        rows.append({
                          "layer":layer,"sample":s,"n":n,"operator":op,
                          "epsilon_index":k,"epsilon":e,"invisible":int(inv),
                          "hidden_relative_l2_mean_all96":effect[k]["hidden_relative_l2_mean"],
                          "hidden_relative_l2_min_all96":effect[k]["hidden_relative_l2_min"],
                        })
                for oi in range(len(OPS)-1):
                    coarse=invisible_by_op[OPS[oi]]; fine=invisible_by_op[OPS[oi+1]]
                    for k,(a,b) in enumerate(zip(coarse,fine)):
                        if b and not a: violations.append(["operator",layer,s,n,OPS[oi],OPS[oi+1],k])
                for op in OPS:
                    invisible_eps=[eps[k] for k,v in enumerate(invisible_by_op[op]) if v]
                    invisible_delta=[effect[k]["hidden_relative_l2_mean"]
                                     for k,v in enumerate(invisible_by_op[op]) if v]
                    frontiers.append({
                      "layer":layer,"sample":s,"n":n,"operator":op,
                      "epsilon_star":max(invisible_eps) if invisible_eps else np.nan,
                      "delta_star_hidden_l2":max(invisible_delta) if invisible_delta else np.nan,
                      "invisible_grid_count":len(invisible_eps),
                    })
        # nested n monotonicity by sample/operator/epsilon
        rdf=pd.DataFrame([r for r in rows if r["layer"]==layer])
        for (s,op,k),g in rdf.groupby(["sample","operator","epsilon_index"]):
            v=dict(zip(g["n"],g["invisible"]))
            seq=[v[n] for n in NS]
            if any(seq[i]<seq[i+1] for i in range(len(seq)-1)):
                violations.append(["sample",layer,s,op,k,seq])

    raw=pd.DataFrame(rows)
    frontier=pd.DataFrame(frontiers)
    if violations:
        raise AssertionError(f"monotonicity violations: {violations[:10]}")
    counts=(raw.groupby(["layer","operator","n","epsilon","epsilon_index",
                         "hidden_relative_l2_mean_all96"],as_index=False)
              .agg(invisible_count=("invisible","sum"),sample_count=("invisible","size")))
    counts["material_effect"]=(counts["hidden_relative_l2_mean_all96"]>=MATERIAL_HIDDEN_L2).astype(int)

    mu_grid=np.linspace(0.01,0.99,41)
    logk_grid=np.linspace(-2.0,5.0,41)
    posterior=[]; hypers=[]
    for (layer,op),group in counts.groupby(["layer","operator"],sort=True):
        fitted,hyper=fit_group(group.copy(),mu_grid,logk_grid,rng)
        posterior.extend(fitted); hypers.append({"layer":layer,"operator":op,**hyper})
    posterior=pd.DataFrame(posterior)
    eig=posterior.sort_values("next_sample_eig_nats",ascending=False).reset_index(drop=True)

    # Jurisdictional summaries, never collapsed to a sole grand mean.
    material=posterior[posterior["material_effect"]==1]
    jurisdiction=[]
    for (layer,op,n),g in material.groupby(["layer","operator","n"]):
        jurisdiction.append({
          "layer":int(layer),"operator":op,"n":int(n),
          "mean_p_invisible_material":float(g["posterior_mean"].mean()),
          "max_p_invisible_material":float(g["posterior_mean"].max()),
          "min_p_invisible_material":float(g["posterior_mean"].min()),
          "n_grid_cells":int(len(g)),
        })

    sample_manifest=[]
    for s,b in enumerate(blocks):
        sample_manifest.append({"sample":s,"item_ids":[ids[i] for i in b],
                                "item_id_sha256":[hashlib.sha256(ids[i].encode()).hexdigest() for i in b]})
    result={
      "status":"PASS",
      "layers":list(LAYERS),"operators":list(OPS),"n_values":list(NS),
      "samples":SAMPLES,"items_per_sample":16,"samples_disjoint":True,
      "material_hidden_l2_threshold":MATERIAL_HIDDEN_L2,
      "exact_monotonicity_violations":len(violations),
      "n_binary_rows":int(len(raw)),"n_posterior_cells":int(len(posterior)),
      "jurisdictional_material_summaries":jurisdiction,
      "highest_eig_cells":eig.head(25).to_dict("records"),
      "hyperposterior_groups":hypers,
      "sample_manifest":sample_manifest,
      "model_note":"Local hierarchical Beta-Binomial pooling is by layer/operator. Exact collision certificates remain primary; posterior estimates describe across-sample variability.",
      "claim_boundary":[
        "Six disjoint real-data blocks support local uncertainty estimates but remain one domain and one model family.",
        "Hyperposterior grid integration is Bayesian but finite-grid approximate.",
        "Pooling never overrides exact monotonicity or per-sample certificates.",
        "No biological, phenomenal, semantic-understanding, agency or authority claim follows."
      ],
      "software":{"python":sys.version,"numpy":np.__version__,"pandas":pd.__version__,
                  "platform":platform.platform()},
      "elapsed_seconds":time.time()-t0,
    }
    raw.to_csv(OUT/"exact_sample_cells.csv",index=False)
    counts.to_csv(OUT/"cell_counts.csv",index=False)
    posterior.to_csv(OUT/"hierarchical_posterior.csv",index=False)
    eig.to_csv(OUT/"eig_rank.csv",index=False)
    frontier.to_csv(OUT/"frontier_samples.csv",index=False)
    dump(OUT/"bayesian_multisample_summary.json",result)
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=="__main__": main()
