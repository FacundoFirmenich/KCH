from __future__ import annotations

import argparse, json, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import logsumexp
from scipy.stats import norm

MODELS=['P0_POPULATION','P1_GLOBAL_POOL','P2_GLOBAL_LOCAL','P3_LOW_POOL']
SUBJECTS=['308','309','310','330','331','332','333','334','335','337','349','350','351','352','369','370','371','372']
FEATURES=['forecast_horizon','origin','subject_empirical_slope','subject_last_residual','subject_residual_dispersion','P1_effect_mean','P1_effect_sd','P2_effect_mean','P2_effect_sd','P2_kappa_mean','model_previous_mean_NLPD','model_previous_NLPD_count']
STAGES=[('crossfit__origin_2',2),('crossfit__origin_3',3),('crossfit__origin_4',4),('calibration__origin_5',5),('final__origin_7',7)]

def sha(path):
 h=hashlib.sha256(); h.update(Path(path).read_bytes()); return h.hexdigest()

def log_pred(mu,sigma,y):
 lp=norm.logpdf(y[None,:],loc=mu,scale=sigma[:,None])
 return logsumexp(lp,axis=0)-np.log(lp.shape[0])

def load_npz(root,backend,model,stage):
 return np.load(root/f'pg006-{backend}-{model}'/f'{stage}.npz',allow_pickle=False)

def train_frame_for_origin(con,cal,origin):
 if origin<=4:return con[con.Days<=origin].copy()
 if origin==5:return con.copy()
 if origin==7:return pd.concat([con,cal],ignore_index=True)
 raise ValueError(origin)

def deterministic(train,target):
 train=train.copy();target=target.copy();train['Subject']=train.Subject.astype(str);target['Subject']=target.Subject.astype(str);train['t']=(train.Days-2.5)/2.5
 xall=np.column_stack([np.ones(len(train)),train.t]);yall=train.y.to_numpy(float);ball=np.linalg.lstsq(xall,yall,rcond=None)[0]
 out={k:[] for k in ('slope','last_resid','disp')}
 for s in target.Subject.astype(str):
  sf=train[train.Subject==s].sort_values('Days');x=np.column_stack([np.ones(len(sf)),sf.t]);y=sf.y.to_numpy(float);b=np.linalg.lstsq(x,y,rcond=None)[0];resid=y-x@b
  out['slope'].append(float(b[1]));out['last_resid'].append(float(y[-1]-np.array([1.,sf.t.iloc[-1]])@ball));out['disp'].append(float(np.sqrt(np.mean(resid**2))) if len(resid)>2 else 0.)
 return {k:np.asarray(v,float) for k,v in out.items()}

def stage_data(root,backend,stage,origin,con,cal,history):
 z={m:load_npz(root,backend,m,stage) for m in MODELS};base=z[MODELS[0]]
 subj=base['target__subject_index'].astype(int);day=base['target__day'].astype(int);y=base['target__y'].astype(float)
 target=pd.DataFrame({'Subject':[SUBJECTS[i] for i in subj],'Days':day,'y':y});train=train_frame_for_origin(con,cal,origin);det=deterministic(train,target)
 p1=z['P1_GLOBAL_POOL']['pred__effect'];p2=z['P2_GLOBAL_LOCAL']['pred__effect'];kap=z['P2_GLOBAL_LOCAL']['pred__kappa']
 common=np.column_stack([day-origin,np.full(len(day),origin),det['slope'],det['last_resid'],det['disp'],p1.mean(0),p1.std(0,ddof=1),p2.mean(0),p2.std(0,ddof=1),kap.mean(0)])
 mus=[];sigmas=[];nls=[]
 for m in MODELS:
  mu=z[m]['pred__mu'];sigma=z[m]['pred__sigma'].reshape(-1);mus.append(mu);sigmas.append(sigma);nls.append(-log_pred(mu,sigma,y) if np.all(np.isfinite(y)) else np.full(len(day),np.nan))
 mus=np.stack(mus);sigmas=np.stack(sigmas);nls=np.stack(nls,axis=1)
 rows=[];mids=[];sids=[]
 for i,s in enumerate(subj):
  for mi in range(4):
   vals=history.get((int(s),mi),[]);rows.append(np.r_[common[i],float(np.mean(vals)) if vals else 0.,float(len(vals))]);mids.append(mi);sids.append(int(s))
 if np.all(np.isfinite(nls)):
  for i,s in enumerate(subj):
   for mi in range(4):history.setdefault((int(s),mi),[]).append(float(nls[i,mi]))
 return {'X_raw':np.asarray(rows),'model_idx':np.asarray(mids),'subject_idx':np.asarray(sids),'target_subject_idx':subj,'target_day':day,'target_y':y,'nlpd':nls,'mu':mus,'sigma':sigmas}

def helmert(n):
 b=np.zeros((n,n-1))
 for k in range(1,n):
  d=np.sqrt(k*(k+1.));b[:k,k-1]=1/d;b[k,k-1]=-k/d
 return b

def main():
 p=argparse.ArgumentParser();p.add_argument('--artifacts-root',required=True);p.add_argument('--backend',choices=['pymc','numpyro'],required=True);p.add_argument('--data-root',required=True);p.add_argument('--out',required=True);a=p.parse_args()
 root=Path(a.artifacts_root);data_root=Path(a.data_root);out=Path(a.out);out.parent.mkdir(parents=True,exist_ok=True)
 con=pd.read_csv(data_root/'train/construction_days_0_5.csv');cal=pd.read_csv(data_root/'calibration/calibration_days_6_7.csv');ym=con.Reaction.mean();ys=con.Reaction.std(ddof=0)
 for f in (con,cal):f['Subject']=f.Subject.astype(str);f['y']=(f.Reaction-ym)/ys
 hist={};split={}
 for stage,origin in STAGES:split[stage]=stage_data(root,a.backend,stage,origin,con,cal,hist)
 cross=[split[s] for s,_ in STAGES[:3]];Xraw=np.concatenate([q['X_raw'] for q in cross]);mid=np.concatenate([q['model_idx'] for q in cross]);sid=np.concatenate([q['subject_idx'] for q in cross]);nlpd=np.concatenate([q['nlpd'] for q in cross])
 regret=nlpd-np.min(nlpd,axis=1,keepdims=True);z=np.log(regret.reshape(-1)+0.005);mean=Xraw.mean(0);sd=np.where(Xraw.std(0)>1e-12,Xraw.std(0),1.);X=(Xraw-mean)/sd
 c=split['calibration__origin_5'];f=split['final__origin_7']
 payload={'z':z,'X':X,'model_idx':mid,'subject_idx':sid,'basis':helmert(18),'n_models':np.array(4),'feature_mean':mean,'feature_sd':sd,'X_calibration':(c['X_raw']-mean)/sd,'model_idx_calibration':c['model_idx'],'subject_idx_calibration':c['subject_idx'],'X_final':(f['X_raw']-mean)/sd,'model_idx_final':f['model_idx'],'subject_idx_final':f['subject_idx'],'calibration_subject_idx':c['target_subject_idx'],'calibration_day':c['target_day'],'calibration_y':c['target_y'],'calibration_nlpd_components':c['nlpd'],'calibration_mu_components':c['mu'],'calibration_sigma_components':c['sigma'],'final_subject_idx':f['target_subject_idx'],'final_day':f['target_day'],'final_mu_components':f['mu'],'final_sigma_components':f['sigma'],'crossfit_nlpd_components':nlpd,'crossfit_regret':regret}
 np.savez_compressed(out,**payload)
 field_out=out.with_name(out.stem+'_fit.npz');keep=['z','X','model_idx','subject_idx','basis','n_models','X_calibration','model_idx_calibration','subject_idx_calibration','X_final','model_idx_final','subject_idx_final'];np.savez_compressed(field_out,**{k:payload[k] for k in keep})
 receipts={m:json.load(open(root/f'pg006-{a.backend}-{m}'/'receipt.json'))['receipt_hash'] for m in MODELS}
 meta={'backend':a.backend,'models':MODELS,'features':FEATURES,'order':'target-major, model-minor','n_crossfit_targets':int(nlpd.shape[0]),'n_field_records':int(len(z)),'n_calibration_targets':int(len(c['target_y'])),'n_final_targets':int(len(f['target_day'])),'response_scaler':{'mean':float(ym),'sd':float(ys)},'component_receipts':receipts,'full_npz_sha256':sha(out),'fit_npz_sha256':sha(field_out)}
 out.with_suffix('.json').write_text(json.dumps(meta,indent=2,sort_keys=True)+'\n');print(json.dumps(meta,indent=2))

if __name__=='__main__':main()
