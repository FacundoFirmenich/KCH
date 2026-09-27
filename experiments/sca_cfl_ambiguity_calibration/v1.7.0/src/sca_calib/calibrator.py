from __future__ import annotations
import math
from dataclasses import dataclass
from .family import p_a

def _lse(xs):
    m=max(xs)
    return m+math.log(sum(math.exp(x-m) for x in xs))

@dataclass
class FiniteConfidenceCalibrator:
    models: tuple
    alpha: float = .05
    def __post_init__(self):
        self.loglik=[0.0]*len(self.models)
        self.active=[True]*len(self.models)
        self.t=0
        self.elimination_time=[None]*len(self.models)
    def update(self,sensor:int,y:int):
        self.t+=1
        for i,m in enumerate(self.models):
            p=p_a(m,sensor)
            self.loglik[i]+=math.log(p if y else 1-p)
        th=math.log(1/self.alpha); k=len(self.models)
        for i in range(k):
            if not self.active[i]: continue
            others=self.loglik[:i]+self.loglik[i+1:]
            log_alt=_lse(others)-math.log(k-1)
            if log_alt-self.loglik[i]>=th:
                self.active[i]=False
                self.elimination_time[i]=self.t
    def active_ids(self): return tuple(i for i,x in enumerate(self.active) if x)
    def posterior(self):
        z=_lse(self.loglik)
        return tuple(math.exp(x-z) for x in self.loglik)
    def bayes_credible_ids(self,mass=.95):
        ps=self.posterior(); order=sorted(range(len(ps)),key=lambda i:ps[i],reverse=True)
        s=0.; out=[]
        for i in order:
            out.append(i); s+=ps[i]
            if s>=mass: break
        return tuple(sorted(out))

def union_class_evalue(loglik_full,loglik_null):
    log_q=_lse(loglik_full)-math.log(len(loglik_full))
    return math.exp(log_q-max(loglik_null))

class ClassMonitor:
    def __init__(self,full_models,null_indices,alpha=.05):
        self.full_models=tuple(full_models); self.null_indices=tuple(null_indices); self.alpha=alpha
        self.loglik_full=[0.0]*len(full_models); self.loglik_null=[0.0]*len(null_indices)
        self.t=0; self.cross_time=None; self.max_e=0.0
    def update(self,sensor,y):
        self.t+=1
        for i,m in enumerate(self.full_models):
            p=p_a(m,sensor); self.loglik_full[i]+=math.log(p if y else 1-p)
        for j,i in enumerate(self.null_indices):
            m=self.full_models[i]; p=p_a(m,sensor); self.loglik_null[j]+=math.log(p if y else 1-p)
        e=union_class_evalue(self.loglik_full,self.loglik_null)
        self.max_e=max(self.max_e,e)
        if self.cross_time is None and e>=1/self.alpha: self.cross_time=self.t
        return e
