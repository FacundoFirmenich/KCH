#!/usr/bin/env python3
import hashlib, json, os, sys
sys.path.insert(0,os.path.dirname(__file__))
from structural_quotient import census

def expand(m):
    obs=[]; prop=[]
    for i,row in enumerate(m):
        for j,count in enumerate(row):
            for _ in range(count):
                obs.append(i); prop.append(j)
    return obs,prop

def certificate(m,ident):
    obs,prop=expand(m)
    if ident:
        fm={}
        for o,q in zip(obs,prop):
            if o in fm: assert fm[o]==q
            fm[o]=q
        return {"kind":"factor_map","map":sorted(fm.items())}
    seen={}
    for idx,(o,q) in enumerate(zip(obs,prop)):
        if o in seen and seen[o][1]!=q:
            return {"kind":"collision_witness","worlds":[seen[o][0],idx],"observation_class":o,"property_classes":[seen[o][1],q]}
        seen[o]=(idx,q)
    raise AssertionError("missing collision")

def main(outpath=None):
    classes,_=census(); rows=[]
    for n,m,ident in sorted(classes,key=lambda x:(x[0],len(x[1]),len(x[1][0]),x[1])):
        rec={"n":n,"contingency":[list(r) for r in m],"structural_status":"IDENTIFIABLE" if ident else "NOT_IDENTIFIABLE","certificate":certificate(m,ident)}
        rec["structural_sha256"]=hashlib.sha256(json.dumps(rec,sort_keys=True,separators=(",",":")).encode()).hexdigest()
        rows.append(rec)
    assert len(rows)==1347
    assert len({r["structural_sha256"] for r in rows})==1347
    if outpath:
        with open(outpath,"w",encoding="utf-8") as f:
            for r in rows: f.write(json.dumps(r,sort_keys=True,separators=(",",":"))+"\n")
    print(json.dumps({"instances":len(rows),"unique_structural_hashes":len({r["structural_sha256"] for r in rows}),"identifiable":sum(r["structural_status"]=="IDENTIFIABLE" for r in rows),"not_identifiable":sum(r["structural_status"]=="NOT_IDENTIFIABLE" for r in rows)},indent=2,sort_keys=True))

if __name__=="__main__":
    main(sys.argv[1] if len(sys.argv)>1 else None)
