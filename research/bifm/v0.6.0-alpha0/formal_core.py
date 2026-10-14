"""BIFM–CertiClaim v0.6 formal core (stdlib only)."""
import hashlib, json

FAMILIES=("behavior_to_mechanism","statistics_to_causality","capability_to_authority","local_to_global","genealogy_vs_performance","function_to_biology","behavior_to_phenomenology","control_and_temporal_effect")
STATUSES=("IDENTIFIABLE","NOT_IDENTIFIABLE","CONDITIONALLY_IDENTIFIABLE","RECOVERABLE_BY_PROBE","PRACTICALLY_UNSTABLE","OUT_OF_SCOPE")

def partitions(n):
    a=[0]*n
    if n==1:
        yield (0,); return
    def rec(i,m):
        if i==n:
            yield tuple(a); return
        for x in range(m+2):
            a[i]=x
            yield from rec(i+1,max(m,x))
    yield from rec(1,0)

def refines(obs,prop):
    seen={}
    for o,q in zip(obs,prop):
        if o in seen and seen[o]!=q:
            return False
        seen[o]=q
    return True

def factor_map(obs,prop):
    if not refines(obs,prop):
        return None
    return tuple(sorted({o:q for o,q in zip(obs,prop)}.items()))

def collision_witness(obs,prop):
    seen={}
    for i,(o,q) in enumerate(zip(obs,prop)):
        if o in seen and seen[o][1]!=q:
            return seen[o][0],i
        seen[o]=(i,q)
    return None

def join(*parts):
    remap={}; out=[]
    for t in zip(*parts):
        if t not in remap:
            remap[t]=len(remap)
        out.append(remap[t])
    return tuple(out)

def restrict(part,subset):
    remap={}; out=[]
    for i in subset:
        x=part[i]
        if x not in remap:
            remap[x]=len(remap)
        out.append(remap[x])
    return tuple(out)

def make_instance(family,status,k):
    n=6; shift=k%n
    rot=lambda x:tuple(x[(j+shift)%n] for j in range(n))
    oid=(0,1,2,3,4,5); om=(0,0,1,1,2,2); pp=(0,1,0,1,0,1); pc=(0,0,1,1,2,2)
    z={"id":f"{family}:{status}:{k:03d}","family":family,"status":status,"o":None,"q":None,"probes":(),"subset":None,"ratio":None,"compat":True}
    if status=="IDENTIFIABLE": z.update(o=rot(oid),q=rot(pc))
    elif status=="NOT_IDENTIFIABLE": z.update(o=rot(om),q=rot(pp))
    elif status=="CONDITIONALLY_IDENTIFIABLE": z.update(o=rot(om),q=rot(pp),subset=tuple(sorted(((0-shift)%n,(2-shift)%n,(4-shift)%n))))
    elif status=="RECOVERABLE_BY_PROBE": z.update(o=rot(om),q=rot(pp),probes=(rot(pp),))
    elif status=="PRACTICALLY_UNSTABLE": z.update(o=rot(oid),q=rot(pc),ratio=100.0+k)
    else: z.update(o=rot(om),q=None,compat=False)
    return z

def classify(z):
    if not z["compat"] or z["q"] is None:
        return "OUT_OF_SCOPE",("type_mismatch",)
    o,q=z["o"],z["q"]; fm=factor_map(o,q)
    if fm is not None:
        if z["ratio"] is not None and z["ratio"]>50:
            return "PRACTICALLY_UNSTABLE",("factor_map",fm,z["ratio"])
        return "IDENTIFIABLE",("factor_map",fm)
    if z["subset"] and factor_map(restrict(o,z["subset"]),restrict(q,z["subset"])) is not None:
        return "CONDITIONALLY_IDENTIFIABLE",("subset",z["subset"])
    if z["probes"] and factor_map(join(o,*z["probes"]),q) is not None:
        return "RECOVERABLE_BY_PROBE",("probes",len(z["probes"]))
    return "NOT_IDENTIFIABLE",("witness",collision_witness(o,q))

def fingerprint(z):
    x=dict(z)
    x["o"]=list(x["o"]); x["q"]=None if x["q"] is None else list(x["q"])
    x["probes"]=[list(p) for p in x["probes"]]
    x["subset"]=None if x["subset"] is None else list(x["subset"])
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(",",":")).encode()).hexdigest()
