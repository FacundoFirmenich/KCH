import math
from functools import lru_cache
from sca_dep.model import ProvenanceConstraint,Relation
from sca_dep.robust import robust_genealogy_gate

def deficit(events,constraints,T=20.):
    e=robust_genealogy_gate(events,constraints,T).robust_e_value
    return max(0.,math.log(T/e))

def consistent(worlds,obs):
    d=dict(obs); ws=[w for w in worlds if all(w.outcome(a)==o for a,o in d.items())]; z=sum(w.probability for w in ws)
    if z<=0: raise ValueError('ZERO_POSTERIOR')
    return [(w,w.probability/z) for w in ws]

def apply(constraints,a,o):
    if a.kind!='relation': return tuple(constraints)
    return tuple(constraints)+(ProvenanceConstraint(a.left,a.right,Relation(o),'attested:'+a.action_id,True),)

def exact_plan(events,constraints,actions,worlds,horizon,cost_weight=.25,T=20.):
    by={a.action_id:a for a in actions}
    @lru_cache(None)
    def V(obs,h):
        cc=tuple(constraints)
        for aid,o in obs: cc=apply(cc,by[aid],o)
        stop=-deficit(events,cc,T)
        if h==0:return stop,('STOP',)
        best=(stop,('STOP',)); post=consistent(worlds,obs); used={a for a,_ in obs}
        for a in actions:
            if a.action_id in used or not a.authorized: continue
            outcomes={w.outcome(a.action_id) for w,_ in post}; exp=0.; branches=[]
            for o in outcomes:
                po=sum(p for w,p in post if w.outcome(a.action_id)==o)
                nv,np=V(tuple(sorted(obs+((a.action_id,o),))),h-1)
                exp+=po*nv; branches.append((o,po,np))
            q=-cost_weight*a.cost+exp
            if q>best[0]+1e-15: best=(q,(a.action_id,tuple(sorted(branches))))
        return best
    return V(tuple(),horizon)
