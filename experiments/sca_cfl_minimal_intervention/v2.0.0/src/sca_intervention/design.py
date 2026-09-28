from itertools import combinations

def pair_universe(n):
    return tuple((i,j) for i in range(n) for j in range(i+1,n))

def separated_pairs(hypotheses,k,tol=1e-12):
    return frozenset((i,j) for i,j in pair_universe(len(hypotheses)) if abs(hypotheses[i].predictions[k]-hypotheses[j].predictions[k])>tol)

def partition_cells(hypotheses,selected,digits=12):
    cells={}
    for i,h in enumerate(hypotheses):
        sig=tuple(round(h.predictions[k],digits) for k in selected)
        cells.setdefault(sig,[]).append(i)
    return tuple(tuple(v) for _,v in sorted(cells.items(),key=lambda kv:kv[0]))

def exact_min_cost_design(hypotheses,interventions):
    allowed=[i for i,a in enumerate(interventions) if a.authorized]
    target=set(pair_universe(len(hypotheses)))
    cover={i:set(separated_pairs(hypotheses,i)) for i in allowed}
    possible=set().union(*(cover.values())) if cover else set()
    irreducible=target-possible
    required=target-irreducible
    best=None
    for r in range(len(allowed)+1):
        for S in combinations(allowed,r):
            got=set().union(*(cover[i] for i in S)) if S else set()
            if required<=got:
                cand=(sum(interventions[i].cost for i in S),len(S),S)
                if best is None or cand<best: best=cand
    cost,_,selected=best if best else (0.0,0,())
    got=set().union(*(cover[i] for i in selected)) if selected else set()
    return {"selected_ids":tuple(interventions[i].intervention_id for i in selected),"cost":cost,"resolved_pairs":len(got),"irreducible_pairs":tuple(sorted(irreducible)),"globally_complete":not irreducible and target<=got}

def greedy_cost_design(hypotheses,interventions):
    allowed=[i for i,a in enumerate(interventions) if a.authorized]
    target=set(pair_universe(len(hypotheses))); cover={i:set(separated_pairs(hypotheses,i)) for i in allowed}
    unresolved=target & (set().union(*(cover.values())) if cover else set()); chosen=[]
    while unresolved:
        cand=[]
        for i in allowed:
            if i in chosen: continue
            gain=len(unresolved & cover[i])
            if gain: cand.append((gain/interventions[i].cost,gain,-interventions[i].cost,-i,i))
        if not cand: break
        i=max(cand)[-1]; chosen.append(i); unresolved-=cover[i]
    return {"selected_ids":tuple(interventions[i].intervention_id for i in chosen),"cost":sum(interventions[i].cost for i in chosen),"unresolved":tuple(sorted(unresolved))}
