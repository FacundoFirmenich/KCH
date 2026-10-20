"""Deterministic documentary/operator audit; no fitting, sampling or data acquisition."""
from pathlib import Path
import argparse, csv, hashlib, io, json, math, re, sys, zipfile

PATTERN=re.compile(r'dave\s*4\s*vm|dave4vm|inducti|helicity.?flux|v1[._]3',re.I)
CODE_EXT={'.py','.ipynb','.pro','.m','.f','.f90','.c','.cpp','.jl','.r'}
TEXT_EXT=CODE_EXT|{'.md','.txt','.json','.yaml','.yml','.csv','.toml','.sh'}

def sha(b): return hashlib.sha256(b).hexdigest()
def write(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    repo=a.repo.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
    roots=[repo/'research'/x for x in ['continuity_20261013','continuity_v2_20261013','continuity_v3_20261013']]
    inventory=[];matches=[];archives=[];skips=[]
    def inspect(name,b,container=None,depth=0):
        suffix=Path(name).suffix.lower();record={'path':name,'container':container,'bytes':len(b),'sha256':sha(b)}
        inventory.append(record)
        if PATTERN.search(name):matches.append(dict(record,match_kind='name',code_extension=suffix in CODE_EXT))
        if suffix in TEXT_EXT:
            try:txt=b.decode('utf-8')
            except UnicodeDecodeError:skips.append({'path':name,'reason':'not_utf8'});return
            hits=[{'line':i,'text':line[:600]} for i,line in enumerate(txt.splitlines(),1) if PATTERN.search(line)]
            if hits:matches.append(dict(record,match_kind='text',code_extension=suffix in CODE_EXT,hits=hits))
        if suffix=='.zip':
            if depth>=4:skips.append({'path':name,'reason':'nested_depth_limit'});return
            with zipfile.ZipFile(io.BytesIO(b)) as z:
                entries=[x for x in z.infolist() if not x.is_dir()]
                archives.append({'path':name,'sha256':sha(b),'file_entries':len(entries),'names':[x.filename for x in entries]})
                for x in entries:
                    if x.file_size>50_000_000:skips.append({'path':name+'!'+x.filename,'reason':'entry_size_limit'});continue
                    inspect(name+'!'+x.filename,z.read(x),name,depth+1)
    files=sorted(f for root in roots for f in root.rglob('*') if f.is_file())
    for f in files:inspect(str(f.relative_to(repo)),f.read_bytes())
    code_matches=[x for x in matches if x.get('code_extension')]
    search={'format':'KCH_PHYSICAL_SOURCE_SEARCH_V1','date':'2026-10-20','roots':[str(p.relative_to(repo))for p in roots],
      'method':'Name inventory first, then full UTF-8 text scan, including every ZIP member and nested ZIP up to depth four.',
      'pattern':PATTERN.pattern,'pattern_serialization_note':'JSON escapes a single regular-expression backslash as two characters; the Python raw string contains a single backslash before s.',
      'pattern_examples':{s:bool(PATTERN.search(s))for s in ['DAVE4VM','DAVE 4 VM','induction','helicity flux','v1.3']},
      'files_on_disk':len(files),'total_items_including_archive_members':len(inventory),
      'archives':archives,'inventory':inventory,'matches':matches,'code_matches':code_matches,'skipped':skips,
      'scope_limit':'Absence is limited to the recovered v1/v2/v3 research corpus; remote references and unmaterialized source archives are not bytes searched.'}
    write(out/'DAVE_SOURCE_SEARCH.json',search)
    v2=repo/'research/continuity_v2_20261013';v3=repo/'research/continuity_v3_20261013';v1=repo/'research/continuity_20261013'
    paths={'protocol':v2/'evidence/solar/SELECTED_PROTOCOL_V1_6.json','result':v2/'evidence/solar/TEMPORAL_LIFT_DEVELOPMENT_RESULT_V1_6.json','local':v3/'evidence/solar_local/AGGREGATES_ALL_1200.csv','m33':v1/'evidence/m33/M33_RADIAL_VERIFICATION.json'}
    protocol=json.loads(paths['protocol'].read_text());result=json.loads(paths['result'].read_text());m33=json.loads(paths['m33'].read_text())
    trajectories={t['trajectory_id']:t for t in result['trajectories']}
    folds=[]
    for f in result['fold_results']:
        te=trajectories[f['held_out_trajectory']];test_times=sorted(s['requested_time_tai']for s in te['snapshots'])
        tr=[trajectories[t]for t in f['train_trajectories']];train_times=[s['requested_time_tai']for t in tr for s in t['snapshots']]
        future=[t['harp']for t in tr if max(s['requested_time_tai']for s in t['snapshots'])>test_times[0]]
        folds.append({'held_out_harp':f['held_out_harp'],'train_harps':[t['harp']for t in tr],'test_start_tai':test_times[0],
          'test_end_tai':test_times[-1],'max_train_time_tai':max(train_times),'train_harps_after_test_start':future,
          'train_time_ranges_tai':[{'harp':t['harp'],'start':min(s['requested_time_tai']for s in t['snapshots']),'end':max(s['requested_time_tai']for s in t['snapshots'])}for t in tr],
          'source_join':'fold_results[].held_out_trajectory/train_trajectories -> trajectories[].trajectory_id -> snapshots[].requested_time_tai',
          'chronological_fit_before_test_start':not future,'retrospective_development':True,'prospective_validation':False})
    model_contracts=[]
    for model,definition in protocol['operational_transport_rivals'].items():
        endpoint=model=='G_ACTIVITY_AFFINE';fitted=definition['trainable_parameters']>0
        model_contracts.append({'model_id':model,'equation':definition['prediction'],'trainable_parameters':definition['trainable_parameters'],
         'test_endpoint_activity_input':endpoint,'equation_compatible_with_issue_time_inputs_if_parameters_preavailable':not endpoint,
         'current_task':'RECONSTRUCT' if endpoint else 'RETROSPECTIVE_TRANSITION_EVALUATION',
         'PREDICT_validated':False,'TRACK_validated':False,'learned_parameters_require_emission_time_provenance':fitted})
    rows=list(csv.DictReader(paths['local'].open()));local=[]
    for harp in [401,2920,5249]:
        for k in range(4):
            rr={x['model']:x for x in rows if x['level']=='transition'and int(x['harp'])==harp and int(x['transition_k'])==k}
            base=float(rr['T0_TRIVIAL_IDENTITY']['nmse'])
            for model in ['H_HELICAL_TRANSLATION','L_LEMNISCATIC_ALTERNATING','G_ACTIVITY_AFFINE','M_MOBIUS_SIGN']:
                value=float(rr[model]['nmse']);local.append({'harp':harp,'transition_k':k,'model':model,'T0_nmse':base,'model_nmse':value,'absolute_nmse_gain':base-value,'relative_nmse_gain_percent':100*(base-value)/base,'descriptive_gain':value<base})
    with(out/'SOLAR_LOCAL_PRESERVED.csv').open('w',newline='')as f:
        writer=csv.DictWriter(f,fieldnames=list(local[0]));writer.writeheader();writer.writerows(local)
    matrix=m33['deterministic_primary']['natural_response']['response_matrix_kms_per_eta'];u,v=matrix
    cross=[u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0]];norm=math.sqrt(sum(x*x for x in cross));n=[x/norm for x in cross]
    if next(x for x in n if abs(x)>1e-12)<0:n=[-x for x in n]
    residual=[sum(x*y for x,y in zip(row,n))for row in matrix]
    assert max(abs(x)for x in residual)<1e-15
    singular=m33['deterministic_primary']['natural_response']['singular_values']
    rank_tolerance=3*sys.float_info.epsilon*singular[0]
    result_out={'format':'KCH_PHYSICAL_CONTRACT_AUDIT_V1','date':'2026-10-20','source_files':{k:{'path':str(p.relative_to(repo)),'sha256':sha(p.read_bytes())}for k,p in paths.items()},
      'new_observations':False,'new_model_fits':False,'synthetic_data':False,'scientific_result_changed':False,
      'solar':{'historical_outcome':result['outcome'],'folds':folds,'folds_with_future_training_sources':sum(not f['chronological_fit_before_test_start']for f in folds),'models':model_contracts,
       'window_selection_uses_complete_future_metadata':True,'note':'Selection conditioned on all five snapshots satisfying quality/support; not an online eligibility policy.',
       'local_wins':{m:sum(x['descriptive_gain']for x in local if x['model']==m)for m in ['H_HELICAL_TRANSLATION','L_LEMNISCATIC_ALTERNATING','G_ACTIVITY_AFFINE','M_MOBIUS_SIGN']}},
      'm33':{'operator_source':'deterministic_primary.natural_response.response_matrix_kms_per_eta','matrix_rows':2,'matrix_columns':3,
       'rank_archived':2,'rank_dimension_upper_bound':2,'nullity_lower_bound_from_dimensions':1,
       'nullity_at_archived_numerical_rank':1,'nullity':1,'unit_null_direction_eta':n,'K_times_null_direction_kms_per_eta':residual,
       'rank_check':{'method':'Count archived singular values above max(m,n)*binary64_epsilon*sigma_max; no new SVD or refit.','binary64_epsilon':sys.float_info.epsilon,'tolerance':rank_tolerance,'rank_at_tolerance':sum(s>rank_tolerance for s in singular),'singular_values_archived':singular,'kernel_check_absolute_tolerance':1e-15,'kernel_check_max_absolute_residual':max(abs(x)for x in residual)},
       'nonzero_singular_value_ratio':singular[0]/singular[1],'interpretation':'With this fixed two-ring operator, eta and eta+t*n have the same predicted two-ring vector. This is a structural ambiguity, not a parameter fit or physical amplitude estimate.',
       'nuisance_adjusted_rank_computed':False,'nuisance_information_condition':'A^T (I - B B^+) A with A=Sigma^(-1/2)K, B=Sigma^(-1/2)N, positive-definite Sigma; N and Sigma must be justified from measurement, not chosen by significance.',
       'additional_response_condition':'A new response row k must satisfy k*n != 0 and retain independent information after instrument projection and nuisance adjustment.','physical_lorentz_kernel_equivalence_proved':False,
       'historical_deterministic_primary':m33['deterministic_primary'],'historical_covariance_scenarios':m33['covariance_scenarios']}}
    write(out/'PHYSICAL_CONTRACT_AUDIT.json',result_out)
    print(json.dumps({'files_searched':len(files),'archives':len(archives),'code_matches':len(code_matches),'future_training_folds':result_out['solar']['folds_with_future_training_sources'],'local_wins':result_out['solar']['local_wins'],'M33_null_direction':n,'max_null_residual':max(abs(x)for x in residual)},ensure_ascii=False))

if __name__=='__main__':main()
