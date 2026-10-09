from __future__ import annotations

import hashlib
import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path

import drms

SERIES = 'hmi.sharp_cea_720s'
KEYWORDS = [
    'HARPNUM','T_REC','NOAA_AR','NOAA_ARS','QUALITY','LAT_FWT','LON_FWT',
    'USFLUX','MEANGBT','MEANGBZ','MEANGBH','MEANJZD','TOTUSJZ','MEANALP',
    'MEANJZH','TOTUSJH','ABSNJZH','SAVNCPP','MEANPOT','TOTPOT','MEANSHR',
    'SHRGT45','R_VALUE','AREA_ACR'
]


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def main() -> int:
    out = Path(os.environ.get('PROBE_OUT', '/tmp/mhd001-sharp-probe'))
    out.mkdir(parents=True, exist_ok=True)
    client = drms.Client()
    info = client.info(SERIES)
    available_keywords = list(info.keywords.index.astype(str))
    available_segments = list(info.segments.index.astype(str))
    missing_keywords = sorted(set(KEYWORDS) - set(available_keywords))
    required_segments = ['Br','Bp','Bt','bitmap','conf_disambig']
    missing_segments = sorted(set(required_segments) - set(available_segments))

    query = f'{SERIES}[][2025.01.01_00:00:00_TAI/1d@12h]'
    sample = client.query(query, key=','.join(KEYWORDS), n=4)
    sample_path = out / 'SHARP_KEYWORD_SAMPLE.csv'
    sample.to_csv(sample_path, index=False)

    body = {
        'format':'KCH_MHD_HELICAL_OBSERVABILITY_001_JSOC_SCHEMA_PROBE',
        'series':SERIES,
        'queried_at_utc':datetime.now(timezone.utc).isoformat().replace('+00:00','Z'),
        'query':query,
        'requested_keywords':KEYWORDS,
        'missing_keywords':missing_keywords,
        'required_segments':required_segments,
        'missing_segments':missing_segments,
        'available_keyword_count':len(available_keywords),
        'available_segment_count':len(available_segments),
        'sample_record_count':int(len(sample)),
        'python':platform.python_version(),
        'drms_version':getattr(drms,'__version__','unknown'),
        'scientific_execution_performed':False,
        'authority_ceiling':'NONE',
    }
    body['probe_id']='mhd001probe:'+hashlib.sha256(canonical(body)).hexdigest()
    (out/'SHARP_SCHEMA_PROBE.json').write_text(json.dumps(body,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps(body,indent=2,sort_keys=True))
    return 0 if not missing_keywords and not missing_segments and len(sample)>0 else 3

if __name__ == '__main__':
    raise SystemExit(main())
