"""Exhaustive post-hoc decomposition of frozen real solar v1.6 aggregates.
No production runtime import, no data acquisition, no modified model predictions.
"""
from pathlib import Path
from collections import defaultdict
import argparse, csv, hashlib, json, math, subprocess, sys
import numpy as np

MODELS=['T0_TRIVIAL_IDENTITY','M_MOBIUS_SIGN','H_HELICAL_TRANSLATION','L_LEMNISCATIC_ALTERNATING','G_ACTIVITY_AFFINE']
T0,H,L=MODELS[0],MODELS[2],MODELS[3]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,d): p.write_text(json.dumps(d,indent=2,sort_keys=True,allow_nan=False)+'\n')
def writecsv(p, rows):
    with p.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def mean(x): return math.fsum(x)/len(x)
def sign(x): return int(x>0)-int(x<0)
def dimensions(name):
    if '@sigma=' in name:
        fam,s=name.split('@sigma=');return fam,str(float(s))
    return name,'cross_scale'
def close(a,b):
    assert np.allclose(a,b,rtol=1e-10,atol=1e-12),(a,b)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();out=a.out;out.mkdir(parents=True,exist_ok=True)
    source=a.repo/'research/continuity_v2_20261013/evidence/solar';runtime=a.repo/'.github/helical_v16';v2=a.repo/'research/continuity_v2_20261013/tools/verify_solar_v16.py'
    scope=out/'PRECALCULATION_SCOPE_ES.md';assert scope.is_file()
    rp=source/'TEMPORAL_LIFT_DEVELOPMENT_RESULT_V1_6.json';r=json.loads(rp.read_text());assert r['outcome']=='NO_DEVELOPMENT_DOMINANT_LIFT' and r['scientific_confirmation'] is False
    replay=out/'REEXECUTED_V2_60_CHECKS.json'
    subprocess.run([sys.executable,str(v2),'--metadata',str(source/'METADATA_SELECTION.json'),'--result',str(rp),'--protocol',str(runtime/'TEMPORAL_PROTOCOL_V1_6.json'),'--output',str(replay)],check=True,stdout=subprocess.DEVNULL)
    checked=json.loads(replay.read_text());assert checked['status']=='FULL_SELECTION_AND_AGGREGATE_REPLAY_PASS';assert len(checked['numeric_checks'])==60 and all(c['pass'] for c in checked['numeric_checks'])
    names=r['fiber_names'];assert len(names)==16;trajs=r['trajectories'];assert len(trajs)==3 and all(len(t['snapshots'])==5 for t in trajs)
    cells=[];transitions=[];snapshots=[];pars=[];harpcon=[];influence=[];snapshot_derivatives=[]
    for test in trajs:
        harp=test['harp'];fold=next(f for f in r['fold_results'] if f['held_out_harp']==harp);train=[t for t in trajs if t['harp']!=harp];scale=np.array(fold['fiber_train_rms_scale']);mu=np.array(fold['activity_train_mean']);sd=np.array(fold['activity_train_sd']);hb=np.array(fold['helical_b']);lb=np.array(fold['lemniscatic_b'])
        assert set(fold['train_trajectories'])=={t['trajectory_id'] for t in train}
        deltas={t['harp']:np.diff(np.array([s['fiber'] for s in t['snapshots']]),axis=0) for t in trajs};sg=np.array([1,-1,1,-1]);td=deltas[harp]
        train_activity=np.array([s['activity_control_log'] for t in train for s in t['snapshots']]);close(train_activity.mean(0),mu);close(np.maximum(train_activity.std(0),1e-12),sd)
        for s in test['snapshots']:
            snapshots.append({'harp':harp,'time_tai':s['requested_time_tai'],'quality':s['record']['QUALITY'],'mask_pixels':s['mask_pixels'],'CMASK':s['record']['CMASK'],'components':len(s['fiber']),'all_components_finite':bool(np.isfinite(s['fiber']).all()),'native_reconciliation_pass':s['native_reconciliation']['pass']})
        for model,b,weights in [(H,hb,np.ones(4)),(L,lb,sg)]:
            train_u={t['harp']:deltas[t['harp']]*weights[:,None] for t in train};u=np.concatenate(list(train_u.values()));close(u.mean(0),b)
            for training_t in train:
                ww=[-1,0,0,0,1] if model==H else [-1,2,-2,2,-1]
                for tindex,w in enumerate(ww):
                    snapshot_derivatives.append({'held_out_harp':harp,'model':model,'training_harp':training_t['harp'],'training_snapshot_index':tindex,'time_tai':training_t['snapshots'][tindex]['requested_time_tai'],'db_j_d_training_x_j':w/8,'cross_component_derivative':0,'holds_for_each_of_16_components':True,'analytic_frozen_fit_sensitivity':True})
            b_endpoint=sum(np.sum(np.array([s['fiber'] for s in t['snapshots']])*np.array(ww)[:,None],axis=0) for t in train)/8
            close(b_endpoint,b)
            for j,name in enumerate(names):
                family,sigma=dimensions(name);trainmeans={h:float(v[:,j].mean()) for h,v in train_u.items()};align=2*np.mean(td[:,j]/scale[j]*weights*b[j]/scale[j]);cost=(b[j]/scale[j])**2;gain=align-cost;den=float(np.abs(u[:,j]).sum())
                pars.append({'held_out_harp':harp,'model':model,'component_index':j,'component':name,'family':family,'scale':sigma,'b_frozen':float(b[j]),'b_from_snapshot_formula':float(b_endpoint[j]),'b_sign':sign(b[j]),'train_target_rms':float(scale[j]),'b_normalized':float(b[j]/scale[j]),'training_harps':';'.join(str(t['harp']) for t in train),'training_transitions':8,'positive_training_signed_deltas':int((u[:,j]>0).sum()),'negative_training_signed_deltas':int((u[:,j]<0).sum()),'zero_training_signed_deltas':int((u[:,j]==0).sum()),'training_harp_means_opposite_sign':bool(np.prod(list(trainmeans.values()))<0),'coherence_abs_sum_over_sum_abs':float(abs(u[:,j].sum())/den) if den else 0.0,'heldout_alignment_credit':float(align),'heldout_correction_cost':float(cost),'heldout_nmse_gain':float(gain)})
                for h,v in train_u.items():
                    hh=list(train_u);other=hh[1] if h==hh[0] else hh[0];removed=trainmeans[other];shift=removed-b[j]
                    harpcon.append({'held_out_harp':harp,'model':model,'component_index':j,'component':name,'training_harp':h,'training_harp_signed_delta_mean':trainmeans[h],'contribution_to_frozen_b':trainmeans[h]/2,'frozen_b':float(b[j]),'frozen_b_sign':sign(b[j]),'remaining_b_if_this_training_harp_removed':removed,'parameter_shift_normalized':float(shift/scale[j]),'sign_changes_if_harp_removed':sign(removed)!=sign(b[j]),'diagnostic_only_not_used_for_predictions':True})
                    for k in range(4):
                        remaining=float((8*b[j]-v[k,j])/7);shift=remaining-b[j]
                        influence.append({'held_out_harp':harp,'model':model,'component_index':j,'component':name,'training_harp':h,'training_transition_k':k,'raw_observed_delta':float(deltas[h][k,j]),'phase_weight':float(weights[k]),'weighted_delta':float(v[k,j]),'contribution_to_frozen_b':float(v[k,j]/8),'db_d_raw_delta':float(weights[k]/8),'frozen_b':float(b[j]),'remaining_b_if_transition_removed':remaining,'parameter_shift_normalized':float(shift/scale[j]),'sign_changes_if_transition_removed':sign(remaining)!=sign(b[j]),'diagnostic_only_not_used_for_predictions':True})
        for k in range(4):
            left,right=test['snapshots'][k:k+2];x=np.array(left['fiber']);y=np.array(right['fiber']);ql=float(((np.array(left['activity_control_log'])-mu)/sd).mean());qr=float(((np.array(right['activity_control_log'])-mu)/sd).mean());dq=qr-ql
            predictions={T0:x,MODELS[1]:-x,H:x+hb,L:x+sg[k]*lb,MODELS[4]:(fold['generic_common_a']*x/scale+fold['generic_common_c']*dq+np.array(fold['generic_component_intercepts']))*scale}
            transitions.append({'harp':harp,'transition_k':k,'time_left_tai':left['requested_time_tai'],'time_right_tai':right['requested_time_tai'],'phase_L':int(sg[k]),'activity_q_left':ql,'activity_q_right':qr,'activity_delta_q':dq,'generic_a':fold['generic_common_a'],'generic_c':fold['generic_common_c'],'generic_c_times_delta_q':fold['generic_common_c']*dq,'activity_endpoint_used':True,'normalization_training_harps':';'.join(str(t['harp']) for t in train)})
            for model,pred in predictions.items():
                err=(pred-y)/scale;identity=(x-y)/scale
                for j,name in enumerate(names):
                    family,sigma=dimensions(name);corr=(pred[j]-x[j])/scale[j];delta=(y[j]-x[j])/scale[j]
                    cells.append({'harp':harp,'transition_k':k,'component_index':j,'component':name,'family':family,'scale':sigma,'model':model,'x':float(x[j]),'y':float(y[j]),'prediction':float(pred[j]),'train_target_rms':float(scale[j]),'normalized_error':float(err[j]),'squared_error':float(err[j]**2),'absolute_error':float(abs(err[j])),'identity_squared_error':float(identity[j]**2),'identity_absolute_error':float(abs(identity[j])),'nmse_gain_vs_identity':float(identity[j]**2-err[j]**2),'nmae_gain_vs_identity':float(abs(identity[j])-abs(err[j])),'alignment_credit':float(2*delta*corr),'correction_cost':float(corr*corr)})
    levels={'global':[],'harp':['harp'],'transition':['harp','transition_k'],'scale':['scale'],'family':['family'],'component':['component'],'harp_scale':['harp','scale'],'harp_family':['harp','family'],'harp_component':['harp','component'],'transition_scale':['harp','transition_k','scale'],'transition_family':['harp','transition_k','family']}
    aggregates=[]
    for level,dims in levels.items():
        groups=defaultdict(list)
        for c in cells:groups[tuple(c[d] for d in dims)+ (c['model'],)].append(c)
        for key,rr in groups.items():
            d={k:'' for k in ['harp','transition_k','scale','family','component']};d.update(dict(zip(dims,key[:-1])));nmse=mean([c['squared_error'] for c in rr]);nmae=mean([c['absolute_error'] for c in rr]);idmse=mean([c['identity_squared_error'] for c in rr]);idmae=mean([c['identity_absolute_error'] for c in rr]);gain=idmse-nmse
            aggregates.append({'level':level,**d,'model':key[-1],'component_transition_cells':len(rr),'harps':len({c['harp'] for c in rr}),'transitions':len({(c['harp'],c['transition_k']) for c in rr}),'components':len({c['component'] for c in rr}),'nmse':nmse,'nmae':nmae,'identity_nmse':idmse,'identity_nmae':idmae,'nmse_gain_vs_identity':gain,'relative_nmse_gain_percent':100*gain/idmse if idmse else None,'nmae_gain_vs_identity':idmae-nmae,'mean_alignment_credit':mean([c['alignment_credit'] for c in rr]),'mean_correction_cost':mean([c['correction_cost'] for c in rr]),'share_of_192_cells':len(rr)/192,'contribution_to_global_nmse':nmse*len(rr)/192,'contribution_to_global_nmse_gain':gain*len(rr)/192,'cells_better_than_identity':sum(c['nmse_gain_vs_identity']>1e-12*max(1,c['identity_squared_error'],c['squared_error']) for c in rr),'cells_worse_than_identity':sum(c['nmse_gain_vs_identity'] < -1e-12*max(1,c['identity_squared_error'],c['squared_error']) for c in rr)})
    expected_counts={'global':5,'harp':15,'transition':60,'scale':30,'family':20,'component':80,'harp_scale':90,'harp_family':60,'harp_component':240,'transition_scale':360,'transition_family':240}
    assert len(cells)==960 and len(pars)==96 and len(harpcon)==192 and len(influence)==768
    for level,num in expected_counts.items():assert sum(v['level']==level for v in aggregates)==num
    for row in aggregates:
        close(row['nmse_gain_vs_identity'],row['mean_alignment_credit']-row['mean_correction_cost'])
        if row['level']=='global':close([row['nmse'],row['nmae']],[r['global_scores'][row['model']]['mean_nmse'],r['global_scores'][row['model']]['mean_nmae']])
    files={'CELLS_ALL_960.csv':cells,'AGGREGATES_ALL_1200.csv':aggregates,'SNAPSHOT_COVERAGE_ALL_15.csv':snapshots,'TRANSITIONS_ALL_12.csv':transitions,'TRAIN_PARAMETERS_H_L_ALL_96.csv':pars,'TRAIN_HARP_CONTRIBUTIONS_ALL_192.csv':harpcon,'TRAIN_TRANSITION_INFLUENCE_ALL_768.csv':influence,'TRAIN_SNAPSHOT_DERIVATIVES_ALL_60.csv':snapshot_derivatives}
    for name,data in files.items():writecsv(out/name,data)
    globalrows=[x for x in aggregates if x['level']=='global'];harprows=[x for x in aggregates if x['level']=='harp'];scalerows=[x for x in aggregates if x['level']=='scale'];familyrows=[x for x in aggregates if x['level']=='family'];transitionrows=[x for x in aggregates if x['level']=='transition']
    diag={'format':'KCH_SOLAR_V16_EXHAUSTIVE_LOCAL_DIAGNOSTIC_V1','scope':'POST_HOC_DESCRIPTIVE_FROZEN_PARAMETERS_NO_GATE_CHANGE','scientific_confirmation':False,'development_only':True,'outcome_preserved':r['outcome'],'dominance_rule_pass_preserved':r['dominance_rule_pass'],'source_result_receipt':r['receipt_id'],'source_files':{str(p.relative_to(a.repo)):sha(p) for p in [rp,source/'METADATA_SELECTION.json',source/'SELECTED_PROTOCOL_V1_6.json',source/'INDEPENDENT_REPLAY.json',runtime/'TEMPORAL_PROTOCOL_V1_6.json',v2]},'precalculation_scope_sha256':sha(scope),'script_sha256':sha(Path(__file__)),'coverage':{'harps':3,'snapshots':15,'transitions':12,'components':16,'models':5,'raw_cells':960,'aggregate_rows':1200,'aggregate_level_rows':expected_counts,'training_parameter_rows':96,'training_harp_contribution_rows':192,'training_transition_influence_rows':768,'analytic_snapshot_derivative_rows':60,'original_replay_numeric_checks_passed':60,'missing_cells':0,'new_observations':0},'global_scores':globalrows,'harp_scores':harprows,'scale_scores':scalerows,'family_scores':familyrows,'transition_scores':transitionrows,'H_L_diagnostics':[],'limitations':['Three development HARPs; no independent confirmation.','Components and scales share source fields; transitions share endpoints; counts are descriptive and not independent replicates.','Selected metadata windows are conditioned on quality/support; original v1.5 remains insufficient.','G uses endpoint activity; not ex ante forecasting.','H/L/M labels are operational transformations, not demonstrations or refutations of physical topological classes.','Deletion sensitivities describe frozen coefficients; no altered-coefficient predictions were scored.','Scale and family marginals overlap; do not sum across different aggregation levels.']}
    for harp in [t['harp'] for t in trajs]:
        for model in [H,L]:
            pp=[p for p in pars if p['held_out_harp']==harp and p['model']==model];cc=[p for p in harpcon if p['held_out_harp']==harp and p['model']==model];ii=[p for p in influence if p['held_out_harp']==harp and p['model']==model];ss=next(x for x in harprows if x['harp']==harp and x['model']==model)
            diag['H_L_diagnostics'].append({'held_out_harp':harp,'model':model,'frozen_b_positive_components':sum(p['b_sign']>0 for p in pp),'frozen_b_negative_components':sum(p['b_sign']<0 for p in pp),'opposite_training_harp_means_components':sum(p['training_harp_means_opposite_sign'] for p in pp),'sign_changes_removing_one_training_harp_cases_of_32':sum(p['sign_changes_if_harp_removed'] for p in cc),'sign_changes_removing_one_training_transition_cases_of_128':sum(p['sign_changes_if_transition_removed'] for p in ii),'max_absolute_normalized_parameter_change_removing_harp':max(abs(p['parameter_shift_normalized']) for p in cc),'mean_alignment_credit':ss['mean_alignment_credit'],'mean_correction_cost':ss['mean_correction_cost'],'mean_nmse_gain':ss['nmse_gain_vs_identity']})
    diag['output_hashes']={n:sha(out/n) for n in files};diag['output_hashes'][replay.name]=sha(replay);dump(out/'SOLAR_LOCAL_DIAGNOSTIC.json',diag)
    print(json.dumps({'coverage':diag['coverage'],'H_L_diagnostics':diag['H_L_diagnostics'],'global':[{'model':g['model'],'nmse':g['nmse'],'gain_percent':g['relative_nmse_gain_percent']} for g in globalrows]},indent=2))
if __name__=='__main__':main()
