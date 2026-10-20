#!/usr/bin/env python3
"""Frozen stagewise residual-multicover greedy on the archived real ECH kernel.

The stage policy receives ONLY current evidence and its current destination.
It cannot access the subsequent contract, joint optimum or historical witness.
No synthesized observations, optimizer or randomized/tuned tie rule is used.
"""
from __future__ import annotations
import argparse, csv, hashlib, json, platform, time
from collections import defaultdict
from pathlib import Path
import numpy as np

def sha(b):return hashlib.sha256(b).hexdigest()
def require(c,m):
    if not c:raise ValueError(m)
def dump(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n')

class FiniteModel:
    def __init__(self,kernel,books):
        self.books=books;self.nodes=kernel['nodes'];self.roots={int(r['class_id']):int(r['root']) for r in kernel['roots']}
        self.classes=sorted(self.roots)
        self.masks=[m for m in range(1<<len(kernel['ordered_blocks'])) if m.bit_count()>=kernel['domain_floor']]
        self.names=[f'{m:03x}' for m in self.masks];self.index={m:i for i,m in enumerate(self.names)}
        exact=np.asarray([[self.evaluate(self.roots[c],m) for m in self.masks] for c in self.classes])
        mode=np.asarray([[x.split(':',1)[0] for x in row] for row in exact])
        action=np.isin(mode,['APPLY','TOP_2']);i,j=np.triu_indices(len(self.classes),1)
        self.diff={name:mat[i]!=mat[j] for name,mat in [('EXACT',exact),('MODE',mode),('ACTIONABLE',action)]}
        self.relevant={name:mat.any(axis=1) for name,mat in self.diff.items()}
        require(len(self.classes)==65 and len(self.names)==4017 and len(i)==2080,'Unexpected frozen kernel dimensions')
    def evaluate(self,root,mask):
        for _ in range(len(self.nodes)):
            node=self.nodes[root]
            if 'label' in node:return node['label']
            root=node['if_included'] if mask&(1<<node['query_index']) else node['if_excluded']
        raise ValueError('Cyclic kernel')
    def distances(self,evidence):
        d=np.zeros(2080,dtype=np.int64)
        for q in evidence:
            sensor,mask=q.split(':');d+=self.diff[sensor][:,self.index[mask]]
        return d
    def initial(self,contract):
        book=self.books[contract];return {book['sensor']+':'+m for m in book['probes']}
    def greedy_stage(self,inherited,destination):
        """No subsequent destination or comparator data is accepted here."""
        started=time.monotonic();book=self.books[destination];sensor=book['sensor'];D=self.diff[sensor]
        E=set(inherited);dist=self.distances(E);chosen=[];trace=[]
        while True:
            deficient=self.relevant[book['target']]&(dist<book['distance'])
            if not deficient.any():break
            gains=D[deficient].sum(axis=0,dtype=np.int64)
            for q in E:
                s,m=q.split(':')
                if s==sensor:gains[self.index[m]]=-1
            idx=int(np.argmax(gains));gain=int(gains[idx]);require(gain>0,'Greedy stuck while a contract is unmet')
            q=sensor+':'+self.names[idx]
            # np.argmax selects the first ascending numeric mask among maximizers.
            trace.append({'coordinate':q,'gain':gain,'unsatisfied_pairs_before':int(deficient.sum()),'total_deficit_before':int((book['distance']-dist[deficient]).sum())})
            E.add(q);chosen.append(q);dist+=D[:,idx]
        return {'destination':destination,'sensor':sensor,'target':book['target'],'required_distance':book['distance'],'inherited_coordinates':sorted(inherited),'witness':chosen,'cost':len(chosen),'trace':trace,'minimum_distance':int(dist[self.relevant[book['target']]].min()),'elapsed_seconds':time.monotonic()-started}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);args=ap.parse_args()
    protocol_path=args.out/'PROTOCOL_GREEDY_V1.json';P=json.loads(protocol_path.read_text())
    for p,h in P['input_sha256'].items():require(sha((args.repo/p).read_bytes())==h,'Input digest mismatch '+p)
    require(sha(Path(__file__).read_bytes())==P['producer_sha256'],'Producer differs from frozen protocol')
    source=args.repo/'research/continuity_v2_20261013/evidence/ech';joint=args.repo/'research/continuity_v3_20261013/evidence/ech_joint'
    started=time.monotonic();M=FiniteModel(json.loads((source/'inputs/cas_constitutional_kernel_v1.json').read_text()),json.loads((source/'inputs/compiled_distance_codebooks.json').read_text()));kernel_seconds=time.monotonic()-started
    frozen=json.loads((joint/'PROTOCOL_FIXED_TWO_STAGE.json').read_text())
    certs={x['route']['route_id']:x for x in json.loads((joint/'JOINT_ROUTE_CERTIFICATES.json').read_text())}
    results=[];stage_cache={};cache_seconds=0.0
    for route in frozen['routes']:
        E=M.initial(route['source']);stages=[]
        for dest in [route['intermediate'],route['destination']]:
            key=(tuple(sorted(E)),dest)
            if key not in stage_cache:stage_cache[key]=M.greedy_stage(E,dest)
            else:cache_seconds+=stage_cache[key]['elapsed_seconds']
            stage=stage_cache[key];stages.append(stage);E.update(stage['witness'])
        cost=sum(s['cost'] for s in stages);cert=certs[route['route_id']];opt=cert['certified_integer_lower_bound']
        require(cert['joint_cost']==opt and cert['certified_gap']==0,'Reference not exact')
        require(cost>=opt,'Greedy contradicts the certified optimum')
        result={'route':route,'stages':stages,'greedy_cost':cost,'joint_optimum':opt,'excess_over_joint':cost-opt,'historical_cost':route['archived_local_cost'],'greedy_minus_historical':cost-route['archived_local_cost'],'first_excess_over_certified_local_minimum':stages[0]['cost']-route['archived_first_cost'],'joint_certificate_sha256':cert['certificate_sha256']}
        results.append(result);dump(args.out/'GREEDY_ROUTE_WITNESSES.partial.json',results)
        print(json.dumps({'route':route['route_id'],'greedy':cost,'joint':opt,'historical':route['archived_local_cost'],'first_excess':result['first_excess_over_certified_local_minimum']}),flush=True)
    dump(args.out/'GREEDY_ROUTE_WITNESSES.json',results)
    fields=['route_id','source','intermediate','destination','first_sensor','second_sensor','greedy_first_cost','greedy_second_cost','greedy_cost','joint_optimum','excess_over_joint','historical_cost','greedy_minus_historical','first_excess_over_certified_local_minimum']
    rows=[]
    for r in results:
        row={k:r.get(k,r['route'].get(k)) for k in fields}
        row.update(first_sensor=r['stages'][0]['sensor'],second_sensor=r['stages'][1]['sensor'],greedy_first_cost=r['stages'][0]['cost'],greedy_second_cost=r['stages'][1]['cost']);rows.append(row)
    with (args.out/'GREEDY_ROUTE_COMPARISON.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    groups=defaultdict(list)
    for row in rows:groups[row['first_sensor']+' -> '+row['second_sensor']].append(row)
    jurisdictions=[]
    for label,rs in sorted(groups.items()):
        jurisdictions.append({'sensor_route':label,'routes':[x['route_id'] for x in rs],'n_routes':len(rs),'equal_joint_optimum':sum(x['excess_over_joint']==0 for x in rs),'strictly_above_joint':sum(x['excess_over_joint']>0 for x in rs),'max_excess':max(x['excess_over_joint'] for x in rs),'sum_independent_greedy_cost':sum(x['greedy_cost'] for x in rs),'sum_independent_joint_cost':sum(x['joint_optimum'] for x in rs),'better_than_historical':sum(x['greedy_minus_historical']<0 for x in rs),'equal_historical':sum(x['greedy_minus_historical']==0 for x in rs),'worse_than_historical':sum(x['greedy_minus_historical']>0 for x in rs)})
    dump(args.out/'GREEDY_JURISDICTIONS.json',jurisdictions)
    summary={'schema':'ECH_FROZEN_GREEDY_COMPARISON_V1','status':'COMPUTED_PENDING_INDEPENDENT_CHECK','protocol_sha256':sha(protocol_path.read_bytes()),'producer_sha256':sha(Path(__file__).read_bytes()),'witnesses_sha256':sha((args.out/'GREEDY_ROUTE_WITNESSES.json').read_bytes()),'all_routes':len(results),'equal_joint_optimum':sum(x['excess_over_joint']==0 for x in results),'strictly_above_joint':sum(x['excess_over_joint']>0 for x in results),'max_excess_over_joint':max(x['excess_over_joint'] for x in results),'sum_independent_greedy_cost':sum(x['greedy_cost'] for x in results),'sum_independent_joint_cost':sum(x['joint_optimum'] for x in results),'sum_independent_historical_cost':sum(x['historical_cost'] for x in results),'better_than_historical':sum(x['greedy_minus_historical']<0 for x in results),'equal_historical':sum(x['greedy_minus_historical']==0 for x in results),'worse_than_historical':sum(x['greedy_minus_historical']>0 for x in results),'first_stage_above_exact_local_minimum':sum(x['first_excess_over_certified_local_minimum']>0 for x in results),'distinct_stage_inputs':len(stage_cache),'timing':{'kernel_construction_seconds':kernel_seconds,'elapsed_seconds':time.monotonic()-started,'stage_policy_seconds_unique_inputs':sum(x['elapsed_seconds'] for x in stage_cache.values()),'unexecuted_repeated_stage_times_excluded':True,'single_run_descriptive_not_performance_benchmark':True},'environment':{'python':platform.python_version(),'numpy':np.__version__},'limitations':P['limitations'],'permission_granted':False}
    dump(args.out/'GREEDY_COMPARISON_RESULT.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
