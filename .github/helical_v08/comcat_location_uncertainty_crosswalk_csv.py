from __future__ import annotations

import argparse, bisect, csv, hashlib, io, json, math, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import numpy as np

COHORTS={0:("BAY_AREA_HAYWARD_CALAVERAS",(36.85,38.45,-122.75,-121.15)),1:("PARKFIELD_CENTRAL_SAF",(35.45,36.25,-121.05,-119.95))}
START_YEAR,END_YEAR,LIMIT=1981,2021,20000

def sha256_bytes(b): return hashlib.sha256(b).hexdigest()
def write_json(p,obj):
    p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8")
def hav(lat1,lon1,lat2,lon2):
    r=6371.0088;p1=math.radians(lat1);p2=math.radians(lat2);dp=math.radians(lat2-lat1);dl=math.radians(lon2-lon1)
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2;return 2*r*math.asin(min(1,math.sqrt(a)))
def fetch(url,retries=4):
    err=None
    for a in range(retries):
        try:
            req=urllib.request.Request(url,headers={"User-Agent":"KCH-Helical-v0.8-ComCat-csv-crosswalk","Accept-Encoding":"identity"})
            with urllib.request.urlopen(req,timeout=180) as r:
                b=r.read();return b,{"status":int(r.status),"effective_url":r.geturl(),"bytes":len(b),"sha256":sha256_bytes(b),"content_type":r.headers.get("Content-Type")}
        except Exception as e: err=e; time.sleep(2**a)
    raise RuntimeError(f"request failure {url}: {err}")
def tofloat(x):
    if x is None or str(x).strip()=="" or str(x).lower()=="nan": return None
    try:return float(x)
    except:return None
def epoch(s):
    return datetime.fromisoformat(str(s).replace("Z","+00:00")).timestamp()
def get_catalog(out,code,bbox):
    name,_=COHORTS[code];a,b,c,d=bbox;events=[];seen=set();receipts=[]
    for year in range(START_YEAR,END_YEAR+1):
        off=1;page=0
        while True:
            params={"format":"csv","starttime":f"{year}-01-01T00:00:00.000Z","endtime":f"{year}-12-31T23:59:59.999Z",
                    "minlatitude":a,"maxlatitude":b,"minlongitude":c,"maxlongitude":d,"orderby":"time-asc","limit":LIMIT,"offset":off}
            url="https://earthquake.usgs.gov/fdsnws/event/1/query?"+urllib.parse.urlencode(params)
            body,rec=fetch(url); rd=out/"raw_csv"/name;rd.mkdir(parents=True,exist_ok=True)
            path=rd/f"{year}_p{page:03d}.csv";path.write_bytes(body)
            text=body.decode("utf-8-sig",errors="strict"); rows=list(csv.DictReader(io.StringIO(text)))
            rec.update({"cohort":name,"year":year,"page":page,"offset":off,"url":url,"path":str(path.relative_to(out)),"row_count":len(rows)})
            receipts.append(rec)
            for row in rows:
                fid=str(row.get("id",""))
                if fid and fid not in seen:
                    seen.add(fid)
                    events.append({"id":fid,"time":epoch(row["time"]),"lat":float(row["latitude"]),"lon":float(row["longitude"]),
                                   "depth":float(row["depth"]),"mag":tofloat(row.get("mag")),"net":row.get("net"),"locationSource":row.get("locationSource"),
                                   "horizontalError":tofloat(row.get("horizontalError")),"depthError":tofloat(row.get("depthError"))})
            if len(rows)<LIMIT:break
            off+=LIMIT;page+=1
    events.sort(key=lambda x:(x["time"],x["id"]));return events,receipts
def match(sel,events):
    ts=np.array([e["time"] for e in events]);out=[];m=he=de=both=amb=0
    for r in sel:
        t=r["epoch"];lo=bisect.bisect_left(ts,t-3);hi=bisect.bisect_right(ts,t+3);evid=str(int(r["evid"]));rank=[]
        for e in events[lo:hi]:
            dt=abs(e["time"]-t);h=hav(r["lat"],r["lon"],e["lat"],e["lon"]);dz=abs(r["depth"]-e["depth"]);dm=abs(r["mag"]-e["mag"]) if e["mag"] is not None else 9
            alias=e["id"].endswith(evid);score=(dt/1)**2+(h/5)**2+(dz/10)**2+(dm/.5)**2-(4 if alias else 0)
            if dt<=2 and h<=15 and dz<=20 and dm<=1.5:rank.append((score,dt,h,dz,dm,e["id"],alias,e))
        rank.sort(key=lambda x:(x[0],x[1],x[2],x[3],x[4],x[5]))
        rec={"global_index":r["global_index"],"cohort_code":r["cohort_code"],"evid":evid,"matched":False,"candidate_count":len(rank)}
        if rank:
            best=rank[0];margin=rank[1][0]-best[0] if len(rank)>1 else None;isamb=margin is not None and margin<.25 and not best[6]
            if isamb:amb+=1;rec.update({"ambiguous":True,"best_score":best[0],"score_margin":margin})
            else:
                e=best[7];m+=1
                if e["horizontalError"] is not None:he+=1
                if e["depthError"] is not None:de+=1
                if e["horizontalError"] is not None and e["depthError"] is not None:both+=1
                rec.update({"matched":True,"ambiguous":False,"comcat_id":e["id"],"dt_seconds":best[1],"horizontal_distance_km":best[2],
                            "depth_difference_km":best[3],"magnitude_difference":best[4],"alias_hit":best[6],"match_score":best[0],"score_margin":margin,
                            "horizontalError_km":e["horizontalError"],"depthError_km":e["depthError"],"net":e["net"],"locationSource":e["locationSource"]})
        out.append(rec)
    n=len(sel);return out,{"selected":n,"matched":m,"ambiguous":amb,"match_fraction":m/max(n,1),"horizontal_error_fraction":he/max(n,1),
                            "depth_error_fraction":de/max(n,1),"both_errors_fraction":both/max(n,1),"both_errors_among_matched_fraction":both/max(m,1)}
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--selected-npz",type=Path,required=True);ap.add_argument("--out",type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    with np.load(a.selected_npz,allow_pickle=False) as z:
        keys=["global_index","cohort_code","evid","event_time_epoch","lat_reloc","lon_reloc","dep_reloc","mag","nc_sc"];data={k:z[k] for k in keys}
    receipts=[];cw=[];summ={}
    for code,(name,bbox) in COHORTS.items():
        idx=np.flatnonzero(data["cohort_code"]==code)
        sel=[{"global_index":int(data["global_index"][i]),"cohort_code":code,"evid":float(data["evid"][i]),"epoch":float(data["event_time_epoch"][i]),
              "lat":float(data["lat_reloc"][i]),"lon":float(data["lon_reloc"][i]),"depth":float(data["dep_reloc"][i]),"mag":float(data["mag"][i])} for i in idx]
        cat,recs=get_catalog(a.out,code,bbox);receipts+=recs;matched,s=match(sel,cat);cw+=matched;s["comcat_events_in_bbox"]=len(cat);summ[name]=s
    write_json(a.out/"COMCAT_CSV_QUERY_RECEIPTS.json",receipts);write_json(a.out/"COMCAT_CSV_LOCATION_UNCERTAINTY_CROSSWALK.json",cw)
    threshold=.80;outcome="LOCATION_UNCERTAINTY_CROSSWALK_PASS" if all(v["both_errors_fraction"]>=threshold for v in summ.values()) else "NOT_IDENTIFIABLE_LOCATION_UNCERTAINTY_COVERAGE"
    result={"format":"KCH_HELICAL_V0_8_COMCAT_CSV_LOCATION_UNCERTAINTY_GATE","representation":"USGS_FDSN_CSV",
            "outcome":outcome,"minimum_both_errors_fraction":threshold,"cohorts":summ,
            "matching_contract_inherited_from_geojson_gate":True,"directional_fields_accessed":False,
            "scientific_model_execution_performed":False,"result_is_confirmatory_scientific_evidence":False,"authority_ceiling":"NONE"}
    result["gate_id"]="h8loccsv:"+hashlib.sha256(json.dumps(result,sort_keys=True,separators=(",",":")).encode()).hexdigest();write_json(a.out/"COMCAT_CSV_LOCATION_UNCERTAINTY_GATE_RESULT.json",result)
    print(json.dumps(result,indent=2,sort_keys=True));return 0 if outcome.endswith("_PASS") else 3
if __name__=="__main__":raise SystemExit(main())
