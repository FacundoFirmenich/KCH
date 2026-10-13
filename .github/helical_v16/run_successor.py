"""Enforce frozen source, uploaded selection receipt, exact identities and result integrity."""
from pathlib import Path
import ast,hashlib,json,os,runpy,shutil,socket,sys,traceback
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def canon(x): return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def write(p,x): p.write_text(json.dumps(x,indent=2,sort_keys=True,allow_nan=False)+'\n')
def check_sources():
    manifest=json.loads((HERE/'FROZEN_INPUTS.json').read_text())
    checks=[{'path':p,'expected':h,'actual':digest(ROOT/p)} for p,h in manifest['sha256'].items()]
    if not all(x['expected']==x['actual'] for x in checks): raise ValueError('frozen input mismatch')
    def functions(p): return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(p.read_text()).body if isinstance(n,ast.FunctionDef)}
    old=functions(ROOT/'.github/helical_v15/temporal_lift_development.py')
    new=functions(HERE/'temporal_lift_development.py')
    unchanged=[k for k in old if k not in ('main','load_snapshot')]
    if set(old)!=set(new) or any(old[k]!=new[k] for k in unchanged): raise ValueError('scientific function divergence')
    return checks,unchanged

def main():
    checks,unchanged=check_sources()
    if len(sys.argv)>1 and sys.argv[1]=='check':
        print(json.dumps({'frozen_inputs':len(checks),'unchanged_functions':unchanged}));return 0
    out=Path(os.environ['OUT']);meta=out/'metadata';safe=out/'safe'
    safe.mkdir(exist_ok=False)
    receipt={'format':'KCH_SOLAR_V16_EXECUTION_V1','source_checks':checks,'unchanged_runtime_functions':unchanged,'execution_commit':os.environ.get('GITHUB_SHA'),'run_id':os.environ.get('GITHUB_RUN_ID'),'metadata_artifact_id':os.environ['METADATA_ARTIFACT_ID'],'scientific_confirmation':False,'authority_ceiling':'NONE','interpretation':'CONDITIONAL_TRANSITION_RECONSTRUCTION_NOT_EX_ANTE_FORECAST'}
    before={p.name:digest(p) for p in meta.glob('*.json')}
    selected=json.loads((meta/'METADATA_SELECTION.json').read_text())
    body=dict(selected);rid=body.pop('receipt_id')
    assert rid=='h16meta:'+canon(body) and selected['status']=='SELECTED_ALL_THREE'
    assert selected['protocol_sha256']==digest(HERE/'TEMPORAL_PROTOCOL_V1_6.json')
    protocol_path=meta/'SELECTED_PROTOCOL_V1_6.json'
    selected_protocol=json.loads(protocol_path.read_text())
    expected=json.loads((HERE/'TEMPORAL_PROTOCOL_V1_6.json').read_text())
    expected.update(harp_trajectories=selected['selected_trajectories'],metadata_selection_receipt=rid,status='METADATA_SELECTED_BEFORE_FIELD_ACCESS')
    assert selected_protocol==expected
    os.environ['SELECTED_PROTOCOL_PATH']=str(protocol_path)
    socket.setdefaulttimeout(90)
    rc=99
    try:
        runpy.run_path(str(HERE/'temporal_lift_development.py'),run_name='__main__')
        rc=0
    except SystemExit as exc: rc=int(exc.code or 0)
    except Exception as exc:
        receipt['exception']=repr(exc);traceback.print_exc()
    finally:
        shutil.rmtree(out/'raw',ignore_errors=True)
    receipt.update(runtime_exit_code=rc,metadata_sha256_before=before,metadata_unchanged=before=={p.name:digest(p) for p in meta.glob('*.json')},raw_directory_absent=not(out/'raw').exists(),status='RUNTIME_FAILURE')
    result=safe/'TEMPORAL_LIFT_DEVELOPMENT_RESULT_V1_6.json'
    if result.exists():
        report=json.loads(result.read_text());body=dict(report);reported=body.pop('receipt_id')
        allowed={(t['harp'],ts) for t in selected['selected_trajectories'] for ts in t['times_tai']}
        snapshots=[s for t in report['trajectories'] for s in t['snapshots']]
        identities=[s['record']['HARPNUM']==s['harp'] and s['record']['T_REC']==s['requested_time_tai'] and (s['harp'],s['requested_time_tai']) in allowed for s in snapshots]
        valid=(reported=='h16lift:'+canon(body) and all(identities) and report['protocol_sha256']==digest(protocol_path) and report['metadata_selection_receipt']==rid and report['scientific_confirmation'] is False and report['fresh_2026_holdout_accessed'] is False and report['flare_outcomes_accessed'] is False and receipt['metadata_unchanged'])
        receipt.update(result_sha256=digest(result),result_receipt_id=reported,content_and_identity_valid=valid,snapshot_count=len(snapshots),outcome=report['outcome'])
        if valid and rc==31 and report['outcome']=='INSUFFICIENT_TEMPORAL_SUPPORT': receipt['status']='VALID_RECEIPT_INSUFFICIENT_SUPPORT'
        elif valid and rc==0 and len(snapshots)==15 and report['outcome']!='INSUFFICIENT_TEMPORAL_SUPPORT': receipt['status']='VALID_DEVELOPMENT_RESULT_NO_CONFIRMATION'
        else: rc=90;receipt['status']='RESULT_OR_IDENTITY_MISMATCH'
    elif rc in (0,31): rc=90;receipt['status']='MISSING_RESULT'
    receipt['wrapper_exit_code']=rc
    write(safe/'EXECUTION_RECEIPT_V1_6.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('source_checks',)},indent=2))
    return rc
if __name__=='__main__': raise SystemExit(main())
