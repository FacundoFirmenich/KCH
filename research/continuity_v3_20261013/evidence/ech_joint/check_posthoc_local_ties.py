#!/usr/bin/env python3
"""Standard-library proof checker for the posterior local-tie discrimination."""
import argparse,hashlib,json,math,time
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from pathlib import Path
def sha(b):return hashlib.sha256(b).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def require(c,m):
    if not c:raise ValueError(m)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--results',type=Path,required=True);args=ap.parse_args();p=args.results;t=time.monotonic()
    proto=json.loads((p/'PROTOCOL_POSTHOC_LOCAL_TIE_AUDIT.json').read_text());base=json.loads((p/'PROTOCOL_FIXED_TWO_STAGE.json').read_text());result=json.loads((p/'POSTHOC_LOCAL_TIE_RESULT.json').read_text());saved=result.pop('result_sha256');require(sha(canonical(result))==saved,'result digest')
    require(sha((p/'PROTOCOL_POSTHOC_LOCAL_TIE_AUDIT.json').read_bytes())==result['protocol_sha256'],'protocol digest');require(sha((p/'PROTOCOL_FIXED_TWO_STAGE.json').read_bytes())==proto['parent_protocol_sha256'],'parent protocol digest');require(sha((p/'ECH_JOINT_ROUTE_RESULT.json').read_bytes())==proto['parent_result_sha256'],'parent result digest')
    for name,h in base['input_sha256'].items():require(sha((args.source/name).read_bytes())==h,'source digest')
    original={c['problem_id']:c for c in json.loads((args.source/'results/EXACT_BRIDGE_CERTIFICATES.json').read_text())};joint=json.loads((p/'JOINT_ROUTE_CERTIFICATES.json').read_text());improved={c['route']['route_id']:c for c in joint if c['saving_against_archived_local_policy']>0};require(len(improved)==len(proto['routes'])==11,'wrong posterior scope')
    raw=(p/'POSTHOC_LOCAL_TIE_CERTIFICATES.json').read_bytes();require(sha(raw)==result['certificates_sha256'],'certificates digest');cs=json.loads(raw);require(len(cs)==11,'wrong certificate count')
    k=json.loads((args.source/'inputs/cas_constitutional_kernel_v1.json').read_text());books=json.loads((args.source/'inputs/compiled_distance_codebooks.json').read_text());nodes=k['nodes'];roots={int(r['class_id']):r['root'] for r in k['roots']};classes=sorted(roots);pairs=list(combinations(classes,2));masks=[m for m in range(1<<len(k['ordered_blocks'])) if m.bit_count()>=k['domain_floor']];idx={f'{m:03x}':i for i,m in enumerate(masks)}
    def read(root,m):
        for _ in range(len(nodes)):
            n=nodes[root]
            if 'label' in n:return n['label']
            root=n['if_included'] if m&(1<<n['query_index']) else n['if_excluded']
        raise ValueError('cycle')
    exact={c:tuple(read(roots[c],m) for m in masks) for c in classes};mode={c:tuple(s.split(':',1)[0] for s in exact[c]) for c in classes};action={c:tuple(s in ('APPLY','TOP_2') for s in mode[c]) for c in classes};mats={'EXACT':exact,'MODE':mode,'ACTIONABLE':action};rel={s:set(p for p in pairs if M[p[0]]!=M[p[1]]) for s,M in mats.items()}
    @lru_cache(None)
    def diff(sensor,p):return bytes(a!=b for a,b in zip(mats[sensor][p[0]],mats[sensor][p[1]]))
    def distance(pair,E):return sum(diff(q.split(':')[0],pair)[idx[q.split(':')[1]]] for q in E)
    def feasible(E,b):return all(distance(pair,E)>=b['distance'] for pair in rel[b['target']])
    inequalities=0;closed=0;tiebest=0;strict=0;seen=set()
    for route,c in zip(proto['routes'],cs):
        require(route==c['route'],'route scope mismatch');rid=route['route_id'];require(rid in improved and rid not in seen,'posterior route selection');seen.add(rid);basec=improved[rid];require(route['unrestricted_joint_optimum']==basec['joint_cost'],'unrestricted optimum mismatch')
        require(sha(canonical({k:v for k,v in c.items() if k!='certificate_sha256'}))==c['certificate_sha256'],'certificate hash')
        b0,b1,b2=[books[route[k]] for k in ['source','intermediate','destination']];E=c['inherited_coordinates'];W1=c['first_witness'];W2=c['second_witness'];m=route['first_stage_budget'];require(E==sorted(b0['sensor']+':'+x for x in b0['probes']),'source replacement');require(len(E+W1+W2)==len(set(E+W1+W2)),'duplicate coordinate');require(len(W1)==m,'first stage not minimum budget')
        require(all(q.split(':')[0]==b1['sensor'] and q.split(':')[1] in idx for q in W1) and all(q.split(':')[0]==b2['sensor'] and q.split(':')[1] in idx for q in W2),'sensor/mask failure');require(feasible(E+W1,b1) and feasible(E+W1+W2,b2),'restricted witness infeasible')
        # Re-prove the original first-step lower bound rather than trust m.
        oc=original[route['original_first_bridge_problem_id']];require(oc['inherited_coordinates']==E and oc['destination']==route['intermediate'] and oc['certified_minimum_queries']==m,'wrong first-stage original certificate')
        od=oc['rational_dual'];ow=[Fraction(x['weight']) for x in od];require(all(w>=0 for w in ow),'negative original dual')
        for x in od:require(tuple(x['classes']) in rel[b1['target']] and x['residual_distance']==b1['distance']-distance(tuple(x['classes']),E)>0,'wrong original dual RHS')
        den=math.lcm(*(w.denominator for w in ow)) if ow else 1;terms=[(w.numerator*(den//w.denominator),diff(b1['sensor'],tuple(x['classes']))) for w,x in zip(ow,od)]
        for mask,j in idx.items():
            if b1['sensor']+':'+mask in E:continue
            require(sum(n*bits[j] for n,bits in terms)<=den,'invalid original local dual');inequalities+=1
        require(math.ceil(sum((w*x['residual_distance'] for w,x in zip(ow,od)),Fraction(0)))==m,'original local bound not closed')
        ds=c['rational_dual'];weights=[Fraction(x['weight']) for x in ds];lam=Fraction(c['first_budget_dual_weight']);require(lam>=0 and all(w>=0 for w in weights),'negative restricted dual');keys=[(x['stage'],tuple(x['classes'])) for x in ds];require(len(keys)==len(set(keys)),'duplicate dual row')
        for x in ds:
            require(x['stage'] in (1,2),'invalid stage');b=b1 if x['stage']==1 else b2;pair=tuple(x['classes']);require(pair in rel[b['target']] and x['residual_distance']==b['distance']-distance(pair,E)>0,'restricted dual RHS')
        den=math.lcm(*(w.denominator for w in weights+[lam]));ln=lam.numerator*(den//lam.denominator)
        for stage,sensor in [(1,b1['sensor']),(2,b2['sensor'])]:
            terms=[(w.numerator*(den//w.denominator),diff(sensor,tuple(x['classes']))) for w,x in zip(weights,ds) if stage==1 or x['stage']==2]
            for mask,j in idx.items():
                if sensor+':'+mask in E:continue
                require(sum(n*bits[j] for n,bits in terms)-(ln if stage==1 else 0)<=den,'restricted exact dual inequality');inequalities+=1
        lower=sum((w*x['residual_distance'] for w,x in zip(weights,ds)),Fraction(0))-m*lam;ilower=math.ceil(lower);R=len(W1+W2);J=route['unrestricted_joint_optimum'];A=route['archived_local_cost']
        require(str(lower)==c['exact_dual_lower_bound'] and ilower==c['certified_integer_lower_bound'] and R==c['restricted_joint_cost'],'cost or lower bound mismatch');require(c['certified_gap']==R-ilower>=0,'gap mismatch');require(J<=ilower<=R<=A,'bounds nesting mismatch');closed+=R==ilower
        require(c['status']==('EXACT_OPTIMUM' if R==ilower else 'OPEN_GAP'),'false closed status')
        classification=('LOCAL_MINIMUM_TIE_SUFFICES' if J==R else 'STRICT_ANTICIPATION_REQUIRED_FOR_FULL_JOINT_OPTIMUM') if R==ilower else 'UNRESOLVED';require(classification==c['classification'],'wrong classification');tiebest+=classification=='LOCAL_MINIMUM_TIE_SUFFICES';strict+=classification=='STRICT_ANTICIPATION_REQUIRED_FOR_FULL_JOINT_OPTIMUM'
    require(seen==set(improved),'not all improved routes audited');require(closed==result['exact_optima_certified'] and tiebest==result['local_minimum_tie_suffices'] and strict==result['strict_anticipation_required_for_full_joint_optimum'],'summary mismatch')
    receipt={'schema':'ECH_POSTHOC_LOCAL_TIE_SOLVER_FREE_CHECK_V1','status':'PASS','routes':len(cs),'exact_optima_certified':closed,'original_first_step_minima_reproved':len(cs),'all_admissible_coordinate_dual_inequalities_checked':inequalities,'local_minimum_tie_suffices':tiebest,'strict_anticipation_required_for_full_joint_optimum':strict,'optimizer_imported':False,'producer_imported':False,'third_party_libraries_imported':False,'result_sha256':saved,'checker_sha256':sha(Path(__file__).read_bytes()),'elapsed_seconds':time.monotonic()-t,'permission_granted':False};(p/'SOLVER_FREE_POSTHOC_TIE_CHECK.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
