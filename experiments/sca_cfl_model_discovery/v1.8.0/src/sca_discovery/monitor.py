import math
from dataclasses import dataclass
from .context import UniversalDepthMixture,KTContextPredictor
from .family import outer_models,p_one
@dataclass(frozen=True)
class MonitorResult:
    cross_time:int|None; final_e_value:float; max_e_value:float; n:int

def _exp(x): return math.exp(min(700.0,x))

def monitor_outer_class(seq,threshold=20.0,max_depth=3):
    models=outer_models(); ll=[0.0]*len(models); alt=UniversalDepthMixture(max_depth)
    cross=None; maxe=0.0; e=1.0
    for t,(sensor,history,y,_) in enumerate(seq,1):
        for i,m in enumerate(models):
            p=p_one(m,sensor); ll[i]+=math.log(p if y else 1-p)
        e=_exp(alt.update(sensor,history,y)-max(ll)); maxe=max(maxe,e)
        if cross is None and e>=threshold: cross=t
    return MonitorResult(cross,e,maxe,len(seq)),alt

def certify_candidate(depth,seq,threshold=20.0):
    models=outer_models(); ll=[0.0]*len(models); c=KTContextPredictor(depth)
    cross=None; maxe=0.0; e=1.0
    for t,(sensor,history,y,_) in enumerate(seq,1):
        for i,m in enumerate(models):
            p=p_one(m,sensor); ll[i]+=math.log(p if y else 1-p)
        c.update(sensor,history,y); e=_exp(c.loglik-max(ll)); maxe=max(maxe,e)
        if cross is None and e>=threshold: cross=t
    return MonitorResult(cross,e,maxe,len(seq))
