from __future__ import annotations

import json
import os
from pathlib import Path
import drms
import requests

OUT=Path(os.environ.get("OUT","/tmp/v12_vector_probe"))
OUT.mkdir(parents=True,exist_ok=True)
q="hmi.sharp_cea_720s[5249][2015.03.02_12:00:00_TAI]"
keys=["HARPNUM","T_REC","NOAA_AR","QUALITY","MEANJZH","TOTUSJH","MEANALP","CDELT1","RSUN_OBS","RSUN_REF"]
segments=["Br","Bt","Bp","conf_disambig","bitmap"]
client=drms.Client()
key,seg=client.query(q,key=",".join(keys),seg=",".join(segments))
report={"query":q,"keys":key.reset_index(drop=True).to_dict(orient="records"),"segments":seg.reset_index(drop=True).to_dict(orient="records"),"downloads":[]}
for name in segments:
    raw=str(seg.iloc[0][name])
    candidates=[]
    if raw.startswith("http://") or raw.startswith("https://"):
        candidates=[raw]
    else:
        path=raw if raw.startswith("/") else "/"+raw
        candidates=[
            "https://jsoc1.stanford.edu"+path,
            "https://jsoc.stanford.edu"+path,
            "http://jsoc.stanford.edu"+path,
        ]
    ok=False
    for i,url in enumerate(candidates):
        try:
            r=requests.get(url,headers={"User-Agent":"KCH-Helical-v1.2-vector-probe/2026-10-12"},timeout=60,stream=True)
            status=r.status_code
            body=b""
            if status==200:
                body=r.raw.read(1024)
            report["downloads"].append({"segment":name,"candidate":i,"url":url,"status":status,"prefix_hex":body[:32].hex(),"content_type":r.headers.get("content-type"),"content_length":r.headers.get("content-length")})
            if status==200 and body:
                ok=True; break
        except Exception as exc:
            report["downloads"].append({"segment":name,"candidate":i,"url":url,"error":repr(exc)})
    report.setdefault("segment_reachable",{})[name]=ok
(OUT/"VECTOR_SEGMENT_PROBE.json").write_text(json.dumps(report,indent=2,sort_keys=True,default=str)+"\n")
print(json.dumps(report,indent=2,sort_keys=True,default=str))
