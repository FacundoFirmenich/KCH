#!/usr/bin/env python3
"""Independent SMT cross-check of BIFM structural classes.

Requires: z3-solver.
The Python reference defines identifiability as row-wise functional dependence
in the contingency matrix. Z3 independently asks whether a function from
observation block to property block can satisfy all worlds.
"""
import json
from z3 import Int, Solver, sat
from structural_quotient import census, identifiable

def expand_worlds(m):
    obs=[]; prop=[]
    for i,row in enumerate(m):
        for j,count in enumerate(row):
            for _ in range(count):
                obs.append(i); prop.append(j)
    return obs,prop

def z3_identifiable(m):
    obs,prop=expand_worlds(m)
    rows=len(m)
    g=[Int(f"g_{i}") for i in range(rows)]
    s=Solver()
    for o,q in zip(obs,prop):
        s.add(g[o]==q)
    return s.check()==sat

def main():
    classes,by_n=census()
    mismatches=[]
    for n,m,expected in classes:
        got=z3_identifiable(m)
        if got!=expected:
            mismatches.append({"n":n,"matrix":[list(r) for r in m],"expected":expected,"z3":got})
    result={
        "classes_checked":len(classes),
        "reference_identifiable":sum(s for _,_,s in classes),
        "reference_not_identifiable":sum(not s for _,_,s in classes),
        "z3_mismatches":len(mismatches),
        "mismatch_examples":mismatches[:10],
    }
    assert result["classes_checked"]==1347
    assert result["z3_mismatches"]==0
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
