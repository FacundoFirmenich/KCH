import math
from functools import lru_cache
from .model import ALPHA_TOTAL,BANDS

_LOG_BETA_HALF=math.lgamma(.5)+math.lgamma(.5)-math.lgamma(1.0)
def _log_beta(a,b): return math.lgamma(a)+math.lgamma(b)-math.lgamma(a+b)

@lru_cache(maxsize=None)
def mixture_cs_interval(successes,n,alpha_action=ALPHA_TOTAL/2):
    if n<=0:return (0.0,1.0)
    failures=n-successes
    logq=_log_beta(successes+.5,failures+.5)-_LOG_BETA_HALF
    threshold=math.log(1/alpha_action)
    phat=successes/n
    def loge(p):
        if p<=0:return math.inf if successes else logq
        if p>=1:return math.inf if failures else logq
        return logq-(successes*math.log(p)+failures*math.log(1-p))
    if successes==0: lo=0.0
    else:
        a=1e-15; b=phat
        for _ in range(60):
            m=(a+b)/2
            if loge(m)>threshold:a=m
            else:b=m
        lo=b
    if failures==0: hi=1.0
    else:
        a=phat; b=1-1e-15
        for _ in range(60):
            m=(a+b)/2
            if loge(m)<=threshold:a=m
            else:b=m
        hi=a
    return (max(0.0,lo),min(1.0,hi))

def classify_interval(interval):
    lo,hi=interval
    contained=[name for name,(a,b) in BANDS.items() if lo>=a and hi<=b]
    intersect=[name for name,(a,b) in BANDS.items() if not (hi<a or lo>b)]
    if len(contained)==1:return {'state':'CERTIFIED_BAND','label':contained[0],'intersects':intersect}
    if not intersect:return {'state':'OUTSIDE_ALL_BANDS','label':None,'intersects':[]}
    return {'state':'UNRESOLVED','label':None,'intersects':intersect}
