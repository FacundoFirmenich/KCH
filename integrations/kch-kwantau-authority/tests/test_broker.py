from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from kch_kwantau_authority.broker import AuthorityBroker, AuthorityError, canonical, sha256_text


PREDECESSOR_DDL = """
CREATE TABLE settings(
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
CREATE TABLE events(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  event_name TEXT NOT NULL,
  session_id TEXT,
  turn_id TEXT,
  payload_sha256 TEXT NOT NULL,
  payload_json TEXT,
  previous_hash TEXT NOT NULL,
  event_hash TEXT NOT NULL
);
CREATE TABLE proposals(
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  session_id TEXT NOT NULL,
  turn_id TEXT,
  tool_name TEXT NOT NULL,
  args_sha256 TEXT NOT NULL,
  resources_json TEXT NOT NULL,
  tool_input_json TEXT NOT NULL,
  reason TEXT NOT NULL DEFAULT '',
  impact TEXT NOT NULL DEFAULT '',
  recovery TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'DRAFT'
);
CREATE TABLE authorizations(
  proposal_id TEXT PRIMARY KEY REFERENCES proposals(id),
  session_id TEXT NOT NULL,
  args_sha256 TEXT NOT NULL,
  authorized_at TEXT NOT NULL,
  consumed_at TEXT,
  consumed_tool_use_id TEXT
);
"""


class BrokerCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "kch_native_r21.sqlite"
        db = sqlite3.connect(self.db_path)
        db.executescript(PREDECESSOR_DDL)
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        db.execute(
            "INSERT INTO settings VALUES(?,?,?)",
            ("persist_exact_inputs", "true", now),
        )
        self.tool_input = {
            "message": "Return READY",
            "sessionKey": "agent:test:main",
            "deliver": False,
        }
        self.args_sha = sha256_text(canonical(self.tool_input))
        db.execute(
            "INSERT INTO proposals("
            "id,created_at,session_id,turn_id,tool_name,args_sha256,"
            "resources_json,tool_input_json,reason,impact,recovery,status"
            ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "proposal-1",
                now,
                "agent:test:main",
                "turn-1",
                "openclaw.agent",
                self.args_sha,
                "[]",
                canonical(self.tool_input),
                "run exact authorized agent turn",
                "bounded",
                "idempotent replay",
                "AUTHORIZED",
            ),
        )
        db.execute(
            "INSERT INTO authorizations("
            "proposal_id,session_id,args_sha256,authorized_at"
            ") VALUES(?,?,?,?)",
            ("proposal-1", "agent:test:main", self.args_sha, now),
        )
        db.commit()
        db.close()
        self.broker = AuthorityBroker(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def params(self, **overrides):
        value = {
            "envelopeHash": "a" * 64,
            "leaseId": "lease-1",
            "reservationId": "reservation-1",
            "decisionId": "decision-1",
            "intentId": "intent-1",
            "policyHash": "b" * 64,
            "epoch": 7,
            "sessionId": "agent:test:main",
            "toolName": "openclaw.agent",
            "argsSha256": self.args_sha,
            "ttlSeconds": 5,
        }
        value.update(overrides)
        return value

    def test_verify_is_read_only(self):
        result = self.broker.verify(self.params())
        self.assertTrue(result["active"])
        self.assertEqual(result["status"], "AUTHORIZED_AVAILABLE")
        with sqlite3.connect(self.db_path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM authority_claims").fetchone()[0], 0)

    def test_prepare_replay_and_commit_consumes_exact_authorization(self):
        first = self.broker.prepare(self.params())
        second = self.broker.prepare(self.params())
        self.assertEqual(first["claimId"], second["claimId"])
        self.assertEqual(first["status"], "PREPARED")
        committed = self.broker.commit(
            {
                "claimId": first["claimId"],
                "envelopeHash": "a" * 64,
                "dispatchId": "dispatch-1",
            }
        )
        self.assertEqual(committed["status"], "COMMITTED")
        with sqlite3.connect(self.db_path) as db:
            consumed = db.execute(
                "SELECT consumed_at,consumed_tool_use_id FROM authorizations "
                "WHERE proposal_id='proposal-1'"
            ).fetchone()
            status = db.execute(
                "SELECT status FROM proposals WHERE id='proposal-1'"
            ).fetchone()[0]
            dispatch_id = db.execute(
                "SELECT dispatch_id FROM authority_claims WHERE claim_id=?",
                (first["claimId"],),
            ).fetchone()[0]
        self.assertIsNotNone(consumed[0])
        self.assertEqual(consumed[1], "dispatch-1")
        self.assertEqual(status, "CONSUMED")
        self.assertEqual(dispatch_id, "dispatch-1")

        receipted = self.broker.receipt(
            {
                "claimId": first["claimId"],
                "envelopeHash": "a" * 64,
                "runId": "run-1",
                "receiptHash": "c" * 64,
            }
        )
        self.assertEqual(receipted["status"], "COMMITTED")
        with sqlite3.connect(self.db_path) as db:
            run_id, receipt_hash = db.execute(
                "SELECT run_id,receipt_hash FROM authority_claims WHERE claim_id=?",
                (first["claimId"],),
            ).fetchone()
        self.assertEqual(run_id, "run-1")
        self.assertEqual(receipt_hash, "c" * 64)

    def test_one_authorization_cannot_be_rebound_to_another_envelope(self):
        self.broker.prepare(self.params())
        shadow = self.broker.verify(self.params(envelopeHash="d" * 64))
        self.assertFalse(shadow["active"])
        self.assertEqual(shadow["reason"], "authorization is already claimed")
        with self.assertRaises(AuthorityError) as caught:
            self.broker.prepare(self.params(envelopeHash="d" * 64))
        self.assertEqual(caught.exception.code, "AUTHORITY_CLAIM_CONFLICT")

    def test_abort_makes_attempt_non_reusable(self):
        prepared = self.broker.prepare(self.params())
        aborted = self.broker.abort(
            {
                "claimId": prepared["claimId"],
                "envelopeHash": "a" * 64,
                "reason": "dispatch proved not to have occurred",
            }
        )
        self.assertEqual(aborted["status"], "ABORTED")
        with self.assertRaises(AuthorityError) as caught:
            self.broker.prepare(self.params(envelopeHash="e" * 64))
        self.assertEqual(caught.exception.code, "AUTHORITY_DENIED")

    def test_indoubt_can_only_follow_consumed_authority_and_resolve_by_receipt(self):
        prepared = self.broker.prepare(self.params())
        committed = self.broker.commit(
            {
                "claimId": prepared["claimId"],
                "envelopeHash": "a" * 64,
                "dispatchId": "dispatch-indoubt",
            }
        )
        self.assertEqual(committed["status"], "COMMITTED")
        uncertain = self.broker.indoubt(
            {
                "claimId": prepared["claimId"],
                "envelopeHash": "a" * 64,
                "reason": "remote acceptance may have occurred",
            }
        )
        self.assertEqual(uncertain["status"], "IN_DOUBT")
        recovered = self.broker.receipt(
            {
                "claimId": prepared["claimId"],
                "envelopeHash": "a" * 64,
                "runId": "run-recovered",
                "receiptHash": "f" * 64,
            }
        )
        self.assertEqual(recovered["status"], "COMMITTED")

    def test_expired_prepare_is_terminal_and_requires_new_user_authority(self):
        prepared = self.broker.prepare(self.params())
        expired = (datetime.now(UTC) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        with sqlite3.connect(self.db_path) as db:
            db.execute(
                "UPDATE authority_claims SET expires_at=? WHERE claim_id=?",
                (expired, prepared["claimId"]),
            )
            db.commit()
        status = self.broker.status({"claimId": prepared["claimId"]})
        self.assertEqual(status["status"], "EXPIRED")
        with self.assertRaises(AuthorityError) as caught:
            self.broker.prepare(self.params(envelopeHash="1" * 64))
        self.assertEqual(caught.exception.code, "AUTHORITY_DENIED")

    def test_tampered_kch_event_chain_fails_closed(self):
        prepared = self.broker.prepare(self.params())
        with sqlite3.connect(self.db_path) as db:
            db.execute("UPDATE events SET event_hash=? WHERE id=1", ("0" * 64,))
            db.commit()
        with self.assertRaises(AuthorityError) as caught:
            self.broker.status({"claimId": prepared["claimId"]})
        self.assertEqual(caught.exception.code, "LEDGER_CHAIN_INVALID")

    def test_exact_session_tool_and_args_are_required(self):
        for changed in (
            {"sessionId": "agent:test:other"},
            {"toolName": "openclaw.other"},
            {"argsSha256": "9" * 64},
        ):
            with self.assertRaises(AuthorityError) as caught:
                self.broker.prepare(self.params(**changed))
            self.assertEqual(caught.exception.code, "AUTHORITY_DENIED")


if __name__ == "__main__":
    unittest.main()
