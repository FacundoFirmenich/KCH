from __future__ import annotations

import argparse, hashlib, json, math, os, traceback
from pathlib import Path
from typing import Any

import drms
import numpy as np
import pandas as pd
import requests
from astropy.io import fits
from scipy.stats import spearmanr

KEYS=[
 "HARPNUM","T_REC","NOAA_AR","QUALITY","CMASK",
 "MEANJZH","TOTUSJH","ABSNJZH","MEANALP","ERRMIH","ERRTUI","ERRTAI","ERRALP",
 "CDELT1","RSUN_OBS","RSUN_REF"
]
SEGS=["Br","Bt","Bp","br_err","bt_err","bp_err","conf_disambig","bitmap"]

def sha256_file(p:Path)->str:
 h=hashlib.sha256()
 with p.open("rb") as f:
  for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
 return h.hexdigest()

def write_json(p:Path,o:Any)->None:
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(o,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False,default=str)+"\n",encoding="utf-8")

def data2d(path:Path)->np.ndarray:
 with fits.open(path,memmap=False) as hdul:
  for hdu in hdul:
   if hdu.data is not None and getattr(hdu.data,"ndim",0)==2:
    return np.asarray(hdu.data)
 raise RuntimeError(f"no 2D FITS image in {path}")

def derivatives(Bx:np.ndarray,By:np.ndarray)->np.ndarray:
 # arrays: rows latitude/northward, cols longitude/westward
 dBy_dx=np.gradient(By,axis=1,edge_order=1)
 dBx_dy=np.gradient(Bx,axis=0,edge_order=1)
 return dBy_dx-dBx_dy

def metrics(Br,Bt,Bp,mask,cdelt1_deg,rsun_ref):
 Bx=Bp
 By=-Bt
 jz=derivatives(Bx,By)
 scale=1.0/(float(rsun_ref)*math.radians(float(cdelt1_deg)))
 valid=mask & np.isfinite(jz) & np.isfinite(Br)
 hc=Br*jz*scale
 n=int(valid.sum())
 if n==0: raise RuntimeError("no valid pixels")
 meanjzh=float(np.mean(hc[valid]))
 totusjh=float(np.sum(np.abs(hc[valid])))
 absnjzh=float(abs(np.sum(hc[valid])))
 denom=float(np.sum((Br[valid])**2))
 meanalp=float(np.sum(jz[valid]*Br[valid])/denom*scale*1e6) if denom>0 else float("nan")
 return {"cmask":n,"meanjzh":meanjzh,"totusjh":totusjh,"absnjzh":absnjzh,"meanalp":meanalp}

def parity_x_metrics(Br,Bt,Bp,mask,cdelt1_deg,rsun_ref):
 # x -> -x: reverse x coordinate and transform Bx as a vector component.
 Br2=Br[:,::-1]
 Bt2=Bt[:,::-1]
 Bp2=-Bp[:,::-1]
 mask2=mask[:,::-1]
 return metrics(Br2,Bt2,Bp2,mask2,cdelt1_deg,rsun_ref)

def relerr(a,b):
 return float(abs(a-b)/max(abs(b),1e-12))

def seed64(harp:int,t_rec:str)->int:
 x=hashlib.sha256(f"KCH_MHD12_MC|{harp}|{t_rec}".encode()).digest()[:8]
 return int.from_bytes(x,"big",signed=False)

def download(url:str,path:Path)->dict[str,Any]:
 r=requests.get(url,headers={"User-Agent":"KCH-Helical-v1.2-direct-field/2026-10-12"},timeout=180,stream=True)
 r.raise_for_status()
 h=hashlib.sha256(); n=0
 path.parent.mkdir(parents=True,exist_ok=True)
 with path.open("wb") as f:
  for chunk in r.iter_content(1024*1024):
   if not chunk: continue
   f.write(chunk); h.update(chunk); n+=len(chunk)
 return {"url":url,"bytes":n,"sha256":h.hexdigest(),"content_type":r.headers.get("content-type")}

def main()->int:
 ap=argparse.ArgumentParser()
 ap.add_argument("--lock",type=Path,required=True)
 ap.add_argument("--out",type=Path,required=True)
 args=ap.parse_args()
 out=args.out; out.mkdir(parents=True,exist_ok=True)
 lock=json.loads(args.lock.read_text(encoding="utf-8"))
 client=drms.Client()
 record_results=[]; transports=[]
 try:
  for record in lock["selection"]["records"]:
   harp=int(record["HARPNUM"]); trec=str(record["T_REC"])
   q=f"hmi.sharp_cea_720s[{harp}][{trec}]"
   k,s=client.query(q,key=",".join(KEYS),seg=",".join(SEGS))
   if len(k)!=1 or len(s)!=1: raise RuntimeError(f"{q}: expected one record")
   kw={key:(None if pd.isna(k.iloc[0][key]) else k.iloc[0][key]) for key in KEYS}
   recdir=out/"fits"/f"HARP{harp}_{trec.replace(':','-')}"
   files={}
   for seg in SEGS:
    raw=str(s.iloc[0][seg])
    url=raw if raw.startswith("http") else "https://jsoc1.stanford.edu"+(raw if raw.startswith("/") else "/"+raw)
    p=recdir/f"{seg}.fits"
    tr=download(url,p); tr.update({"HARPNUM":harp,"T_REC":trec,"segment":seg})
    transports.append(tr); files[seg]=p
   arr={seg:data2d(files[seg]) for seg in SEGS}
   shapes={seg:list(arr[seg].shape) for seg in SEGS}
   if len({tuple(v) for v in shapes.values()})!=1: raise RuntimeError(f"{q}: segment shape mismatch {shapes}")
   finite=np.isfinite(arr["Br"]) & np.isfinite(arr["Bt"]) & np.isfinite(arr["Bp"])
   mask=(arr["bitmap"]>=33)&(arr["conf_disambig"]==90)&finite
   nominal=metrics(arr["Br"],arr["Bt"],arr["Bp"],mask,float(kw["CDELT1"]),float(kw["RSUN_REF"]))
   if nominal["cmask"]!=int(kw["CMASK"]): raise RuntimeError(f"{q}: CMASK mismatch {nominal['cmask']} != {kw['CMASK']}")
   parity=parity_x_metrics(arr["Br"],arr["Bt"],arr["Bp"],mask,float(kw["CDELT1"]),float(kw["RSUN_REF"]))
   flip_mean=abs(parity["meanjzh"]+nominal["meanjzh"])/max(abs(nominal["meanjzh"]),1e-12)
   flip_alpha=abs(parity["meanalp"]+nominal["meanalp"])/max(abs(nominal["meanalp"]),1e-12)
   if flip_mean>1e-8 or flip_alpha>1e-8: raise RuntimeError(f"{q}: parity sign-control failed {flip_mean=} {flip_alpha=}")
   rng=np.random.default_rng(seed64(harp,trec))
   mc_mean=[]; mc_alpha=[]
   for _ in range(64):
    br=arr["Br"]+rng.normal(0.0,np.nan_to_num(arr["br_err"],nan=0.0))
    bt=arr["Bt"]+rng.normal(0.0,np.nan_to_num(arr["bt_err"],nan=0.0))
    bp=arr["Bp"]+rng.normal(0.0,np.nan_to_num(arr["bp_err"],nan=0.0))
    m=metrics(br,bt,bp,mask,float(kw["CDELT1"]),float(kw["RSUN_REF"]))
    mc_mean.append(m["meanjzh"]); mc_alpha.append(m["meanalp"])
   sign0=lambda x: 1 if x>0 else (-1 if x<0 else 0)
   nominal_sign=sign0(nominal["meanjzh"]); alpha_sign=sign0(nominal["meanalp"])
   mean_stab=float(np.mean([sign0(x)==nominal_sign for x in mc_mean])) if nominal_sign else 0.0
   alpha_stab=float(np.mean([sign0(x)==alpha_sign for x in mc_alpha])) if alpha_sign else 0.0
   result={
    **record,
    "query":q,
    "shape":shapes["Br"],
    "keyword":{x:(float(kw[x]) if isinstance(kw[x],(int,float,np.integer,np.floating)) else kw[x]) for x in KEYS},
    "reconstructed":nominal,
    "relative_error":{
      "MEANJZH":relerr(nominal["meanjzh"],float(kw["MEANJZH"])),
      "TOTUSJH":relerr(nominal["totusjh"],float(kw["TOTUSJH"])),
      "ABSNJZH":relerr(nominal["absnjzh"],float(kw["ABSNJZH"])),
      "MEANALP":relerr(nominal["meanalp"],float(kw["MEANALP"])),
    },
    "sign_agreement_MEANJZH":sign0(nominal["meanjzh"])==sign0(float(kw["MEANJZH"])),
    "sign_agreement_MEANALP":sign0(nominal["meanalp"])==sign0(float(kw["MEANALP"])),
    "parity_control":{"relative_antisymmetry_MEANJZH":flip_mean,"relative_antisymmetry_MEANALP":flip_alpha},
    "uncertainty":{
      "MEANJZH_sign_stability":mean_stab,
      "MEANALP_sign_stability":alpha_stab,
      "keyword_MEANJZH_informative_2sigma":abs(float(kw["MEANJZH"]))>=2*abs(float(kw["ERRMIH"])),
      "keyword_MEANALP_informative_2sigma":abs(float(kw["MEANALP"]))>=2*abs(float(kw["ERRALP"])),
      "MEANJZH_mc_p025":float(np.quantile(mc_mean,0.025)),
      "MEANJZH_mc_p975":float(np.quantile(mc_mean,0.975)),
      "MEANALP_mc_p025":float(np.quantile(mc_alpha,0.025)),
      "MEANALP_mc_p975":float(np.quantile(mc_alpha,0.975)),
    }
   }
   record_results.append(result)
  df=pd.DataFrame([{
   "NOAA_AR":r["NOAA_AR"],"HARPNUM":r["HARPNUM"],"hemisphere":r["hemisphere"],
   "keyword_MEANJZH":r["keyword"]["MEANJZH"],"recon_MEANJZH":r["reconstructed"]["meanjzh"],
   "keyword_MEANALP":r["keyword"]["MEANALP"],"recon_MEANALP":r["reconstructed"]["meanalp"],
   "keyword_TOTUSJH":r["keyword"]["TOTUSJH"],"recon_TOTUSJH":r["reconstructed"]["totusjh"],
   "relerr_MEANJZH":r["relative_error"]["MEANJZH"],"relerr_MEANALP":r["relative_error"]["MEANALP"],
   "relerr_TOTUSJH":r["relative_error"]["TOTUSJH"],
   "sign_MEANJZH":r["sign_agreement_MEANJZH"],"sign_MEANALP":r["sign_agreement_MEANALP"],
   "stability_MEANJZH":r["uncertainty"]["MEANJZH_sign_stability"],"stability_MEANALP":r["uncertainty"]["MEANALP_sign_stability"],
   "informative_MEANJZH":r["uncertainty"]["keyword_MEANJZH_informative_2sigma"],"informative_MEANALP":r["uncertainty"]["keyword_MEANALP_informative_2sigma"],
   "cmask":r["reconstructed"]["cmask"],
  } for r in record_results])
  rho_h=float(spearmanr(df.keyword_MEANJZH,df.recon_MEANJZH).statistic)
  rho_a=float(spearmanr(df.keyword_MEANALP,df.recon_MEANALP).statistic)
  ih=df[df.informative_MEANJZH]; ia=df[df.informative_MEANALP]
  stable_h=float((ih.stability_MEANJZH>=0.8).mean()) if len(ih) else 0.0
  stable_a=float((ia.stability_MEANALP>=0.8).mean()) if len(ia) else 0.0
  gates={
   "all_16_records":len(df)==16,
   "hemisphere_balance":df.hemisphere.value_counts().to_dict()=={"N":8,"S":8},
   "all_cmask_ge_100":bool((df.cmask>=100).all()),
   "MEANJZH_sign_fraction":float(df.sign_MEANJZH.mean()),
   "MEANALP_sign_fraction":float(df.sign_MEANALP.mean()),
   "MEANJZH_spearman":rho_h,
   "MEANALP_spearman":rho_a,
   "median_relerr_MEANJZH":float(df.relerr_MEANJZH.median()),
   "median_relerr_MEANALP":float(df.relerr_MEANALP.median()),
   "median_relerr_TOTUSJH":float(df.relerr_TOTUSJH.median()),
   "informative_MEANJZH_records":int(len(ih)),
   "informative_MEANALP_records":int(len(ia)),
   "stable_informative_MEANJZH_fraction":stable_h,
   "stable_informative_MEANALP_fraction":stable_a,
  }
  thresholds=lock["observability_gates"]
  ua=json.loads((args.lock.parent/"MHD_DIRECT_FIELD_UNCERTAINTY_ADDENDUM.json").read_text())
  passed=(
   gates["all_16_records"] and gates["hemisphere_balance"] and gates["all_cmask_ge_100"] and
   gates["MEANJZH_sign_fraction"]>=thresholds["record_level_MEANJZH_sign_agreement_fraction"] and
   abs(rho_h)>=thresholds["record_level_MEANJZH_spearman_abs_min"] and
   abs(rho_a)>=thresholds["record_level_MEANALP_spearman_abs_min"] and
   gates["median_relerr_MEANJZH"]<=thresholds["median_relative_abs_error_MEANJZH_max"] and
   gates["median_relerr_MEANALP"]<=thresholds["median_relative_abs_error_MEANALP_max"] and
   len(ih)>=ua["uncertainty_gates"]["minimum_informative_records_each_quantity"] and
   len(ia)>=ua["uncertainty_gates"]["minimum_informative_records_each_quantity"] and
   stable_h>=ua["uncertainty_gates"]["minimum_fraction_signed_informative_records_with_sign_stability_ge_0_80"] and
   stable_a>=ua["uncertainty_gates"]["minimum_fraction_signed_informative_records_with_sign_stability_ge_0_80"]
  )
  outcome="DIRECT_SIGNED_CURRENT_HELICITY_OBSERVABLE" if passed else "DIRECT_FIELD_RECONSTRUCTION_GATE_FAILED"
  result={"format":"KCH_HELICAL_V1_2_DIRECT_VECTOR_FIELD_GATE_RESULT","lock_id":lock["lock_id"],"outcome":outcome,"gates":gates,"records":record_results,"physical_helicity":"CURRENT_HELICITY_PROXY_OBSERVABLE_NOT_CORONAL_RELATIVE_HELICITY","flare_prediction":"NOT_EVALUATED","authority_ceiling":"NONE"}
  canon=json.dumps(result,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
  result["result_id"]="mhd12obs:"+hashlib.sha256(canon).hexdigest()
  write_json(out/"DIRECT_VECTOR_FIELD_GATE_RESULT.json",result)
  df.to_csv(out/"DIRECT_VECTOR_FIELD_METRICS.csv",index=False)
  pd.DataFrame(transports).to_csv(out/"EXACT_SEGMENT_TRANSPORT.csv",index=False)
  print(json.dumps({"outcome":outcome,"result_id":result["result_id"],"gates":gates},indent=2,sort_keys=True))
  return 0 if passed else 4
 except Exception as exc:
  write_json(out/"FAIL_CLOSED_RECEIPT.json",{"format":"KCH_HELICAL_V1_2_DIRECT_FIELD_FAIL_CLOSED","error_type":type(exc).__name__,"error":str(exc),"traceback":traceback.format_exc(),"scientific_claim_authorized":False,"authority_ceiling":"NONE"})
  print(traceback.format_exc())
  return 2

if __name__=="__main__": raise SystemExit(main())
