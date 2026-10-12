from __future__ import annotations

import argparse, hashlib, json, math, traceback
from pathlib import Path
from typing import Any

import drms
import numpy as np
import pandas as pd
import requests
from astropy.io import fits
from scipy.stats import spearmanr, binomtest

KEYS=["HARPNUM","T_REC","NOAA_AR","QUALITY","CMASK","MEANJZH","MEANALP","ERRMIH","ERRALP","CDELT1","RSUN_REF"]
SEGS=["Br","Bt","Bp","br_err","bt_err","bp_err","conf_disambig","bitmap"]

def write_json(p:Path,o:Any)->None:
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(o,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False,default=str)+"\n",encoding="utf-8")

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def data2d(path:Path)->np.ndarray:
    with fits.open(path,memmap=False) as hdul:
        for hdu in hdul:
            if hdu.data is not None and getattr(hdu.data,"ndim",0)==2:
                return np.asarray(hdu.data)
    raise RuntimeError(f"no 2D image in {path}")

def metrics(Br,Bt,Bp,mask,cdelt1_deg,rsun_ref):
    Bx=Bp; By=-Bt
    jz=np.gradient(By,axis=1,edge_order=1)-np.gradient(Bx,axis=0,edge_order=1)
    scale=1.0/(float(rsun_ref)*math.radians(float(cdelt1_deg)))
    valid=mask & np.isfinite(jz) & np.isfinite(Br)
    hc=Br*jz*scale
    n=int(valid.sum())
    if n==0: raise RuntimeError("no valid pixels")
    denom=float(np.sum(Br[valid]**2))
    return {
      "cmask":n,
      "meanjzh":float(np.mean(hc[valid])),
      "meanalp":float(np.sum(jz[valid]*Br[valid])/denom*scale*1e6) if denom>0 else float("nan")
    }

def parity(Br,Bt,Bp,mask,cdelt1_deg,rsun_ref):
    return metrics(Br[:,::-1],Bt[:,::-1],-Bp[:,::-1],mask[:,::-1],cdelt1_deg,rsun_ref)

def seed64(harp:int,trec:str)->int:
    return int.from_bytes(hashlib.sha256(f"KCH_MHD12_MC|{harp}|{trec}".encode()).digest()[:8],"big")

def download(url:str,path:Path)->dict[str,Any]:
    r=requests.get(url,headers={"User-Agent":"KCH-Helical-v1.2-HSR/2026-10-12"},timeout=180,stream=True)
    r.raise_for_status()
    h=hashlib.sha256(); n=0
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("wb") as f:
        for chunk in r.iter_content(1024*1024):
            if not chunk: continue
            f.write(chunk); h.update(chunk); n+=len(chunk)
    return {"url":url,"bytes":n,"sha256":h.hexdigest(),"content_type":r.headers.get("content-type")}

def sign(x:float)->int:
    return 1 if x>0 else (-1 if x<0 else 0)

def relerr(a:float,b:float)->float:
    return float(abs(a-b)/max(abs(b),1e-12))

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--lock",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    out=args.out; out.mkdir(parents=True,exist_ok=True)
    lock=json.loads(args.lock.read_text(encoding="utf-8"))
    client=drms.Client()
    results=[]; transports=[]
    try:
        for rec in lock["selection"]["records"]:
            harp=int(rec["HARPNUM"]); trec=str(rec["T_REC"])
            q=f"hmi.sharp_cea_720s[{harp}][{trec}]"
            k,s=client.query(q,key=",".join(KEYS),seg=",".join(SEGS))
            if len(k)!=1 or len(s)!=1: raise RuntimeError(f"{q}: expected one record")
            kw={key:(None if pd.isna(k.iloc[0][key]) else k.iloc[0][key]) for key in KEYS}
            recdir=out/"fits"/f"HARP{harp}_{trec.replace(':','-')}"
            files={}
            for seg in SEGS:
                raw=str(s.iloc[0][seg])
                url=raw if raw.startswith("http") else "https://jsoc1.stanford.edu"+(raw if raw.startswith("/") else "/"+raw)
                p=recdir/f"{seg}.fits"; tr=download(url,p)
                tr.update({"HARPNUM":harp,"T_REC":trec,"segment":seg})
                transports.append(tr); files[seg]=p
            arr={seg:data2d(files[seg]) for seg in SEGS}
            if len({tuple(a.shape) for a in arr.values()})!=1: raise RuntimeError(f"{q}: shape mismatch")
            finite=np.isfinite(arr["Br"])&np.isfinite(arr["Bt"])&np.isfinite(arr["Bp"])
            mask=(arr["bitmap"]>=33)&(arr["conf_disambig"]==90)&finite
            m=metrics(arr["Br"],arr["Bt"],arr["Bp"],mask,float(kw["CDELT1"]),float(kw["RSUN_REF"]))
            if m["cmask"]!=int(kw["CMASK"]): raise RuntimeError(f"{q}: CMASK mismatch")
            px=parity(arr["Br"],arr["Bt"],arr["Bp"],mask,float(kw["CDELT1"]),float(kw["RSUN_REF"]))
            anti_h=abs(px["meanjzh"]+m["meanjzh"])/max(abs(m["meanjzh"]),1e-12)
            anti_a=abs(px["meanalp"]+m["meanalp"])/max(abs(m["meanalp"]),1e-12)
            if anti_h>1e-8 or anti_a>1e-8: raise RuntimeError(f"{q}: parity fail")
            rng=np.random.default_rng(seed64(harp,trec))
            mc_h=[]; mc_a=[]
            for _ in range(64):
                br=arr["Br"]+rng.normal(0,np.nan_to_num(arr["br_err"],nan=0.0))
                bt=arr["Bt"]+rng.normal(0,np.nan_to_num(arr["bt_err"],nan=0.0))
                bp=arr["Bp"]+rng.normal(0,np.nan_to_num(arr["bp_err"],nan=0.0))
                mm=metrics(br,bt,bp,mask,float(kw["CDELT1"]),float(kw["RSUN_REF"]))
                mc_h.append(mm["meanjzh"]); mc_a.append(mm["meanalp"])
            sh=sign(m["meanjzh"]); sa=sign(m["meanalp"])
            stab_h=float(np.mean([sign(x)==sh for x in mc_h])) if sh else 0.0
            stab_a=float(np.mean([sign(x)==sa for x in mc_a])) if sa else 0.0
            hsr_h=bool(m["meanjzh"]*float(rec["LAT_FWT"])<0)
            hsr_a=bool(m["meanalp"]*float(rec["LAT_FWT"])<0)
            robust=bool(hsr_h and stab_h>=lock["uncertainty"]["minimum_sign_stability"])
            results.append({
              **rec,"query":q,
              "keyword_MEANJZH":float(kw["MEANJZH"]),"recon_MEANJZH":m["meanjzh"],
              "keyword_MEANALP":float(kw["MEANALP"]),"recon_MEANALP":m["meanalp"],
              "relerr_MEANJZH":relerr(m["meanjzh"],float(kw["MEANJZH"])),
              "relerr_MEANALP":relerr(m["meanalp"],float(kw["MEANALP"])),
              "sign_agreement_MEANJZH":sign(m["meanjzh"])==sign(float(kw["MEANJZH"])),
              "sign_agreement_MEANALP":sign(m["meanalp"])==sign(float(kw["MEANALP"])),
              "MEANJZH_sign_stability":stab_h,"MEANALP_sign_stability":stab_a,
              "MEANJZH_informative_2sigma":abs(float(kw["MEANJZH"]))>=2*abs(float(kw["ERRMIH"])),
              "MEANALP_informative_2sigma":abs(float(kw["MEANALP"]))>=2*abs(float(kw["ERRALP"])),
              "HSR_MEANJZH":hsr_h,"HSR_MEANALP":hsr_a,"robust_HSR_MEANJZH":robust,
              "cmask":m["cmask"],"parity_antisymmetry_MEANJZH":anti_h,"parity_antisymmetry_MEANALP":anti_a,
              "MEANJZH_mc_p025":float(np.quantile(mc_h,0.025)),"MEANJZH_mc_p975":float(np.quantile(mc_h,0.975)),
              "MEANALP_mc_p025":float(np.quantile(mc_a,0.025)),"MEANALP_mc_p975":float(np.quantile(mc_a,0.975))
            })
        df=pd.DataFrame(results)
        rg=lock["reconstruction_gate"]
        reconstruction={
          "all_32_records":len(df)==32,
          "all_cmask_ge_100":bool((df.cmask>=rg["minimum_valid_cmask_pixels"]).all()),
          "MEANJZH_sign_fraction":float(df.sign_agreement_MEANJZH.mean()),
          "MEANALP_sign_fraction":float(df.sign_agreement_MEANALP.mean()),
          "MEANJZH_spearman":float(spearmanr(df.keyword_MEANJZH,df.recon_MEANJZH).statistic),
          "MEANALP_spearman":float(spearmanr(df.keyword_MEANALP,df.recon_MEANALP).statistic),
          "median_relerr_MEANJZH":float(df.relerr_MEANJZH.median()),
          "median_relerr_MEANALP":float(df.relerr_MEANALP.median()),
          "parity_pass":bool((df.parity_antisymmetry_MEANJZH<=1e-8).all() and (df.parity_antisymmetry_MEANALP<=1e-8).all())
        }
        reconstruction_pass=(
          reconstruction["all_32_records"] and reconstruction["all_cmask_ge_100"] and reconstruction["parity_pass"] and
          reconstruction["MEANJZH_sign_fraction"]>=rg["MEANJZH_sign_agreement_fraction_min"] and
          abs(reconstruction["MEANJZH_spearman"])>=rg["MEANJZH_spearman_abs_min"] and
          abs(reconstruction["MEANALP_spearman"])>=rg["MEANALP_spearman_abs_min"] and
          reconstruction["median_relerr_MEANJZH"]<=rg["median_relative_abs_error_MEANJZH_max"] and
          reconstruction["median_relerr_MEANALP"]<=rg["median_relative_abs_error_MEANALP_max"]
        )
        total=int(df.robust_HSR_MEANJZH.sum())
        north=int(df.loc[df.hemisphere=="N","robust_HSR_MEANJZH"].sum())
        south=int(df.loc[df.hemisphere=="S","robust_HSR_MEANJZH"].sum())
        p=float(binomtest(total,32,0.5,alternative="greater").pvalue)
        alpha_total=int(df.HSR_MEANALP.sum())
        primary=lock["primary_adjudication"]
        replicate=bool(reconstruction_pass and total>=primary["minimum_robust_compliant_regions"] and north>=primary["minimum_robust_compliant_each_hemisphere"] and south>=primary["minimum_robust_compliant_each_hemisphere"] and p<=primary["maximum_one_sided_p"])
        outcome="HEMISPHERIC_CURRENT_HELICITY_SIGN_PREFERENCE_REPLICATED" if replicate else "HEMISPHERIC_SIGN_PREFERENCE_NOT_REPLICATED"
        result={
          "format":"KCH_HELICOIDAL_V1_2_HEMISPHERIC_CURRENT_HELICITY_RESULT",
          "lock_id":lock["lock_id"],"outcome":outcome,
          "reconstruction_gate":{"pass":reconstruction_pass,**reconstruction},
          "primary":{"robust_compliant_total":total,"robust_compliant_north":north,"robust_compliant_south":south,"exact_binomial_p_one_sided":p,"fraction":total/32.0},
          "secondary":{"MEANALP_HSR_total":alpha_total,"MEANALP_HSR_fraction":alpha_total/32.0},
          "records":results,
          "classification":"locked-before-direct-field-acquisition replication on previously censused CALIBRATION-period aggregate metadata/features; not pristine pre-data discovery",
          "physical_helicity":"PHOTOSPHERIC_VERTICAL_CURRENT_HELICITY_PROXY_SIGN_PREFERENCE_ONLY",
          "coronal_relative_magnetic_helicity":"NOT_EVALUATED",
          "flare_prediction":"NOT_EVALUATED",
          "promotion":"BLOCKED","canonicalization":"BLOCKED","authority_ceiling":"NONE"
        }
        canon=json.dumps(result,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
        result["result_id"]="mhd12hsrres:"+hashlib.sha256(canon).hexdigest()
        write_json(out/"HEMISPHERIC_CURRENT_HELICITY_RESULT.json",result)
        df.to_csv(out/"HEMISPHERIC_CURRENT_HELICITY_METRICS.csv",index=False)
        pd.DataFrame(transports).to_csv(out/"EXACT_SEGMENT_TRANSPORT.csv",index=False)
        print(json.dumps({"result_id":result["result_id"],"outcome":outcome,"reconstruction_pass":reconstruction_pass,"robust_total":total,"north":north,"south":south,"p":p,"alpha_total":alpha_total},indent=2,sort_keys=True))
        return 0
    except Exception as exc:
        write_json(out/"FAIL_CLOSED_RECEIPT.json",{"format":"KCH_HELICOIDAL_V1_2_HSR_FAIL_CLOSED","error_type":type(exc).__name__,"error":str(exc),"traceback":traceback.format_exc(),"scientific_claim_authorized":False,"authority_ceiling":"NONE"})
        print(traceback.format_exc())
        return 2

if __name__=="__main__": raise SystemExit(main())
