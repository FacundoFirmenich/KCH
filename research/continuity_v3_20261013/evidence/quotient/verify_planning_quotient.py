"""Exact finite planning quotient of the archived ECH kernel; no observed data generation."""
from pathlib import Path
from itertools import combinations
from collections import defaultdict,Counter
import argparse,hashlib,json
import numpy as np

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canon(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ech',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    kp=a.ech/'inputs/cas_constitutional_kernel_v1.json';assert sha(kp)=='82a9d8b10b90ea1debfeb480ac10e5bcc183e034d0d33a6dbf23b55931053138';k=json.loads(kp.read_text());assert sha(a.ech/'inputs/compiled_distance_codebooks.json')=='9d5ffe66c18b6c764963a484f91eed09ebb064a59be205fc3f7a0681adb81a5b';assert sha(a.ech/'results/EXACT_BRIDGE_CERTIFICATES.json')=='aaf4b8a0da82db4677dc032816d9c9c43bdcc7698a70a29c611b3a49139b97d9';books=json.loads((a.ech/'inputs/compiled_distance_codebooks.json').read_text());certs=json.loads((a.ech/'results/EXACT_BRIDGE_CERTIFICATES.json').read_text());nodes=k['nodes'];roots={int(r['class_id']):r['root'] for r in k['roots']};classes=sorted(roots);masks=[m for m in range(1<<len(k['ordered_blocks'])) if m.bit_count()>=k['domain_floor']];pairs=list(combinations(range(len(classes)),2));ii,jj=np.triu_indices(len(classes),1)
    def read(root,m):
        while 'label' not in nodes[root]:
            n=nodes[root];root=n['if_included'] if m&(1<<n['query_index']) else n['if_excluded']
        return nodes[root]['label']
    exact=np.array([[read(roots[c],m) for m in masks] for c in classes]);mode=np.array([[v.split(':',1)[0] for v in row] for row in exact]);act=np.isin(mode,['APPLY','TOP_2']);mat={'EXACT':exact,'MODE':mode,'ACTIONABLE':act};diff={s:(v[ii]!=v[jj]).astype(np.int64) for s,v in mat.items()};groups=[];coord_group={};group_vector={};stats={};global_ix=0
    for sensor,A in diff.items():
        bypattern=defaultdict(list)
        for j,m in enumerate(masks):bypattern[np.packbits(A[:,j],bitorder='little').tobytes()].append(f'{m:03x}')
        sizes=[]
        for pattern,qs in sorted(bypattern.items(),key=lambda kv:kv[1][0]):
            gid=f'{sensor}:{qs[0]}';vec=np.unpackbits(np.frombuffer(pattern,dtype=np.uint8),bitorder='little')[:len(pairs)].astype(np.int64)
            groups.append({'group_id':gid,'sensor':sensor,'capacity':len(qs),'masks':qs,'pair_pattern_sha256':hashlib.sha256(pattern).hexdigest(),'separated_pairs':int(vec.sum())});group_vector[gid]=vec;sizes.append(len(qs))
            for q in qs:coord_group[sensor+':'+q]=gid
        stats[sensor]={'typed_coordinates':len(masks),'separation_patterns':len(sizes),'max_capacity':max(sizes),'multi_coordinate_patterns':sum(n>1 for n in sizes),'zero_separation_patterns':sum(g['separated_pairs']==0 for g in groups if g['sensor']==sensor)}
    capacities={g['group_id']:g['capacity'] for g in groups}
    def distances(E):
        d=np.zeros(len(pairs),dtype=np.int64)
        for q in E:d+=group_vector[coord_group[q]]
        return d
    checks=[];support_multiplicity=[];all_E=set()
    for cert in certs:
        E=cert['inherited_coordinates'];W=cert['witness'];target=books[cert['destination']];before=Counter(coord_group[q] for q in E);delta=Counter(coord_group[q] for q in W);after=before+delta
        assert set(E).isdisjoint(W)
        assert all(n<=capacities[g] for g,n in after.items())
        compressed=np.zeros(len(pairs),dtype=np.int64)
        for g,n in after.items():compressed+=n*group_vector[g]
        explicit=np.zeros(len(pairs),dtype=np.int64)
        for q in E+W:
            ss,mm=q.split(':');explicit+=diff[ss][:,masks.index(int(mm,16))]
        assert np.array_equal(compressed,explicit)
        relevant=diff[target['target']].any(axis=1);assert int(compressed[relevant].min())>=target['distance']
        available={g:capacities[g]-before[g] for g in capacities if g.startswith(target['sensor']+':')};assert sum(available.values())==len(masks)-sum(q.startswith(target['sensor']+':') for q in E)
        assert all(delta[g]<=available[g] for g in delta)
        checks.append({'problem_id':cert['problem_id'],'cost':len(W),'grouped_cost':sum(delta.values()),'inherited_distances_exact':True,'terminal_distances_exact':True,'availability_exact':True,'nonempty_inherited_groups':len(before),'nonempty_added_groups':len(delta),'multiple_added_same_pattern':max(delta.values(),default=0)})
        if max(after.values(),default=0)>1:support_multiplicity.append({'problem_id':cert['problem_id'],'destination':cert['destination'],'multiplicities':[{'group':g,'count':n,'coordinates':[q for q in E+W if coord_group[q]==g]} for g,n in after.items() if n>1]})
        all_E.add(tuple(sorted(E)));all_E.add(tuple(sorted(E+W)))
    # A concrete pair of different archived states with the same quotient, if it exists.
    quotient_states=defaultdict(list)
    for E in sorted(all_E):quotient_states[tuple(sorted(Counter(coord_group[q] for q in E).items()))].append(E)
    collisions=[{'ledger_a':list(v[0]),'ledger_b':list(v[1]),'same_group_counts':dict(key)} for key,v in quotient_states.items() if len(v)>1]
    partition={'format':'ECH_TYPED_SEPARATION_PATTERN_PARTITION_V1','kernel_sha256':sha(kp),'class_order':classes,'pair_order':'itertools.combinations(class_order,2)','packing':'numpy.packbits bitorder=little; final padding zero','groups':groups}
    (a.out/'PLANNING_PATTERN_PARTITION.json').write_text(json.dumps(partition,indent=2,sort_keys=True)+'\n')
    report={'format':'ECH_PLANNING_QUOTIENT_VERIFICATION_V1','status':'PASS','input_kernel_sha256':sha(kp),'script_sha256':sha(Path(__file__)),'partition_sha256':sha(a.out/'PLANNING_PATTERN_PARTITION.json'),'sensors':stats,'total_typed_coordinates':len(coord_group),'total_typed_patterns':len(groups),'original_certificates_replayed':len(checks),'certificate_checks':checks,'archived_ledgers_checked':len(all_E),'quotient_states_in_archived_ledgers':len(quotient_states),'archived_distinct_ledger_collisions':collisions,'certificates_with_multiplicity_in_terminal_quotient':len(support_multiplicity),'terminal_multiplicity_examples':support_multiplicity,'scope':'SUFFICIENT_QUOTIENT_FOR_FINITE_DISTANCE_CONTRACT_PLANNING_UNIT_COST_SENSOR_ONLY_ADMISSIBILITY','not_claimed':['minimal quotient','observation decoder sufficiency','receipt or ledger identity','authority equivalence','noisy or time varying observations','arbitrary coordinate-specific cost or permissions'],'synthetic_observations_created':False,'permission_granted':False}
    (a.out/'PLANNING_QUOTIENT_VERIFICATION.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('certificate_checks','archived_distinct_ledger_collisions','terminal_multiplicity_examples')},indent=2));print('distinct ledger same quotient collisions',len(collisions))
if __name__=='__main__':
    if not __debug__:raise RuntimeError('Assertions required')
    main()
