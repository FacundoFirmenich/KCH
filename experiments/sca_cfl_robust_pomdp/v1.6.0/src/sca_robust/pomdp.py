from __future__ import annotations
from functools import lru_cache
from .model import AmbiguityModel,BeliefState

def model_from_key(t): return AmbiguityModel(float(t[0]),tuple(float(x) for x in t[1]))
def canonical_models(models): return tuple(sorted(set((round(m.q,12),tuple(round(x,12) for x in m.accuracies)) for m in models)))

def outcome_probs(model,action):
    q=model.q
    if action.kind=='sensor':
        r=model.accuracies[action.sensor_index]; pa=q*r+(1-q)*(1-r)
        return {'A':pa,'B':1-pa}
    if action.action_id=='critical_A': return {'D':q,'S':1-q}
    if action.action_id=='critical_B': return {'D':1-q,'S':q}
    raise ValueError('UNKNOWN_ACTION')

def update_model(model,action,obs):
    q=model.q
    if action.kind=='sensor':
        r=model.accuracies[action.sensor_index]
        if obs=='A': num=q*r; den=q*r+(1-q)*(1-r)
        elif obs=='B': num=q*(1-r); den=q*(1-r)+(1-q)*r
        else: raise ValueError('BAD_OBS')
        return None if den<=1e-15 else AmbiguityModel(num/den,model.accuracies)
    if action.action_id=='critical_A': return AmbiguityModel(1.0 if obs=='D' else 0.0,model.accuracies)
    if action.action_id=='critical_B': return AmbiguityModel(0.0 if obs=='D' else 1.0,model.accuracies)
    raise ValueError('BAD_OBS')

def outcomes(state,action):
    possible=('A','B') if action.kind=='sensor' else ('D','S')
    return tuple(o for o in possible if any(outcome_probs(model_from_key(k),action)[o]>1e-15 for k in state.models))

def successor(state,action,obs):
    models=[]
    for k in state.models:
        m=model_from_key(k); p=outcome_probs(m,action)[obs]
        if p>1e-15:
            u=update_model(m,action,obs)
            if u is not None: models.append(u)
    eligible=state.eligible or (action.kind=='critical' and obs=='D')
    return BeliefState(canonical_models(models),tuple(sorted(state.used+(action.action_id,))),eligible)

def available(state,actions): return tuple(a for a in actions if a.action_id not in state.used)

class ExactRobustSolver:
    def __init__(self,actions):
        self.actions=tuple(actions); self.calls=0; self.by={a.action_id:a for a in actions}
        self._value=lru_cache(None)(self._uncached)
    def clear(self): self._value.cache_clear(); self.calls=0
    def _uncached(self,state,h):
        self.calls+=1
        if state.eligible:return (1.0,'STOP')
        if h==0:return (0.0,'STOP')
        best=(0.0,'STOP')
        for a in available(state,self.actions):
            child={o:successor(state,a,o) for o in outcomes(state,a)}; vals=[]
            for k in state.models:
                m=model_from_key(k); ex=0.0
                for o,p in outcome_probs(m,a).items():
                    if p>1e-15: ex+=p*self._value(child[o],h-1)[0]
                vals.append(ex)
            q=-a.cost+min(vals)
            if q>best[0]+1e-12: best=(q,a.action_id)
        return best
    def value(self,state,h): return self._value(state,h)

def evaluate_policy(planning_state,true_model,h,solver):
    if planning_state.eligible:return 1.0
    if h==0:return 0.0
    _,aid=solver.value(planning_state,h)
    if aid=='STOP':return 0.0
    a=solver.by[aid]; total=-a.cost
    for o,p in outcome_probs(true_model,a).items():
        if p>1e-15:
            total+=p*evaluate_policy(successor(planning_state,a,o),update_model(true_model,a,o),h-1,solver)
    return total
