#!/usr/bin/env python3
"""Create publication-facing BIFM v0.11 figures from frozen result tables."""
from __future__ import annotations
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

SUMMARY=Path(os.environ.get("BIFM_SUMMARY","bifm_v0111_summary"))
BOOT=Path(os.environ.get("BIFM_BOOTSTRAP","bifm_v0111_bootstrap"))
OUT=Path(os.environ.get("BIFM_FIGURES","bifm_v0111_figures"))
OUT.mkdir(parents=True,exist_ok=True)

OPS=["O0_TOP1","O1_RANK4","O2_CHOICE_Q8","O3_FULL_TOP8","O4_FULL_TOP32"]


def save(fig,name):
    fig.tight_layout()
    fig.savefig(OUT/name,dpi=220,bbox_inches="tight")
    plt.close(fig)


def exact_frequency_fig(counts,layer,n=16):
    fig,ax=plt.subplots(figsize=(8.4,5.2))
    g=counts[(counts.layer==layer)&(counts.n==n)]
    for op in OPS:
        x=g[g.operator==op].sort_values("epsilon")
        ax.plot(x.epsilon,x.invisible_count/x.sample_count,marker="o",label=op)
    ax.set_xlabel("MLP scaling epsilon")
    ax.set_ylabel("Exact invisible-block frequency")
    ax.set_ylim(-0.03,1.03)
    ax.set_title(f"Qwen layer {layer}: exact invisibility across six ARC blocks (n={n})")
    ax.legend(fontsize=8)
    ax.grid(True,alpha=0.25)
    save(fig,f"exact_invisibility_layer_{layer}_n{n}.png")


def posterior_fig(post,layer,n=16):
    fig,ax=plt.subplots(figsize=(8.4,5.2))
    g=post[(post.layer==layer)&(post.n==n)]
    for op in OPS:
        x=g[g.operator==op].sort_values("epsilon")
        line,=ax.plot(x.epsilon,x.posterior_mean,marker="o",label=op)
        ax.fill_between(x.epsilon,x.posterior_q025,x.posterior_q975,
                        alpha=0.15,color=line.get_color())
    ax.set_xlabel("MLP scaling epsilon")
    ax.set_ylabel("Local posterior invisible-block probability")
    ax.set_ylim(-0.03,1.03)
    ax.set_title(f"Qwen layer {layer}: local hierarchical posterior (n={n})")
    ax.legend(fontsize=8)
    ax.grid(True,alpha=0.25)
    save(fig,f"posterior_invisibility_layer_{layer}_n{n}.png")


def frontier_boxplot(frontier,n=16):
    fig,ax=plt.subplots(figsize=(10.0,5.5))
    g=frontier[frontier.n==n].copy()
    labels=[]; data=[]
    for layer in sorted(g.layer.unique()):
        for op in OPS:
            vals=g[(g.layer==layer)&(g.operator==op)].delta_star_hidden_l2.fillna(0).to_numpy()
            labels.append(f"L{layer}\n{op.replace('O','',1)}")
            data.append(vals)
    ax.boxplot(data,labels=labels,showmeans=True)
    ax.set_ylabel("Largest invisible realized hidden relative-L2")
    ax.set_title(f"Effect-normalized invisibility frontiers across ARC blocks (n={n})")
    ax.tick_params(axis="x",labelrotation=45,labelsize=7)
    ax.grid(True,axis="y",alpha=0.25)
    save(fig,f"effect_normalized_frontiers_n{n}.png")


def eig_fig(eig,top=20):
    x=eig.head(top).copy()
    labels=[f"L{int(r.layer)} {r.operator} n{int(r.n)} e{r.epsilon:g}"
            for r in x.itertuples(index=False)]
    fig,ax=plt.subplots(figsize=(9.5,6.5))
    pos=np.arange(len(x))
    ax.barh(pos,x.next_sample_eig_nats)
    ax.set_yticks(pos,labels=labels,fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("One-step expected information gain (nats)")
    ax.set_title("Highest-priority future-only jurisdictional cells")
    ax.grid(True,axis="x",alpha=0.25)
    save(fig,"eig_top_cells.png")


def bootstrap_frontier_fig(frontiers,n=16):
    fig,ax=plt.subplots(figsize=(9.0,5.2))
    g=frontiers[frontiers.n==n]
    for layer in sorted(g.layer.unique()):
        x=g[g.layer==layer].set_index("operator").loc[OPS].reset_index()
        line,=ax.plot(np.arange(len(OPS)),x.delta_star_posterior_mean,
                      marker="o",label=f"layer {int(layer)}")
        ax.fill_between(np.arange(len(OPS)),x.delta_star_posterior_q025,
                        x.delta_star_posterior_q975,alpha=0.15,color=line.get_color())
    ax.set_xticks(np.arange(len(OPS)),OPS,rotation=25,ha="right")
    ax.set_ylabel("Bayesian-bootstrap mean hidden-effect frontier")
    ax.set_title(f"Dependence-preserving frontier posterior (n={n})")
    ax.legend()
    ax.grid(True,axis="y",alpha=0.25)
    save(fig,f"bootstrap_effect_frontier_n{n}.png")


def main():
    counts=pd.read_csv(SUMMARY/"cell_counts.csv")
    post=pd.read_csv(SUMMARY/"hierarchical_posterior.csv")
    frontier=pd.read_csv(SUMMARY/"frontier_samples.csv")
    eig=pd.read_csv(SUMMARY/"eig_rank.csv")
    bfront=pd.read_csv(BOOT/"bayesian_bootstrap_frontiers.csv")
    for layer in sorted(counts.layer.unique()):
        exact_frequency_fig(counts,int(layer))
        posterior_fig(post,int(layer))
    frontier_boxplot(frontier)
    eig_fig(eig)
    bootstrap_frontier_fig(bfront)
    print(f"PASS: figures written to {OUT}")

if __name__=="__main__": main()
