#!/usr/bin/env python3
"""Joint anticipatory optimization of every frozen, fixed two-stage ECH route.

All inputs are finite archived mathematical objects, never observational samples.
Identical columns are aggregated with their genuine integer capacities. Stage
coupling is preserved. Floating solvers propose witnesses/dual weights only;
integer feasibility and rational dual checks determine certified conclusions.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, math, platform, time
from collections import defaultdict
from fractions import Fraction
from pathlib import Path
import numpy as np
import scipy
from scipy.optimize import linprog, milp, Bounds, LinearConstraint
from scipy.sparse import csc_matrix

def sha(raw): return hashlib.sha256(raw).hexdigest()
def canonical(x): return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def require(c,m):
    if not c: raise ValueError(m)

class Kernel:
    def __init__(self,k,books):
        self.k=k; self.books=books; self.nodes=k['nodes']
        self.roots={int(r['class_id']):int(r['root']) for r in k['roots']}
        self.classes=sorted(self.roots)
        self.masks=[m for m in range(1<<len(k['ordered_blocks'])) if m.bit_count()>=k['domain_floor']]
        self.names=[f'{m:03x}' for m in self.masks]; self.idx={m:i for i,m in enumerate(self.names)}
        exact=np.array([[self.evaluate(self.roots[c],m) for m in self.masks] for c in self.classes])
        modes=np.array([[x.split(':',1)[0] for x in row] for row in exact])
        action=np.isin(modes,['APPLY','TOP_2'])
        self.i,self.j=np.triu_indices(len(self.classes),1)
        self.diff={s:m[self.i]!=m[self.j] for s,m in [('EXACT',exact),('MODE',modes),('ACTIONABLE',action)]}
        self.relevant={s:v.any(axis=1) for s,v in self.diff.items()}
        require(len(self.masks)==4017,'unexpected mask family')
    def evaluate(self,r,m):
        for _ in range(len(self.nodes)):
            n=self.nodes[r]
            if 'label' in n:return n['label']
            r=n['if_included'] if m&(1<<n['query_index']) else n['if_excluded']
        raise ValueError('cyclic kernel')
    def ledger(self,c):
        b=self.books[c]
        return {b['sensor']+':'+m for m in b['probes']}
    def distances(self,E):
        d=np.zeros(len(self.i),dtype=np.int64)
        for q in E:
            s,m=q.split(':'); d+=self.diff[s][:,self.idx[m]]
        return d
    def feasible(self,E,c):
        b=self.books[c]; d=self.distances(E)[self.relevant[b['target']]]
        return int(d.min())
    def group(self,s,E,a1,a2):
        groups={}
        for j,m in enumerate(self.names):
            q=s+':'+m
            if q in E:continue
            bits=np.concatenate([self.diff[s][a1,j],self.diff[s][a2,j]])
            key=np.packbits(bits).tobytes()
            if key not in groups: groups[key]={'coordinates':[],'column':bits.astype(np.int8)}
            groups[key]['coordinates'].append(q)
        return list(groups.values())

def solve(F,route,square,time_limit):
    t0=time.monotonic(); E=F.ledger(route['source'])
    b1=F.books[route['intermediate']]; b2=F.books[route['destination']]
    s1,s2=b1['sensor'],b2['sensor']; dist=F.distances(E)
    active1=np.flatnonzero(F.relevant[b1['target']]&(dist<b1['distance']))
    active2=np.flatnonzero(F.relevant[b2['target']]&(dist<b2['distance']))
    needs=np.concatenate([b1['distance']-dist[active1],b2['distance']-dist[active2]])
    rowmeta=[{'stage':stage,'classes':[F.classes[int(F.i[p])],F.classes[int(F.j[p])]],'residual_distance':int(d)} for stage,inds,dd in [(1,active1,b1['distance']),(2,active2,b2['distance'])] for p,d in [(p,dd-dist[p]) for p in inds]]
    g1=F.group(s1,E,active1,active2)
    g2=g1 if s1==s2 else F.group(s2,E,np.array([],dtype=int),active2)
    n1,n2=len(g1),len(g2)
    if len(needs):
        A1=np.stack([g['column'] for g in g1],axis=1)
        C2=np.stack([g['column'][len(active1):] if s1==s2 else g['column'] for g in g2],axis=1)
        A2=np.vstack([np.zeros((len(active1),n2),dtype=np.int8),C2])
        A=np.hstack([A1,A2])
    else:A=np.zeros((0,n1+n2),dtype=np.int8)
    # Actual capacities, including coupling where both stages use same sensor.
    caps=np.array([len(g['coordinates']) for g in g1+g2],dtype=int)
    if s1==s2:
        U=np.hstack([np.eye(n1,dtype=np.int8),np.eye(n1,dtype=np.int8)])
        ub=caps[:n1]
    else:
        U=np.eye(n1+n2,dtype=np.int8); ub=caps
    # Unbounded relaxation is a valid lower bound. Its dual needs no cap terms.
    if len(needs):
        lp=linprog(np.ones(n1+n2),A_ub=-A,b_ub=-needs,bounds=(0,None),method='highs')
        require(lp.success,lp.message)
        weights=[max(Fraction(0),Fraction(float(-v)).limit_denominator(1000000)) for v in lp.ineqlin.marginals]
        den=math.lcm(*(w.denominator for w in weights)); nums=np.array([w.numerator*(den//w.denominator) for w in weights],dtype=object)
        loads=nums@A.astype(object); maxload=max([den]+[int(x) for x in loads])
        if maxload>den:weights=[w*Fraction(den,maxload) for w in weights]
        lower=sum((w*int(r) for w,r in zip(weights,needs)),Fraction(0))
        # A feasible rounded LP solution is useful, but accepted only by integers.
        rounded=np.rint(lp.x).astype(int)
        integral=np.all(np.abs(lp.x-rounded)<1e-7) and np.all(rounded>=0) and np.all(A@rounded>=needs) and np.all(U@rounded<=ub)
        if integral:
            counts=rounded; milp_status='LP_INTEGER_WITNESS'; diagnostic_bound=float(lp.fun)
        else:
            B=csc_matrix(np.vstack([A,U]),dtype=float)
            sol=milp(np.ones(n1+n2),integrality=np.ones(n1+n2),bounds=Bounds(np.zeros(n1+n2),caps),constraints=LinearConstraint(B,np.concatenate([needs,np.full(len(ub),-np.inf)]),np.concatenate([np.full(len(needs),np.inf),ub])),options={'time_limit':time_limit,'mip_rel_gap':0.0})
            require(sol.x is not None,'MILP found no integer witness: '+str(sol.message))
            counts=np.rint(sol.x).astype(int); milp_status=str(sol.message); diagnostic_bound=float(sol.mip_dual_bound)
    else:
        weights=[];lower=Fraction(0);counts=np.zeros(n1+n2,dtype=int);milp_status='ZERO_FEASIBLE';diagnostic_bound=0.0
    require(np.all(counts>=0) and np.all(A@counts>=needs) and np.all(U@counts<=ub),'integer grouped witness infeasible')
    W1=[];W2=[]
    for g,n in zip(g1,counts[:n1]):W1+=g['coordinates'][:int(n)]
    for j,(g,n) in enumerate(zip(g2,counts[n1:])):
        offset=int(counts[j]) if s1==s2 else 0
        W2+=g['coordinates'][offset:offset+int(n)]
    require(not E.intersection(W1+W2) and len(set(W1+W2))==len(W1+W2),'duplicate typed coordinate')
    require(F.feasible(E|set(W1),route['intermediate'])>=b1['distance'],'stage1 infeasible')
    require(F.feasible(E|set(W1+W2),route['destination'])>=b2['distance'],'stage2 infeasible')
    cost=len(W1)+len(W2); integer_lower=math.ceil(lower)
    # Recheck the unbounded rational certificate exactly on aggregated columns;
    # checker later evaluates every original coordinate independently.
    den=math.lcm(*(w.denominator for w in weights)) if weights else 1
    nums=np.array([w.numerator*(den//w.denominator) for w in weights],dtype=object)
    require(all(int(x)<=den for x in nums@A.astype(object)),'invalid rational dual')
    archived=square['path'+route['route_id'][-1]]
    archived_W1=set(archived[0]['witness']); archived_W2=set(archived[1]['witness'])
    require(F.feasible(E|archived_W1,route['intermediate'])>=b1['distance'],'archived stage1 infeasible')
    require(F.feasible(E|archived_W1|archived_W2,route['destination'])>=b2['distance'],'archived stage2 infeasible')
    require(cost<=route['archived_local_cost'],'optimized witness worse than archive')
    cert={'route':route,'inherited_coordinates':sorted(E),'first_witness':sorted(W1),'second_witness':sorted(W2),'first_cost':len(W1),'second_cost':len(W2),'joint_cost':cost,'exact_dual_lower_bound':str(lower),'certified_integer_lower_bound':integer_lower,'certified_gap':cost-integer_lower,'status':'EXACT_OPTIMUM' if integer_lower==cost else 'INTEGER_WITNESS_WITH_OPEN_GAP','rational_dual':[dict(meta,weight=str(w)) for meta,w in zip(rowmeta,weights) if w],'grouping':{'first_sensor':s1,'second_sensor':s2,'same_sensor_coupled':s1==s2,'first_available_coordinates':sum(len(g['coordinates']) for g in g1),'second_available_coordinates_before_stage1':sum(len(g['coordinates']) for g in g2),'first_groups':n1,'second_groups':n2,'first_capacity_max':max(len(g['coordinates']) for g in g1),'second_capacity_max':max(len(g['coordinates']) for g in g2),'first_capacity_sum':sum(len(g['coordinates']) for g in g1),'second_capacity_sum':sum(len(g['coordinates']) for g in g2),'capacity_digest':sha(canonical({'first':[g['coordinates'] for g in g1],'second':[g['coordinates'] for g in g2]}))},'minimum_stage1_distance':F.feasible(E|set(W1),route['intermediate']),'minimum_stage2_distance':F.feasible(E|set(W1+W2),route['destination']),'saving_against_archived_local_policy':route['archived_local_cost']-cost,'first_stage_excess_over_archived_local_minimum':len(W1)-route['archived_first_cost'],'archived_local_witness_reverified':True,'diagnostic_milp_status':milp_status,'diagnostic_solver_lower_bound':diagnostic_bound,'elapsed_seconds':time.monotonic()-t0,'permission_granted':False}
    cert['certificate_sha256']=sha(canonical(cert))
    print(json.dumps({'route':route['route_id'],'groups':[n1,n2],'cost':cost,'lower':str(lower),'gap':cost-integer_lower,'archived':route['archived_local_cost'],'seconds':round(cert['elapsed_seconds'],2)}),flush=True)
    return cert

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--time-limit',type=float,default=120);args=ap.parse_args()
    protocol_path=args.output/'PROTOCOL_FIXED_TWO_STAGE.json'; protocol=json.loads(protocol_path.read_text())
    for name,h in protocol['input_sha256'].items():require(sha((args.source/name).read_bytes())==h,'source hash mismatch: '+name)
    F=Kernel(json.loads((args.source/'inputs/cas_constitutional_kernel_v1.json').read_text()),json.loads((args.source/'inputs/compiled_distance_codebooks.json').read_text()))
    detail=json.loads((args.source/'results/FINITE_ATLAS_REPLAY_DETAIL.json').read_text())
    results=[]
    for route in protocol['routes']:
        result=solve(F,route,detail['squares'][int(route['square_id'][1:])-1],args.time_limit);results.append(result)
        (args.output/'JOINT_ROUTE_CERTIFICATES.partial.json').write_text(json.dumps(results,indent=2,sort_keys=True)+'\n')
    raw=(json.dumps(results,indent=2,sort_keys=True)+'\n').encode();(args.output/'JOINT_ROUTE_CERTIFICATES.json').write_bytes(raw)
    square_results=[]
    for r1,r2 in zip(results[::2],results[1::2]):
        square_results.append({'square_id':r1['route']['square_id'],'source':r1['route']['source'],'destination':r1['route']['destination'],'path1_joint_cost':r1['joint_cost'],'path2_joint_cost':r2['joint_cost'],'joint_cost_commutes':r1['joint_cost']==r2['joint_cost'],'archived_path1_cost':r1['route']['archived_local_cost'],'archived_path2_cost':r2['route']['archived_local_cost'],'archived_cost_commutes':r1['route']['archived_local_cost']==r2['route']['archived_local_cost'],'both_exact_certified':r1['status']==r2['status']=='EXACT_OPTIMUM'})
    (args.output/'JOINT_SQUARE_COMPARISON.json').write_text(json.dumps(square_results,indent=2,sort_keys=True)+'\n')
    with (args.output/'JOINT_ROUTE_COMPARISON.csv').open('w') as f:
        fields=['route_id','source','intermediate','destination','archived_first_cost','archived_second_cost','archived_local_cost','first_cost','second_cost','joint_cost','certified_integer_lower_bound','certified_gap','saving_against_archived_local_policy','first_stage_excess_over_archived_local_minimum','status'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
        for r in results:w.writerow({key:r.get(key,r['route'].get(key)) for key in fields})
    summary={'schema':'ECH_JOINT_FIXED_TWO_STAGE_RESULT_V1','status':'ALL_46_FIXED_ROUTES_EXACTLY_CERTIFIED' if all(r['certified_gap']==0 for r in results) else 'PARTIAL_CERTIFICATION_WITH_OPEN_GAPS','protocol_sha256':sha(protocol_path.read_bytes()),'solver_script_sha256':sha(Path(__file__).read_bytes()),'environment':{'python':platform.python_version(),'numpy':np.__version__,'scipy':scipy.__version__},'routes':len(results),'certified_optimal_routes':sum(r['certified_gap']==0 for r in results),'improved_routes':sum(r['saving_against_archived_local_policy']>0 for r in results),'unchanged_routes':sum(r['saving_against_archived_local_policy']==0 for r in results),'archived_total_cost_across_routes':sum(r['route']['archived_local_cost'] for r in results),'joint_total_cost_across_routes':sum(r['joint_cost'] for r in results),'route_sum_interpretation':'Sum of independently evaluated route costs, not one executable shared acquisition experiment.','maximum_route_saving':max(r['saving_against_archived_local_policy'] for r in results),'routes_whose_returned_witness_acquires_extra_at_first_stage':sum(r['first_stage_excess_over_archived_local_minimum']>0 for r in results),'archived_noncommuting_cost_squares':sum(not r['archived_cost_commutes'] for r in square_results),'joint_noncommuting_cost_squares':sum(not r['joint_cost_commutes'] for r in square_results),'joint_commuting_cost_squares':sum(r['joint_cost_commutes'] for r in square_results),'certificate_sha256':sha(raw),'scope_boundaries':protocol['scope_boundaries'],'permission_granted':False}
    summary['result_sha256']=sha(canonical(summary));(args.output/'ECH_JOINT_ROUTE_RESULT.json').write_text(json.dumps(summary,indent=2,sort_keys=True)+'\n');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
