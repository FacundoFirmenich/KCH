"""Verify evidence links, exact local-minimum catalogue and cross-domain continuity."""
from pathlib import Path
import hashlib,json
H=Path(__file__).resolve().parents[1];R=H.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
    registry=read(H/'CLAIM_EVIDENCE_REGISTRY.json');parent=R/'research/continuity_v2_20261013/CLAIM_EVIDENCE_REGISTRY.json';assert sha(parent)==registry['parent_registry_sha256'];claims={c['id']:c for c in registry['claims']};sources={s['id']:s for s in registry['sources']};assert len(claims)==len(registry['claims']);assert len(sources)==len(registry['sources'])
    for source in sources.values():
        if 'local_path' in source:assert sha(H/source['local_path'])==source['sha256'],source['id']
    effective={}
    def visit(cid,stack=()):
        assert cid not in stack;c=claims[cid];assert not c['new_authority_granted'];assert all(x in sources for x in c['sources']);rr=set(c['reservations'])
        for dep in c['depends_on']:rr.update(visit(dep,stack+(cid,)))
        effective[cid]=sorted(rr);return rr
    for cid in claims:visit(cid)
    assert set(registry['required_domains'])=={c['domain'] for c in claims.values()}
    assert 'UNCERTIFIED_HISTORICAL_EVENT_MEMBERSHIP' in effective['SEISMIC_DYNAMIC_V082'] and 'UNCERTIFIED_HISTORICAL_EVENT_MEMBERSHIP' in effective['SEISMIC_DESIGN_V09A'];assert 'UNCERTIFIED_HISTORICAL_EVENT_MEMBERSHIP' not in effective['SEISMIC_TERMINAL_V11']
    ech=H/'evidence/ech_joint';old=R/'research/continuity_v2_20261013/evidence/ech';result=read(ech/'ECH_JOINT_ROUTE_RESULT.json');post=read(ech/'POSTHOC_LOCAL_TIE_RESULT.json');check=read(ech/'SOLVER_FREE_JOINT_CHECK.json');pcheck=read(ech/'SOLVER_FREE_POSTHOC_TIE_CHECK.json')
    assert result['certified_optimal_routes']==46 and result['improved_routes']==11 and result['joint_noncommuting_cost_squares']==13;assert check['status']==pcheck['status']=='PASS';assert check['local_minimum_lookahead_catalog_plans_verified']==46 and check['catalog_sha256']==sha(ech/'LOCAL_MINIMUM_LOOKAHEAD_CATALOG.json');assert post['exact_optima_certified']==post['local_minimum_tie_suffices']==11 and post['strict_anticipation_required_for_full_joint_optimum']==0
    originals={c['problem_id']:c for c in read(old/'results/EXACT_BRIDGE_CERTIFICATES.json')};joint={c['route']['route_id']:c for c in read(ech/'JOINT_ROUTE_CERTIFICATES.json')};restricted={c['route']['route_id']:c for c in read(ech/'POSTHOC_LOCAL_TIE_CERTIFICATES.json')};squares=read(old/'results/FINITE_ATLAS_REPLAY_DETAIL.json')['squares'];cat=read(ech/'LOCAL_MINIMUM_LOOKAHEAD_CATALOG.json');assert len(cat['plans'])==46;plans={p['route_id']:p for p in cat['plans']};assert set(plans)==set(joint);catalog_checks=[]
    for rid,p in plans.items():
        c=joint[rid];orig=originals[p['first_original_minimum_certificate']];route=c['route']
        for key in ['source','intermediate','destination']:assert p[key]==route[key]
        assert p['inherited_coordinates']==c['inherited_coordinates']==orig['inherited_coordinates'];assert orig['destination']==p['intermediate']
        assert p['first_cost']==len(p['first_witness'])==orig['certified_minimum_queries'];assert p['second_cost']==len(p['second_witness']);assert p['joint_optimum']==p['first_cost']+p['second_cost']==c['joint_cost'];assert p['joint_lower_bound_certificate_sha256']==c['certificate_sha256'];assert not p['permission_granted']
        assert len(p['inherited_coordinates']+p['first_witness']+p['second_witness'])==len(set(p['inherited_coordinates']+p['first_witness']+p['second_witness']))
        if rid in restricted:
            pp=restricted[rid];assert p['first_witness']==pp['first_witness'] and p['second_witness']==pp['second_witness'];kind='NEW_LOCAL_MINIMUM_TIE'
        else:
            q=squares[int(rid[1:3])-1]['path'+rid[-1]];assert p['first_witness']==q[0]['witness'] and p['second_witness']==q[1]['witness'];assert route['archived_local_cost']==c['joint_cost'];kind='ARCHIVED_LOCAL_MINIMUM_PLAN'
        catalog_checks.append({'route_id':rid,'kind':kind,'first_cost_locally_minimal':True,'total_cost_joint_optimal':True,'second_cost_locally_minimal_by_joint_lower_bound':True})
    solar=H/'evidence/solar_local';sv=read(solar/'SOLAR_LOCAL_VERIFICATION.json');sd=read(solar/'SOLAR_LOCAL_DIAGNOSTIC.json');assert sv['status']=='PASS' and sv['numeric_comparisons_passed']==43924;assert sd['coverage']['raw_cells']==960 and sd['coverage']['aggregate_rows']==1200;assert sd['outcome_preserved']=='NO_DEVELOPMENT_DOMINANT_LIFT' and not sd['scientific_confirmation']
    q=read(H/'evidence/quotient/results/PLANNING_QUOTIENT_VERIFICATION.json');assert q['status']=='PASS' and q['total_typed_coordinates']==12051 and q['total_typed_patterns']==7880 and q['original_certificates_replayed']==204;assert sha(H/'evidence/quotient/results/PLANNING_PATTERN_PARTITION.json')==q['partition_sha256']
    report={'format':'KCH_INTEGRAL_CORPUS_VERIFICATION_V3','status':'PASS','claims':len(claims),'sources':len(sources),'domains':registry['required_domains'],'parent_registry_unchanged':True,'effective_reservations':effective,'exact_joint_routes':46,'optimal_value_asymmetric_squares':13,'improved_archived_routes':11,'all_improvements_attainable_by_local_minimum_ties':True,'locally_minimal_joint_optimal_catalogue':catalog_checks,'planning_quotient_patterns':7880,'solar_local_cells':960,'solar_aggregate_rows':1200,'solar_numeric_checks':43924,'solar_gate_preserved':True,'synthetic_observations_created':False,'new_authority_granted':False}
    (H/'CORPUS_VERIFICATION.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    manifest_path=H/'DELIVERY_MANIFEST.json'
    if manifest_path.exists():
        for item in read(manifest_path)['files']:assert sha(R/item['path'])==item['sha256'],item['path']
    print(json.dumps({k:v for k,v in report.items() if k not in ('effective_reservations','locally_minimal_joint_optimal_catalogue')},indent=2))
if __name__=='__main__':
    if not __debug__:raise RuntimeError('Assertions required')
    main()
