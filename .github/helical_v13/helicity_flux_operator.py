from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import drms
import numpy as np
import pandas as pd
import requests
from astropy.io import fits
from scipy.ndimage import shift as nd_shift
from scipy.signal import fftconvolve
from scipy.stats import pearsonr

from pyflowmaps.dave4vm import pydave4vm
from pyflowmaps.math_tools import odiff

KEYS=["HARPNUM","T_REC","NOAA_AR","QUALITY","CMASK","CDELT1","RSUN_REF"]
SEGS=["Br","Bt","Bp","conf_disambig","bitmap"]

def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def write_json(p:Path,o:Any)->None:
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(o,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False,default=str)+"\n",encoding="utf-8")

def parse_trec(s:str)->datetime:
    return datetime.strptime(s,"%Y.%m.%d_%H:%M:%S_TAI")

def fmt_trec(d:datetime)->str:
    return d.strftime("%Y.%m.%d_%H:%M:%S_TAI")

def fits2d(p:Path)->np.ndarray:
    with fits.open(p,memmap=False) as hdul:
        for hdu in hdul:
            if hdu.data is not None and getattr(hdu.data,"ndim",0)==2:
                return np.asarray(hdu.data,dtype=np.float64)
    raise RuntimeError(f"no 2D image in {p}")

def download(url:str,path:Path)->dict[str,Any]:
    r=requests.get(url,headers={"User-Agent":"KCH-Helical-v1.3-flux-operator/2026-10-12"},timeout=180,stream=True)
    r.raise_for_status()
    h=hashlib.sha256(); n=0
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("wb") as f:
        for chunk in r.iter_content(1024*1024):
            if not chunk: continue
            f.write(chunk); h.update(chunk); n+=len(chunk)
    return {"url":url,"bytes":n,"sha256":h.hexdigest(),"content_type":r.headers.get("content-type")}

def high_conf(frame:dict[str,np.ndarray])->np.ndarray:
    return ((frame["bitmap"]>=33)&(frame["conf_disambig"]==90)&
            np.isfinite(frame["Br"])&np.isfinite(frame["Bt"])&np.isfinite(frame["Bp"]))

def edge_guard(shape,guard:int)->np.ndarray:
    m=np.zeros(shape,dtype=bool)
    if shape[0]>2*guard and shape[1]>2*guard:
        m[guard:-guard,guard:-guard]=True
    return m

def bbox_union(masks:list[np.ndarray],margin:int)->tuple[slice,slice]:
    u=np.logical_or.reduce(masks)
    yy,xx=np.where(u)
    if len(yy)==0: raise RuntimeError("empty union high-confidence mask")
    y0=max(0,int(yy.min())-margin); y1=min(u.shape[0],int(yy.max())+1+margin)
    x0=max(0,int(xx.min())-margin); x1=min(u.shape[1],int(xx.max())+1+margin)
    return slice(y0,y1),slice(x0,x1)

def crop_frame(frame:dict[str,np.ndarray],sl)->dict[str,np.ndarray]:
    sy,sx=sl
    return {k:v[sy,sx].copy() for k,v in frame.items()}

def clean(a):
    return np.nan_to_num(np.asarray(a,dtype=np.float64),nan=0.0,posinf=0.0,neginf=0.0)

def dave_pair(start,stop,dt_s:float,dx_km:float,window:int):
    bx0,by0,bz0=clean(start["Bp"]),clean(-start["Bt"]),clean(start["Br"])
    bx1,by1,bz1=clean(stop["Bp"]),clean(-stop["Bt"]),clean(stop["Br"])
    bx=(bx0+bx1)/2.0; by=(by0+by1)/2.0; bz=(bz0+bz1)/2.0
    bzt=(bz1-bz0)/dt_s
    bxx,bxy=odiff(bx); byx,byy=odiff(by); bzx,bzy=odiff(bz)
    mag={
      "bzt":bzt,"bx":bx,"bxx":bxx/dx_km,"bxy":bxy/dx_km,
      "by":by,"byx":byx/dx_km,"byy":byy/dx_km,
      "bz":bz,"bzx":bzx/dx_km,"bzy":bzy/dx_km,
      "dx":dx_km,"dy":dx_km,"dt":dt_s
    }
    vel=pydave4vm(mag,window)
    vx=np.asarray(vel["U0"],dtype=float); vy=np.asarray(vel["V0"],dtype=float); vz=np.asarray(vel["W0"],dtype=float)
    solved=(np.abs(vx)+np.abs(vy)+np.abs(vz)+
            np.abs(vel["UX"])+np.abs(vel["UY"])+np.abs(vel["VX"])+np.abs(vel["VY"])+
            np.abs(vel["WX"])+np.abs(vel["WY"]))>0
    return {"bx":bx,"by":by,"bz":bz,"bzt":bzt,"vx":vx,"vy":vy,"vz":vz,"solved":solved}

def vperp(pair):
    bx,by,bz=pair["bx"],pair["by"],pair["bz"]
    vx,vy,vz=pair["vx"],pair["vy"],pair["vz"]
    b2=bx*bx+by*by+bz*bz
    good=b2>0
    dot=vx*bx+vy*by+vz*bz
    f=np.zeros_like(dot); f[good]=dot[good]/b2[good]
    return vx-f*bx,vy-f*by,vz-f*bz

def ap_green(bz:np.ndarray,dx_cm:float):
    ny,nx=bz.shape
    ys=np.arange(-(ny-1),ny,dtype=float)*dx_cm
    xs=np.arange(-(nx-1),nx,dtype=float)*dx_cm
    X,Y=np.meshgrid(xs,ys)
    r2=X*X+Y*Y
    kx=np.zeros_like(r2); ky=np.zeros_like(r2)
    nz=r2>0
    kx[nz]=-Y[nz]/(2.0*np.pi*r2[nz])
    ky[nz]= X[nz]/(2.0*np.pi*r2[nz])
    area=dx_cm*dx_cm
    fx=fftconvolve(bz,kx,mode="full")*area
    fy=fftconvolve(bz,ky,mode="full")*area
    sy,sx=ny-1,nx-1
    return fx[sy:sy+ny,sx:sx+nx],fy[sy:sy+ny,sx:sx+nx]

def ap_diagnostics(bz,apx,apy,dx_cm,mask):
    curl=np.gradient(apy,dx_cm,axis=1)-np.gradient(apx,dx_cm,axis=0)
    m=mask&np.isfinite(bz)&np.isfinite(curl)
    if m.sum()<10: return float("nan"),float("inf")
    corr=float(pearsonr(bz[m],curl[m]).statistic)
    den=float(np.sqrt(np.mean(bz[m]**2)))
    nrmse=float(np.sqrt(np.mean((curl[m]-bz[m])**2))/max(den,1e-30))
    return corr,nrmse

def induction_reduction(pair,dx_km,mask):
    vx,vy,vz=pair["vx"],pair["vy"],pair["vz"]
    bx,by,bz,bzt=pair["bx"],pair["by"],pair["bz"],pair["bzt"]
    fx=vx*bz-vz*bx; fy=vy*bz-vz*by
    div=np.gradient(fx,dx_km,axis=1)+np.gradient(fy,dx_km,axis=0)
    res=bzt+div
    m=mask&np.isfinite(res)&np.isfinite(bzt)
    if m.sum()<10: return float("-inf"),float("inf"),float("inf")
    base=float(np.sqrt(np.mean(bzt[m]**2))); rr=float(np.sqrt(np.mean(res[m]**2)))
    reduction=float(1.0-rr/max(base,1e-30))
    return reduction,base,rr

def helicity_flux(pair,mask,dx_km):
    bx,by,bz=pair["bx"],pair["by"],pair["bz"]
    vpx,vpy,vpz=vperp(pair)
    dx_cm=dx_km*1e5
    apx,apy=ap_green(bz,dx_cm)
    dA=dx_cm*dx_cm
    density=2.0*((apx*bx+apy*by)*(vpz*1e5)-(apx*(vpx*1e5)+apy*(vpy*1e5))*bz)
    good=mask&np.isfinite(density)
    return float(np.sum(density[good])*dA),apx,apy,density

def symdiff(a,b):
    return float(2.0*abs(a-b)/(abs(a)+abs(b)+1e-30))

def load_frame(client,harp,trec,out,transport):
    q=f"hmi.sharp_cea_720s[{harp}][{trec}]"
    k,s=client.query(q,key=",".join(KEYS),seg=",".join(SEGS))
    if len(k)!=1 or len(s)!=1: raise RuntimeError(f"{q}: expected one record")
    kw={key:(None if pd.isna(k.iloc[0][key]) else k.iloc[0][key]) for key in KEYS}
    arrays={}
    recdir=out/"fits"/f"HARP{harp}_{trec.replace(':','-')}"
    for seg in SEGS:
        raw=str(s.iloc[0][seg])
        url=raw if raw.startswith("http") else "https://jsoc1.stanford.edu"+(raw if raw.startswith("/") else "/"+raw)
        p=recdir/f"{seg}.fits"
        tr=download(url,p); tr.update({"HARPNUM":harp,"T_REC":trec,"segment":seg})
        transport.append(tr); arrays[seg]=fits2d(p)
    if len({a.shape for a in arrays.values()})!=1: raise RuntimeError(f"{q}: shape mismatch")
    return arrays,kw

def pair_mask(start,stop,center,bz_mid,guard,threshold,centered):
    m=high_conf(start)&high_conf(stop)
    if centered: m &= high_conf(center)
    m &= np.isfinite(bz_mid)
    bal=m&edge_guard(m.shape,guard)
    integ=bal&(np.abs(bz_mid)>=threshold)
    return bal,integ

def parity_flux(pair,mask,dx_km):
    # active x-reflection: B axial, v polar
    bx=pair["bx"][:,::-1]
    by=-pair["by"][:,::-1]
    bz=-pair["bz"][:,::-1]
    vx=-pair["vx"][:,::-1]
    vy=pair["vy"][:,::-1]
    vz=pair["vz"][:,::-1]
    pp={"bx":bx,"by":by,"bz":bz,"vx":vx,"vy":vy,"vz":vz}
    return helicity_flux(pp,mask[:,::-1],dx_km)[0]

def synthetic_test(window,dx_km,dt_s,true_u,true_v):
    ny=nx=96
    y,x=np.mgrid[0:ny,0:nx]
    g1=np.exp(-((x-28.)**2+(y-35.)**2)/(2*9.**2))
    g2=np.exp(-((x-66.)**2+(y-58.)**2)/(2*12.**2))
    g3=np.exp(-((x-52.)**2+(y-26.)**2)/(2*14.**2))
    bz0=950*g1-720*g2+110*np.sin(x/6.7)*np.cos(y/8.3)
    bx0=260*g3+80*np.cos(x/8.0)*np.sin(y/11.0)
    by0=-210*g1+160*g2+70*np.sin((x+y)/9.0)
    sx=true_u*dt_s/dx_km; sy=true_v*dt_s/dx_km
    sh=(sy,sx)
    bx1=nd_shift(bx0,sh,order=3,mode="nearest")
    by1=nd_shift(by0,sh,order=3,mode="nearest")
    bz1=nd_shift(bz0,sh,order=3,mode="nearest")
    a={"Bp":bx0,"Bt":-by0,"Br":bz0}; b={"Bp":bx1,"Bt":-by1,"Br":bz1}
    pair=dave_pair(a,b,dt_s,dx_km,window)
    m=edge_guard((ny,nx),20)&(np.abs((bz0+bz1)/2)>=50)&pair["solved"]
    u=float(np.median(pair["vx"][m])); v=float(np.median(pair["vy"][m]))
    err=float(np.sqrt((u-true_u)**2+(v-true_v)**2))
    return {"recovered_u_km_s":u,"recovered_v_km_s":v,"true_u_km_s":true_u,"true_v_km_s":true_v,
            "vector_error_km_s":err,"sign_u_match":np.sign(u)==np.sign(true_u),"sign_v_match":np.sign(v)==np.sign(true_v),
            "valid_pixels":int(m.sum())}

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--lock",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    out=args.out; out.mkdir(parents=True,exist_ok=True)
    lock=json.loads(args.lock.read_text())
    add=json.loads((args.lock.parent/"OPERATOR_NUMERICAL_ADDENDUM.json").read_text())
    guard=int(add["edge_guard_pixels"])
    client=drms.Client()
    transport=[]
    report={"format":"KCH_HELICOIDAL_V1_3_HELICITY_FLUX_OPERATOR_RESULT","lock_sha256":sha256_file(args.lock),
            "started_at_utc":datetime.utcnow().isoformat()+"Z","regions":[],"authority_ceiling":"NONE"}
    try:
        syn=synthetic_test(lock["synthetic_qualification"]["primary_window_pixels"],
                           lock["synthetic_qualification"]["pixel_size_km"],
                           lock["synthetic_qualification"]["cadence_seconds"],
                           lock["synthetic_qualification"]["true_velocity_km_s"][0],
                           lock["synthetic_qualification"]["true_velocity_km_s"][1])
        syn_pass=(syn["vector_error_km_s"]<=lock["synthetic_qualification"]["median_horizontal_velocity_absolute_error_km_s_max"]
                  and syn["sign_u_match"] and syn["sign_v_match"])
        report["synthetic"]=syn; report["synthetic_pass"]=bool(syn_pass)
        if not syn_pass:
            report["outcome"]="SYNTHETIC_DAVE4VM_RECOVERY_FAILED"
            write_json(out/"HELICITY_FLUX_OPERATOR_RESULT.json",report)
            print(json.dumps(report,indent=2,sort_keys=True)); return 4

        for rec in lock["real_data_panel"]["records"]:
            harp=int(rec["HARPNUM"]); t=parse_trec(rec["T_REC"])
            ts=[fmt_trec(t-timedelta(minutes=12)),fmt_trec(t),fmt_trec(t+timedelta(minutes=12))]
            frames=[]; kws=[]
            for trec in ts:
                fr,kw=load_frame(client,harp,trec,out,transport); frames.append(fr); kws.append(kw)
            shapes={a["Br"].shape for a in frames}
            if len(shapes)!=1: raise RuntimeError(f"HARP{harp}: temporal shape mismatch")
            sl=bbox_union([high_conf(fr) for fr in frames],24)
            frames=[crop_frame(fr,sl) for fr in frames]
            f0,f1,f2=frames
            dx_km=float(kws[1]["RSUN_REF"])*math.radians(float(kws[1]["CDELT1"]))/1000.0

            p24=dave_pair(f0,f2,1440.0,dx_km,19)
            bmask24,imask24=pair_mask(f0,f2,f1,p24["bz"],guard,50.0,True)
            imbalance=float(abs(np.sum(p24["bz"][bmask24]))/max(np.sum(np.abs(p24["bz"][bmask24])),1e-30))
            if imbalance>lock["boundary_and_mask"]["maximum_unsigned_flux_imbalance_fraction"]:
                region={"NOAA_AR":rec["NOAA_AR"],"HARPNUM":harp,"flux_imbalance":imbalance,"status":"BOUNDARY_FLUX_IMBALANCE"}
                report["regions"].append(region); continue
            flux24,apx,apy,_=helicity_flux(p24,imask24,dx_km)
            apcorr,aprmse=ap_diagnostics(p24["bz"],apx,apy,dx_km*1e5,bmask24&edge_guard(p24["bz"].shape,guard))
            indred,base_rms,res_rms=induction_reduction(p24,dx_km,imask24)
            solfrac=float(np.mean(p24["solved"][imask24])) if imask24.sum() else 0.0

            rev=dave_pair(f2,f0,1440.0,dx_km,19)
            fluxrev=helicity_flux(rev,imask24,dx_km)[0]
            revanti=float(abs(flux24+fluxrev)/max(abs(flux24),1e-30))

            p13=dave_pair(f0,f2,1440.0,dx_km,13)
            flux13=helicity_flux(p13,imask24,dx_km)[0]

            pl=dave_pair(f0,f1,720.0,dx_km,19)
            _,ml=pair_mask(f0,f1,f1,pl["bz"],guard,50.0,False)
            fl=helicity_flux(pl,ml,dx_km)[0]
            pr=dave_pair(f1,f2,720.0,dx_km,19)
            _,mr=pair_mask(f1,f2,f1,pr["bz"],guard,50.0,False)
            fr=helicity_flux(pr,mr,dx_km)[0]
            f12avg=(fl+fr)/2.0

            fp=parity_flux(p24,imask24,dx_km)
            parityanti=float(abs(flux24+fp)/max(abs(flux24),1e-30))
            region={
              **rec,"crop_shape":list(p24["bz"].shape),"pixel_size_km":dx_km,
              "integration_pixels":int(imask24.sum()),"flux_imbalance":imbalance,
              "velocity_solution_fraction":solfrac,
              "induction_residual_reduction_fraction":indred,"baseline_induction_rms":base_rms,"fitted_induction_rms":res_rms,
              "Ap_curl_correlation":apcorr,"Ap_curl_normalized_rmse":aprmse,
              "dHdt_primary_19px_24m_Mx2_s":flux24,"dHdt_reverse_Mx2_s":fluxrev,
              "time_reversal_relative_antisymmetry":revanti,
              "dHdt_window13_Mx2_s":flux13,"window_same_sign":bool(np.sign(flux13)==np.sign(flux24)),
              "window_symmetric_relative_difference":symdiff(flux13,flux24),
              "dHdt_left12_Mx2_s":fl,"dHdt_right12_Mx2_s":fr,"dHdt_12m_average_Mx2_s":f12avg,
              "cadence_same_sign":bool(np.sign(f12avg)==np.sign(flux24)),
              "cadence_symmetric_relative_difference":symdiff(f12avg,flux24),
              "dHdt_parity_Mx2_s":fp,"parity_relative_antisymmetry":parityanti,
              "status":"EVALUATED"
            }
            report["regions"].append(region)
            print(json.dumps({"region":rec["NOAA_AR"],"flux":flux24,"induction_reduction":indred,"window_diff":region["window_symmetric_relative_difference"],"cadence_diff":region["cadence_symmetric_relative_difference"]}),flush=True)

        df=pd.DataFrame(report["regions"])
        evald=df[df.status=="EVALUATED"].copy() if len(df) else pd.DataFrame()
        gates=lock["qualification_gates"]
        if len(evald)!=4:
            outcome="NOT_IDENTIFIABLE_BOUNDARY_OR_FLUX_BALANCE"
        else:
            potential_pass=bool((evald.Ap_curl_correlation>=gates["Ap_curl_correlation_min_each"]).all() and
                                (evald.Ap_curl_normalized_rmse<=gates["Ap_curl_normalized_rmse_max_each"]).all())
            realvel_pass=bool((evald.integration_pixels>=gates["minimum_integration_pixels_each"]).all() and
                              (evald.velocity_solution_fraction>=gates["minimum_velocity_solution_fraction_each"]).all() and
                              (evald.induction_residual_reduction_fraction>=gates["minimum_induction_residual_reduction_fraction_each"]).all())
            reverse_pass=bool((evald.time_reversal_relative_antisymmetry<=gates["time_reversal_relative_antisymmetry_max_each"]).all())
            parity_pass=bool((evald.parity_relative_antisymmetry<=gates["parity_relative_antisymmetry_max_each"]).all())
            window_signs=int(evald.window_same_sign.sum())
            cadence_signs=int(evald.cadence_same_sign.sum())
            window_median=float(evald.window_symmetric_relative_difference.median())
            cadence_median=float(evald.cadence_symmetric_relative_difference.median())
            window_pass=window_signs>=gates["window_13_19_same_sign_min_regions"] and window_median<=gates["window_13_19_median_symmetric_relative_difference_max"]
            cadence_pass=cadence_signs>=gates["cadence_12_24_same_sign_min_regions"] and cadence_median<=gates["cadence_12_24_median_symmetric_relative_difference_max"]
            report["aggregate"]={
              "potential_operator_pass":potential_pass,"real_velocity_operator_pass":realvel_pass,
              "time_reversal_pass":reverse_pass,"parity_pass":parity_pass,
              "window_same_sign_regions":window_signs,"window_median_symmetric_relative_difference":window_median,"window_stability_pass":bool(window_pass),
              "cadence_same_sign_regions":cadence_signs,"cadence_median_symmetric_relative_difference":cadence_median,"cadence_stability_pass":bool(cadence_pass)
            }
            if not potential_pass: outcome="POTENTIAL_VECTOR_OPERATOR_FAILED"
            elif not realvel_pass: outcome="REAL_DATA_VELOCITY_OPERATOR_FAILED"
            elif not reverse_pass: outcome="HELICITY_FLUX_TIME_REVERSAL_FAILED"
            elif not parity_pass: outcome="POTENTIAL_VECTOR_OPERATOR_FAILED"
            elif not window_pass: outcome="HELICITY_FLUX_WINDOW_UNSTABLE"
            elif not cadence_pass: outcome="HELICITY_FLUX_CADENCE_UNSTABLE"
            else: outcome="HELICITY_FLUX_OPERATOR_QUALIFIED"
        report["outcome"]=outcome
        report["completed_at_utc"]=datetime.utcnow().isoformat()+"Z"
        report["scientific_claim"]="OPERATOR_QUALIFICATION_ONLY"
        report["helicity_injection_population_claim"]="NOT_EVALUATED"
        canon=json.dumps(report,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
        report["result_id"]="mhd13op:"+hashlib.sha256(canon).hexdigest()
        write_json(out/"HELICITY_FLUX_OPERATOR_RESULT.json",report)
        pd.DataFrame(report["regions"]).to_csv(out/"HELICITY_FLUX_OPERATOR_METRICS.csv",index=False)
        pd.DataFrame(transport).to_csv(out/"EXACT_SEGMENT_TRANSPORT.csv",index=False)
        files=sorted(p for p in out.rglob("*") if p.is_file() and p.name!="SHA256SUMS.txt")
        (out/"SHA256SUMS.txt").write_text("".join(f"{sha256_file(p)}  {p.relative_to(out).as_posix()}\n" for p in files),encoding="utf-8")
        print(json.dumps({"outcome":outcome,"result_id":report["result_id"],"synthetic":syn,"aggregate":report.get("aggregate")},indent=2,sort_keys=True))
        return 0
    except Exception as exc:
        fail={"format":"KCH_HELICOIDAL_V1_3_OPERATOR_FAIL_CLOSED","error_type":type(exc).__name__,"error":str(exc),"traceback":traceback.format_exc(),"scientific_claim_authorized":False,"authority_ceiling":"NONE"}
        write_json(out/"FAIL_CLOSED_RECEIPT.json",fail)
        print(traceback.format_exc())
        return 2

if __name__=="__main__": raise SystemExit(main())
