#!/usr/bin/env python3
"""Reproduce the structural-diversity audit of the v0.6 generator.

This does not alter v0.6 history. It reconstructs its documented generator:
8 family labels x 6 coarse statuses x 90 k values, with rotations k mod 6.
"""
import itertools, json

FAMILIES=(
 "behavior_to_mechanism","statistics_to_causality","capability_to_authority","local_to_global",
 "genealogy_vs_performance","function_to_biology","behavior_to_phenomenology","control_and_temporal_effect",
)
STATUSES=("IDENTIFIABLE","NOT_IDENTIFIABLE","CONDITIONALLY_IDENTIFIABLE","RECOVERABLE_BY_PROBE","PRACTICALLY_UNSTABLE","OUT_OF_SCOPE")

def perm(base,shift):
    n=len(base); return tuple(base[(k+shift)%n] for k in range(n))

def row(f,s,k):
    n=6; oi=(0,1,2,3,4,5); om=(0,0,1,1,2,2); pp=(0,1,0,1,0,1); pc=(0,0,1,1,2,2); probe=pp; sh=k%n
    z={"family":f,"status":s,"obs":None,"prop":None,"probes":(),"subset":None,"ratio":None,"compat":True}
    if s=="IDENTIFIABLE": z.update(obs=perm(oi,sh),prop=perm(pc,sh))
    elif s=="NOT_IDENTIFIABLE": z.update(obs=perm(om,sh),prop=perm(pp,sh))
    elif s=="CONDITIONALLY_IDENTIFIABLE": z.update(obs=perm(om,sh),prop=perm(pp,sh),subset=tuple(sorted(((0-sh)%n,(2-sh)%n,(4-sh)%n))))
    elif s=="RECOVERABLE_BY_PROBE": z.update(obs=perm(om,sh),prop=perm(pp,sh),probes=(perm(probe,sh),))
    elif s=="PRACTICALLY_UNSTABLE": z.update(obs=perm(oi,sh),prop=perm(pc,sh),ratio=100.0+k)
    elif s=="OUT_OF_SCOPE": z.update(obs=perm(om,sh),prop=None,compat=False)
    return z

def norm(v):
    if v is None:return None
    d={}; out=[]
    for x in v:
        if x not in d:d[x]=len(d)
        out.append(d[x])
    return tuple(out)

def canonical(z,bucket_ratio):
    n=len(z["obs"]); best=None; aset=set(z["subset"] or ())
    for p in itertools.permutations(range(n)):
        o=norm([z["obs"][j] for j in p])
        q=None if z["prop"] is None else norm([z["prop"][j] for j in p])
        probes=tuple(sorted(norm([pr[j] for j in p]) for pr in z["probes"]))
        subset=None if z["subset"] is None else tuple(k for k,j in enumerate(p) if j in aset)
        ratio=None if z["ratio"] is None else ("UNSTABLE" if bucket_ratio else z["ratio"])
        c=(z["status"],z["compat"],o,q,probes,subset,ratio)
        if best is None or repr(c)<repr(best):best=c
    return best

def main():
    rows=[row(f,s,k) for f in FAMILIES for s in STATUSES for k in range(90)]
    raw_no_family={
      json.dumps({k:(list(v) if isinstance(v,tuple) else v) for k,v in z.items() if k!="family"},sort_keys=True,default=list)
      for z in rows
    }
    raw_family={
      json.dumps({k:(list(v) if isinstance(v,tuple) else v) for k,v in z.items()},sort_keys=True,default=list)
      for z in rows
    }
    reps=[]
    seen=set()
    for z in rows:
        key=json.dumps({k:(list(v) if isinstance(v,tuple) else v) for k,v in z.items() if k!="family"},sort_keys=True,default=list)
        if key not in seen:
            seen.add(key); reps.append(z)
    exact={canonical(z,False) for z in reps}
    bucket={canonical(z,True) for z in reps}
    result={
      "rows":len(rows),
      "raw_unique_excluding_family":len(raw_no_family),
      "raw_unique_including_family":len(raw_family),
      "structural_classes_exact_ratio_excluding_family":len(exact),
      "structural_classes_bucketed_ratio_excluding_family":len(bucket),
      "interpretation":"v0.6 is certificate-correct but structurally repetitive; v0.7 reports quotient classes explicitly.",
    }
    assert result["rows"]==4320
    assert result["raw_unique_excluding_family"]==120
    assert result["raw_unique_including_family"]==960
    assert result["structural_classes_exact_ratio_excluding_family"]==95
    assert result["structural_classes_bucketed_ratio_excluding_family"]==6
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
