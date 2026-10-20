#!/usr/bin/env python3
"""Independent standard-library verification of frozen greedy policy and comparators.

Rebuilds responses directly from the original DAG. Integer bitsets implement
pair coverage, independently of the NumPy producer. Verifies all greedy choices,
sensor/domain/no-reacquisition contracts and exact rational joint lower bounds.
No solver, producer or stored grouped response matrix is imported.
"""
import argparse,csv,hashlib,json,math,time
from collections import defaultdict
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from pathlib import Path

def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def require(c,m):
    if not c:raise ValueError(m)
def indices(bits):
    while bits:
        low=bits&-bits;yield low.bit_length()-1;bits^=low

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();start=time.monotonic()
    P=json.loads((args.out/'PROTOCOL_GREEDY_V1.json').read_text())
    for p,h in P['input_sha256'].items():require(sha((args.repo/p).read_bytes())==h,'Frozen input mismatch '+p)
    require(sha((args.out/'run_greedy_baseline.py').read_bytes())==P['producer_sha256'],'Frozen producer changed')
    v2=args.repo/'research/continuity_v2_20261013/evidence/ech';v3=args.repo/'research/continuity_v3_20261013/evidence/ech_joint'
    books=json.loads((v2/'inputs/compiled_distance_codebooks.json').read_text());K=json.loads((v2/'inputs/cas_constitutional_kernel_v1.json').read_text());nodes=K['nodes'];roots={int(r['class_id']):int(r['root']) for r in K['roots']};classes=sorted(roots)
    masks=[m for m in range(1<<len(K['ordered_blocks'])) if m.bit_count()>=K['domain_floor']];names=[f'{m:03x}' for m in masks]
    pairs=list(combinations(classes,2));pair_index={p:i for i,p in enumerate(pairs)}
    require(len(classes)==65 and len(masks)==4017 and len(pairs)==2080,'Wrong original domain')
    @lru_cache(None)
    def structural_hash(i):
        n=nodes[i]
        if 'label' in n:return sha(('L\0'+n['label']).encode())
        require(0<=n['if_excluded']<i and 0<=n['if_included']<i,'Invalid DAG order')
        return sha(b'Q\0'+str(n['query_index']).encode()+b'\0'+bytes.fromhex(structural_hash(n['if_excluded']))+bytes.fromhex(structural_hash(n['if_included'])))
    for r in K['roots']:require(structural_hash(r['root'])==r['structural_sha256'],'Root structural hash mismatch')
    def evaluation(root,mask):
        while 'label' not in nodes[root]:
            n=nodes[root];root=n['if_included'] if mask&(1<<n['query_index']) else n['if_excluded']
        return nodes[root]['label']
    coordinates={s:[] for s in ['EXACT','MODE','ACTIONABLE']};coverage={};relevance={s:0 for s in coordinates}
    for mask,name in zip(masks,names):
        exact={c:evaluation(roots[c],mask) for c in classes};require(all(x!='OUTSIDE_DECLARED_DOMAIN' for x in exact.values()),'Outside-domain label')
        mode={c:x.split(':',1)[0] for c,x in exact.items()};action={c:x in ('APPLY','TOP_2') for c,x in mode.items()}
        for sensor,values in [('EXACT',exact),('MODE',mode),('ACTIONABLE',action)]:
            bits=sum(1<<i for i,(a,b) in enumerate(pairs) if values[a]!=values[b]);q=sensor+':'+name
            coverage[q]=bits;coordinates[sensor].append(q);relevance[sensor]|=bits
    def initial(contract):
        b=books[contract];return set(b['sensor']+':'+m for m in b['probes'])
    def distances(E):
        result=[0]*len(pairs)
        for q in E:
            require(q in coverage,'Unknown typed coordinate')
            for i in indices(coverage[q]):result[i]+=1
        return result
    def feasible(E,b):
        ds=distances(E);return min(ds[i] for i in indices(relevance[b['target']]))>=b['distance']
    dual_inequalities=0;pair_feasibility_checks=0;greedy_step_checks=0;greedy_candidate_checks=0
    def check_dual(ds,E,b1,b2=None):
        nonlocal dual_inequalities
        inherited=distances(E);terms=[];keys=set();lower=Fraction(0)
        for x in ds:
            stage=x.get('stage',1);b=b1 if stage==1 else b2;require(b is not None and stage in (1,2),'Invalid dual stage')
            p=pair_index[tuple(x['classes'])];w=Fraction(x['weight']);require(w>=0,'Negative rational weight')
            require((stage,p) not in keys,'Duplicate dual constraint');keys.add((stage,p))
            require(relevance[b['target']]&(1<<p),'Irrelevant dual pair')
            require(x['residual_distance']==b['distance']-inherited[p]>0,'Invalid residual dual demand')
            terms.append((stage,p,w));lower+=w*x['residual_distance']
        den=math.lcm(*(w.denominator for _,_,w in terms)) if terms else 1
        for stage,b in [(1,b1)]+([(2,b2)] if b2 else []):
            weights=[(p,w.numerator*(den//w.denominator)) for st,p,w in terms if stage==1 or st==2]
            for q in coordinates[b['sensor']]:
                if q in E:continue
                require(sum(n for p,n in weights if coverage[q]&(1<<p))<=den,'Exact dual coordinate constraint violated')
                dual_inequalities+=1
        return lower
    frozen=json.loads((v3/'PROTOCOL_FIXED_TWO_STAGE.json').read_text());certs=json.loads((v3/'JOINT_ROUTE_CERTIFICATES.json').read_text());details=json.loads((v2/'results/FINITE_ATLAS_REPLAY_DETAIL.json').read_text())
    old={x['problem_id']:x for x in json.loads((v2/'results/EXACT_BRIDGE_CERTIFICATES.json').read_text())}
    results=json.loads((args.out/'GREEDY_ROUTE_WITNESSES.json').read_text());summary=json.loads((args.out/'GREEDY_COMPARISON_RESULT.json').read_text())
    require(len(results)==len(certs)==len(frozen['routes'])==46,'Incomplete route coverage')
    require(summary['witnesses_sha256']==sha((args.out/'GREEDY_ROUTE_WITNESSES.json').read_bytes()),'Result witness digest mismatch')
    require(summary['protocol_sha256']==sha((args.out/'PROTOCOL_GREEDY_V1.json').read_bytes()),'Protocol digest mismatch')
    require(summary['producer_sha256']==P['producer_sha256'],'Summary producer mismatch')
    first_checked={};rows=[];checked_stages={}
    for route,cert,record in zip(frozen['routes'],certs,results):
        require(record['route']==cert['route']==route,'Frozen route changed')
        require(cert['certificate_sha256']==sha(canonical({k:v for k,v in cert.items() if k!='certificate_sha256'})),'Joint certificate digest invalid')
        E=initial(route['source']);b1=books[route['intermediate']];b2=books[route['destination']]
        require(cert['inherited_coordinates']==sorted(E),'Joint initial state mismatch')
        W1,W2=cert['first_witness'],cert['second_witness']
        require(len(E)+len(W1)+len(W2)==len(E|set(W1)|set(W2)),'Joint witness repeated coordinate')
        for W,b in [(W1,b1),(W2,b2)]:require(all(q in coverage and q.startswith(b['sensor']+':') for q in W),'Joint witness wrong sensor')
        require(feasible(E|set(W1),b1) and feasible(E|set(W1)|set(W2),b2),'Joint witness infeasible')
        lower=check_dual(cert['rational_dual'],E,b1,b2);opt=math.ceil(lower)
        require(str(lower)==cert['exact_dual_lower_bound'] and opt==cert['certified_integer_lower_bound']==cert['joint_cost']==len(W1)+len(W2),'Exact optimum does not close')
        pair_feasibility_checks+=relevance[b1['target']].bit_count()+relevance[b2['target']].bit_count()
        sq=details['squares'][int(route['square_id'][1:])-1];hist=sq['path'+route['route_id'][-1]]
        require(route['source']==sq['source'] and route['intermediate']==sq['intermediate_'+route['route_id'][-1]] and route['destination']==sq['destination'],'Route not original')
        require(route['archived_local_cost']==sum(x['cost'] for x in hist),'Archived cost mismatch')
        H=E.copy()
        for step,b in zip(hist,[b1,b2]):
            W=step['witness'];require(len(W)==len(set(W))==step['cost'] and not H.intersection(W),'Archived acquisition invalid')
            require(all(q in coverage and q.startswith(b['sensor']+':') for q in W),'Archived sensor mismatch');H.update(W);require(feasible(H,b),'Archived infeasible')
        first=old[hist[0]['problem_id']];require(first['destination']==route['intermediate'] and first['inherited_coordinates']==sorted(E),'Original local bound changed input')
        if first['problem_id'] not in first_checked:
            fl=check_dual(first['rational_dual'],E,b1);minimum=math.ceil(fl)
            require(str(fl)==first['exact_dual_lower_bound'] and minimum==first['certified_minimum_queries']==len(first['witness']),'Local certificate does not close')
            FW=first['witness'];require(not E.intersection(FW) and len(FW)==len(set(FW)) and all(q in coverage and q.startswith(b1['sensor']+':') for q in FW),'Local witness invalid');require(feasible(E|set(FW),b1),'Local witness infeasible')
            first_checked[first['problem_id']]=minimum
        minimum=first_checked[first['problem_id']];require(route['archived_first_cost']==minimum,'Historical first cost not certified minimum')
        require(len(record['stages'])==2,'Wrong stage count')
        for stage,dest in zip(record['stages'],[route['intermediate'],route['destination']]):
            b=books[dest];require(stage['destination']==dest and stage['sensor']==b['sensor'] and stage['target']==b['target'] and stage['required_distance']==b['distance'],'Wrong stage contract')
            require(stage['inherited_coordinates']==sorted(E),'Greedy inherited state altered')
            key=(tuple(sorted(E)),dest)
            if key not in checked_stages:
                ds=distances(E);current=set(E);require(len(stage['witness'])==len(stage['trace'])==stage['cost'],'Greedy witness/trace/cost mismatch')
                for q,tr in zip(stage['witness'],stage['trace']):
                    deficient=sum(1<<i for i in indices(relevance[b['target']]) if ds[i]<b['distance']);require(deficient,'Greedy acquired after contract satisfied')
                    best_q=None;best_gain=-1
                    for candidate in coordinates[b['sensor']]:
                        if candidate in current:continue
                        gain=(coverage[candidate]&deficient).bit_count();greedy_candidate_checks+=1
                        if gain>best_gain:best_gain=gain;best_q=candidate
                    require(best_gain>0 and q==best_q,'Not exact maximum-gain/ascending-mask choice')
                    require(tr=={'coordinate':q,'gain':best_gain,'unsatisfied_pairs_before':deficient.bit_count(),'total_deficit_before':sum(b['distance']-ds[i] for i in indices(deficient))},'Step trace mismatch')
                    current.add(q)
                    for i in indices(coverage[q]):ds[i]+=1
                    greedy_step_checks+=1
                md=min(ds[i] for i in indices(relevance[b['target']]));require(md>=b['distance'] and md==stage['minimum_distance'],'Greedy final contract unsatisfied')
                checked_stages[key]={k:v for k,v in stage.items() if k!='elapsed_seconds'}
            else:require(checked_stages[key]=={k:v for k,v in stage.items() if k!='elapsed_seconds'},'Same policy input produced a different output')
            E.update(stage['witness']);pair_feasibility_checks+=relevance[b['target']].bit_count()
        firstcost=record['stages'][0]['cost'];secondcost=record['stages'][1]['cost'];cost=firstcost+secondcost
        require(record['joint_certificate_sha256']==cert['certificate_sha256'],'Wrong certificate reference')
        vals={'greedy_cost':cost,'joint_optimum':opt,'excess_over_joint':cost-opt,'historical_cost':route['archived_local_cost'],'greedy_minus_historical':cost-route['archived_local_cost'],'first_excess_over_certified_local_minimum':firstcost-minimum}
        require(all(record[k]==v for k,v in vals.items()) and cost>=opt and firstcost>=minimum,'Invalid reported comparison')
        rows.append(dict(route_id=route['route_id'],source=route['source'],intermediate=route['intermediate'],destination=route['destination'],first_sensor=b1['sensor'],second_sensor=b2['sensor'],greedy_first_cost=firstcost,greedy_second_cost=secondcost,**vals))
    expected={'all_routes':46,'equal_joint_optimum':sum(x['excess_over_joint']==0 for x in rows),'strictly_above_joint':sum(x['excess_over_joint']>0 for x in rows),'max_excess_over_joint':max(x['excess_over_joint'] for x in rows),'sum_independent_greedy_cost':sum(x['greedy_cost'] for x in rows),'sum_independent_joint_cost':sum(x['joint_optimum'] for x in rows),'sum_independent_historical_cost':sum(x['historical_cost'] for x in rows),'better_than_historical':sum(x['greedy_minus_historical']<0 for x in rows),'equal_historical':sum(x['greedy_minus_historical']==0 for x in rows),'worse_than_historical':sum(x['greedy_minus_historical']>0 for x in rows),'first_stage_above_exact_local_minimum':sum(x['first_excess_over_certified_local_minimum']>0 for x in rows),'distinct_stage_inputs':len(checked_stages)}
    require(all(summary[k]==v for k,v in expected.items()),'Summary mismatch')
    csvrows=list(csv.DictReader((args.out/'GREEDY_ROUTE_COMPARISON.csv').open()));require(len(csvrows)==46,'CSV incomplete')
    for a,b in zip(csvrows,rows):require(a=={k:str(v) for k,v in b.items()},'CSV differs from verified result')
    groups=defaultdict(list)
    for row in rows:groups[row['first_sensor']+' -> '+row['second_sensor']].append(row)
    expected_groups=[]
    for label,rs in sorted(groups.items()):
        expected_groups.append({'sensor_route':label,'routes':[x['route_id'] for x in rs],'n_routes':len(rs),'equal_joint_optimum':sum(x['excess_over_joint']==0 for x in rs),'strictly_above_joint':sum(x['excess_over_joint']>0 for x in rs),'max_excess':max(x['excess_over_joint'] for x in rs),'sum_independent_greedy_cost':sum(x['greedy_cost'] for x in rs),'sum_independent_joint_cost':sum(x['joint_optimum'] for x in rs),'better_than_historical':sum(x['greedy_minus_historical']<0 for x in rs),'equal_historical':sum(x['greedy_minus_historical']==0 for x in rs),'worse_than_historical':sum(x['greedy_minus_historical']>0 for x in rs)})
    require(json.loads((args.out/'GREEDY_JURISDICTIONS.json').read_text())==expected_groups,'Jurisdiction result mismatch')
    receipt={'schema':'ECH_GREEDY_INDEPENDENT_CHECK_V1','status':'PASS','routes_checked':46,'stages_reconstructed':len(checked_stages),'unique_greedy_steps_checked':greedy_step_checks,'exact_greedy_candidate_gain_checks':greedy_candidate_checks,'exact_rational_coordinate_inequalities_checked':dual_inequalities,'stage_pair_feasibility_checks':pair_feasibility_checks,'original_root_structural_hashes_checked':len(K['roots']),'unique_first_stage_optima_recertified':len(first_checked),'joint_optima_recertified':46,'producer_imported':False,'solver_imported':False,'third_party_libraries_imported':False,'grouped_matrices_trusted':False,'all_original_coordinates_checked':True,'protocol_sha256':sha((args.out/'PROTOCOL_GREEDY_V1.json').read_bytes()),'checker_sha256':sha(Path(__file__).read_bytes()),'result_sha256':sha((args.out/'GREEDY_COMPARISON_RESULT.json').read_bytes()),'witnesses_sha256':sha((args.out/'GREEDY_ROUTE_WITNESSES.json').read_bytes()),'elapsed_seconds':time.monotonic()-start,'permission_granted':False}
    (args.out/'GREEDY_INDEPENDENT_CHECK.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
