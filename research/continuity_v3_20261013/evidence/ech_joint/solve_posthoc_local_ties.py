#!/usr/bin/env python3
"""Explicitly post-hoc restricted planning audit of all 11 improved routes."""
import argparse, json, math, time
from fractions import Fraction
from pathlib import Path
import numpy as np
from scipy.optimize import linprog,milp,Bounds,LinearConstraint
from scipy.sparse import csc_matrix
from solve_joint_routes import Kernel,sha,canonical,require

def solve(F,r,limit):
    E=F.ledger(r['source']);b1=F.books[r['intermediate']];b2=F.books[r['destination']];s1,s2=b1['sensor'],b2['sensor'];dist=F.distances(E);m=r['first_stage_budget']
    a1=np.flatnonzero(F.relevant[b1['target']]&(dist<b1['distance']));a2=np.flatnonzero(F.relevant[b2['target']]&(dist<b2['distance']))
    needs=np.concatenate([b1['distance']-dist[a1],b2['distance']-dist[a2]])
    metadata=[{'stage':st,'classes':[F.classes[int(F.i[p])],F.classes[int(F.j[p])]],'residual_distance':int(d-dist[p])} for st,active,d in [(1,a1,b1['distance']),(2,a2,b2['distance'])] for p in active]
    g1=F.group(s1,E,a1,a2);g2=g1 if s1==s2 else F.group(s2,E,np.array([],dtype=int),a2);n1,n2=len(g1),len(g2)
    A1=np.stack([g['column'] for g in g1],axis=1);A2=np.vstack([np.zeros((len(a1),n2),dtype=np.int8),np.stack([g['column'][len(a1):] if s1==s2 else g['column'] for g in g2],axis=1)]);A=np.hstack([A1,A2])
    budget=np.concatenate([np.ones(n1,dtype=np.int8),np.zeros(n2,dtype=np.int8)])
    cap=np.array([len(g['coordinates']) for g in g1+g2]);U=np.hstack([np.eye(n1,dtype=np.int8),np.eye(n1,dtype=np.int8)]) if s1==s2 else np.eye(n1+n2,dtype=np.int8);ub=cap[:n1] if s1==s2 else cap
    lp=linprog(np.ones(n1+n2),A_ub=np.vstack([-A,budget]),b_ub=np.concatenate([-needs,[m]]),bounds=(0,None),method='highs');require(lp.success,lp.message)
    ws=[max(Fraction(0),Fraction(float(-x)).limit_denominator(1000000)) for x in lp.ineqlin.marginals];ys,lam=ws[:-1],ws[-1]
    den=math.lcm(*(w.denominator for w in ws));yn=np.array([w.numerator*(den//w.denominator) for w in ys],dtype=object);ln=lam.numerator*(den//lam.denominator)
    loads=yn@A.astype(object)-ln*budget.astype(object);maxload=max([den]+[int(x) for x in loads])
    if maxload>den:ys=[w*Fraction(den,maxload) for w in ys];lam*=Fraction(den,maxload)
    lower=sum((w*int(v) for w,v in zip(ys,needs)),Fraction(0))-m*lam
    rounded=np.rint(lp.x).astype(int);ok=np.all(np.abs(rounded-lp.x)<1e-7) and np.all(rounded>=0) and np.all(A@rounded>=needs) and np.all(U@rounded<=ub) and budget@rounded<=m
    if ok:counts=rounded;status='LP_INTEGER_WITNESS'
    else:
        B=csc_matrix(np.vstack([A,U,budget]),dtype=float);lo=np.concatenate([needs,np.full(len(ub)+1,-np.inf)]);hi=np.concatenate([np.full(len(needs),np.inf),ub,[m]])
        sol=milp(np.ones(n1+n2),integrality=np.ones(n1+n2),bounds=Bounds(np.zeros(n1+n2),cap),constraints=LinearConstraint(B,lo,hi),options={'time_limit':limit,'mip_rel_gap':0.0});require(sol.x is not None,sol.message);counts=np.rint(sol.x).astype(int);status=str(sol.message)
    require(np.all(counts>=0) and np.all(A@counts>=needs) and np.all(U@counts<=ub) and budget@counts<=m,'infeasible grouped witness')
    W1=[];W2=[]
    for g,n in zip(g1,counts[:n1]):W1+=g['coordinates'][:int(n)]
    for j,(g,n) in enumerate(zip(g2,counts[n1:])):
        offset=int(counts[j]) if s1==s2 else 0;W2+=g['coordinates'][offset:offset+int(n)]
    require(len(W1)==m,'first-stage minimum not met');require(len(E)+len(W1)+len(W2)==len(E|set(W1+W2)),'repeated coordinate');require(F.feasible(E|set(W1),r['intermediate'])>=b1['distance'] and F.feasible(E|set(W1+W2),r['destination'])>=b2['distance'],'infeasible expanded witness')
    cost=len(W1+W2);ilower=math.ceil(lower);J=r['unrestricted_joint_optimum'];Aold=r['archived_local_cost'];require(J<=ilower<=cost<=Aold,'bounds not nested')
    cert={'route':r,'inherited_coordinates':sorted(E),'first_witness':sorted(W1),'second_witness':sorted(W2),'first_cost':len(W1),'second_cost':len(W2),'restricted_joint_cost':cost,'exact_dual_lower_bound':str(lower),'certified_integer_lower_bound':ilower,'certified_gap':cost-ilower,'status':'EXACT_OPTIMUM' if cost==ilower else 'OPEN_GAP','rational_dual':[dict(meta,weight=str(w)) for meta,w in zip(metadata,ys) if w],'first_budget_dual_weight':str(lam),'classification':('LOCAL_MINIMUM_TIE_SUFFICES' if J==cost else 'STRICT_ANTICIPATION_REQUIRED_FOR_FULL_JOINT_OPTIMUM') if cost==ilower else 'UNRESOLVED','diagnostic_solver_status':status,'permission_granted':False};cert['certificate_sha256']=sha(canonical(cert));print(json.dumps({'route':r['route_id'],'J':J,'R':cost,'A':Aold,'lower':str(lower),'gap':cost-ilower}),flush=True);return cert

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--time-limit',type=float,default=120);args=ap.parse_args();p=args.output
    protocol=json.loads((p/'PROTOCOL_POSTHOC_LOCAL_TIE_AUDIT.json').read_text());base=json.loads((p/'PROTOCOL_FIXED_TWO_STAGE.json').read_text())
    require(sha((p/'PROTOCOL_FIXED_TWO_STAGE.json').read_bytes())==protocol['parent_protocol_sha256'],'parent protocol changed');require(sha((p/'ECH_JOINT_ROUTE_RESULT.json').read_bytes())==protocol['parent_result_sha256'],'parent result changed')
    for name,h in base['input_sha256'].items():require(sha((args.source/name).read_bytes())==h,'source changed')
    F=Kernel(json.loads((args.source/'inputs/cas_constitutional_kernel_v1.json').read_text()),json.loads((args.source/'inputs/compiled_distance_codebooks.json').read_text()))
    cs=[solve(F,r,args.time_limit) for r in protocol['routes']];raw=(json.dumps(cs,indent=2,sort_keys=True)+'\n').encode();(p/'POSTHOC_LOCAL_TIE_CERTIFICATES.json').write_bytes(raw)
    result={'schema':'ECH_POSTHOC_LOCAL_TIE_RESULT_V1','phase':'POST_HOC_DIRECTED_INTERPRETATION_AUDIT','routes':len(cs),'exact_optima_certified':sum(c['certified_gap']==0 for c in cs),'local_minimum_tie_suffices':sum(c['classification']=='LOCAL_MINIMUM_TIE_SUFFICES' for c in cs),'strict_anticipation_required_for_full_joint_optimum':sum(c['classification']=='STRICT_ANTICIPATION_REQUIRED_FOR_FULL_JOINT_OPTIMUM' for c in cs),'protocol_sha256':sha((p/'PROTOCOL_POSTHOC_LOCAL_TIE_AUDIT.json').read_bytes()),'certificates_sha256':sha(raw),'script_sha256':sha(Path(__file__).read_bytes()),'permission_granted':False};result['result_sha256']=sha(canonical(result));(p/'POSTHOC_LOCAL_TIE_RESULT.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
