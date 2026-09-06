"""Deterministic unit fixtures, never represented as observations of a real VPS."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import subprocess
from datetime import datetime,timezone,timedelta

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime'))
from kch_ops.agents import AgentObservatory, dispatch_preflight
from kch_ops.vps import compare, parse_stat, ssh_command, diagnose_ssh
spec=importlib.util.spec_from_file_location('agent_hook',ROOT/'scripts/agent_hook.py')
hook=importlib.util.module_from_spec(spec);spec.loader.exec_module(hook)


class VpsTests(unittest.TestCase):
    def sample(self):
        return {'monotonic':0,'cpu':[0]*8,'memory':{'MemTotal':1000,'MemAvailable':400},
                'load_average':[0,0,0],'processes':{},'pressure':{},'errors':[],'process_scope':'NOT_REQUESTED'}
    def compare(self,b,a):
        return compare(b,a,ticks_per_second=100,page_size=4096,cpu_count=4)
    def test_steal_is_not_real_cpu_consumption(self):
        b=self.sample();a={**b,'monotonic':1,'cpu':[10,0,0,50,10,0,0,30]}
        r=self.compare(b,a)
        self.assertEqual(r['cpu_busy_percent'],10);self.assertEqual(r['cpu_steal_percent'],30)
        self.assertEqual(r['cpu_iowait_percent'],10)
    def test_no_process_scope_does_not_claim_process_inventory(self):
        b=self.sample();a={**b,'monotonic':1,'cpu':[0,0,0,100,0,0,0,0]}
        self.assertEqual(self.compare(b,a)['process_scope'],'NOT_REQUESTED')
    def test_zero_interval_rejected(self):
        with self.assertRaises(ValueError):self.compare(self.sample(),self.sample())
    def test_counter_reset_rejected(self):
        b={**self.sample(),'cpu':[100]*8};a={**self.sample(),'monotonic':1}
        with self.assertRaises(ValueError):self.compare(b,a)
    def test_process_name_parentheses_and_spaces(self):
        fields=['S','1','0','0','0','0','0','0','0','0','0','10','20','0','0','0','0','0','0','123','0','4']
        r=parse_stat('42 (a (name) x) '+' '.join(fields))
        self.assertEqual((r['pid'],r['comm'],r['cpu_ticks'],r['start_ticks'],r['rss_pages']),(42,'a (name) x',30,123,4))
    def test_pid_reuse_not_cpu_delta(self):
        b=self.sample();p={'pid':42,'comm':'worker','state':'S','ppid':1,'cpu_ticks':50,'start_ticks':1,'rss_pages':1}
        b['processes']={'42':p};a={**b,'monotonic':1,'cpu':[50,0,0,50,0,0,0,0],'processes':{'42':{**p,'start_ticks':2}}}
        r=self.compare(b,a)['processes'][0]
        self.assertIsNone(r['cpu_percent_one_core']);self.assertEqual(r['orphan_status'],'NOT_INFERRED_FROM_PPID')
    def test_sleeping_is_not_declared_useless(self):
        b=self.sample();p={'pid':42,'comm':'service','state':'S','ppid':1,'cpu_ticks':50,'start_ticks':1,'rss_pages':1}
        b['processes']={'42':p};a={**b,'monotonic':1,'cpu':[0,0,0,100,0,0,0,0]}
        r=self.compare(b,a)['processes'][0]
        self.assertEqual(r['activity'],'NO_CPU_DELTA_IN_WINDOW');self.assertEqual(r['useful_progress'],'NOT_ESTABLISHED_BY_PROCESS_COUNTERS')
    def test_ssh_injection_rejected(self):
        for host in ('-oProxyCommand=bad','host;command','host$(command)'):
            with self.assertRaises(ValueError):ssh_command({'host':host,'user':'root'})
    def test_ssh_expired_lease_rejected_before_key_read(self):
        with self.assertRaises(ValueError):ssh_command({'host':'example.org','user':'root','authorization_ref':'test-only','expires_at_utc':'2000-01-01T00:00:00Z'})
    def test_ssh_timeout_preserves_failure_receipt(self):
        with patch('kch_ops.vps.ssh_command',return_value=['ssh-test-fixture']), patch('kch_ops.vps.subprocess.run',side_effect=subprocess.TimeoutExpired('fixture',5,stderr=b'test timeout')):
            result=diagnose_ssh({'host':'fixture.invalid','authorization_ref':'test-fixture','timeout_seconds':5},{})
        self.assertEqual(result['gate'],'SSH_DEADLINE_EXCEEDED')
        self.assertIsNone(result['observation']);self.assertTrue(result['local_client_terminated'])
        self.assertEqual(result['remote_process_exit'],'UNVERIFIED')
    def test_ssh_invalid_output_does_not_become_observation(self):
        with patch('kch_ops.vps.ssh_command',return_value=['ssh-test-fixture']), patch('kch_ops.vps.subprocess.run',return_value=subprocess.CompletedProcess('fixture',0,'not JSON','')):
            result=diagnose_ssh({'host':'fixture.invalid','authorization_ref':'test-fixture'},{})
        self.assertEqual(result['gate'],'REMOTE_OUTPUT_INVALID');self.assertIsNone(result['observation'])
    def test_ssh_timeout_bounded_before_launch(self):
        with patch('kch_ops.vps.subprocess.run') as launch:
            with self.assertRaises(ValueError):diagnose_ssh({'timeout_seconds':float('inf')},{})
        launch.assert_not_called()


class AgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.store=AgentObservatory(self.root/'state.sqlite3')
        self.now=datetime(2026,9,6,12,tzinfo=timezone.utc)
    def receipt(self,ident='observation-1',time=None,agents=None):
        return {'event_id':ident,'source_ref':'test-fixture://native-receipt','host':'CODEX','scope':'fixture',
                'observed_at':(time or self.now).isoformat(),'agents':agents if agents is not None else [{'agent_id':'test-agent','status':'running','model':'gpt-5.6-luna'}]}
    def review(self,ident='review-1',outcome='PASS'):
        path=self.root/'fixture-artifact.txt';path.write_text('unit-test fixture, not empirical evidence',encoding='utf-8')
        return {'review_id':ident,'agent_id':'test-agent','role_id':'FIXTURE_ROLE','task_id':ident,'jurisdiction':'test-fixture',
                'reviewer_id':'fixture-reviewer','source_ref':'test-fixture://review','outcome':outcome,
                'artifacts':[{'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}]}
    def role(self):
        return {'role_id':'FIXTURE_ROLE',
                'GENERALIZABLE':{k:'Explicit unit-test fixture, not a real capability' for k in ('invariant','workflow','failure_signatures','recovery','counterexamples','tests','portability','secrets_handling')},
                'TOPIC_SPECIFIC':{k:'Explicit unit-test fixture' for k in ('subject','jurisdiction','source_refs','observed_evidence','adverse_evidence','open_questions')}}
    def test_empty_status_does_not_create_database(self):
        self.assertEqual(self.store.status()['event_count'],0);self.assertFalse(self.store.path.exists())
    def test_native_observation_roundtrip_and_replay(self):
        a=self.store.observe(self.receipt());b=self.store.observe(self.receipt())
        self.assertEqual(a,b);self.assertEqual(len(self.store.events()),1)
    def test_replay_drift_rejected(self):
        self.store.observe(self.receipt())
        with self.assertRaises(ValueError):self.store.observe(self.receipt(agents=[]))
    def test_duplicate_agents_rejected(self):
        r=self.receipt();r['agents']*=2
        with self.assertRaises(ValueError):self.store.observe(r)
    def test_missing_agent_not_declared_dead(self):
        self.store.observe(self.receipt());self.store.observe(self.receipt('next',self.now+timedelta(seconds=1),[]))
        self.assertIn('ABSENT_FROM_LATEST_SNAPSHOT_NOT_PROOF_OF_EXIT',self.store.status(now=self.now+timedelta(seconds=2))['agents'][0]['alerts'])
    def test_stale_not_declared_stalled(self):
        self.store.observe(self.receipt());r=self.store.status(now=self.now+timedelta(seconds=181))
        self.assertIn('OBSERVATION_STALE_NOT_PROOF_OF_STALL',r['agents'][0]['alerts'])
    def test_forbidden_model_preserved_as_adverse_evidence(self):
        self.store.observe(self.receipt(agents=[{'agent_id':'bad-model','status':'running','model':'gpt-6-astra'}]))
        self.assertIn('MODEL_POLICY_VIOLATION',self.store.status(now=self.now)['agents'][0]['alerts'])
    def test_out_of_order_receipt_does_not_roll_back_status(self):
        self.store.observe(self.receipt());self.store.observe(self.receipt('old',self.now-timedelta(seconds=10),[{'agent_id':'test-agent','status':'failed'}]))
        self.assertEqual(self.store.status(now=self.now)['agents'][0]['status'],'running')
    def test_ledger_tamper_detected(self):
        self.store.observe(self.receipt())
        db = sqlite3.connect(self.store.path)
        try:
            with db:db.execute("UPDATE events SET payload='{}'")
        finally:
            db.close()
        with self.assertRaises(ValueError):self.store.events()
    def test_review_hash_mismatch_rejected(self):
        review=self.review();review['artifacts'][0]['sha256']='0'*64
        with self.assertRaises(ValueError):self.store.record_review(review,admitted_roots=[self.root])
    def test_self_review_rejected(self):
        review=self.review();review['reviewer_id']=review['agent_id']
        with self.assertRaises(ValueError):self.store.record_review(review,admitted_roots=[self.root])
    def test_unadmitted_artifact_rejected(self):
        other=self.root/'admitted';other.mkdir()
        with self.assertRaises(ValueError):self.store.record_review(self.review(),admitted_roots=[other])
    def test_preregister_needs_review_and_both_branches(self):
        with self.assertRaises(ValueError):self.store.preregister(self.role(),authorization_ref='test-fixture')
        self.store.record_review(self.review(),admitted_roots=[self.root])
        broken=self.role();del broken['GENERALIZABLE']
        with self.assertRaises(ValueError):self.store.preregister(broken,authorization_ref='test-fixture')
    def test_preregister_preserves_adverse_evidence_without_promotion(self):
        self.store.record_review(self.review(),admitted_roots=[self.root])
        self.store.record_review(self.review('failed-review','FAIL'),admitted_roots=[self.root])
        result=self.store.preregister(self.role(),authorization_ref='test-fixture')['payload']
        self.assertEqual(result['adverse_review_count'],1);self.assertFalse(result['automatic_promotion'])
        self.assertFalse(result['published']);self.assertEqual(result['generalizability'],'CANDIDATE_NOT_PROVEN')
        a,b=result['branches'].values();self.assertEqual(a['peer_sha256'],b['sha256'])
    def test_preflight_never_claims_dispatch(self):
        spec={'model':'gpt-5.6-luna','role_id':'X','obligation_id':'X','topology_id':'X','source_ref':'fixture','stop_condition':'tests','max_turns':2}
        self.assertFalse(dispatch_preflight(spec)['dispatched'])
        with self.assertRaises(ValueError):dispatch_preflight({**spec,'model':'gpt-6-astra'})
        with self.assertRaises(ValueError):dispatch_preflight({**spec,'model':'gpt-5.6-terra','replicated':True})
    def test_hook_blocks_forbidden_auxiliary_not_user_tasks(self):
        result=hook.handle({'hook_event_name':'PreToolUse','tool_name':'collaboration.spawn_agent','tool_input':{'model':'gpt-6-astra'}})
        self.assertEqual(result['hookSpecificOutput']['permissionDecision'],'deny')
        self.assertEqual(hook.handle({'hook_event_name':'PreToolUse','tool_name':'create_thread','tool_input':{'model':'gpt-6-astra'}}),{})
    def test_hook_allows_explicit_luna_or_terra(self):
        for model in ('gpt-5.6-luna','gpt-5.6-terra'):
            self.assertEqual(hook.handle({'hook_event_name':'PreToolUse','tool_name':'collaboration.spawn_agent','tool_input':{'model':model,'fork_turns':'none'}}),{})
    def test_hook_native_receipt_capture(self):
        payload={'hook_event_name':'PostToolUse','tool_name':'collaboration.list_agents','tool_use_id':'fixture-call','session_id':'fixture-session','cwd':str(self.root),
                 'tool_response':{'agents':[{'agent_name':'/root','agent_status':'running'}]}}
        self.assertEqual(hook.handle(payload),{});self.assertEqual(hook.handle(payload),{})
        captured=AgentObservatory(self.root/'.kch/operational-supervision/agents.sqlite3')
        self.assertEqual(len(captured.events()),1)


if __name__=='__main__':unittest.main()
