from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import drms
import pandas as pd
import requests

SERIES = "hmi.sharp_cea_720s"
KEYS = [
    "HARPNUM","T_REC","NOAA_AR","NOAA_NUM","NOAA_ARS","QUALITY",
    "USFLUX","MEANJZH","ABSNJZH","TOTUSJH","MEANALP","MEANSHR",
    "SHRGT45","R_VALUE","TOTUSJZ","TOTPOT","AREA_ACR","LAT_FWT","LON_FWT",
]
GOES_BASE = "https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/multi/l2/data/xrsf-l2-flrpt_science/csv/"
START = pd.Timestamp("2026-01-01T00:00:00Z")
END = pd.Timestamp("2026-10-10T23:59:59Z")

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()

def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj,sort_keys=True,indent=2,default=str)+"\n",encoding="utf-8")

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--out",type=Path,required=True); a=ap.parse_args()
    out=a.out; out.mkdir(parents=True,exist_ok=True)
    client=drms.Client()
    frames=[]; receipts=[]
    for month in range(1,11):
        last=calendar.monthrange(2026,month)[1]
        s=pd.Timestamp(year=2026,month=month,day=1,hour=0,tz="UTC")
        e=pd.Timestamp(year=2026,month=month,day=last,hour=18,tz="UTC")
        if e>END: e=END.floor("h")
        qs=s.strftime("%Y.%m.%d_%H:%M_TAI"); qe=e.strftime("%Y.%m.%d_%H:%M_TAI")
        q=f"{SERIES}[][{qs}-{qe}@6h]"
        frame=None
        for attempt in range(1,6):
            try:
                frame=client.query(q,key=",".join(KEYS)).reset_index(drop=False); break
            except Exception:
                if attempt==5: raise
                time.sleep(5*attempt)
        p=out/f"sharp_cea_6h_2026_{month:02d}.csv"
        frame.to_csv(p,index=False,lineterminator="\n")
        receipts.append({"month":month,"query":q,"rows":len(frame),"bytes":p.stat().st_size,"sha256":sha256(p)})
        frames.append(frame)
        time.sleep(0.5)
    allf=pd.concat(frames,ignore_index=True)
    allp=out/"sharp_cea_6h_2026.csv"; allf.to_csv(allp,index=False,lineterminator="\n")

    headers={"User-Agent":"KCH-Helical-v1.1-fresh-2026/2026-10-11"}
    listing=requests.get(GOES_BASE,headers=headers,timeout=180); listing.raise_for_status()
    import re
    names=sorted(set(re.findall(rb"sci_xrsf-l2-flrpt_geo_s\d+_e\d+_v[\d-]+\.csv",listing.content)))
    if not names: raise RuntimeError("GOES flare report not found")
    name=names[-1].decode("ascii")
    flare=requests.get(GOES_BASE+name,headers=headers,timeout=180); flare.raise_for_status()
    fp=out/name; fp.write_bytes(flare.content)
    lp=out/"goes_listing.html"; lp.write_bytes(listing.content)

    report={
      "format":"KCH_MHD_FRESH_2026_EXACT_SOURCE_ACQUISITION_V1",
      "acquired_at_utc":datetime.now(timezone.utc).isoformat().replace("+00:00","Z"),
      "window":["2026-01-01","2026-10-10"],
      "series":SERIES,"keys":KEYS,
      "monthly":receipts,
      "annual":{"rows":len(allf),"bytes":allp.stat().st_size,"sha256":sha256(allp)},
      "goes":{"file":name,"bytes":fp.stat().st_size,"sha256":sha256(fp),"listing_sha256":sha256(lp)},
      "scientific_model_execution_performed":False,
      "authority_ceiling":"NONE",
    }
    write_json(out/"ACQUISITION_RECEIPT.json",report)
    files=sorted(p for p in out.iterdir() if p.is_file() and p.name!="SHA256SUMS.txt")
    (out/"SHA256SUMS.txt").write_text("".join(f"{sha256(p)}  {p.name}\n" for p in files),encoding="utf-8")
    print(json.dumps(report,indent=2,sort_keys=True))
    return 0

if __name__=="__main__": raise SystemExit(main())
