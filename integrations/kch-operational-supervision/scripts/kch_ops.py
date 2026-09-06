"""JSON CLI shared by native Codex commands and the Cline adapter."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'runtime'))
from kch_ops.agents import AgentObservatory, dispatch_preflight
from kch_ops.vps import collect, diagnose_ssh


def execute(action, request, database):
    observer = AgentObservatory(database)
    if action=='status': return observer.status(stale_seconds=request.get('stale_seconds',180))
    if action=='observe': return observer.observe(request)
    if action=='dispatch-preflight': return dispatch_preflight(request)
    if action=='review':
        if request.get('role_spec') and request['role_spec'].get('role_id')!=request['review']['role_id']:
            raise ValueError('ROLE_SPEC_REVIEW_MISMATCH')
        result={'review':observer.record_review(request['review'],admitted_roots=request['admitted_roots'])}
        # Preregistration can run automatically under the explicitly configured
        # mandate, but never synthesizes an unreviewed reusable role specification.
        if request['review']['outcome']=='PASS' and request.get('role_spec'):
            result['construct']=observer.preregister(request['role_spec'],authorization_ref=request.get('authorization_ref'))
        return result
    if action=='preregister': return observer.preregister(request['role_spec'],authorization_ref=request.get('authorization_ref'))
    if action=='vps-local': return collect(request)
    if action=='vps-ssh': return diagnose_ssh(request['profile'],request.get('measurement',{}))
    raise ValueError('UNKNOWN_ACTION')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['status','observe','dispatch-preflight','review','preregister','vps-local','vps-ssh'])
    parser.add_argument('--database',default=str(Path.cwd()/'.kch/operational-supervision/agents.sqlite3'))
    arguments=parser.parse_args()
    try:
        raw=sys.stdin.read(2_000_001)
        if len(raw)>2_000_000: raise ValueError('REQUEST_TOO_LARGE')
        request=json.loads(raw) if raw.strip() else {}
        if not isinstance(request,dict): raise ValueError('OBJECT_REQUEST_REQUIRED')
        print(json.dumps(execute(arguments.action,request,arguments.database),ensure_ascii=False,allow_nan=False))
    except Exception as error:
        print(json.dumps({'gate':'FAIL','error_type':type(error).__name__,'error':str(error)},ensure_ascii=False))
        raise SystemExit(1)
