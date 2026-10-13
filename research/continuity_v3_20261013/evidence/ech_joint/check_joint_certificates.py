#!/usr/bin/env python3
"""Independent standard-library checker for fixed-route ECH optimality.

No optimizer, NumPy, or producer code is imported. It reconstructs the finite
kernel and checks every admissible stage-coordinate dual inequality exactly.
The dual relaxes binary/capacity constraints; a matching integer witness closes
the original bounded problem without relying on grouping or solver status.
"""
import argparse, hashlib, json, math, time
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from pathlib import Path

def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def require(c,m):
    if not c:raise ValueError(m)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--results',type=Path,required=True);ap.add_argument('--catalog',type=Path);args=ap.parse_args();started=time.monotonic()
    protocol=json.loads((args.results/'PROTOCOL_FIXED_TWO_STAGE.json').read_text())
    result=json.loads((args.results/'ECH_JOINT_ROUTE_RESULT.json').read_text())
    saved=result.pop('result_sha256');require(sha(canonical(result))==saved,'result digest mismatch')
    require(sha((args.results/'PROTOCOL_FIXED_TWO_STAGE.json').read_bytes())==result['protocol_sha256'],'protocol digest mismatch')
    for name,h in protocol['input_sha256'].items():require(sha((args.source/name).read_bytes())==h,'input hash mismatch: '+name)
    raw=(args.results/'JOINT_ROUTE_CERTIFICATES.json').read_bytes();require(sha(raw)==result['certificate_sha256'],'certificates digest mismatch')
    certs=json.loads(raw);require(len(certs)==len(protocol['routes'])==46,'wrong route coverage')
    detail=json.loads((args.source/'results/FINITE_ATLAS_REPLAY_DETAIL.json').read_text());require(len(detail['squares'])==23,'wrong archived square count')
    books=json.loads((args.source/'inputs/compiled_distance_codebooks.json').read_text())
    kernel=json.loads((args.source/'inputs/cas_constitutional_kernel_v1.json').read_text());nodes=kernel['nodes']
    roots={int(r['class_id']):int(r['root']) for r in kernel['roots']};classes=sorted(roots);pairs=list(combinations(classes,2))
    masks=[m for m in range(1<<len(kernel['ordered_blocks'])) if m.bit_count()>=kernel['domain_floor']]
    require(len(masks)==4017,'unexpected admissible-mask family');names=[f'{m:03x}' for m in masks];idx={m:i for i,m in enumerate(names)}
    @lru_cache(None)
    def node_hash(i):
        n=nodes[i]
        if 'label' in n:return sha(('L\0'+n['label']).encode())
        require(0<=n['if_excluded']<i and 0<=n['if_included']<i,'not child-before-parent DAG')
        return sha(b'Q\0'+str(n['query_index']).encode()+b'\0'+bytes.fromhex(node_hash(n['if_excluded']))+bytes.fromhex(node_hash(n['if_included'])))
    for r in kernel['roots']:require(node_hash(r['root'])==r['structural_sha256'],'root structural digest mismatch')
    def evaluate(root,mask):
        for _ in range(len(nodes)):
            n=nodes[root]
            if 'label' in n:return n['label']
            root=n['if_included'] if mask&(1<<n['query_index']) else n['if_excluded']
        raise ValueError('cycle')
    exact={c:tuple(evaluate(roots[c],m) for m in masks) for c in classes}
    require(all(s!='OUTSIDE_DECLARED_DOMAIN' for row in exact.values() for s in row),'inadmissible-domain output')
    modes={c:tuple(s.split(':',1)[0] for s in exact[c]) for c in classes}
    action={c:tuple(s in ('APPLY','TOP_2') for s in modes[c]) for c in classes}
    mats={'EXACT':exact,'MODE':modes,'ACTIONABLE':action}
    relevant={s:set(p for p in pairs if mat[p[0]]!=mat[p[1]]) for s,mat in mats.items()}
    @lru_cache(None)
    def differences(sensor,p):
        return bytes(a!=b for a,b in zip(mats[sensor][p[0]],mats[sensor][p[1]]))
    def delta(p,q):
        sensor,m=q.split(':');return differences(sensor,p)[idx[m]]
    def distance(p,E):return sum(delta(p,q) for q in E)
    def satisfies(E,book):return min(distance(p,E) for p in relevant[book['target']])>=book['distance']
    inequalities=0;staged_pair_checks=0;archived_checks=0;closed=0;improved=0;route_ids=set();summedcost=0;summedold=0
    for route,cert in zip(protocol['routes'],certs):
        require(cert['route']==route,'route not identical to frozen scope')
        checksum=cert['certificate_sha256'];unsigned={k:v for k,v in cert.items() if k!='certificate_sha256'}
        require(sha(canonical(unsigned))==checksum,'route certificate content hash mismatch')
        rid=route['route_id'];require(rid not in route_ids,'duplicate route');route_ids.add(rid)
        sq=detail['squares'][int(route['square_id'][1:])-1];path=int(rid[-1]);archived=sq[f'path{path}']
        require(route['source']==sq['source'] and route['intermediate']==sq[f'intermediate_{path}'] and route['destination']==sq['destination'],'route differs from archived square')
        require(route['archived_local_cost']==sq[f'path{path}_cost'] and route['archived_first_cost']==archived[0]['cost'] and route['archived_second_cost']==archived[1]['cost'],'archived cost mismatch')
        b0,b1,b2=[books[route[k]] for k in ['source','intermediate','destination']];E=cert['inherited_coordinates'];W1=cert['first_witness'];W2=cert['second_witness']
        require(E==sorted(b0['sensor']+':'+m for m in b0['probes']),'source codebook changed')
        require(len(E+W1+W2)==len(set(E+W1+W2)),'repeated/acquired inherited typed coordinate')
        for W,b in [(W1,b1),(W2,b2)]:require(all(q.split(':')[0]==b['sensor'] and q.split(':')[1] in idx for q in W),'stage sensor or mask invalid')
        require(satisfies(E+W1,b1) and satisfies(E+W1+W2,b2),'infeasible joint witness')
        staged_pair_checks+=len(relevant[b1['target']])+len(relevant[b2['target']])
        require(cert['first_cost']==len(W1) and cert['second_cost']==len(W2) and cert['joint_cost']==len(W1+W2),'witness cost mismatch')
        # Check historical comparator independently, including its stage rules.
        A1,A2=archived[0]['witness'],archived[1]['witness']
        require(len(E+A1+A2)==len(set(E+A1+A2)),'historical witness duplicates')
        require(all(q.split(':')[0]==b1['sensor'] for q in A1) and all(q.split(':')[0]==b2['sensor'] for q in A2),'historical sensor mismatch')
        require(satisfies(E+A1,b1) and satisfies(E+A1+A2,b2),'historical comparator infeasible');archived_checks+=1
        ds=cert['rational_dual'];weights=[Fraction(x['weight']) for x in ds];require(all(w>=0 for w in weights),'negative dual')
        dualkeys=[(x['stage'],tuple(x['classes'])) for x in ds];require(len(dualkeys)==len(set(dualkeys)),'duplicate dual constraint')
        for x in ds:
            stage=x['stage'];p=tuple(x['classes']);require(stage in (1,2),'invalid dual stage');b=b1 if stage==1 else b2
            require(p in relevant[b['target']],'irrelevant class pair');require(x['residual_distance']==b['distance']-distance(p,E)>0,'wrong residual distance')
        den=math.lcm(*(w.denominator for w in weights)) if weights else 1
        nums=[w.numerator*(den//w.denominator) for w in weights]
        # Stage-1 coordinate contributes to BOTH stages; stage-2 only to final.
        for stage,sensor in [(1,b1['sensor']),(2,b2['sensor'])]:
            terms=[(n,differences(sensor,tuple(x['classes']))) for n,x in zip(nums,ds) if stage==1 or x['stage']==2]
            for m,j in idx.items():
                if sensor+':'+m in E:continue
                require(sum(n*bits[j] for n,bits in terms)<=den,'infeasible rational dual coordinate: '+rid)
                inequalities+=1
        lower=sum((w*x['residual_distance'] for w,x in zip(weights,ds)),Fraction(0));ilower=math.ceil(lower)
        require(str(lower)==cert['exact_dual_lower_bound'] and ilower==cert['certified_integer_lower_bound'],'lower bound mismatch')
        require(cert['certified_gap']==len(W1+W2)-ilower>=0,'gap mismatch');closed+=cert['certified_gap']==0
        require(cert['status']==('EXACT_OPTIMUM' if ilower==len(W1+W2) else 'INTEGER_WITNESS_WITH_OPEN_GAP'),'false optimum status')
        saving=route['archived_local_cost']-len(W1+W2);require(saving==cert['saving_against_archived_local_policy']>=0,'false saving');improved+=saving>0
        summedcost+=len(W1+W2);summedold+=route['archived_local_cost']
    require(closed==result['certified_optimal_routes'] and improved==result['improved_routes'],'summary counts mismatch')
    require(summedcost==result['joint_total_cost_across_routes'] and summedold==result['archived_total_cost_across_routes'],'summary costs mismatch')
    square_rows=json.loads((args.results/'JOINT_SQUARE_COMPARISON.json').read_text());require(len(square_rows)==23,'square comparison size mismatch')
    noncommuting=0
    for i,row in enumerate(square_rows):
        c1,c2=certs[2*i:2*i+2];require(row['path1_joint_cost']==c1['joint_cost'] and row['path2_joint_cost']==c2['joint_cost'],'square cost mismatch')
        same=c1['joint_cost']==c2['joint_cost'];require(row['joint_cost_commutes']==same,'commutation flag mismatch');noncommuting+=not same
    require(noncommuting==result['joint_noncommuting_cost_squares'],'joint noncommuting count mismatch')
    catalog_count=0;catalog_inequalities=0
    if args.catalog:
        catalog=json.loads(args.catalog.read_text());require(len(catalog['plans'])==46,'wrong catalog size')
        oldcert={c['problem_id']:c for c in json.loads((args.source/'results/EXACT_BRIDGE_CERTIFICATES.json').read_text())}
        for plan,joint in zip(catalog['plans'],certs):
            r=joint['route'];require(all(plan[x]==r[x] for x in ['route_id','source','intermediate','destination']),'catalog route mismatch')
            E=plan['inherited_coordinates'];W1=plan['first_witness'];W2=plan['second_witness'];b1=books[r['intermediate']];b2=books[r['destination']]
            require(E==joint['inherited_coordinates'],'catalog inherited state mismatch')
            require(len(E+W1+W2)==len(set(E+W1+W2)),'catalog duplicate coordinate')
            require(all(q.split(':')[0]==b1['sensor'] and q.split(':')[1] in idx for q in W1) and all(q.split(':')[0]==b2['sensor'] and q.split(':')[1] in idx for q in W2),'catalog sensor/mask violation')
            require(satisfies(E+W1,b1) and satisfies(E+W1+W2,b2),'catalog infeasible')
            require(len(W1)==plan['first_cost'] and len(W2)==plan['second_cost'],'catalog stage cost mismatch')
            require(plan['joint_optimum']==joint['joint_cost']==len(W1+W2) and joint['certified_gap']==0,'catalog not jointly optimal')
            require(plan['joint_lower_bound_certificate_sha256']==joint['certificate_sha256'],'catalog joint proof reference mismatch')
            sq=detail['squares'][int(r['square_id'][1:])-1];historical=sq['path'+r['route_id'][-1]][0]
            require(plan['first_original_minimum_certificate']==historical['problem_id'],'catalog first-minimum reference mismatch')
            first=oldcert[historical['problem_id']];require(first['inherited_coordinates']==E and first['destination']==r['intermediate'],'original first proof state mismatch')
            ds=first['rational_dual'];ws=[Fraction(x['weight']) for x in ds];require(all(w>=0 for w in ws),'negative original first dual')
            for x in ds:
                pair=tuple(x['classes']);require(pair in relevant[b1['target']] and x['residual_distance']==b1['distance']-distance(pair,E)>0,'invalid original first RHS')
            den=math.lcm(*(w.denominator for w in ws)) if ws else 1
            terms=[(w.numerator*(den//w.denominator),differences(b1['sensor'],tuple(x['classes']))) for w,x in zip(ws,ds)]
            for m,j in idx.items():
                if b1['sensor']+':'+m in E:continue
                require(sum(n*bits[j] for n,bits in terms)<=den,'original first exact dual infeasible');catalog_inequalities+=1
            minimum=math.ceil(sum((w*x['residual_distance'] for w,x in zip(ws,ds)),Fraction(0)))
            require(minimum==first['certified_minimum_queries']==len(W1),'catalog first stage not locally minimum')
            # The already checked unrestricted joint bound, minus this fixed
            # first cost, proves the catalog's second-stage local optimum too.
            require(joint['certified_integer_lower_bound']-len(W1)==len(W2),'catalog second optimum not closed')
            catalog_count+=1
    receipt={'schema':'ECH_JOINT_ROUTE_SOLVER_FREE_CHECK_V1','status':'PASS','routes_checked':46,'exact_optima_certified':closed,'squares_checked':23,'archived_comparators_reverified':archived_checks,'exact_rational_dual_coordinate_inequalities_checked':inequalities,'integer_stage_pair_feasibility_checks':staged_pair_checks,'all_source_root_structural_hashes_checked':len(kernel['roots']),'solver_imported':False,'producer_imported':False,'third_party_libraries_imported':False,'grouped_matrices_trusted':False,'all_original_admissible_coordinates_checked':True,'local_minimum_lookahead_catalog_plans_verified':catalog_count,'catalog_original_first_minimum_dual_inequalities_checked':catalog_inequalities,'catalog_both_stages_locally_optimal_and_total_globally_optimal_for_fixed_route':catalog_count==46,'catalog_sha256':sha(args.catalog.read_bytes()) if args.catalog else None,'result_sha256':saved,'checker_sha256':sha(Path(__file__).read_bytes()),'elapsed_seconds':time.monotonic()-started,'permission_granted':False}
    (args.results/'SOLVER_FREE_JOINT_CHECK.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
