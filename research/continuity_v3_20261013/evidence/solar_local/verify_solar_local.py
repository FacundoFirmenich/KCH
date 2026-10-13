"""Independent stdlib verifier for exhaustive solar tables; no diagnostic imports.
Predictions are rebuilt from the frozen result. All diagnostic table cells are checked.
"""
from pathlib import Path
from collections import defaultdict
import argparse,csv,hashlib,json,math

T0='T0_TRIVIAL_IDENTITY';H='H_HELICAL_TRANSLATION';L='L_LEMNISCATIC_ALTERNATING'
MODELS=[T0,'M_MOBIUS_SIGN',H,L,'G_ACTIVITY_AFFINE']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def mean(vals):return math.fsum(vals)/len(vals)
def sign(v):return int(v>0)-int(v<0)
def table(p):
    with p.open(newline='') as f:return list(csv.DictReader(f))
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--diagnostic',type=Path,required=True);a=ap.parse_args();d=a.diagnostic;diag=json.loads((d/'SOLAR_LOCAL_DIAGNOSTIC.json').read_text());checks=0;maxdiff=0.;group_checks=0
    def numeric(x,y):
        nonlocal checks,maxdiff
        x=float(x);y=float(y);diff=abs(x-y);assert math.isclose(x,y,rel_tol=1e-10,abs_tol=1e-12),(x,y);checks+=1;maxdiff=max(maxdiff,diff)
    for path,digest in diag['source_files'].items():assert sha(a.repo/path)==digest
    for name,digest in diag['output_hashes'].items():assert sha(d/name)==digest
    assert sha(d/'PRECALCULATION_SCOPE_ES.md')==diag['precalculation_scope_sha256'];assert sha(d/'diagnose_solar_v16.py')==diag['script_sha256']
    result_path=a.repo/'research/continuity_v2_20261013/evidence/solar/TEMPORAL_LIFT_DEVELOPMENT_RESULT_V1_6.json';r=json.loads(result_path.read_text());body=dict(r);receipt=body.pop('receipt_id');canonical=json.dumps(body,sort_keys=True,separators=(',',':'),allow_nan=False);assert receipt=='h16lift:'+hashlib.sha256(canonical.encode()).hexdigest()
    assert r['outcome']==diag['outcome_preserved']=='NO_DEVELOPMENT_DOMINANT_LIFT';assert not r['dominance_rule_pass'];assert not diag['scientific_confirmation']
    replay=json.loads((d/'REEXECUTED_V2_60_CHECKS.json').read_text());previous=json.loads((a.repo/'research/continuity_v2_20261013/evidence/solar/INDEPENDENT_REPLAY.json').read_text());assert len(replay['numeric_checks'])==60;assert all(v['pass'] for v in replay['numeric_checks']);assert {v['label'] for v in replay['numeric_checks']}=={v['label'] for v in previous['numeric_checks']};assert replay['result_sha256']==sha(result_path)
    traj={t['harp']:t for t in r['trajectories']};folds={f['held_out_harp']:f for f in r['fold_results']};gold={};nmses=defaultdict(list);nmaes=defaultdict(list)
    for harp,t in traj.items():
        f=folds[harp]
        for k in range(4):
            left,right=t['snapshots'][k:k+2];dq=mean([(right['activity_control_log'][j]-f['activity_train_mean'][j])/f['activity_train_sd'][j] for j in range(4)])-mean([(left['activity_control_log'][j]-f['activity_train_mean'][j])/f['activity_train_sd'][j] for j in range(4)])
            for j,name in enumerate(r['fiber_names']):
                x,y,s=left['fiber'][j],right['fiber'][j],f['fiber_train_rms_scale'][j]
                preds={T0:x,'M_MOBIUS_SIGN':-x,H:x+f['helical_b'][j],L:x+(-1)**k*f['lemniscatic_b'][j],'G_ACTIVITY_AFFINE':(f['generic_common_a']*x/s+f['generic_common_c']*dq+f['generic_component_intercepts'][j])*s}
                for model,p in preds.items():
                    e=(p-y)/s;ie=(x-y)/s;corr=(p-x)/s;delta=(y-x)/s;v={'x':x,'y':y,'prediction':p,'train_target_rms':s,'normalized_error':e,'squared_error':e*e,'absolute_error':abs(e),'identity_squared_error':ie*ie,'identity_absolute_error':abs(ie),'nmse_gain_vs_identity':ie*ie-e*e,'nmae_gain_vs_identity':abs(ie)-abs(e),'alignment_credit':2*delta*corr,'correction_cost':corr*corr};gold[(harp,k,j,model)]=v
                    nmses[(harp,model)].append(e*e);nmaes[(harp,model)].append(abs(e))
    rows=table(d/'CELLS_ALL_960.csv');assert len(rows)==len(gold)==960;seen=set()
    for row in rows:
        key=(int(row['harp']),int(row['transition_k']),int(row['component_index']),row['model']);assert key in gold and key not in seen;seen.add(key);name=r['fiber_names'][key[2]];assert row['component']==name
        family,scale=(name.split('@sigma=') if '@sigma=' in name else (name,'cross_scale'));assert row['family']==family and row['scale']==scale
        for col,value in gold[key].items():numeric(row[col],value)
        numeric(row['nmse_gain_vs_identity'],float(row['alignment_credit'])-float(row['correction_cost']))
    assert seen==set(gold)
    levels={'global':[],'harp':['harp'],'transition':['harp','transition_k'],'scale':['scale'],'family':['family'],'component':['component'],'harp_scale':['harp','scale'],'harp_family':['harp','family'],'harp_component':['harp','component'],'transition_scale':['harp','transition_k','scale'],'transition_family':['harp','transition_k','family']};groups={}
    for level,dims in levels.items():
        grouped=defaultdict(list)
        for row in rows:grouped[tuple(row[x] for x in dims)+(row['model'],)].append(row)
        for key,v in grouped.items():groups[(level,key)]=v
    aggregates=table(d/'AGGREGATES_ALL_1200.csv');assert len(aggregates)==len(groups)==1200;seen_groups=set()
    for row in aggregates:
        level=row['level'];dims=levels[level];key=(level,tuple(row[x] for x in dims)+(row['model'],));assert key in groups and key not in seen_groups;seen_groups.add(key);rr=groups[key];nmse=mean([float(c['squared_error']) for c in rr]);nmae=mean([float(c['absolute_error']) for c in rr]);idmse=mean([float(c['identity_squared_error']) for c in rr]);idmae=mean([float(c['identity_absolute_error']) for c in rr]);gain=idmse-nmse
        expected={'component_transition_cells':len(rr),'harps':len({c['harp'] for c in rr}),'transitions':len({(c['harp'],c['transition_k']) for c in rr}),'components':len({c['component'] for c in rr}),'nmse':nmse,'nmae':nmae,'identity_nmse':idmse,'identity_nmae':idmae,'nmse_gain_vs_identity':gain,'relative_nmse_gain_percent':100*gain/idmse,'nmae_gain_vs_identity':idmae-nmae,'mean_alignment_credit':mean([float(c['alignment_credit']) for c in rr]),'mean_correction_cost':mean([float(c['correction_cost']) for c in rr]),'share_of_192_cells':len(rr)/192,'contribution_to_global_nmse':nmse*len(rr)/192,'contribution_to_global_nmse_gain':gain*len(rr)/192,'cells_better_than_identity':sum(float(c['nmse_gain_vs_identity'])>1e-12*max(1,float(c['identity_squared_error']),float(c['squared_error'])) for c in rr),'cells_worse_than_identity':sum(float(c['nmse_gain_vs_identity']) < -1e-12*max(1,float(c['identity_squared_error']),float(c['squared_error'])) for c in rr)}
        for col,value in expected.items():numeric(row[col],value)
        group_checks+=1
    assert seen_groups==set(groups)
    for (harp,model),vals in nmses.items():numeric(mean(vals),folds[harp]['scores'][model]['nmse']);numeric(mean(nmaes[(harp,model)]),folds[harp]['scores'][model]['nmae'])
    for model in MODELS:
        numeric(mean([mean(nmses[(h,model)]) for h in traj]),r['global_scores'][model]['mean_nmse']);numeric(mean([mean(nmaes[(h,model)]) for h in traj]),r['global_scores'][model]['mean_nmae'])
    trainmeans={};deltas={h:[[t['snapshots'][k+1]['fiber'][j]-t['snapshots'][k]['fiber'][j] for j in range(16)] for k in range(4)] for h,t in traj.items()}
    for harp in traj:
        for model in [H,L]:
            for j in range(16):
                for th in traj:
                    if th!=harp:trainmeans[(harp,model,j,th)]=mean([deltas[th][k][j]*(1 if model==H else (-1)**k) for k in range(4)])
    for name,count in [('TRAIN_HARP_CONTRIBUTIONS_ALL_192.csv',192),('TRAIN_TRANSITION_INFLUENCE_ALL_768.csv',768),('TRAIN_PARAMETERS_H_L_ALL_96.csv',96)]:
        rr=table(d/name);assert len(rr)==count;keys=set()
        for row in rr:
            harp=int(row['held_out_harp']);j=int(row['component_index']);model=row['model'];assert row['component']==r['fiber_names'][j];b=folds[harp]['helical_b' if model==H else 'lemniscatic_b'][j];s=folds[harp]['fiber_train_rms_scale'][j];train=[t for t in traj if t!=harp];assert len(train)==2
            if name.startswith('TRAIN_HARP'):
                th=int(row['training_harp']);assert th in train;other=next(t for t in train if t!=th);tm=trainmeans[(harp,model,j,th)];remaining=trainmeans[(harp,model,j,other)];key=(harp,model,j,th)
                for col,v in {'training_harp_signed_delta_mean':tm,'contribution_to_frozen_b':tm/2,'frozen_b':b,'remaining_b_if_this_training_harp_removed':remaining,'parameter_shift_normalized':(remaining-b)/s,'frozen_b_sign':sign(b)}.items():numeric(row[col],v)
                assert row['sign_changes_if_harp_removed']==str(sign(remaining)!=sign(b))
            elif name.startswith('TRAIN_TRANSITION'):
                th=int(row['training_harp']);k=int(row['training_transition_k']);assert th in train and 0<=k<4;w=1 if model==H else (-1)**k;delta=deltas[th][k][j];remaining=(8*b-w*delta)/7;key=(harp,model,j,th,k)
                for col,v in {'raw_observed_delta':delta,'phase_weight':w,'weighted_delta':w*delta,'contribution_to_frozen_b':w*delta/8,'db_d_raw_delta':w/8,'frozen_b':b,'remaining_b_if_transition_removed':remaining,'parameter_shift_normalized':(remaining-b)/s}.items():numeric(row[col],v)
                assert row['sign_changes_if_transition_removed']==str(sign(remaining)!=sign(b))
            else:
                key=(harp,model,j);u=[deltas[th][k][j]*(1 if model==H else (-1)**k) for th in train for k in range(4)];alignment=mean([2*deltas[harp][k][j]/s*(1 if model==H else (-1)**k)*b/s for k in range(4)]);cost=(b/s)**2
                for col,v in {'b_frozen':b,'b_from_snapshot_formula':sum(sum(traj[th]['snapshots'][k]['fiber'][j]*([-1,0,0,0,1] if model==H else [-1,2,-2,2,-1])[k] for k in range(5)) for th in train)/8,'b_sign':sign(b),'train_target_rms':s,'b_normalized':b/s,'training_transitions':8,'positive_training_signed_deltas':sum(x>0 for x in u),'negative_training_signed_deltas':sum(x<0 for x in u),'zero_training_signed_deltas':sum(x==0 for x in u),'coherence_abs_sum_over_sum_abs':abs(math.fsum(u))/math.fsum([abs(x) for x in u]),'heldout_alignment_credit':alignment,'heldout_correction_cost':cost,'heldout_nmse_gain':alignment-cost}.items():numeric(row[col],v)
                numeric(mean(u),b);assert row['training_harp_means_opposite_sign']==str(trainmeans[(harp,model,j,train[0])]*trainmeans[(harp,model,j,train[1])]<0)
            assert key not in keys;keys.add(key)
    snaprows=table(d/'SNAPSHOT_COVERAGE_ALL_15.csv');assert len(snaprows)==15;assert {(int(v['harp']),v['time_tai']) for v in snaprows}=={(h,s['requested_time_tai']) for h,t in traj.items() for s in t['snapshots']};assert all(v['quality']=='0' and v['all_components_finite']=='True' and v['native_reconciliation_pass']=='True' for v in snaprows)
    transitionrows=table(d/'TRANSITIONS_ALL_12.csv');assert len(transitionrows)==12;assert {(int(v['harp']),int(v['transition_k'])) for v in transitionrows}=={(h,k) for h in traj for k in range(4)}
    for row in transitionrows:
        h=int(row['harp']);k=int(row['transition_k']);f=folds[h];left,right=traj[h]['snapshots'][k:k+2];ql=mean([(v-u)/s for v,u,s in zip(left['activity_control_log'],f['activity_train_mean'],f['activity_train_sd'])]);qr=mean([(v-u)/s for v,u,s in zip(right['activity_control_log'],f['activity_train_mean'],f['activity_train_sd'])])
        for col,val in {'phase_L':(-1)**k,'activity_q_left':ql,'activity_q_right':qr,'activity_delta_q':qr-ql,'generic_a':f['generic_common_a'],'generic_c':f['generic_common_c'],'generic_c_times_delta_q':f['generic_common_c']*(qr-ql)}.items():numeric(row[col],val)
        assert row['time_left_tai']==left['requested_time_tai'] and row['time_right_tai']==right['requested_time_tai']
    derivative_rows=table(d/'TRAIN_SNAPSHOT_DERIVATIVES_ALL_60.csv');assert len(derivative_rows)==60;seen_derivatives=set()
    for row in derivative_rows:
        h=int(row['held_out_harp']);th=int(row['training_harp']);k=int(row['training_snapshot_index']);m=row['model'];assert h in traj and th in traj and h!=th and 0<=k<5 and m in [H,L];key=(h,m,th,k);assert key not in seen_derivatives;seen_derivatives.add(key);numeric(row['db_j_d_training_x_j'],([-1,0,0,0,1] if m==H else [-1,2,-2,2,-1])[k]/8);numeric(row['cross_component_derivative'],0);assert row['time_tai']==traj[th]['snapshots'][k]['requested_time_tai']
    report={'analytic_snapshot_derivative_rows_verified':60,'format':'KCH_SOLAR_LOCAL_STDLIB_VERIFICATION_V1','status':'PASS','diagnostic_sha256':sha(d/'SOLAR_LOCAL_DIAGNOSTIC.json'),'verifier_sha256':sha(Path(__file__)),'original_replay_numeric_checks':60,'frozen_prediction_cells_verified':960,'exhaustive_aggregate_rows_verified':group_checks,'numeric_comparisons_passed':checks,'max_absolute_float_difference':maxdiff,'source_result_receipt':receipt,'independent_from_diagnostic_module':True,'production_or_diagnostic_imports':False,'new_observations':0,'outcome_preserved':r['outcome']};(d/'SOLAR_LOCAL_VERIFICATION.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
    if not __debug__:raise RuntimeError('Assertions must be enabled')
    main()
