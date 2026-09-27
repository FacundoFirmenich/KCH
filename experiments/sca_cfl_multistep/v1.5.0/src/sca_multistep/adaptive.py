import itertools
from .planner import consistent,apply
from sca_dep.robust import robust_genealogy_gate

def partials(actions,worlds):
    ids=[a.action_id for a in actions]; seen=set(); out=[]
    for r in range(len(ids)+1):
        for sub in itertools.combinations(ids,r):
            for w in worlds:
                psi=tuple(sorted((a,w.outcome(a)) for a in sub))
                if psi not in seen: seen.add(psi); out.append(psi)
    return out

def marginal(events,constraints,actions,worlds,psi,aid,objective='eligibility'):
    by={a.action_id:a for a in actions}; a=by[aid]; post=consistent(worlds,psi)
    cc=tuple(constraints)
    for x,o in psi: cc=apply(cc,by[x],o)
    if objective=='eligibility': base=float(robust_genealogy_gate(events,cc).eligible)
    else: base=float(len(psi))
    g=0.
    for w,p in post:
        c2=apply(cc,a,w.outcome(aid))
        val=float(robust_genealogy_gate(events,c2).eligible) if objective=='eligibility' else float(len(psi)+1)
        g+=p*(val-base)
    return g

def check(events,constraints,actions,worlds,objective='eligibility',tol=1e-12):
    states=partials(actions,worlds); violations=[]; n=0
    for p in states:
      for q in states:
        if not set(p).issubset(set(q)): continue
        used={a for a,_ in q}
        for a in actions:
          if a.action_id in used: continue
          d1=marginal(events,constraints,actions,worlds,p,a.action_id,objective)
          d2=marginal(events,constraints,actions,worlds,q,a.action_id,objective)
          n+=1
          if d1+tol<d2: violations.append({'psi':p,'psi_prime':q,'action':a.action_id,'delta_before':d1,'delta_after':d2,'gap':d2-d1})
    return {'adaptive_submodular':not violations,'checked':n,'violations':violations}
