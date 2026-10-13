#!/usr/bin/env python3
"""Solver-free, standard-library verifier of finite ECH rational certificates.

This checker does not import the certificate-producing implementation or SciPy.
Every lower-bound inequality is checked using integers on all legal new queries.
"""
import argparse, hashlib, json, math, sys
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from pathlib import Path

def digest(b): return hashlib.sha256(b).hexdigest()
def canonical(v): return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def require(condition, message):
    if not condition: raise ValueError(message)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--inputs',type=Path,required=True)
    ap.add_argument('--results',type=Path,required=True)
    args=ap.parse_args()
    result=json.loads((args.results/'ECH_EXACT_SUCCESSOR_RESULT.json').read_text())
    saved=result.pop('result_sha256')
    require(digest(canonical(result))==saved,'result content digest mismatch')
    for item in result['inputs']:
        require(digest((args.inputs/item['name']).read_bytes())==item['sha256'],'input digest mismatch')
    for name,expected in result['output_hashes'].items():
        require(digest((args.results/name).read_bytes())==expected,'certificate/detail digest mismatch')
    k=json.loads((args.inputs/'cas_constitutional_kernel_v1.json').read_text())
    books=json.loads((args.inputs/'compiled_distance_codebooks.json').read_text())
    nodes=k['nodes']; roots={r['class_id']:r['root'] for r in k['roots']}
    masks=[m for m in range(1<<len(k['ordered_blocks'])) if m.bit_count()>=k['domain_floor']]
    classes=sorted(roots); pairs=list(combinations(classes,2))
    def read(root,m):
        for _ in range(len(nodes)):
            n=nodes[root]
            if 'label' in n:return n['label']
            root=n['if_included'] if m&(1<<n['query_index']) else n['if_excluded']
        raise ValueError('cyclic kernel')
    exact={c:tuple(read(roots[c],m) for m in masks) for c in classes}
    mode={c:tuple(s.split(':',1)[0] for s in exact[c]) for c in classes}
    act={c:tuple(s in ('APPLY','TOP_2') for s in mode[c]) for c in classes}
    mats={'EXACT':exact,'MODE':mode,'ACTIONABLE':act}
    index={f'{m:03x}':q for q,m in enumerate(masks)}
    relevant={s:[p for p in pairs if mats[s][p[0]]!=mats[s][p[1]]] for s in mats}
    @lru_cache(None)
    def observation_difference(pair,coordinate):
        sensor,probe=coordinate.split(':')
        return int(mats[sensor][pair[0]][index[probe]]!=mats[sensor][pair[1]][index[probe]])
    def distance(pair,E):return sum(observation_difference(pair,q) for q in E)
    certificates=json.loads((args.results/'EXACT_BRIDGE_CERTIFICATES.json').read_text())
    detail=json.loads((args.results/'FINITE_ATLAS_REPLAY_DETAIL.json').read_text())
    ids=set(); inequalities=0; positive=0
    for cert in certificates:
        E=cert['inherited_coordinates']; W=cert['witness']; dst=cert['destination']; b=books[dst]
        require(len(E)==len(set(E)) and len(W)==len(set(W)),'repeated typed coordinate')
        require(not set(E)&set(W),'witness re-acquires inherited coordinate')
        require(all(q.startswith(b['sensor']+':') and q.split(':')[1] in index for q in W),'inadmissible witness')
        pid=digest(canonical({'E':sorted(E),'destination':dst}))
        require(pid==cert['problem_id'] and pid not in ids,'invalid/duplicate problem identity')
        ids.add(pid)
        for p in relevant[b['target']]:
            require(distance(p,E+W)>=b['distance'],'infeasible witness')
        require(len(W)==cert['certified_minimum_queries'],'witness cost mismatch')
        ds=cert['rational_dual']; weights=[Fraction(x['weight']) for x in ds]
        require(all(w>=0 for w in weights),'negative dual weight')
        require(len({tuple(x['classes']) for x in ds})==len(ds),'repeated dual constraint')
        dual_pairs=[tuple(x['classes']) for x in ds]
        for item,p in zip(ds,dual_pairs):
            require(p in relevant[b['target']],'irrelevant dual pair')
            require(item['residual_distance']==b['distance']-distance(p,E)>0,'incorrect dual right hand side')
        denominator=math.lcm(*(w.denominator for w in weights)) if weights else 1
        integer_weights=[w.numerator*(denominator//w.denominator) for w in weights]
        if ds:
            positive+=1
            for probe in index:
                q=b['sensor']+':'+probe
                if q in E:continue
                require(sum(w*observation_difference(p,q) for p,w in zip(dual_pairs,integer_weights))<=denominator,'infeasible exact dual')
                inequalities+=1
        lower=sum((w*item['residual_distance'] for w,item in zip(weights,ds)),Fraction(0))
        require(str(lower)==cert['exact_dual_lower_bound'],'reported lower bound mismatch')
        integer_bound=(lower.numerator+lower.denominator-1)//lower.denominator
        require(integer_bound==len(W),'integer optimality not closed')
    references=[]
    for row in detail['adjacent']:references.append(row['problem_id'])
    for row in detail['loops']:references += [row['first']['problem_id'],row['return']['problem_id']]
    for row in detail['squares']:
        references += [p['problem_id'] for p in row['path1']+row['path2']]
    require(set(references)==ids,'certificate reference closure mismatch')
    receipt={
        'schema':'ECH_SOLVER_FREE_CERTIFICATE_CHECK_V1','status':'PASS',
        'certificate_count':len(certificates),'positive_cost_certificates':positive,
        'zero_cost_certificates':len(certificates)-positive,
        'exact_integer_dual_inequalities_checked':inequalities,
        'bridge_applications_covered':len(references),
        'result_sha256_checked':saved,
        'checker_sha256':digest(Path(__file__).read_bytes()),
        'optimizer_imported':False,'third_party_libraries_imported':False,
        'permission_granted':False,
    }
    (args.results/'SOLVER_FREE_CERTIFICATE_CHECK.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
