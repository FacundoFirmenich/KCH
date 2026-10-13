"""Verify the real integrated successor corpus and the boundaries it preserves."""
from pathlib import Path
import hashlib,json
H=Path(__file__).resolve().parents[1];R=H.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    reg=json.loads((H/'CLAIM_EVIDENCE_REGISTRY.json').read_text());old=R/'research/continuity_20261013/CLAIM_EVIDENCE_REGISTRY.json';assert sha(old)==reg['parent_registry_sha256']
    claims={c['id']:c for c in reg['claims']};sources={s['id']:s for s in reg['sources']};assert len(claims)==len(reg['claims'])==30;assert len(sources)==len(reg['sources'])==25
    hashes=[]
    for s in sources.values():
        if 'local_path' in s:assert sha(H/s['local_path'])==s['sha256'];hashes.append(s['id'])
    effective={}
    def visit(cid,trail=()):
        assert cid not in trail;c=claims[cid];assert not c['new_authority_granted'];assert all(s in sources for s in c['sources']);rr=set(c['reservations'])
        for d in c['depends_on']:rr.update(visit(d,trail+(cid,)))
        effective[cid]=sorted(rr);return rr
    for c in claims:visit(c)
    assert set(reg['required_domains'])=={c['domain'] for c in claims.values()}
    assert 'UNCERTIFIED_HISTORICAL_EVENT_MEMBERSHIP' in effective['SEISMIC_DYNAMIC_V082'] and 'UNCERTIFIED_HISTORICAL_EVENT_MEMBERSHIP' in effective['SEISMIC_DESIGN_V09A']
    assert 'UNCERTIFIED_HISTORICAL_EVENT_MEMBERSHIP' not in effective['SEISMIC_TERMINAL_V11']
    solar=H/'evidence/solar';proof=json.loads((solar/'INDEPENDENT_REPLAY.json').read_text());result=json.loads((solar/'TEMPORAL_LIFT_DEVELOPMENT_RESULT_V1_6.json').read_text());ex=json.loads((solar/'EXECUTION_RECEIPT_V1_6.json').read_text());run=json.loads((solar/'RUN_PROVENANCE.json').read_text())
    assert proof['status']=='FULL_SELECTION_AND_AGGREGATE_REPLAY_PASS';assert proof['result_sha256']==sha(solar/'TEMPORAL_LIFT_DEVELOPMENT_RESULT_V1_6.json');assert len(proof['numeric_checks'])==60 and all(x['pass'] for x in proof['numeric_checks']);assert result['outcome']=='NO_DEVELOPMENT_DOMINANT_LIFT';assert ex['content_and_identity_valid'] and ex['metadata_unchanged'] and ex['snapshot_count']==15 and ex['raw_directory_absent']
    steps={s['name']:s for s in run['job_steps']};assert steps['Freeze metadata artifact before any FITS body access']['completed_at']<=steps['Execute once on frozen selected windows']['started_at'];assert str(run['metadata_artifact']['id'])==str(ex['metadata_artifact_id']);assert run['execution_commit']==ex['execution_commit']
    ech=H/'evidence/ech';cert={c['problem_id']:c for c in json.loads((ech/'results/EXACT_BRIDGE_CERTIFICATES.json').read_text())};check=json.loads((ech/'results/SOLVER_FREE_CERTIFICATE_CHECK.json').read_text());assert check['status']=='PASS' and check['certificate_count']==len(cert)==204
    books=json.loads((ech/'inputs/compiled_distance_codebooks.json').read_text());ties=json.loads((ech/'results/TIE_INVARIANT_PATH_WITNESSES.json').read_text());tchecks=[]
    for row in ties['cases']:
        c1,c2,d1,d2=[cert[x['problem_id']] for x in row['path1']+row['path2']]
        start,mid1,mid2,dst=[books[row[k]] for k in ('source','intermediate_1','intermediate_2','destination')]
        E=sorted(start['sensor']+':'+q for q in start['probes'])
        assert c1['inherited_coordinates']==d1['inherited_coordinates']==E and c1['destination']==row['intermediate_1'] and d1['destination']==row['intermediate_2']
        assert c2['inherited_coordinates']==sorted(set(E+c1['witness'])) and d2['inherited_coordinates']==sorted(set(E+d1['witness']))
        assert c2['destination']==d2['destination']==row['destination'];assert c1['certified_minimum_queries']==0 and d2['certified_minimum_queries']==0
        assert start['target']==mid1['target']==mid2['target']==dst['target']
        assert start['distance']==mid1['distance'] and mid2['distance']==dst['distance']==start['distance']+1
        assert start['sensor']==mid2['sensor'] and mid1['sensor']==dst['sensor'] and mid1['sensor']!=mid2['sensor']
        assert row['path1_cost']==c2['certified_minimum_queries']==5 and row['path2_cost']==d1['certified_minimum_queries']>5
        tchecks.append({'source':row['source'],'costs':[row['path1_cost'],row['path2_cost']],'optimal_tie_invariance_verified_by_contract_identity':True})
    assert len(tchecks)==4
    report={'format':'KCH_INTEGRAL_CORPUS_VERIFICATION_V2','status':'PASS','claims':len(claims),'sources':len(sources),'domains':reg['required_domains'],'source_hash_checks':hashes,'parent_registry_unchanged':True,'effective_reservations':effective,'solar_numeric_checks':60,'solar_metadata_uploaded_before_fields':True,'solar_outcome':result['outcome'],'ech_certificates':204,'ech_solver_free_exact_inequalities':check['exact_integer_dual_inequalities_checked'],'ech_tie_invariant_paths':tchecks,'synthetic_observations_created':False,'new_authority_granted':False}
    (H/'CORPUS_VERIFICATION.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ('effective_reservations','source_hash_checks')},indent=2))
if __name__=='__main__':
    if not __debug__:raise RuntimeError('Assertions required')
    main()
