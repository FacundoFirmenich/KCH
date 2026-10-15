#!/usr/bin/env python3
"""Structural quotient census for BIFM finite identifiability worlds.

Canonical object: contingency matrix between observation blocks (rows) and
target-property blocks (columns), modulo independent row/column permutations.
"""
import itertools, json
from collections import Counter

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

def contingency(obs,prop):
    r=max(obs)+1; c=max(prop)+1
    m=[[0]*c for _ in range(r)]
    for a,b in zip(obs,prop):
        m[a][b]+=1
    return tuple(tuple(row) for row in m)

def canonical_matrix(m):
    r=len(m); c=len(m[0]); best=None
    if r<=c:
        for pr in itertools.permutations(range(r)):
            rows=[m[i] for i in pr]
            cols=[tuple(rows[i][j] for i in range(r)) for j in range(c)]
            order=sorted(range(c),key=lambda j:cols[j])
            cand=tuple(tuple(rows[i][j] for j in order) for i in range(r))
            flat=tuple(v for row in cand for v in row)
            if best is None or flat<best[0]:
                best=(flat,cand)
    else:
        for pc in itertools.permutations(range(c)):
            rows=[tuple(row[j] for j in pc) for row in m]
            cand=tuple(sorted(rows))
            flat=tuple(v for row in cand for v in row)
            if best is None or flat<best[0]:
                best=(flat,cand)
    return best[1]

def identifiable(m):
    return all(sum(v>0 for v in row)<=1 for row in m)

def census(max_n=7):
    all_classes=[]; by_n={}
    for n in range(1,max_n+1):
        ps=list(partitions(n))
        raw={contingency(o,q) for o in ps for q in ps}
        classes={}
        for m in raw:
            c=canonical_matrix(m)
            classes[c]=identifiable(c)
        cnt=Counter(classes.values())
        by_n[str(n)]={
            "partitions":len(ps),
            "partition_pairs":len(ps)**2,
            "raw_contingency_matrices":len(raw),
            "isomorphism_classes":len(classes),
            "identifiable":cnt[True],
            "not_identifiable":cnt[False],
        }
        for m,status in classes.items():
            all_classes.append((n,m,status))
    return all_classes,by_n

def main():
    classes,by_n=census()
    result={
        "max_n":7,
        "isomorphism_classes":len(classes),
        "identifiable":sum(s for _,_,s in classes),
        "not_identifiable":sum(not s for _,_,s in classes),
        "by_n":by_n,
    }
    assert result["isomorphism_classes"]==1347
    assert result["identifiable"]==220
    assert result["not_identifiable"]==1127
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
