"""Real repository-file execution and injected process/transport faults.

No LLM calls, generated datasets, fabricated experimental results or remote
provider sessions. SCO nodes here denote trusted local Python file readers.
"""
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve()
REPOSITORY = HERE.parents[3]
sys.path.insert(0, str(HERE.parents[1] / 'src'))
from kch_composed.coordinator import Coordinator, CoordinatorBusy, CoordinatorIntegrityError

FILES = [REPOSITORY / 'work/SCO_RELEASE_STAGE_v0.1.1/src/kch_sco/models.py',
         REPOSITORY / 'work/SCO_RELEASE_STAGE_v0.1.1/src/kch_sco/ledger.py']


def file_result(path=FILES[0]):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'outcome': 'SUCCEEDED', 'output_refs': [path.as_uri()],
            'evidence_ids': ['sha256:' + digest],
            'claims': ['Existing repository file was read and hashed.'],
            'limitations': ['Local file inspection; no model inference.'],
            'authority_exercised': ['READ_REPOSITORY']}


def die_after_read(repository, state, marker):
    coordinator = Coordinator(Path(repository), Path(state))
    def read_then_die(envelope):
        digest = hashlib.sha256(FILES[0].read_bytes()).hexdigest()
        with open(marker, 'w') as stream:
            stream.write(digest)
            stream.flush()
            os.fsync(stream.fileno())
        os._exit(23)
    coordinator.dispatch('local-repo', {'reader': read_then_die})


class CoordinatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / 'dispatch.sqlite3'
        self.coordinator = Coordinator(REPOSITORY, self.state)
        self.sco = self.coordinator.sco
        self._write(self.sco.create_superchat, {
            'schema': 'kch.sco.superchat.v0.1.0', 'sco_id': 'local-repo',
            'name': 'Local repository inspection',
            'objective': 'Read and hash existing SCO source files.',
            'non_goals': ['No LLM inference or remote provider execution'],
            'jurisdiction': str(REPOSITORY),
            'claim_ceiling': 'LOCAL_FILE_EXECUTION_ONLY'})

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, method, record):
        return method(record, actor='local-file-test',
                      command_id=method.__name__ + ':' + str(len(self.sco.export_bundle('local-repo')['nodes']))
                      + ':' + str(record.get('order_id', record.get('sco_id'))),
                      expected_head_hash=self.sco.head()) if method.__name__ != 'create_superchat' else method(
                      record, actor='local-file-test', command_id='create', expected_head_hash=self.sco.head())

    def node(self, node_id, connector='LIVE_READ_WRITE_VERIFIED', autonomy='EXECUTE_WITHIN_SCOPE'):
        self._write(self.sco.add_node, {
            'schema': 'kch.sco.node.v0.1.0', 'sco_id': 'local-repo',
            'node_id': node_id, 'provider': 'CUSTOM',
            'native_uri': 'local+python://repository-reader/' + node_id,
            'title': node_id, 'role': 'SOURCE_READER',
            'responsibilities': ['Read and hash existing files'],
            'capabilities': ['READ_REPOSITORY'], 'authority_granted': ['READ_REPOSITORY'],
            'autonomy_level': autonomy, 'context_policy': 'SCOPED_DISCLOSURE_ONLY',
            'memory_policy': 'NATIVE_MEMORY_PRESERVED', 'connector_state': connector,
            'source_provenance': HERE.as_uri()})

    def order(self, order_id, target, depends=()):
        self._write(self.sco.issue_work_order, {
            'schema': 'kch.sco.work-order.v0.1.0', 'sco_id': 'local-repo',
            'order_id': order_id, 'target_node_id': target,
            'objective': 'Inspect existing repository source files',
            'input_refs': [p.as_uri() for p in FILES], 'disclosed_fragments': [],
            'required_outputs': ['Existing source reference and observed SHA-256'],
            'authority_granted': ['READ_REPOSITORY'], 'depends_on': list(depends),
            'termination': 'File evidence receipt', 'claim_ceiling': 'LOCAL_FILE_EXECUTION_ONLY'})

    def test_parallel_real_reads_dependency_and_no_duplicate_dispatch(self):
        for name in ('left', 'right', 'joined'):
            self.node(name)
        self.order('left-read', 'left')
        self.order('right-read', 'right')
        self.order('join-read', 'joined', ('left-read', 'right-read'))
        barrier = threading.Barrier(2)
        calls = []
        def reader(path):
            def handle(envelope):
                barrier.wait(timeout=5)
                calls.append(envelope['work_order']['order_id'])
                return file_result(path)
            return handle
        def joined(envelope):
            self.assertEqual(set(calls), {'left-read', 'right-read'})
            self.assertEqual(self.sco.projection('local-repo')['receipts'], 2)
            calls.append('join-read')
            result = file_result()
            result['output_refs'] = [p.as_uri() for p in FILES]
            return result
        handlers = {'left': reader(FILES[0]), 'right': reader(FILES[1]), 'joined': joined}
        rows = self.coordinator.dispatch('local-repo', handlers, max_workers=2)
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r['published'] and r['state'] == 'COMPLETED' for r in rows))
        self.assertEqual(self.sco.projection('local-repo')['order_states'], {'COMPLETED': 3})
        self.assertEqual(self.sco.verify()['gate'], 'PASS')
        for row in rows:
            for ref in row['result']['output_refs']:
                expected = hashlib.sha256(Path(ref.removeprefix('file://')).read_bytes()).hexdigest()
                self.assertTrue(any(expected in e for e in row['result']['evidence_ids']))
        self.coordinator.dispatch('local-repo', handlers)
        self.coordinator.recover('local-repo')
        self.assertEqual(len(calls), 3)
        self.assertEqual(len(self.sco.export_bundle('local-repo')['receipts']), 3)

    def test_durable_result_before_receipt_recovers_without_second_invocation(self):
        self.node('reader'); self.order('read', 'reader')
        calls = []
        def read(envelope):
            calls.append(1)
            return file_result()
        with patch.object(self.coordinator, '_publish', side_effect=RuntimeError('Injected receipt transport failure')):
            with self.assertRaises(RuntimeError):
                self.coordinator.dispatch('local-repo', {'reader': read})
        self.assertEqual(self.coordinator.inspect()[0]['state'], 'RESULT_READY')
        self.assertEqual(self.sco.projection('local-repo')['receipts'], 0)
        successor = Coordinator(REPOSITORY, self.state)
        successor.recover('local-repo')
        successor.dispatch('local-repo', {'reader': read})
        self.assertEqual(calls, [1])
        self.assertEqual(successor.sco.projection('local-repo')['receipts'], 1)

    def test_receipt_committed_before_ack_is_reconciled_exactly_once(self):
        self.node('reader'); self.order('read', 'reader')
        original = self.sco.ingest_receipt
        def commit_then_interrupt(*args, **kwargs):
            original(*args, **kwargs)
            raise RuntimeError('Injected interruption after native commit')
        with patch.object(self.sco, 'ingest_receipt', side_effect=commit_then_interrupt):
            with self.assertRaises(RuntimeError):
                self.coordinator.dispatch('local-repo', {'reader': lambda envelope: file_result()})
        self.assertFalse(self.coordinator.inspect()[0]['published'])
        self.assertEqual(self.sco.projection('local-repo')['receipts'], 1)
        successor = Coordinator(REPOSITORY, self.state)
        successor.recover('local-repo'); successor.recover('local-repo')
        self.assertTrue(successor.inspect()[0]['published'])
        self.assertEqual(successor.sco.projection('local-repo')['receipts'], 1)

    def test_process_exit_after_real_read_never_reexecutes_unknown_effect(self):
        self.node('reader'); self.node('dependent')
        self.order('read', 'reader'); self.order('dependent', 'dependent', ('read',))
        marker = Path(self.temp.name) / 'actual-read.sha256'
        process = multiprocessing.get_context('fork').Process(
            target=die_after_read, args=(REPOSITORY, self.state, marker))
        process.start(); process.join(timeout=10)
        if process.is_alive():
            process.terminate(); process.join()
            self.fail('Fault-injection subprocess failed to exit')
        self.assertEqual(process.exitcode, 23)
        self.assertEqual(marker.read_text(), hashlib.sha256(FILES[0].read_bytes()).hexdigest())
        successor = Coordinator(REPOSITORY, self.state)
        def forbidden(envelope):
            self.fail('Uncertain operation or its dependent was rerun')
        rows = successor.dispatch('local-repo', {'reader': forbidden, 'dependent': forbidden})
        self.assertEqual(rows[0]['state'], 'UNKNOWN_EFFECT')
        self.assertEqual(rows[0]['result']['outcome'], 'BLOCKED')
        self.assertEqual(successor.sco.projection('local-repo')['order_states'],
                         {'BLOCKED_PRESERVED': 1, 'BLOCKED_DEPENDENCY_ADVERSE': 1})

    def test_envelope_mutation_cannot_expand_receipt_authority(self):
        self.node('reader'); self.order('read', 'reader')
        def escalate(envelope):
            envelope['work_order']['authority_granted'].append('ADMIN')
            result = file_result(); result['authority_exercised'].append('ADMIN')
            return result
        row = self.coordinator.dispatch('local-repo', {'reader': escalate})[0]
        self.assertEqual(row['state'], 'UNKNOWN_EFFECT')
        self.assertEqual(row['envelope']['work_order']['authority_granted'], ['READ_REPOSITORY'])
        self.assertEqual(row['result']['outcome'], 'BLOCKED')
        self.assertEqual(row['result']['authority_exercised'], [])

    def test_unverified_connector_and_nonexecuting_role_do_not_invoke(self):
        self.node('unverified', connector='REFERENCE_ONLY_NO_LIVE_BRIDGE')
        self.node('observer', autonomy='OBSERVE_ONLY')
        self.order('unverified', 'unverified'); self.order('observer', 'observer')
        def forbidden(envelope):
            self.fail('Blocked node invoked')
        rows = self.coordinator.dispatch('local-repo', {'unverified': forbidden, 'observer': forbidden})
        self.assertEqual([r['result']['outcome'] for r in rows], ['BLOCKED', 'BLOCKED'])

    def test_explicit_failure_blocks_dependents_and_remote_ref_cannot_succeed(self):
        self.node('failed'); self.node('dependent'); self.node('remote')
        self.order('failed', 'failed'); self.order('dependent', 'dependent', ('failed',))
        self.order('remote', 'remote')
        def failed(envelope):
            return {'outcome': 'FAILED', 'limitations': ['No operation requested by this local reader.']}
        def remote(envelope):
            result = file_result(); result['output_refs'] = ['https://example.invalid/unverified']
            return result
        rows = self.coordinator.dispatch('local-repo', {
            'failed': failed, 'remote': remote,
            'dependent': lambda envelope: self.fail('Dependent invoked after FAILED')})
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['result']['outcome'], 'FAILED')
        self.assertEqual(rows[1]['result']['outcome'], 'BLOCKED')

    def test_process_lock_excludes_another_dispatcher(self):
        self.node('reader'); self.order('read', 'reader')
        code = '''import sys
from pathlib import Path
from kch_composed.coordinator import Coordinator, CoordinatorBusy
c = Coordinator(Path(sys.argv[1]), Path(sys.argv[2]))
try:
    c.dispatch('local-repo', {})
except CoordinatorBusy:
    print('BUSY_CONFIRMED')
else:
    raise SystemExit('Dispatcher exclusivity failed')
'''
        env = dict(os.environ, PYTHONPATH=str(HERE.parents[1] / 'src'))
        with self.coordinator._exclusive():
            result = subprocess.run([sys.executable, '-c', code, str(REPOSITORY), str(self.state)],
                                    env=env, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'BUSY_CONFIRMED')
        self.assertEqual(self.coordinator.inspect(), [])

    def test_missing_adapter_leaves_order_available(self):
        self.node('reader'); self.order('read', 'reader')
        self.assertEqual(self.coordinator.dispatch('local-repo', {}), [])
        self.assertEqual(self.sco.schedule('local-repo')['ready_count'], 1)

    def test_exception_message_is_not_persisted_in_journal_or_sco(self):
        self.node('reader'); self.order('read', 'reader')
        def fail_after_read(envelope):
            file_result()
            raise RuntimeError('Bearer DO_NOT_PERSIST https://private.invalid/?token=DO_NOT_PERSIST prompt=DO_NOT_PERSIST')
        row = self.coordinator.dispatch('local-repo', {'reader': fail_after_read})[0]
        self.assertEqual(row['state'], 'UNKNOWN_EFFECT')
        self.assertIn('HANDLER_OR_RESULT_VALIDATION_FAILED:RuntimeError', row['result']['limitations'])
        with sqlite3.connect(self.state) as db:
            persisted = '\n'.join(db.iterdump())
        self.assertNotIn('DO_NOT_PERSIST', persisted)
        self.assertNotIn('private.invalid', persisted)
        self.assertNotIn('Bearer', persisted)

    def test_corrupt_reservation_cannot_hide_from_recovery(self):
        self.node('reader'); self.order('read', 'reader')
        envelope = self.sco.dispatch_envelopes('local-repo')[0]
        self.assertTrue(self.coordinator._reserve(envelope))
        mutations = [
            ("state='COMPLETED', published=1", ()),
            ("state='RESULT_READY'", ()),
            ("published=1", ()),
            ("state='UNRECOGNIZED'", ()),
            ("sco_id=?", ('different-sco',)),
            ("order_id=?", ('different-order',)),
        ]
        for assignment, values in mutations:
            with self.subTest(assignment=assignment):
                with sqlite3.connect(self.state) as db:
                    db.execute('UPDATE composed_dispatch SET ' + assignment, values)
                with self.assertRaises(CoordinatorIntegrityError):
                    self.coordinator.inspect()
                with self.assertRaises(CoordinatorIntegrityError):
                    self.coordinator.recover('local-repo')
                with sqlite3.connect(self.state) as db:
                    db.execute("UPDATE composed_dispatch SET state='RUNNING', published=0, sco_id='local-repo', order_id='read'")

    def test_published_flag_requires_matching_native_receipt(self):
        self.node('reader'); self.order('read', 'reader')
        with patch.object(self.coordinator, '_publish', side_effect=RuntimeError('Injected publish interruption')):
            with self.assertRaises(RuntimeError):
                self.coordinator.dispatch('local-repo', {'reader': lambda envelope: file_result()})
        with sqlite3.connect(self.state) as db:
            db.execute("UPDATE composed_dispatch SET state='COMPLETED', published=1")
        with self.assertRaisesRegex(CoordinatorIntegrityError, 'matching native SCO receipt'):
            self.coordinator.inspect()
        with sqlite3.connect(self.state) as db:
            db.execute("UPDATE composed_dispatch SET state='RESULT_READY', published=0")
        self.coordinator.recover('local-repo')
        with sqlite3.connect(self.state) as db:
            raw = json.loads(db.execute('SELECT record_json FROM receipts').fetchone()[0])
            raw['claims'].append('CORRUPTED_RECEIPT')
            db.execute('UPDATE receipts SET record_json=?', (json.dumps(raw),))
        with self.assertRaisesRegex(CoordinatorIntegrityError, 'matching native SCO receipt'):
            self.coordinator.inspect()


if __name__ == '__main__':
    unittest.main()
