"""Freeze quality-only window selection before FITS access; never inspect observables."""
from __future__ import annotations
from datetime import datetime, timedelta
from pathlib import Path
import hashlib, json, math, os, socket, time
import drms

HERE=Path(__file__).resolve().parent
FMT='%Y.%m.%d_%H:%M:%S_TAI'
KEYS=['HARPNUM','T_REC','QUALITY','CMASK']
SEGMENTS=['Br','Bt','Bp','conf_disambig','bitmap']
def canonical(x):
    return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def write(p,x):
    p.write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')
def clean(x):
    if hasattr(x,'item'): x=x.item()
    if isinstance(x,float) and not math.isfinite(x): return None
    return x

def main():
    socket.setdefaulttimeout(90)
    out=Path(os.environ['OUT'])/'metadata'
    out.mkdir(parents=True,exist_ok=False)
    raw=(HERE/'TEMPORAL_PROTOCOL_V1_6.json').read_bytes()
    p=json.loads(raw)
    spec=p['metadata_selection']
    assert spec['allowed_keys']==KEYS and spec['segments']==SEGMENTS
    receipt={'format':'KCH_SOLAR_V16_METADATA_SELECTION_V1','protocol_sha256':hashlib.sha256(raw).hexdigest(),'execution_commit':os.environ.get('GITHUB_SHA'),'run_id':os.environ.get('GITHUB_RUN_ID'),'allowed_keys':KEYS,'field_bodies_accessed':False,'observable_keywords_accessed':False,'harps':[],'errors':[],'selected_trajectories':[]}
    offsets=sorted(spec['candidate_start_offsets_minutes'],key=lambda m:(abs(m),m))
    for original in p['original_trajectories']:
        base=datetime.strptime(original['times_tai'][0],FMT)
        start=base+timedelta(minutes=min(offsets))
        expected={(base+timedelta(minutes=m+360*k)).strftime(FMT) for m in offsets for k in range(5)}
        duration=(max(offsets)-min(offsets)+4*360+12)*60
        query=f"hmi.sharp_cea_720s[{original['harp']}][{start.strftime(FMT)}/{duration}s@720s]"
        h={'harp':original['harp'],'query':query,'expected_grid_count':len(expected),'attempts':[],'records':[],'candidates':[],'selected':None}
        try:
            for i,delay in enumerate(p['source_resilience']['fixed_backoff_seconds']):
                if delay: time.sleep(delay)
                try:
                    k,s=drms.Client().query(query,key=','.join(KEYS),seg=','.join(SEGMENTS))
                    h['attempts'].append({'attempt':i+1,'rows':len(k),'success':True})
                    break
                except Exception as exc:
                    h['attempts'].append({'attempt':i+1,'success':False,'error':repr(exc)})
                    if i==2: raise
            if len(k)!=len(s): raise ValueError('metadata/segment row mismatch')
            for ix in range(len(k)):
                row={key:clean(k.iloc[ix][key]) for key in KEYS}
                row['segments']={name:clean(s.iloc[ix][name]) for name in SEGMENTS}
                h['records'].append(row)
            index={}
            for row in h['records']:
                index.setdefault(str(row['T_REC']),[]).append(row)
            for m in offsets:
                times=[(base+timedelta(minutes=m+360*j)).strftime(FMT) for j in range(5)]
                failures=[]
                for t in times:
                    rows=index.get(t,[])
                    if len(rows)!=1:
                        failures.append({'time':t,'reason':'EXACTLY_ONE_METADATA_RECORD','count':len(rows)});continue
                    row=rows[0]
                    for key,wanted in [('HARPNUM',original['harp']),('QUALITY',0)]:
                        if row[key]!=wanted: failures.append({'time':t,'reason':key,'value':row[key]})
                    if row['CMASK'] is None or row['CMASK']<1000: failures.append({'time':t,'reason':'CMASK','value':row['CMASK']})
                    for name,value in row['segments'].items():
                        if not isinstance(value,str) or not value.startswith('/') or value.lower() in ('none','nan'):
                            failures.append({'time':t,'reason':'SEGMENT_UNAVAILABLE','segment':name})
                candidate={'offset_minutes':m,'times_tai':times,'eligible':not failures,'failures':failures}
                h['candidates'].append(candidate)
                if not failures and h['selected'] is None:
                    h['selected']={'harp':original['harp'],'trajectory_id':original['trajectory_id']+'_V16','times_tai':times,'start_offset_minutes':m}
            if h['selected']: receipt['selected_trajectories'].append(h['selected'])
        except Exception as exc:
            receipt['errors'].append({'harp':original['harp'],'error':repr(exc)})
        receipt['harps'].append(h)
    receipt['status']='SELECTED_ALL_THREE' if len(receipt['selected_trajectories'])==3 and not receipt['errors'] else 'INSUFFICIENT_METADATA_SUPPORT'
    receipt['receipt_id']='h16meta:'+canonical(receipt)
    write(out/'METADATA_SELECTION.json',receipt)
    if receipt['status']=='SELECTED_ALL_THREE':
        p['harp_trajectories']=receipt['selected_trajectories']
        p['metadata_selection_receipt']=receipt['receipt_id']
        p['status']='METADATA_SELECTED_BEFORE_FIELD_ACCESS'
        write(out/'SELECTED_PROTOCOL_V1_6.json',p)
    print(json.dumps({'status':receipt['status'],'receipt_id':receipt['receipt_id'],'selected':receipt['selected_trajectories'],'errors':receipt['errors']},indent=2))
    return 0 if receipt['status']=='SELECTED_ALL_THREE' else 31
if __name__=='__main__': raise SystemExit(main())
