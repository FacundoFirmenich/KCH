from functools import lru_cache
from .pomdp import model_from_key,outcome_probs,outcomes,successor,available

class CertifiedBoundPlanner:
    def __init__(self,actions,critical_ids=('critical_A','critical_B'),critical_cost=.25):
        self.actions=tuple(actions); self.by={a.action_id:a for a in actions}; self.critical_ids=critical_ids; self.critical_cost=critical_cost
        self._crit=lru_cache(None)(self._critical_lower_uncached)
    def clear(self): self._crit.cache_clear()
    def _critical_lower_uncached(self,state,h):
        if state.eligible:return 1.0
        if h==0:return 0.0
        best=0.0
        for aid in self.critical_ids:
            if aid in state.used: continue
            a=self.by[aid]; child={o:successor(state,a,o) for o in outcomes(state,a)}; vals=[]
            for k in state.models:
                m=model_from_key(k); ex=0.0
                for o,p in outcome_probs(m,a).items():
                    if p>1e-15: ex+=p*self._crit(child[o],h-1)
                vals.append(ex)
            best=max(best,-a.cost+min(vals))
        return best
    def critical_lower(self,state,h): return self._crit(state,h)
    def node_upper(self,state,h):
        if state.eligible:return 1.0
        if h==0:return 0.0
        if not any(a not in state.used for a in self.critical_ids):return 0.0
        return 1.0-self.critical_cost
    def static_action_upper(self,state,h,a):
        child={o:successor(state,a,o) for o in outcomes(state,a)}; vals=[]
        for k in state.models:
            m=model_from_key(k); ex=0.0
            for o,p in outcome_probs(m,a).items():
                if p>1e-15: ex+=p*self.node_upper(child[o],h-1)
            vals.append(ex)
        return -a.cost+min(vals)
    def solve(self,state,h,depth,epsilon=1e-12):
        stats={'expanded':0,'static_pruned':0,'memo_hits':0}; memo={}
        def rec(s,hh,dd):
            key=(s,hh,dd)
            if key in memo: stats['memo_hits']+=1; return memo[key]
            if s.eligible: ans=(1.0,1.0,{'STOP':(1.0,1.0)}); memo[key]=ans; return ans
            if hh==0: ans=(0.0,0.0,{'STOP':(0.0,0.0)}); memo[key]=ans; return ans
            lb0=self.critical_lower(s,hh); ub0=self.node_upper(s,hh)
            if dd==0: ans=(lb0,ub0,{}); memo[key]=ans; return ans
            stats['expanded']+=1; incumbent=lb0; ab={}; cands=[]
            for a in available(s,self.actions):
                u=self.static_action_upper(s,hh,a)
                if u<incumbent-epsilon:
                    stats['static_pruned']+=1; ab[a.action_id]=(-1e300,u); continue
                cands.append((u,a))
            for _,a in sorted(cands,key=lambda z:(z[0],z[1].action_id),reverse=True):
                child={o:successor(s,a,o) for o in outcomes(s,a)}
                cb={o:rec(child[o],hh-1,dd-1)[:2] for o in child}; lbs=[]; ubs=[]
                for k in s.models:
                    m=model_from_key(k); lo=up=0.0
                    for o,p in outcome_probs(m,a).items():
                        if p>1e-15:
                            cl,cu=cb[o]; lo+=p*cl; up+=p*cu
                    lbs.append(lo); ubs.append(up)
                alb=-a.cost+min(lbs); aub=-a.cost+min(ubs); ab[a.action_id]=(alb,aub); incumbent=max(incumbent,alb)
            lb=max(lb0,max((x[0] for x in ab.values()),default=lb0)); ub=max(0.0,max((x[1] for x in ab.values()),default=ub0)); ans=(lb,ub,ab); memo[key]=ans; return ans
        lb,ub,ab=rec(state,h,depth)
        finite={a:x for a,x in ab.items() if x[0]>-1e250}; best=max(finite,key=lambda a:(finite[a][0],a)) if finite else None
        other=max((x[1] for a,x in ab.items() if a!=best),default=-1e300)
        ac=best is not None and finite[best][0]>other+epsilon; vc=(ub-lb)<=epsilon
        return {'lower':lb,'upper':ub,'gap':ub-lb,'root_action':best,'action_certified':ac,'value_certified':vc,'decision':'CERTIFY' if ac and vc else 'ABSTAIN_UNCERTIFIED','action_bounds':ab,'stats':stats,'memo_states':len(memo)}
