#!/usr/bin/env python3
"""Portable fail-closed integration check. Fresh receipts are written outside corpus."""
import argparse, csv, hashlib, json, math, shutil, subprocess, sys
from decimal import Decimal
from fractions import Fraction
from pathlib import Path

def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def require(c,m):
    if not c: raise ValueError(m)
def write(p,d): p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    repo=a.repo.resolve();root=repo/'research/continuity_v4_20261020';out=a.out.resolve()
    require(out!=root and root not in out.parents,'Output must be outside frozen v4 corpus')
    out.mkdir(parents=True,exist_ok=True)
    receipt=out/'CORPUS_VERIFICATION.json';receipt.unlink(missing_ok=True)
    report=dict(schema='KCH_CONTINUITY_V4_VERIFICATION',status='RUNNING',scientific_confirmation=False,new_authority_granted=False)
    try:
        entry=read(root/'ENTRY_SCOPE.json')
        require(entry['no_hhc'] and entry['preserve_all_parent_bytes'],'Entry scope altered')
        require(len(entry['parent_files'])==108,'Parent inventory incomplete')
        for item in entry['parent_files']:
            p=repo/item['path'];require(p.stat().st_size==item['bytes'] and digest(p)==item['sha256'],'Parent changed '+item['path'])
        report['unchanged_parent_files']=108
        parent=repo/'research/continuity_v3_20261013/CLAIM_EVIDENCE_REGISTRY.json';old=read(parent);reg=read(root/'CLAIM_EVIDENCE_REGISTRY.json')
        require(reg['parent_registry_sha256']==digest(parent),'Registry wrong parent')
        require(reg['claims'][:len(old['claims'])]==old['claims'],'Inherited claim altered')
        require(reg['required_domains']==old['required_domains'] and len(reg['required_domains'])==12,'Domain loss')
        sources={s['id']:s for s in reg['sources']};claims={c['id']:c for c in reg['claims']}
        require(len(sources)==len(reg['sources']) and len(claims)==len(reg['claims']),'Duplicate source or claim')
        for sid,s in sources.items():
            if s.get('local_path'): require(digest(root/s['local_path'])==s['sha256'],'Source hash mismatch '+sid)
        for c in claims.values():
            require(c['domain'] in reg['required_domains'] and all(s in sources for s in c['sources']),'Invalid source/domain '+c['id'])
            require(all(d in claims for d in c['depends_on']),'Missing dependency '+c['id'])
            require(c['new_authority_granted'] is False,'Authority promotion '+c['id'])
        def visit(i,seen,active):
            require(i not in active,'Dependency cycle '+i)
            if i in seen:return
            for d in claims[i]['depends_on']:visit(d,seen,active|{i})
            seen.add(i)
        seen=set()
        for i in claims:visit(i,seen,set())
        require(reg['universal_confirmation'] is False and reg['new_observations'] is False,'Invalid global promotion')
        report.update(inherited_claims_unchanged=len(old['claims']),claims=len(claims),sources=len(sources),domains=12,
          remote_source_references_not_redownloaded=sum(not bool(s.get('local_path'))for s in sources.values()))

        retained=out/'MANUSCRIPT_RETENTION_CHECK.json';retained.unlink(missing_ok=True)
        r=subprocess.run([sys.executable,str(root/'tools/check_manuscript_retention.py'),'--repo',str(repo),'--out',str(retained)],capture_output=True,text=True)
        require(r.returncode==0,'Manuscript retention failed '+r.stdout+r.stderr)
        require(retained.exists() and read(retained)['status']=='PASS','Missing fresh retention receipt')
        report['manuscript_retention_receipt_sha256']=digest(retained)

        source=root/'evidence/ech_comparison';fresh=out/'greedy'
        if fresh.exists():shutil.rmtree(fresh)
        shutil.copytree(source,fresh);(fresh/'GREEDY_INDEPENDENT_CHECK.json').unlink(missing_ok=True)
        r=subprocess.run([sys.executable,str(source/'check_greedy_baseline.py'),'--repo',str(repo),'--out',str(fresh)],capture_output=True,text=True)
        require(r.returncode==0,'Fresh greedy check failed '+r.stdout+r.stderr)
        fresh_receipt=read(fresh/'GREEDY_INDEPENDENT_CHECK.json');archived=read(source/'GREEDY_INDEPENDENT_CHECK.json')
        require(fresh_receipt['status']=='PASS','Greedy fresh receipt not PASS')
        for k,v in archived.items():
            if k!='elapsed_seconds':require(fresh_receipt[k]==v,'Greedy receipt drift '+k)
        rows=list(csv.DictReader((source/'GREEDY_ROUTE_COMPARISON.csv').open()))
        minimum_but_suboptimal=sum(int(x['first_excess_over_certified_local_minimum'])==0 and int(x['excess_over_joint'])>0 for x in rows)
        require(minimum_but_suboptimal==19,'First-minimum interpretation incorrect')
        report['ech']=dict(routes=46,greedy_equal_joint_optimum=sum(int(x['excess_over_joint'])==0 for x in rows),first_minimum_but_suboptimal_total=minimum_but_suboptimal,
          fresh_receipt_sha256=digest(fresh/'GREEDY_INDEPENDENT_CHECK.json'),checks=fresh_receipt)

        theory=root/'theory';deps=read(theory/'STRUCTURAL_EVIDENCE_DEPENDENCIES.json')
        review=read(theory/'STRUCTURAL_REVIEW.json')
        require(review['status']=='PASS_WITH_DECLARED_SCOPE' and not review['blocking_findings'],'Structural review has unresolved blockers')
        for f in review['reviewed_files']:require(digest(repo/f['path'])==f['sha256'],'Structural text changed after review')
        report['structural_review_scope']='Separate-agent mathematical review; not proof-assistant verification or human peer review.'
        for s in deps['sources']:require(digest(repo/s['path'])==s['sha256'],'Structural source mismatch '+s['path'])
        v3=repo/'research/continuity_v3_20261013/evidence/ech_joint'
        plans={p['route_id']:p for p in read(v3/'LOCAL_MINIMUM_LOOKAHEAD_CATALOG.json')['plans']}
        certs={c['route']['route_id']:c for c in read(v3/'JOINT_ROUTE_CERTIFICATES.json')}
        decomposed=list(csv.DictReader((theory/'EXACT_SAVING_DECOMPOSITION_46.csv').open()))
        require(len(decomposed)==len({r['route_id']for r in decomposed})==46,'Incomplete structural table')
        for row in decomposed:
            rid=row['route_id'];p=plans[rid];c=certs[rid];route=c['route']
            for k in ['source','intermediate','destination']:require(row[k]==p[k]==route[k],'Structural route mismatch')
            A=route['archived_local_cost'];R=p['first_cost']+p['second_cost'];J=c['joint_cost'];m=p['first_cost']
            expected=dict(minimum_first_cost=m,archived_cost_A=A,restricted_cost_R=R,joint_cost_J=J,tie_choice_saving_A_minus_R=A-R,
              strict_nonminimality_saving_R_minus_J=R-J,catalog_optimal_residual_at_m=p['second_cost'],returned_joint_first_cost=c['first_cost'],returned_joint_first_excess=c['first_cost']-m)
            require(all(int(row[k])==v for k,v in expected.items()),'Structural arithmetic mismatch '+rid)
            require(m==route['archived_first_cost'] and R==J and A>=R,'Unjustified restricted optimum '+rid)
            require(row['joint_certificate_sha256']==c['certificate_sha256']==p['joint_lower_bound_certificate_sha256'],'Structural certificate mismatch')
            require(row['first_minimum_certificate']==p['first_original_minimum_certificate'],'Structural local certificate mismatch')
            require(row['same_sensor']==str(c['grouping']['first_sensor']==c['grouping']['second_sensor']),'Structural sensor mismatch')
        require(sum(int(r['tie_choice_saving_A_minus_R'])>0 for r in decomposed)==11,'Structural saving count mismatch')
        report['structural_decomposition']=dict(routes=46,tie_choice_saving_positive=11,strict_nonminimality_saving_positive=0,
          scope='Recomputed from inherited certified values; analytic proof requires mathematical review, not this arithmetic check.')

        physical=root/'evidence/physical_contracts';physical_fresh=out/'physical';physical_fresh.mkdir(exist_ok=True)
        for name in ['DAVE_SOURCE_SEARCH.json','PHYSICAL_CONTRACT_AUDIT.json','SOLAR_LOCAL_PRESERVED.csv']:(physical_fresh/name).unlink(missing_ok=True)
        r=subprocess.run([sys.executable,str(physical/'audit_physical_contracts.py'),'--repo',str(repo),'--out',str(physical_fresh)],capture_output=True,text=True)
        require(r.returncode==0,'Physical audit replay failed '+r.stdout+r.stderr)
        for name in ['DAVE_SOURCE_SEARCH.json','PHYSICAL_CONTRACT_AUDIT.json','SOLAR_LOCAL_PRESERVED.csv']:
            require(digest(physical_fresh/name)==digest(physical/name),'Physical reproducibility mismatch '+name)
        audit=read(physical/'PHYSICAL_CONTRACT_AUDIT.json')
        solar=read(repo/'research/continuity_v2_20261013/evidence/solar/TEMPORAL_LIFT_DEVELOPMENT_RESULT_V1_6.json')
        trajectories={t['trajectory_id']:t for t in solar['trajectories']};future=[]
        for f in solar['fold_results']:
            test=trajectories[f['held_out_trajectory']];test_time=min(s['requested_time_tai']for s in test['snapshots'])
            train_times=[s['requested_time_tai']for tid in f['train_trajectories']for s in trajectories[tid]['snapshots']]
            if max(train_times)>test_time:future.append(f['held_out_harp'])
        require(sorted(future)==[401,2920] and audit['solar']['folds_with_future_training_sources']==2,'Solar clock mismatch')
        require(audit['solar']['local_wins']=={'H_HELICAL_TRANSLATION':4,'L_LEMNISCATIC_ALTERNATING':7,'G_ACTIVITY_AFFINE':5,'M_MOBIUS_SIGN':0},'Local wins altered')
        report['solar']=dict(future_training_folds=future,local_wins_preserved=audit['solar']['local_wins'],historical_outcome=solar['outcome'])
        m33path=repo/'research/continuity_20261013/evidence/m33/M33_RADIAL_VERIFICATION.json'
        raw=json.loads(m33path.read_text(),parse_float=Decimal)
        K=[[Fraction(v)for v in row]for row in raw['deterministic_primary']['natural_response']['response_matrix_kms_per_eta']]
        require(len(K)==2 and all(len(row)==3 for row in K),'Wrong M33 matrix')
        u,v=K;n=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]]
        require(any(n),'Rank below two');require(all(sum(x*y for x,y in zip(row,n))==0 for row in K),'Exact kernel failure')
        norm=math.sqrt(sum(float(x)**2 for x in n));unit=[float(x)/norm for x in n]
        if next(x for x in unit if abs(x)>1e-12)<0:unit=[-x for x in unit]
        require(max(abs(x-y)for x,y in zip(unit,audit['m33']['unit_null_direction_eta']))<1e-12,'Approximate null direction mismatch')
        prior=read(m33path)
        require(audit['m33']['historical_deterministic_primary']==prior['deterministic_primary'],'M33 primary altered')
        require(audit['m33']['historical_covariance_scenarios']==prior['covariance_scenarios'],'M33 sensitivities altered')
        report['m33']=dict(rank=2,nullity=1,exact_nonzero_cross_product=[str(x)for x in n],exact_K_times_cross_product=['0','0'],unit_null_direction=unit,
          qualification='Exact rational statement for archived decimal matrix; no Lorentz-kernel equivalence or nuisance-adjusted identification claim.')

        manifest=read(root/'DELIVERY_MANIFEST.json')
        for f in manifest['files']:
            p=repo/f['path'];require(p.stat().st_size==f['bytes'] and digest(p)==f['sha256'],'Delivery changed '+f['path'])
        actual={str(p.relative_to(repo)) for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p not in {root/'DELIVERY_MANIFEST.json',root/'CORPUS_VERIFICATION.json'}}
        expected={x['path'] for x in manifest['files'] if x['path'].startswith(str(root.relative_to(repo))+'/')}
        require(actual==expected,'Unmanifested or missing delivered file')
        report.update(manifest_entries_verified=len(manifest['files']),status='PASS')
    except Exception as exc:
        report.update(status='FAIL',error=str(exc));write(receipt,report);raise
    write(receipt,report)
    print(json.dumps({k:v for k,v in report.items()if k not in ['ech','m33']},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
