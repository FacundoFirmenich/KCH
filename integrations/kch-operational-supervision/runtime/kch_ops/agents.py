"""Persistent agent observations and Construct preregistration, without fake agents.

Quality reviews remain attributed evidence, not automatic proof of generality.
SQLite transactions serialize writers; a hash chain detects retrospective drift.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3

ALLOWED_MODELS = frozenset({'gpt-5.6-luna','gpt-5.6-terra'})


def canonical(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def instant(value):
    parsed = datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('TIMEZONE_REQUIRED')
    return parsed.astimezone(timezone.utc)


def dispatch_preflight(spec):
    if spec.get('model') not in ALLOWED_MODELS:
        raise ValueError('MODEL_MUST_BE_LUNA_OR_TERRA')
    for field in ('role_id','obligation_id','topology_id','source_ref','stop_condition'):
        if not isinstance(spec.get(field),str) or not spec[field].strip():
            raise ValueError('MISSING_'+field.upper())
    if spec.get('replicated') and spec['model'] != 'gpt-5.6-luna':
        raise ValueError('REPLICATED_LANES_REQUIRE_LUNA')
    if type(spec.get('max_turns')) is not int or not 1 <= spec['max_turns'] <= 1000:
        raise ValueError('BOUNDED_MAX_TURNS_REQUIRED')
    return {'gate':'DISPATCH_REQUEST_VALIDATED','request':spec,'dispatched':False,
            'native_dispatch_receipt_required':True}


class AgentObservatory:
    def __init__(self, database):
        self.path = Path(database).resolve()

    def _rows(self, connection):
        rows = connection.execute('SELECT seq,event_id,kind,payload,previous_hash,event_hash FROM events ORDER BY seq').fetchall()
        previous = 'GENESIS'
        events = []
        for expected,row in enumerate(rows,1):
            sequence,event_id,kind,payload,prior,event_hash = row
            body = {'sequence':sequence,'event_id':event_id,'kind':kind,'payload':json.loads(payload),'previous_hash':prior}
            if sequence != expected or prior != previous or digest(body) != event_hash:
                raise ValueError('AGENT_LEDGER_TAMPER')
            previous = event_hash
            events.append({**body,'event_hash':event_hash})
        return events

    def events(self):
        if not self.path.exists():
            return []
        connection = sqlite3.connect(self.path.as_uri()+'?mode=ro',uri=True)
        try:
            return self._rows(connection)
        finally:
            connection.close()

    def append(self, kind, event_id, payload):
        if not isinstance(event_id,str) or not event_id.strip():
            raise ValueError('EVENT_ID_REQUIRED')
        serialized = canonical(payload)
        if len(serialized.encode()) > 2_000_000:
            raise ValueError('EVENT_TOO_LARGE')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        connection = sqlite3.connect(self.path,timeout=15,isolation_level=None)
        try:
            connection.execute('PRAGMA synchronous=FULL')
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY,event_id TEXT UNIQUE NOT NULL,kind TEXT NOT NULL,payload TEXT NOT NULL,previous_hash TEXT NOT NULL,event_hash TEXT NOT NULL)')
            rows = self._rows(connection)
            prior = next((r for r in rows if r['event_id']==event_id),None)
            if prior:
                if prior['kind'] != kind or canonical(prior['payload']) != serialized:
                    raise ValueError('IDEMPOTENT_EVENT_DRIFT')
                connection.commit()
                return prior
            event = {'sequence':len(rows)+1,'event_id':event_id,'kind':kind,'payload':payload,
                     'previous_hash':rows[-1]['event_hash'] if rows else 'GENESIS'}
            event_hash = digest(event)
            connection.execute('INSERT INTO events VALUES (?,?,?,?,?,?)',
                               (event['sequence'],event_id,kind,serialized,event['previous_hash'],event_hash))
            connection.commit()
            return {**event,'event_hash':event_hash}
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def observe(self, receipt):
        for field in ('event_id','source_ref','host','observed_at','scope'):
            if not isinstance(receipt.get(field),str) or not receipt[field].strip():
                raise ValueError('MISSING_'+field.upper())
        instant(receipt['observed_at'])
        agents = receipt.get('agents')
        if not isinstance(agents,list) or len(agents)>10000:
            raise ValueError('BOUNDED_AGENT_LIST_REQUIRED')
        identities = set()
        for agent in agents:
            if not isinstance(agent.get('agent_id'),str) or not agent['agent_id']:
                raise ValueError('AGENT_ID_REQUIRED')
            if agent['agent_id'] in identities:
                raise ValueError('DUPLICATE_AGENT_IN_SNAPSHOT')
            identities.add(agent['agent_id'])
            if not isinstance(agent.get('status'),str) or not agent['status']:
                raise ValueError('OBSERVED_STATUS_REQUIRED')
        # Out-of-order observations are kept as evidence, but status() selects by time.
        return self.append('NATIVE_RECEIPT_SUPPLIED',receipt['event_id'],receipt)

    def status(self, *, now=None, stale_seconds=180):
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None or not math.isfinite(stale_seconds) or stale_seconds<=0:
            raise ValueError('INVALID_OBSERVATION_WINDOW')
        rows = self.events()
        observed = {}
        latest_scope = {}
        for event in rows:
            if event['kind'] != 'NATIVE_RECEIPT_SUPPLIED':
                continue
            receipt = event['payload']
            stamp = instant(receipt['observed_at'])
            scope_key = (receipt['host'],receipt['scope'])
            if scope_key not in latest_scope or stamp >= latest_scope[scope_key][0]:
                latest_scope[scope_key] = (stamp,{a['agent_id'] for a in receipt['agents']})
            for agent in receipt['agents']:
                key = (*scope_key,agent['agent_id'])
                if key not in observed or stamp >= observed[key]['timestamp']:
                    observed[key] = {'timestamp':stamp,'agent':agent,'source_ref':receipt['source_ref']}
        result=[]
        for key, value in sorted(observed.items()):
            agent=value['agent']; age=(now-value['timestamp']).total_seconds()
            alerts=[]
            if age<0: alerts.append('FUTURE_OBSERVATION_CLOCK_SKEW')
            elif age>stale_seconds: alerts.append('OBSERVATION_STALE_NOT_PROOF_OF_STALL')
            if key[2] not in latest_scope[key[:2]][1]: alerts.append('ABSENT_FROM_LATEST_SNAPSHOT_NOT_PROOF_OF_EXIT')
            if not agent.get('is_governor',False):
                if not agent.get('model'): alerts.append('MODEL_NOT_OBSERVED')
                elif agent['model'] not in ALLOWED_MODELS: alerts.append('MODEL_POLICY_VIOLATION')
            if agent.get('status') in ('errored','failed','blocked'): alerts.append('HOST_REPORTED_'+agent['status'].upper())
            result.append({'host':key[0],'scope':key[1],**agent,'observation_age_seconds':age,
                           'alerts':alerts,'source_ref':value['source_ref'],
                           'useful_progress':'REQUIRES_VERIFIED_ARTIFACT_OR_TASK_RESULT',
                           'cost':'NOT_ESTIMABLE_WITHOUT_PROVIDER_USAGE_RECEIPT'})
        return {'schema':'kch.agent-observatory.status.v0.1.0','agents':result,'event_count':len(rows),
                'ledger_hash':rows[-1]['event_hash'] if rows else 'GENESIS',
                'scope':'Only supplied native receipts; no claim of global coverage or continuous host attachment',
                'native_receipt_authenticity':'Requires trusted host capture; file hash alone is not authentication'}

    def record_review(self, review, *, admitted_roots):
        for field in ('review_id','agent_id','role_id','task_id','jurisdiction','reviewer_id','source_ref','outcome'):
            if not isinstance(review.get(field),str) or not review[field].strip():
                raise ValueError('MISSING_'+field.upper())
        if review['reviewer_id']==review['agent_id']:
            raise ValueError('SELF_REVIEW_NOT_INDEPENDENT')
        if review['outcome'] not in ('PASS','FAIL','INCONCLUSIVE'):
            raise ValueError('INVALID_REVIEW_OUTCOME')
        roots=[Path(p).resolve(strict=True) for p in admitted_roots]
        artifacts=review.get('artifacts')
        if not isinstance(artifacts,list) or not artifacts:
            raise ValueError('ARTIFACT_EVIDENCE_REQUIRED')
        for artifact in artifacts:
            path=Path(artifact['path']).resolve(strict=True)
            if not any(path.is_relative_to(root) for root in roots):
                raise ValueError('ARTIFACT_OUTSIDE_ADMITTED_ROOT')
            if not path.is_file() or path.stat().st_size>20_000_000:
                raise ValueError('ARTIFACT_SIZE_OR_TYPE_NOT_ADMITTED')
            if hashlib.sha256(path.read_bytes()).hexdigest()!=artifact['sha256']:
                raise ValueError('ARTIFACT_HASH_MISMATCH')
        return self.append('ATTRIBUTED_QUALITY_REVIEW',review['review_id'],review)

    def preregister(self, role_spec, *, authorization_ref):
        if not authorization_ref:
            raise ValueError('PREREGISTRATION_AUTHORIZATION_REQUIRED')
        role_id=role_spec.get('role_id')
        if not isinstance(role_id,str) or not role_id.strip():
            raise ValueError('ROLE_ID_REQUIRED')
        branches={}
        for branch in ('GENERALIZABLE','TOPIC_SPECIFIC'):
            body=role_spec.get(branch)
            if not isinstance(body,dict) or not body:
                raise ValueError('BOTH_CONSTRUCT_BRANCHES_REQUIRED')
            required = ('invariant','workflow','failure_signatures','recovery','counterexamples','tests','portability','secrets_handling') if branch=='GENERALIZABLE' else ('subject','jurisdiction','source_refs','observed_evidence','adverse_evidence','open_questions')
            for field in required:
                if field not in body or body[field] in (None,'',[]):
                    raise ValueError('INCOMPLETE_CONSTRUCT_BRANCH:'+branch+':'+field)
            branches[branch]={'content':body,'sha256':digest(body)}
        reviews=[e for e in self.events() if e['kind']=='ATTRIBUTED_QUALITY_REVIEW' and e['payload']['role_id']==role_id]
        passing=[e for e in reviews if e['payload']['outcome']=='PASS']
        if not passing:
            raise ValueError('NO_REVIEWED_SUCCESS_TO_PREREGISTER')
        for branch,peer in (('GENERALIZABLE','TOPIC_SPECIFIC'),('TOPIC_SPECIFIC','GENERALIZABLE')):
            branches[branch]['peer_sha256']=branches[peer]['sha256']
        candidate={'schema':'kch.construct.agent-preregistration.v0.1.0','role_id':role_id,
                   'status':'PREREGISTERED_FOR_CONSTRUCT_REVIEW','branches':branches,
                   'review_event_hashes':[r['event_hash'] for r in reviews],
                   'successful_task_count':len({r['payload']['task_id'] for r in passing}),
                   'observed_jurisdictions':sorted({r['payload']['jurisdiction'] for r in passing}),
                   'adverse_review_count':sum(r['payload']['outcome']!='PASS' for r in reviews),
                   'generalizability':'CANDIDATE_NOT_PROVEN','authorization_ref':authorization_ref,
                   'installed':False,'published':False,'automatic_promotion':False}
        return self.append('CONSTRUCT_PREREGISTRATION','construct:'+digest(candidate),candidate)
