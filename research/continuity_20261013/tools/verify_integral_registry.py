"""Verify the actual continuity corpus; no generated observational fixtures."""
from pathlib import Path
import csv
import gzip
import hashlib
import io
import json
import re

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parents[1]

def main():
    registry = json.loads((HERE / 'CLAIM_EVIDENCE_REGISTRY.json').read_text())
    claims = {c['id']: c for c in registry['claims']}
    assert len(claims) == len(registry['claims'])
    sources = {s['id']: s for s in registry['sources']}
    source_checks=[]
    for source in sources.values():
        if 'local_path' in source:
            path=HERE/source['local_path']
            actual=hashlib.sha256(path.read_bytes()).hexdigest()
            assert actual==source['sha256'], source['id']
            source_checks.append({'id':source['id'],'sha256_matches':True})
    effective={}
    def visit(cid, stack=()):
        assert cid not in stack, f'dependency cycle: {stack}, {cid}'
        c=claims[cid]
        for sid in c['sources']: assert sid in sources, (cid,sid)
        reservations=set(c['reservations'])
        for dep in c['depends_on']:
            assert dep in claims, (cid,dep)
            reservations.update(visit(dep,stack+(cid,)))
        effective[cid]=sorted(reservations)
        return reservations
    for cid in claims: visit(cid)
    assert 'UNCERTIFIED_HISTORICAL_EVENT_MEMBERSHIP' in effective['SEISMIC_DYNAMIC_V082']
    assert 'UNCERTIFIED_HISTORICAL_EVENT_MEMBERSHIP' in effective['SEISMIC_DESIGN_V09A']
    assert 'UNCERTIFIED_HISTORICAL_EVENT_MEMBERSHIP' not in effective['SEISMIC_TERMINAL_V11']
    assert not any(c['new_authority_granted'] for c in claims.values())
    assert set(registry['required_domains']) == {c['domain'] for c in claims.values()}
    solar=json.loads((HERE/'evidence/solar/TEMPORAL_LIFT_DEVELOPMENT_RESULT_V1_5.json').read_text())
    body=dict(solar);rid=body.pop('receipt_id')
    assert rid=='h15lift:'+hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    assert solar['outcome']=='INSUFFICIENT_TEMPORAL_SUPPORT' and not solar['fold_results'] and not solar['global_scores']
    assert [len(t['snapshots']) for t in solar['trajectories']]==[5,0,1]
    assert not solar['scientific_confirmation'] and not solar['fresh_2026_holdout_accessed']
    frozen=json.loads((ROOT/'.github/helical_continuity/FROZEN_INPUTS.json').read_text())
    for path,sha in frozen['sha256'].items(): assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha
    comp=json.loads((HERE/'evidence/seismic/COMPRESSED_CROSSWALK.json').read_text())
    packed=(HERE/'evidence/seismic'/comp['file']).read_bytes()
    raw=gzip.decompress(packed)
    assert hashlib.sha256(packed).hexdigest()==comp['compressed_sha256']
    assert hashlib.sha256(raw).hexdigest()==comp['uncompressed_sha256']
    rows=list(csv.DictReader(io.StringIO(raw.decode())))
    assert len(rows)==61555
    assert not any(re.search(r'(strike|dip|rake|tensor|axis_[xyz])',col) for col in rows[0])
    report={'format':'KCH_INTEGRAL_CORPUS_VERIFICATION_V1','status':'PASS','claim_count':len(claims),'domains':registry['required_domains'],'source_hash_checks':source_checks,'effective_reservations':effective,'frozen_solar_inputs_unchanged':True,'solar_result_identity_valid':True,'solar_eligible_snapshots':6,'solar_model_scores_produced':0,'historical_membership_rows':len(rows),'nonangular_crosswalk':True,'synthetic_observations_created':False,'new_authority_granted':False}
    (HERE/'CORPUS_VERIFICATION.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ['source_hash_checks','effective_reservations','domains']}))

if __name__=='__main__':main()
