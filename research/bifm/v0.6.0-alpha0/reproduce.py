#!/usr/bin/env python3
"""Reproduce the BIFM v0.6 finite audit and balanced benchmark."""
import json
from formal_core import *

def paircheck(z):
    if not z["compat"] or z["q"] is None:
        return "OUT_OF_SCOPE"
    if collision_witness(z["o"],z["q"]) is None:
        return "PRACTICALLY_UNSTABLE" if z["ratio"] and z["ratio"]>50 else "IDENTIFIABLE"
    if z["subset"]:
        s=set(z["subset"])
        if all(not(z["o"][i]==z["o"][j] and z["q"][i]!=z["q"][j]) for i in s for j in s if i<j):
            return "CONDITIONALLY_IDENTIFIABLE"
    if z["probes"]:
        if all(any(p[i]!=p[j] for p in z["probes"]) for i in range(6) for j in range(i+1,6) if z["o"][i]==z["o"][j] and z["q"][i]!=z["q"][j]):
            return "RECOVERABLE_BY_PROBE"
    return "NOT_IDENTIFIABLE"

def render(z):
    vec=lambda x:"UNDEFINED" if x is None else ",".join(map(str,x))
    probes="NONE" if not z["probes"] else ";".join(vec(p) for p in z["probes"])
    subset="NONE" if not z["subset"] else vec(z["subset"])
    ratio="NONE" if z["ratio"] is None else f'{z["ratio"]:.6f}'
    compat="YES" if z["compat"] else "NO"
    return f'Claim {z["id"]}|Family {z["family"]}|O {vec(z["o"])}|Q {vec(z["q"])}|P {probes}|A {subset}|R {ratio}|C {compat}'

def parse(text,status):
    fields={}
    for chunk in text.split("|"):
        k,v=chunk.split(" ",1)
        fields[k]=v
    pv=lambda s:None if s in ("NONE","UNDEFINED") else tuple(map(int,s.split(",")))
    return {"id":fields["Claim"],"family":fields["Family"],"status":status,"o":pv(fields["O"]),"q":pv(fields["Q"]),
            "probes":() if fields["P"]=="NONE" else tuple(pv(x) for x in fields["P"].split(";")),
            "subset":pv(fields["A"]),"ratio":None if fields["R"]=="NONE" else float(fields["R"]),"compat":fields["C"]=="YES"}

def main():
    total=identified=nonidentified=failures=0
    for n in range(1,8):
        ps=list(partitions(n))
        for o in ps:
            for q in ps:
                total+=1
                a=refines(o,q); b=factor_map(o,q) is not None; c=collision_witness(o,q) is None
                failures += not(a==b==c); identified += a; nonidentified += not a
    assert (total,identified,nonidentified,failures)==(813297,22207,791090,0)

    counts={s:0 for s in STATUSES}; families={f:0 for f in FAMILIES}
    disagreements=roundtrip_failures=0
    for f in FAMILIES:
        for s in STATUSES:
            for k in range(90):
                z=make_instance(f,s,k)
                status,_=classify(z)
                assert status==s
                disagreements += status!=paircheck(z)
                roundtrip_failures += fingerprint(z)!=fingerprint(parse(render(z),s))
                counts[s]+=1; families[f]+=1
    assert disagreements==0 and roundtrip_failures==0 and sum(counts.values())==4320
    print(json.dumps({"formal_pairs":total,"identified":identified,"not_identified":nonidentified,"formal_failures":failures,
        "instances":4320,"status_counts":counts,"family_counts":families,"checker_disagreements":disagreements,
        "cnl_roundtrip_failures":roundtrip_failures},indent=2,sort_keys=True))

if __name__=="__main__":
    main()
