from __future__ import annotations

import argparse, bisect, hashlib, json, math, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import numpy as np

COHORTS = {
    0: ("BAY_AREA_HAYWARD_CALAVERAS", (36.85, 38.45, -122.75, -121.15)),
    1: ("PARKFIELD_CENTRAL_SAF", (35.45, 36.25, -121.05, -119.95)),
}
START_YEAR, END_YEAR = 1981, 2021
LIMIT = 20000

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+"\n", encoding="utf-8")

def haversine_km(lat1, lon1, lat2, lon2):
    r=6371.0088
    p1,p2=math.radians(lat1),math.radians(lat2)
    dp=math.radians(lat2-lat1); dl=math.radians(lon2-lon1)
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*r*math.asin(min(1.0,math.sqrt(a)))

def get(url: str, retries: int=4) -> tuple[bytes, dict[str, Any]]:
    err=None
    for attempt in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"KCH-Helical-v0.8-ComCat-crosswalk","Accept-Encoding":"identity"})
            with urllib.request.urlopen(req,timeout=180) as r:
                body=r.read()
                receipt={"status":int(r.status),"effective_url":r.geturl(),"headers":dict(r.headers.items()),
                         "bytes":len(body),"sha256":sha256_bytes(body)}
                return body,receipt
        except Exception as e:
            err=e; time.sleep(2**attempt)
    raise RuntimeError(f"request failed after {retries} attempts: {url}: {err}")

def fetch_comcat(out: Path, code: int, bbox: tuple[float,float,float,float]):
    name,_=COHORTS[code]; lat_min,lat_max,lon_min,lon_max=bbox
    all_features=[]; receipts=[]; seen=set()
    for year in range(START_YEAR,END_YEAR+1):
        offset=1; page=0
        while True:
            params={
                "format":"geojson","starttime":f"{year}-01-01T00:00:00.000Z",
                "endtime":f"{year}-12-31T23:59:59.999Z",
                "minlatitude":f"{lat_min:.6f}","maxlatitude":f"{lat_max:.6f}",
                "minlongitude":f"{lon_min:.6f}","maxlongitude":f"{lon_max:.6f}",
                "orderby":"time-asc","limit":str(LIMIT),"offset":str(offset),
            }
            url="https://earthquake.usgs.gov/fdsnws/event/1/query?"+urllib.parse.urlencode(params)
            body,rec=get(url)
            raw_dir=out/"raw"/name; raw_dir.mkdir(parents=True,exist_ok=True)
            path=raw_dir/f"{year}_p{page:03d}.geojson"; path.write_bytes(body)
            rec.update({"cohort":name,"year":year,"page":page,"offset":offset,"url":url,"path":str(path.relative_to(out))})
            obj=json.loads(body)
            features=obj.get("features",[])
            for f in features:
                fid=str(f.get("id"))
                if fid not in seen:
                    seen.add(fid); all_features.append(f)
            receipts.append(rec)
            if len(features)<LIMIT: break
            offset += LIMIT; page += 1
    all_features.sort(key=lambda f:(float(f["properties"]["time"]),str(f["id"])))
    return all_features,receipts

def aliases(feature):
    p=feature["properties"]; out={str(feature["id"])}
    ids=p.get("ids")
    if ids:
        out.update(x for x in str(ids).split(",") if x)
    code=p.get("code")
    if code:
        out.add(str(code)); out.add(str(p.get("net",""))+str(code))
    return out

def match(selected, features):
    times=np.array([float(f["properties"]["time"])/1000.0 for f in features],dtype=float)
    results=[]; matched=0; with_h=0; with_d=0; with_both=0; ambiguous=0
    for row in selected:
        t=float(row["epoch"]); lo=bisect.bisect_left(times,t-3.0); hi=bisect.bisect_right(times,t+3.0)
        evid=str(int(row["evid"]))
        ranked=[]
        for f in features[lo:hi]:
            p=f["properties"]; c=f["geometry"]["coordinates"]
            dt=abs(float(p["time"])/1000.0-t)
            h=haversine_km(row["lat"],row["lon"],float(c[1]),float(c[0]))
            dz=abs(float(row["depth"])-float(c[2]))
            pm=p.get("mag"); dm=abs(float(row["mag"])-float(pm)) if pm is not None else 9.0
            alias=any(a.endswith(evid) for a in aliases(f))
            score=(dt/1.0)**2+(h/5.0)**2+(dz/10.0)**2+(dm/0.5)**2-(4.0 if alias else 0.0)
            if dt<=2.0 and h<=15.0 and dz<=20.0 and dm<=1.5:
                ranked.append((score,dt,h,dz,dm,str(f["id"]),alias,f))
        ranked.sort(key=lambda x:(x[0],x[1],x[2],x[3],x[4],x[5]))
        rec={"global_index":int(row["global_index"]),"cohort_code":int(row["cohort_code"]),"evid":evid,
             "matched":False,"candidate_count":len(ranked)}
        if ranked:
            best=ranked[0]
            margin=(ranked[1][0]-best[0]) if len(ranked)>1 else None
            is_ambiguous=margin is not None and margin<0.25 and not best[6]
            if is_ambiguous:
                ambiguous+=1; rec.update({"ambiguous":True,"best_score":best[0],"score_margin":margin})
            else:
                f=best[7]; p=f["properties"]; c=f["geometry"]["coordinates"]
                he=p.get("horizontalError"); de=p.get("depthError")
                rec.update({"matched":True,"ambiguous":False,"comcat_id":f["id"],"dt_seconds":best[1],
                            "horizontal_distance_km":best[2],"depth_difference_km":best[3],
                            "magnitude_difference":best[4],"alias_hit":bool(best[6]),"match_score":best[0],
                            "score_margin":margin,"comcat_lat":c[1],"comcat_lon":c[0],"comcat_depth":c[2],
                            "horizontalError_km":he,"depthError_km":de,"locationSource":p.get("locationSource"),
                            "net":p.get("net"),"status":p.get("status"),"ids":p.get("ids")})
                matched+=1
                if he is not None: with_h+=1
                if de is not None: with_d+=1
                if he is not None and de is not None: with_both+=1
        results.append(rec)
    return results,{"selected":len(selected),"matched":matched,"ambiguous":ambiguous,
                    "match_fraction":matched/max(len(selected),1),"horizontal_error_fraction":with_h/max(len(selected),1),
                    "depth_error_fraction":with_d/max(len(selected),1),"both_errors_fraction":with_both/max(len(selected),1)}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--selected-npz",type=Path,required=True); ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args(); a.out.mkdir(parents=True,exist_ok=True)
    with np.load(a.selected_npz,allow_pickle=False) as z:
        allowed=["global_index","cohort_code","evid","event_time_epoch","lat_reloc","lon_reloc","dep_reloc","mag","nc_sc"]
        data={k:z[k] for k in allowed}
        accessed=sorted(data)
        forbidden_accessed=sorted(set(accessed)&{"strike","dip","rake"})
        if forbidden_accessed: raise SystemExit(f"directional firewall violation {forbidden_accessed}")
    query_receipts=[]; crosswalk=[]; summaries={}
    for code,(name,bbox) in COHORTS.items():
        idx=np.flatnonzero(data["cohort_code"]==code)
        selected=[{"global_index":int(data["global_index"][i]),"cohort_code":code,"evid":float(data["evid"][i]),
                   "epoch":float(data["event_time_epoch"][i]),"lat":float(data["lat_reloc"][i]),
                   "lon":float(data["lon_reloc"][i]),"depth":float(data["dep_reloc"][i]),
                   "mag":float(data["mag"][i]),"nc_sc":str(data["nc_sc"][i])} for i in idx]
        features,recs=fetch_comcat(a.out,code,bbox); query_receipts.extend(recs)
        matched,summary=match(selected,features); crosswalk.extend(matched); summary["comcat_events_in_bbox"]=len(features); summaries[name]=summary
    write_json(a.out/"COMCAT_QUERY_RECEIPTS.json",query_receipts)
    write_json(a.out/"COMCAT_LOCATION_UNCERTAINTY_CROSSWALK.json",crosswalk)
    # Material gate only. Do not subset scientific sample here.
    minimum_both=0.80
    outcome="LOCATION_UNCERTAINTY_CROSSWALK_PASS" if all(v["both_errors_fraction"]>=minimum_both for v in summaries.values()) else "NOT_IDENTIFIABLE_LOCATION_UNCERTAINTY_COVERAGE"
    result={"format":"KCH_HELICAL_V0_8_COMCAT_LOCATION_UNCERTAINTY_GATE","outcome":outcome,
            "match_rule":{"time_seconds":2.0,"horizontal_km":15.0,"depth_km":20.0,"magnitude":1.5,
                          "score":"(dt/1)^2+(h/5)^2+(dz/10)^2+(dmag/0.5)^2-4*alias_hit",
                          "ambiguity_margin":0.25},
            "minimum_both_errors_fraction":minimum_both,"cohorts":summaries,
            "directional_fields_accessed":False,"scientific_model_execution_performed":False,
            "result_is_confirmatory_scientific_evidence":False,"authority_ceiling":"NONE"}
    canonical=json.dumps(result,sort_keys=True,separators=(",",":")).encode(); result["gate_id"]="h8loc:"+hashlib.sha256(canonical).hexdigest()
    write_json(a.out/"COMCAT_LOCATION_UNCERTAINTY_GATE_RESULT.json",result)
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if outcome.endswith("_PASS") else 3

if __name__=="__main__":
    raise SystemExit(main())
