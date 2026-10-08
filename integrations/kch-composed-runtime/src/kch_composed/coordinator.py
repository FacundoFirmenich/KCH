"""Durable local execution for existing SCO work orders.

Handlers are trusted Python adapters, not an isolation boundary or LLM agents.
SCO owns roles, grants, work orders, dependencies and receipts. This module adds
one process-exclusive dispatcher and an at-most-once invocation journal. A
crash after reservation cannot establish whether an external effect occurred:
recovery records UNKNOWN_EFFECT and blocks dependents rather than retrying it.
Exactly-once reconciliation describes SCO receipts, never arbitrary effects.
"""
from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import importlib
import json
from pathlib import Path
import sqlite3
import sys
from typing import Callable
from urllib.parse import unquote, urlsplit


class CoordinatorBusy(RuntimeError):
    """Another dispatcher or recovery process holds the state lock."""


class CoordinatorIntegrityError(RuntimeError):
    """The durable dispatch journal or its SCO receipt disagrees."""


def _json(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False)


def _hash(value):
    return hashlib.sha256(_json(value).encode()).hexdigest()


def _now():
    return datetime.now(timezone.utc).isoformat()


class Coordinator:
    """Use a repository's SCO v0.1.1 and a persistent SQLite ``state_path``.

    ``sco`` is the native SCOService. Configure nodes/orders with its API.
    ``dispatch(sco_id, handlers, max_workers=4)`` maps node IDs to trusted
    ``handler(envelope)`` callables, executing READY orders in parallel.
    Results use only: outcome, output_refs, evidence_ids, claims, limitations,
    authority_exercised. Outcome is required; list fields default to empty.
    SUCCEEDED requires existing local file references. Receipts receive file
    hashes as evidence IDs. Local relative paths resolve against repository.
    ``recover(sco_id)`` reconciles durable results without invoking handlers.
    ``inspect()`` returns persisted dispatch records, with no model inference.
    """

    def __init__(self, repository: Path, state_path: Path):
        self.repository = Path(repository).resolve(strict=True)
        source = self.repository / 'work/SCO_RELEASE_STAGE_v0.1.1/src'
        if not (source / 'kch_sco/ledger.py').is_file():
            raise FileNotFoundError(f'Native SCO source missing: {source}')
        if str(source) not in sys.path:
            sys.path.insert(0, str(source))
        native = importlib.import_module('kch_sco')
        if Path(native.__file__).resolve().parent != source / 'kch_sco':
            raise ImportError('kch_sco already loaded from a different repository')
        self._receipt_validator = importlib.import_module('kch_sco.models').validate_receipt
        self._sco_conflict = native.SCOConflictError
        self.state_path = Path(state_path).resolve()
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.sco = native.SCOService(self.state_path)
        with self._db() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS composed_dispatch (
                order_id TEXT PRIMARY KEY, sco_id TEXT NOT NULL,
                state TEXT NOT NULL, envelope_json TEXT NOT NULL,
                envelope_sha256 TEXT NOT NULL, result_json TEXT,
                result_sha256 TEXT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0
            )''')

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.state_path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA synchronous=FULL')
        try:
            with db:
                yield db
        finally:
            db.close()

    @contextmanager
    def _exclusive(self):
        lock = self.state_path.with_name(self.state_path.name + '.dispatch.lock')
        with lock.open('a+b') as handle:
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise CoordinatorBusy('State already has an active dispatcher') from exc
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def inspect(self):
        with self._db() as db:
            # One SQLite read snapshot binds mutable dispatch metadata to the
            # immutable native order and (when acknowledged) its SCO receipt.
            rows = db.execute('''SELECT d.*, w.record_json AS sco_order_json,
                r.record_json AS native_receipt_json FROM composed_dispatch d
                LEFT JOIN work_orders w ON w.order_id=d.order_id
                LEFT JOIN receipts r ON r.order_id=d.order_id
                ORDER BY d.rowid''').fetchall()
        values = []
        for row in rows:
            try:
                envelope = json.loads(row['envelope_json'])
                result = json.loads(row['result_json']) if row['result_json'] is not None else None
                order = envelope['work_order']
                native_order = json.loads(row['sco_order_json'])
                native_receipt = (json.loads(row['native_receipt_json'])
                                  if row['native_receipt_json'] is not None else None)
            except (KeyError, TypeError, ValueError):
                raise CoordinatorIntegrityError('Malformed dispatch journal or missing native order') from None
            if not isinstance(order, dict) or not isinstance(native_order, dict):
                raise CoordinatorIntegrityError('Dispatch work order must be an object')
            if _hash(envelope) != row['envelope_sha256'] or (
                result is not None and _hash(result) != row['result_sha256']
            ):
                raise CoordinatorIntegrityError('Journal hash mismatch')
            if (order.get('order_id') != row['order_id'] or
                    order.get('sco_id') != row['sco_id'] or
                    _hash(order) != _hash(native_order)):
                raise CoordinatorIntegrityError('Dispatch identity disagrees with native work order')
            state, published = row['state'], row['published']
            if state not in {'RUNNING', 'RESULT_READY', 'COMPLETED', 'UNKNOWN_EFFECT'} or published not in (0, 1):
                raise CoordinatorIntegrityError('Invalid dispatch lifecycle metadata')
            if state == 'RUNNING':
                if result is not None or row['result_sha256'] is not None or published:
                    raise CoordinatorIntegrityError('RUNNING cannot contain a result or acknowledgement')
            else:
                if result is None:
                    raise CoordinatorIntegrityError('Final dispatch state requires a durable result')
                if (state == 'RESULT_READY' and published) or (state == 'COMPLETED' and not published):
                    raise CoordinatorIntegrityError('Dispatch state contradicts acknowledgement')
                try:
                    self._receipt_validator(result)
                    identity_matches = (
                        result['order_id'] == row['order_id'] and
                        result['node_id'] == order['target_node_id'] and
                        result['receipt_id'] == 'composed:' + hashlib.sha256(row['order_id'].encode()).hexdigest() and
                        set(result['authority_exercised']).issubset(order['authority_granted']))
                except (KeyError, TypeError, ValueError):
                    raise CoordinatorIntegrityError('Invalid durable receipt contract') from None
                if not identity_matches:
                    raise CoordinatorIntegrityError('Durable receipt identity or authority mismatch')
                if state == 'UNKNOWN_EFFECT' and (result['outcome'] != 'BLOCKED' or not any(
                        text.startswith('UNKNOWN_EFFECT:') for text in result['limitations'])):
                    raise CoordinatorIntegrityError('UNKNOWN_EFFECT requires its blocked uncertainty receipt')
                if state != 'UNKNOWN_EFFECT' and any(text.startswith('UNKNOWN_EFFECT:')
                                                    for text in result['limitations']):
                    raise CoordinatorIntegrityError('Uncertain effect cannot become a completed execution')
            if published and (native_receipt is None or _hash(native_receipt) != _hash(result)):
                raise CoordinatorIntegrityError('Published result has no matching native SCO receipt')
            if native_receipt is not None and (result is None or _hash(native_receipt) != _hash(result)):
                raise CoordinatorIntegrityError('Native SCO receipt disagrees with durable result')
            values.append({'order_id': row['order_id'], 'sco_id': row['sco_id'],
                           'state': row['state'], 'published': bool(row['published']),
                           'envelope': envelope, 'result': result,
                           'created_at': row['created_at'], 'updated_at': row['updated_at']})
        return values

    def _reserve(self, envelope):
        order = envelope['work_order']
        now = _now()
        with self._db() as db:
            cursor = db.execute('''INSERT OR IGNORE INTO composed_dispatch
                (order_id,sco_id,state,envelope_json,envelope_sha256,created_at,updated_at)
                VALUES (?,?,'RUNNING',?,?,?,?)''',
                (order['order_id'], order['sco_id'], _json(envelope), _hash(envelope), now, now))
        return cursor.rowcount == 1

    def _receipt(self, envelope, result):
        allowed = {'outcome', 'output_refs', 'evidence_ids', 'claims',
                   'limitations', 'authority_exercised'}
        if not isinstance(result, dict) or 'outcome' not in result or set(result) - allowed:
            raise ValueError('Handler result has missing outcome or unsupported fields')
        order = envelope['work_order']
        record = {'schema': 'kch.sco.receipt.v0.1.0',
                  'receipt_id': 'composed:' + hashlib.sha256(order['order_id'].encode()).hexdigest(),
                  'order_id': order['order_id'], 'node_id': order['target_node_id'],
                  'outcome': result['outcome'], 'completed_at': _now()}
        record.update({key: deepcopy(result.get(key, [])) for key in allowed - {'outcome'}})
        record = self._receipt_validator(record)
        if not set(record['authority_exercised']).issubset(order['authority_granted']):
            raise ValueError('Handler result reports authority escalation')
        if record['outcome'] == 'SUCCEEDED':
            for reference in record['output_refs']:
                parts = urlsplit(reference)
                if parts.scheme and (parts.scheme != 'file' or parts.netloc not in ('', 'localhost')):
                    raise ValueError('SUCCEEDED requires verifiable local file output_refs')
                path = Path(unquote(parts.path)) if parts.scheme else Path(reference)
                if not path.is_absolute():
                    path = self.repository / path
                path = path.resolve(strict=True)
                if not path.is_file():
                    raise ValueError('Output reference is not a regular file')
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                record['evidence_ids'].append(f'sha256:{digest}:{path.as_uri()}')
        return record

    def _store_result(self, envelope, receipt, state='RESULT_READY'):
        with self._db() as db:
            cursor = db.execute('''UPDATE composed_dispatch SET state=?, result_json=?,
                result_sha256=?, updated_at=? WHERE order_id=? AND result_json IS NULL''',
                (state, _json(receipt), _hash(receipt), _now(), envelope['work_order']['order_id']))
            if cursor.rowcount != 1:
                raise CoordinatorIntegrityError('A durable result already exists or reservation is absent')

    def _unknown(self, envelope, reason):
        receipt = self._receipt(envelope, {'outcome': 'BLOCKED', 'limitations': [
            'UNKNOWN_EFFECT: execution may have affected external state; automatic retry is prohibited.', reason]})
        self._store_result(envelope, receipt, 'UNKNOWN_EFFECT')

    def _execute(self, envelope, handler, blocker):
        if blocker:
            self._store_result(envelope, self._receipt(envelope, {
                'outcome': 'BLOCKED', 'limitations': [blocker]}))
            return
        try:
            # Never let a handler mutate the journal's grant or receipt identity.
            result = handler(deepcopy(envelope))
            receipt = self._receipt(envelope, result)
        except Exception as exc:
            # Exception messages may include prompts, bearer credentials or
            # signed URLs. Only a fixed category is admitted to durable logs;
            # custom exception class names are also outside this allowlist.
            category = next(name for kind, name in (
                (ValueError, 'ValueError'), (TypeError, 'TypeError'),
                (OSError, 'OSError'), (RuntimeError, 'RuntimeError'),
                (Exception, 'Exception')) if isinstance(exc, kind))
            self._unknown(envelope, 'HANDLER_OR_RESULT_VALIDATION_FAILED:' + category)
            return
        self._store_result(envelope, receipt)

    def _publish(self, row):
        receipt = row['result']
        if receipt is None or row['published']:
            return
        for attempt in range(4):
            existing = next((r for r in self.sco.export_bundle(row['sco_id'])['receipts']
                             if r['order_id'] == row['order_id']), None)
            if existing is not None:
                if _hash(existing) != _hash(receipt):
                    raise CoordinatorIntegrityError('An incompatible SCO receipt already exists')
                break
            try:
                self.sco.ingest_receipt(receipt, actor='kch-composed-coordinator',
                    command_id='composed-receipt:' + receipt['receipt_id'],
                    expected_head_hash=self.sco.head())
                break
            except self._sco_conflict as exc:
                if 'STALE_EXPECTED_HEAD' not in str(exc) or attempt == 3:
                    raise
        with self._db() as db:
            db.execute('''UPDATE composed_dispatch SET published=1,
                state=CASE WHEN state='UNKNOWN_EFFECT' THEN state ELSE 'COMPLETED' END,
                updated_at=? WHERE order_id=?''', (_now(), row['order_id']))

    def _recover(self, sco_id):
        self.sco.schedule(sco_id)  # Validate SCO identity using its public API.
        for row in self.inspect():
            if row['sco_id'] == sco_id and row['state'] == 'RUNNING' and row['result'] is None:
                self._unknown(row['envelope'], 'Recovered a reservation with no durable result.')
        for row in self.inspect():
            if row['sco_id'] == sco_id and row['result'] is not None and not row['published']:
                self._publish(row)
        return [row for row in self.inspect() if row['sco_id'] == sco_id]

    def recover(self, sco_id):
        with self._exclusive():
            return self._recover(sco_id)

    def dispatch(self, sco_id, handlers: dict[str, Callable[[dict], dict]], max_workers=4):
        if type(max_workers) is not int or not 1 <= max_workers <= 64:
            raise ValueError('max_workers must be an integer between 1 and 64')
        if not isinstance(handlers, dict) or any(not isinstance(k, str) or not callable(v)
                                                for k, v in handlers.items()):
            raise TypeError('handlers must map node IDs to callables')
        with self._exclusive():
            self._recover(sco_id)
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                pending = {}
                while True:
                    nodes = {n['node_id']: n for n in self.sco.export_bundle(sco_id)['nodes']}
                    for envelope in self.sco.dispatch_envelopes(sco_id):
                        if len(pending) >= max_workers:
                            break
                        order = envelope['work_order']
                        node_id = order['target_node_id']
                        if node_id not in handlers:
                            continue  # Partial adapter sets do not condemn remaining orders.
                        if not self._reserve(envelope):
                            continue
                        node = nodes[node_id]
                        blocker = None
                        if envelope['dispatch_blocker'] != 'NONE':
                            blocker = envelope['dispatch_blocker']
                        elif node['autonomy_level'] not in {'EXECUTE_WITHIN_SCOPE', 'SUBORCHESTRATE_WITHIN_SCOPE'}:
                            blocker = 'NODE_AUTONOMY_DOES_NOT_AUTHORIZE_EXECUTION'
                        elif not set(order['authority_granted']).issubset(node['authority_granted']):
                            blocker = 'WORK_ORDER_EXCEEDS_NODE_AUTHORITY'
                        future = pool.submit(self._execute, envelope, handlers[node_id], blocker)
                        pending[future] = order['order_id']
                    if not pending:
                        break
                    done, _ = wait(pending, return_when=FIRST_COMPLETED)
                    for future in done:
                        future.result()
                        order_id = pending.pop(future)
                        row = next(r for r in self.inspect() if r['order_id'] == order_id)
                        self._publish(row)
            return [row for row in self.inspect() if row['sco_id'] == sco_id]
