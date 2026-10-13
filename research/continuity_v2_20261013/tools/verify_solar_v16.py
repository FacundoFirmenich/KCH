"""Independent selection and aggregate replay; no production runtime imports or data generation."""
from pathlib import Path
from datetime import datetime,timedelta
import argparse,hashlib,json,math
import numpy as np

def canonical(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--metadata',type=Path,required=True);ap.add_argument('--result',type=Path);ap.add_argument('--protocol',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    p=json.loads(a.protocol.read_text());m=json.loads(a.metadata.read_text());body=dict(m);rid=body.pop('receipt_id');assert rid=='h16meta:'+canonical(body);assert m['protocol_sha256']==sha(a.protocol)
    FMT='%Y.%m.%d_%H:%M:%S_TAI';checks=[]
    for orig,h in zip(p['original_trajectories'],m['harps']):
        assert orig['harp']==h['harp'];index={}
        for row in h['records']:index.setdefault(row['T_REC'],[]).append(row)
        base=datetime.strptime(orig['times_tai'][0],FMT);eligible=[]
        offsets=sorted(range(-360,361,12),key=lambda x:(abs(x),x))
        for delta in offsets:
            times=[(base+timedelta(minutes=delta+360*k)).strftime(FMT) for k in range(5)]
            valid=True
            for ts in times:
                rows=index.get(ts,[])
                if len(rows)!=1:valid=False;continue
                r=rows[0]
                valid &= (r['HARPNUM']==orig['harp'] and r['QUALITY']==0 and r['CMASK'] is not None and r['CMASK']>=1000 and all(isinstance(v,str) and v.startswith('/') for v in r['segments'].values()) and set(r['segments'])==set(p['metadata_selection']['segments']))
            if valid:eligible.append((delta,times))
        if eligible:assert h['selected']['start_offset_minutes']==eligible[0][0] and h['selected']['times_tai']==eligible[0][1]
        else:assert h['selected'] is None
        checks.append({'harp':orig['harp'],'eligible_candidates':len(eligible),'selected_offset_minutes':eligible[0][0] if eligible else None,'selection_verified':True})
    out={'format':'KCH_INDEPENDENT_SOLAR_V16_REPLAY_V1','metadata_sha256':sha(a.metadata),'metadata_selection_verified':checks,'development_only':True,'scientific_confirmation':False,'endpoint_activity_used':True,'interpretation':'CONDITIONAL_TRANSITION_RECONSTRUCTION_NOT_EX_ANTE_FORECAST','numeric_checks':[]}
    if a.result:
        r=json.loads(a.result.read_text());b=dict(r);rid=b.pop('receipt_id');assert rid=='h16lift:'+canonical(b);assert r['metadata_selection_receipt']==m['receipt_id'];assert r['fresh_2026_holdout_accessed'] is False and r['flare_outcomes_accessed'] is False
        out.update(result_sha256=sha(a.result),reported_outcome=r['outcome'])
        traj=r['trajectories'];allowed={(t['harp'],ts) for t in m['selected_trajectories'] for ts in t['times_tai']}
        for t in traj:
            for s in t['snapshots']:
                assert (s['harp'],s['requested_time_tai']) in allowed
                assert s['record']['HARPNUM']==s['harp'] and s['record']['T_REC']==s['requested_time_tai'] and s['record']['QUALITY']==0
        def close(label,x,y):
            xx=np.asarray(x);yy=np.asarray(y);assert np.allclose(xx,yy,rtol=1e-10,atol=1e-12),(label,x,y)
            out['numeric_checks'].append({'label':label,'max_abs_difference':float(np.max(np.abs(xx-yy))),'pass':True})
        if r['outcome']=='INSUFFICIENT_TEMPORAL_SUPPORT':
            assert r['source_failures'] or r['numerical_failures'] or any(len(t['snapshots'])!=5 for t in traj)
            out['status']='SELECTION_AND_VALID_INSUFFICIENT_SUPPORT_RECEIPT_VERIFIED'
        else:
            assert len(traj)==3 and all(len(t['snapshots'])==5 for t in traj)
            models=list(p['operational_transport_rivals']);scores={n:[] for n in models};wins={n:0 for n in models}
            def winner(d):
                q=sorted(d,key=lambda n:(d[n],n));return q[0] if abs(d[q[1]]-d[q[0]])>1e-12*max(abs(d[q[0]]),abs(d[q[1]]),1) else None
            for test in traj:
                train=[t for t in traj if t['harp']!=test['harp']]
                log=np.array([s['activity_control_log'] for t in train for s in t['snapshots']]);mu=log.mean(0);sd=np.maximum(log.std(0),1e-12)
                def matrices(ts):
                    x=[];y=[];dq=[];sg=[]
                    for t in ts:
                        for k in range(4):
                            l,rr=t['snapshots'][k:k+2];x.append(l['fiber']);y.append(rr['fiber']);dq.append(np.mean((np.array(rr['activity_control_log'])-mu)/sd)-np.mean((np.array(l['activity_control_log'])-mu)/sd));sg.append((-1)**k)
                    return np.array(x),np.array(y),np.array(dq),np.array(sg)
                x,y,dq,sg=matrices(train);tx,ty,tdq,tsg=matrices([test]);scale=np.maximum(np.sqrt((y*y).mean(0)),1e-12);hb=(y-x).mean(0);lb=(sg[:,None]*(y-x)).mean(0)
                design=np.column_stack([(x/scale).ravel(),np.repeat(dq,16),np.tile(np.eye(16),(len(x),1))]);rank=np.linalg.matrix_rank(design);condition=np.linalg.cond(design);assert rank==18 and condition<=1e8
                beta=np.linalg.lstsq(design,(y/scale).ravel(),rcond=None)[0]
                pred={'T0_TRIVIAL_IDENTITY':tx,'M_MOBIUS_SIGN':-tx,'H_HELICAL_TRANSLATION':tx+hb,'L_LEMNISCATIC_ALTERNATING':tx+tsg[:,None]*lb,'G_ACTIVITY_AFFINE':(beta[0]*tx/scale+beta[1]*tdq[:,None]+beta[2:])*scale}
                fold=next(f for f in r['fold_results'] if f['held_out_harp']==test['harp']);assert set(fold['train_trajectories'])=={t['trajectory_id'] for t in train}
                for label,actual in [('activity_train_mean',mu),('activity_train_sd',sd),('fiber_train_rms_scale',scale),('helical_b',hb),('lemniscatic_b',lb),('generic_common_a',beta[0]),('generic_common_c',beta[1]),('generic_component_intercepts',beta[2:])]:close(str(test['harp'])+':'+label,actual,fold[label])
                fs={}
                for name,z in pred.items():
                    err=(z-ty)/scale;nmse=float((err*err).mean());nmae=float(np.abs(err).mean());fs[name]=nmse;scores[name].append((nmse,nmae));published=fold['scores'][name];close(f'{test["harp"]}:{name}:metrics',[nmse,nmae],[published['nmse'],published['nmae']]);close(f'{test["harp"]}:{name}:transitions',(err*err).mean(1),[v['normalized_mse'] for v in published['per_transition']])
                w=winner(fs);assert w==fold['fold_winner']
                if w:wins[w]+=1
            global_scores={name:float(np.mean([x[0] for x in vals])) for name,vals in scores.items()}
            for name,values in scores.items():
                pub=r['global_scores'][name];close(name+':global',[global_scores[name],np.mean([x[1] for x in values])],[pub['mean_nmse'],pub['mean_nmae']]);assert pub['fold_wins']==wins[name] and pub['test_transitions']==12
            ordered=sorted(global_scores,key=lambda n:(global_scores[n],n));w=winner(global_scores);assert w==r['global_winner'];margin=1-global_scores[ordered[0]]/global_scores[ordered[1]] if global_scores[ordered[1]]>0 else None
            dominance=w is not None and margin is not None and margin>=0.05 and wins[w]>=2
            assert dominance==r['dominance_rule_pass']
            if w:close('global_margin',margin,r['global_primary_margin_fraction'])
            names={'T0_TRIVIAL_IDENTITY':'TRIVIAL','M_MOBIUS_SIGN':'MOBIUS','H_HELICAL_TRANSLATION':'HELICAL','L_LEMNISCATIC_ALTERNATING':'LEMNISCATIC','G_ACTIVITY_AFFINE':'GENERIC_ACTIVITY'}
            expected='DEVELOPMENT_'+names[w]+'_RIVAL_DOMINATES' if dominance else 'NO_DEVELOPMENT_DOMINANT_LIFT';assert expected==r['outcome']
            out.update(status='FULL_SELECTION_AND_AGGREGATE_REPLAY_PASS',global_scores_recomputed=global_scores,fold_wins_recomputed=wins,dominance_verified=dominance)
    else:out['status']='METADATA_SELECTION_ONLY_VERIFIED'
    out['replay_script_sha256']=sha(Path(__file__));a.output.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='numeric_checks'},indent=2))
if __name__=='__main__':
    if not __debug__:raise RuntimeError('Assertions required')
    main()
