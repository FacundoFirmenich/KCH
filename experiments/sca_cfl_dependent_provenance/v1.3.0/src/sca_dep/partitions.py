from collections import defaultdict
from .model import Relation
class UF:
    def __init__(self,xs): self.p={x:x for x in xs}
    def find(self,x):
        while self.p[x]!=x:
            self.p[x]=self.p[self.p[x]]; x=self.p[x]
        return x
    def union(self,a,b):
        a,b=self.find(a),self.find(b)
        if a!=b:self.p[b]=a

def normalized_components(events,constraints):
    ids=[e.event_id for e in events]; by={e.event_id:e for e in events}; uf=UF(ids)
    for c in constraints:
        if c.authorized and c.relation is Relation.SAME: uf.union(c.left,c.right)
    comps=defaultdict(list)
    for i in ids: comps[uf.find(i)].append(i)
    roots=sorted(comps); idx={r:k for k,r in enumerate(roots)}; distinct=set()
    for c in constraints:
        if not c.authorized or c.relation is not Relation.DISTINCT: continue
        a,b=idx[uf.find(c.left)],idx[uf.find(c.right)]
        if a==b: raise ValueError("INCONSISTENT_PROVENANCE_CONSTRAINTS")
        distinct.add(tuple(sorted((a,b))))
    components=[{"members":tuple(sorted(comps[r])),"directions":tuple(by[x].direction for x in sorted(comps[r]))} for r in roots]
    return components,distinct

def enumerate_partitions(events,constraints,max_components=10):
    comps,distinct=normalized_components(events,constraints); n=len(comps)
    if n>max_components: raise RuntimeError("EXACT_ENUMERATION_LIMIT")
    out=[]; blocks=[]
    def compatible(i,b): return all(tuple(sorted((i,j))) not in distinct for j in b)
    def rec(i):
        if i==n: out.append(tuple(tuple(b) for b in blocks)); return
        for b in blocks:
            if compatible(i,b): b.append(i); rec(i+1); b.pop()
        blocks.append([i]); rec(i+1); blocks.pop()
    rec(0); return comps,out
