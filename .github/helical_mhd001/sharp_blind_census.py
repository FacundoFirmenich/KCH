from __future__ import annotations

import hashlib
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import drms
import pandas as pd

SERIES = 'hmi.sharp_cea_720s'
START = datetime(2010, 5, 1, tzinfo=timezone.utc)
END = datetime(2026, 1, 1, tzinfo=timezone.utc)
CHUNK_DAYS = 92
KEYS = ['HARPNUM','T_REC','NOAA_AR','NOAA_ARS','QUALITY','LON_FWT','LAT_FWT']
PARTITIONS = {
    'train': (datetime(2010,5,1,tzinfo=timezone.utc), datetime(2018,1,1,tzinfo=timezone.utc)),
    'calibration': (datetime(2018,1,1,tzinfo=timezone.utc), datetime(2022,1,1,tzinfo=timezone.utc)),
    'sealed_test': (datetime(2022,1,1,tzinfo=timezone.utc), datetime(2026,1,1,tzinfo=timezone.utc)),
}


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def parse_trec(text: str) -> datetime:
    return datetime.strptime(str(text), '%Y.%m.%d_%H:%M:%S_TAI').replace(tzinfo=timezone.utc)


def partition_of(t: datetime) -> str:
    for name,(a,b) in PARTITIONS.items():
        if a <= t < b: return name
    raise ValueError(t)


def main() -> int:
    out=Path(os.environ.get('CENSUS_OUT','/tmp/mhd001-sharp-census'))
    out.mkdir(parents=True,exist_ok=True)
    client=drms.Client()
    rows=[]
    chunk_receipts=[]
    cursor=START
    while cursor < END:
        stop=min(cursor+timedelta(days=CHUNK_DAYS),END)
        duration=max(1,int(math.ceil((stop-cursor).total_seconds()/86400.0)))
        start_text=cursor.strftime('%Y.%m.%d_%H:%M:%S_TAI')
        query=f'{SERIES}[][{start_text}/{duration}d@1h]'
        frame=client.query(query,key=','.join(KEYS))
        if frame is None: frame=pd.DataFrame(columns=KEYS)
        frame=frame.reset_index(drop=True)
        chunk_path=out/f'chunk_{cursor:%Y%m%d}_{stop:%Y%m%d}.csv'
        frame.to_csv(chunk_path,index=False)
        chunk_receipts.append({
            'query':query,'start_utc':cursor.isoformat(),'stop_exclusive_utc':stop.isoformat(),
            'records':int(len(frame)),'csv':chunk_path.name,'csv_sha256':sha256(chunk_path),
        })
        if len(frame): rows.append(frame)
        cursor=stop

    combined=pd.concat(rows,ignore_index=True) if rows else pd.DataFrame(columns=KEYS)
    combined=combined.drop_duplicates(subset=['HARPNUM','T_REC'],keep='first').copy()
    combined['time_utc']=combined['T_REC'].map(parse_trec)
    combined=combined[(combined.time_utc>=START)&(combined.time_utc<END)].copy()
    combined['partition']=combined.time_utc.map(partition_of)
    combined['QUALITY_num']=pd.to_numeric(combined['QUALITY'],errors='coerce')
    combined['LON_num']=pd.to_numeric(combined['LON_FWT'],errors='coerce')
    combined['definitive_quality_pass']=combined['QUALITY_num'].eq(0)
    combined['disk_position_pass']=combined['LON_num'].abs().le(60.0)
    combined['blind_primary_record_pass']=combined.definitive_quality_pass & combined.disk_position_pass

    summaries=[]
    for (partition,harp),g in combined.groupby(['partition','HARPNUM'],sort=True):
        good=g[g.blind_primary_record_pass]
        noaa=sorted({str(x) for x in g.NOAA_AR if pd.notna(x) and str(x) not in {'0','0.0','nan','None'}})
        summaries.append({
            'partition':partition,'HARPNUM':int(harp),'records_total':int(len(g)),
            'records_quality_disk_pass':int(len(good)),
            'first_time_utc':g.time_utc.min().isoformat(),
            'last_time_utc':g.time_utc.max().isoformat(),
            'time_span_days':float((g.time_utc.max()-g.time_utc.min()).total_seconds()/86400.0),
            'noaa_ar_values':';'.join(noaa),
            'has_primary_record':bool(len(good)>0),
        })
    summary_df=pd.DataFrame(summaries).sort_values(['partition','HARPNUM'])
    summary_path=out/'BLIND_HARP_SUMMARY.csv'; summary_df.to_csv(summary_path,index=False)
    counts={}
    for part in PARTITIONS:
        p=summary_df[summary_df.partition==part]
        counts[part]={
            'harp_count_total':int(len(p)),
            'harp_count_with_primary_record':int(p.has_primary_record.sum()),
            'record_count_total':int((combined.partition==part).sum()),
            'record_count_quality_disk_pass':int(((combined.partition==part)&combined.blind_primary_record_pass).sum()),
        }
    overlap={}
    sets={part:set(summary_df.loc[summary_df.partition==part,'HARPNUM'].astype(int)) for part in PARTITIONS}
    names=list(PARTITIONS)
    for i,a in enumerate(names):
        for b in names[i+1:]: overlap[f'{a}__{b}']=sorted(sets[a]&sets[b])

    body={
        'format':'KCH_MHD_HELICAL_OBSERVABILITY_001_BLIND_HARP_CENSUS',
        'series':SERIES,'cadence':'1h','start_utc':START.isoformat(),'end_exclusive_utc':END.isoformat(),
        'fields_accessed':KEYS,'helical_keywords_accessed':False,'flare_labels_accessed':False,
        'unique_record_count':int(len(combined)),'counts':counts,
        'harp_overlap_across_time_partitions':{k:len(v) for k,v in overlap.items()},
        'overlapping_harp_ids_sha256':hashlib.sha256(canonical(overlap)).hexdigest(),
        'summary_csv_sha256':sha256(summary_path),'summary_csv_bytes':summary_path.stat().st_size,
        'chunk_receipts':chunk_receipts,
        'next_state':'AWAITING_EXACT_FLARE_LABEL_ACQUISITION_AND_HARP_DISJOINT_PARTITION_ADJUDICATION',
        'scientific_execution_performed':False,'authority_ceiling':'NONE',
    }
    body['census_id']='mhd001census:'+hashlib.sha256(canonical(body)).hexdigest()
    (out/'BLIND_HARP_CENSUS.json').write_text(json.dumps(body,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(body,indent=2,sort_keys=True))
    return 0 if all(counts[p]['harp_count_with_primary_record']>0 for p in counts) else 3

if __name__=='__main__': raise SystemExit(main())
