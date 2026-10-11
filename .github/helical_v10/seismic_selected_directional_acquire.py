from __future__ import annotations

import argparse
import concurrent.futures
import gzip
import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BASE="https://earthquake.usgs.gov/fdsnws/event/1/query"
REGIONS=["BAY_AREA","PARKFIELD_CENTRAL_SAF"]

def sha256_bytes(b: bytes)->str: return hashlib.sha256(b).hexdigest()
def write_json(p:Path,o)->None:
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(o,sort_keys=True,indent=2,ensure_ascii=False,default=str)+"\n",encoding="utf-8")

def fetch_one(event_id:str, raw_dir:Path):
    headers={"User-Agent":"KCH-Helical-v1.1-terminal-seismic/2026-10-11"}
    params={"format":"geojson","eventid":event_id,"includeallorigins":"true","includeallmagnitudes":"true"}
    last=None
    for attempt in range(1,6):
        try:
            r=requests.get(BASE,params=params,headers=headers,timeout=90); r.raise_for_status()
            body=r.content
            path=raw_dir/f"{event_id}.geojson.gz"
            with gzip.open(path,"wb",compresslevel=6,mtime=0) as f: f.write(body)
            root=r.json()
            products=root.get("properties",{}).get("products",{}) or {}
            fm=products.get("focal-mechanism",[]) or []
            mt=products.get("moment-tensor",[]) or []
            def best(items):
                if not items: return None
                return sorted(items,key=lambda x:(float(x.get("preferredWeight",0) or 0),str(x.get("updateTime",""))),reverse=True)[0]
            chosen=best(fm) or best(mt)
            props=(chosen or {}).get("properties",{}) or {}
            return {
              "event_id":event_id,"http_status":r.status_code,"effective_url":r.url,
              "body_bytes":len(body),"body_sha256":sha256_bytes(body),
              "focal_mechanism_product_count":len(fm),"moment_tensor_product_count":len(mt),
              "selected_product_type":"focal-mechanism" if fm else ("moment-tensor" if mt else None),
              "selected_preferred_weight":(chosen or {}).get("preferredWeight"),
              "selected_update_time":(chosen or {}).get("updateTime"),
              "property_keys":"|".join(sorted(map(str,props.keys()))),
              "properties_json":json.dumps(props,sort_keys=True,separators=(",",":")),
            }
        except Exception as exc:
            last=repr(exc); time.sleep(min(10,attempt*2))
    return {"event_id":event_id,"error":last}

def main()->int:
    ap=argparse.ArgumentParser(); ap.add_argument("--preflight-root",type=Path,required=True); ap.add_argument("--out",type=Path,required=True); a=ap.parse_args()
    out=a.out; out.mkdir(parents=True,exist_ok=True)
    selected={}
    ids=[]
    for region in REGIONS:
        p=a.preflight_root/"assigned"/f"{region}.csv.gz"
        d=pd.read_csv(p,low_memory=False)
        d=d[d["reason"]=="ASSIGNED"].copy()
        selected[region]=d[["event_id","time_utc","longitude","latitude","depth_km","magnitude","fault_index","along_fault_km"]]
        ids += d["event_id"].astype(str).tolist()
    unique_ids=sorted(set(ids))
    raw=out/"raw_event_details"; raw.mkdir(exist_ok=True)
    rows=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures={pool.submit(fetch_one,eid,raw):eid for eid in unique_ids}
        for n,future in enumerate(concurrent.futures.as_completed(futures),1):
            rows.append(future.result())
            if n%250==0: print(f"fetched {n}/{len(unique_ids)}",flush=True)
    result=pd.DataFrame(rows).sort_values("event_id",kind="stable")
    result.to_csv(out/"DIRECTIONAL_PRODUCT_INDEX.csv.gz",index=False,compression="gzip")
    errors=result[result.get("error").notna()] if "error" in result.columns else result.iloc[0:0]
    for region,d in selected.items():
        merged=d.merge(result,on="event_id",how="left",validate="many_to_one")
        merged.to_csv(out/f"{region}_DIRECTIONAL_PRODUCTS.csv.gz",index=False,compression="gzip")
    key_counts=Counter()
    for keys in result.get("property_keys",pd.Series([],dtype=str)).dropna():
        for key in str(keys).split("|"):
            if key: key_counts[key]+=1
    report={
      "format":"KCH_HELICAL_V1_1_SELECTED_DIRECTIONAL_ACQUISITION",
      "acquired_at_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
      "graph_freeze_id":"fgf:570a56355d7b5fca2957aadb91b2ebd3c63a0d520581a0fc2c8fafff1b4d7c2e",
      "unique_event_ids":len(unique_ids),
      "successful_event_details":int(result["body_sha256"].notna().sum()) if "body_sha256" in result else 0,
      "failed_event_details":int(len(errors)),
      "focal_mechanism_selected":int((result["selected_product_type"]=="focal-mechanism").sum()) if "selected_product_type" in result else 0,
      "moment_tensor_fallback_selected":int((result["selected_product_type"]=="moment-tensor").sum()) if "selected_product_type" in result else 0,
      "selected_property_key_counts":dict(key_counts),
      "raw_event_details_preserved":True,
      "scientific_model_execution_performed":False,
      "authority_ceiling":"NONE",
    }
    write_json(out/"DIRECTIONAL_ACQUISITION_REPORT.json",report)
    files=sorted(p for p in out.rglob("*") if p.is_file() and p.name!="SHA256SUMS.txt")
    (out/"SHA256SUMS.txt").write_text("".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out).as_posix()}\n" for p in files),encoding="utf-8")
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0 if not len(errors) else 2

if __name__=="__main__": raise SystemExit(main())
