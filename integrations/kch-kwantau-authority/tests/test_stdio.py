from __future__ import annotations

import sqlite3
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from kch_kwantau_authority.broker import AuthorityBroker, canonical, sha256_text
from kch_kwantau_authority.stdio_server import handle_request


class StdioContractCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "kch_native_r21.sqlite"
        db = sqlite3.connect(self.db_path)
        db.executescript(
            """
            CREATE TABLE settings(key TEXT PRIMARY KEY,value TEXT NOT NULL,updated_at TEXT NOT NULL);
            CREATE TABLE events(
              id INTEGER PRIMARY KEY AUTOINCREMENT,created_at TEXT NOT NULL,event_name TEXT NOT NULL,
              session_id TEXT,turn_id TEXT,payload_sha256 TEXT NOT NULL,payload_json TEXT,
              previous_hash TEXT NOT NULL,event_hash TEXT NOT NULL
            );
            CREATE TABLE proposals(
              id TEXT PRIMARY KEY,created_at TEXT NOT NULL,session_id TEXT NOT NULL,turn_id TEXT,
              tool_name TEXT NOT NULL,args_sha256 TEXT NOT NULL,resources_json TEXT NOT NULL,
              tool_input_json TEXT NOT NULL,reason TEXT NOT NULL DEFAULT '',impact TEXT NOT NULL DEFAULT '',
              recovery TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'DRAFT'
            );
            CREATE TABLE authorizations(
              proposal_id TEXT PRIMARY KEY REFERENCES proposals(id),session_id TEXT NOT NULL,
              args_sha256 TEXT NOT NULL,authorized_at TEXT NOT NULL,consumed_at TEXT,consumed_tool_use_id TEXT
            );
            """
        )
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        db.execute("INSERT INTO settings VALUES(?,?,?)", ("persist_exact_inputs", "true", now))
        payload = {"message": "READY", "sessionKey": "agent:test:main"}
        args_sha = sha256_text(canonical(payload))
        db.execute(
            "INSERT INTO proposals VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                "proposal-stdio", now, "agent:test:main", "turn-stdio", "openclaw.agent",
                args_sha, "[]", canonical(payload), "reason", "impact", "recovery", "AUTHORIZED",
            ),
        )
        db.execute(
            "INSERT INTO authorizations(proposal_id,session_id,args_sha256,authorized_at) VALUES(?,?,?,?)",
            ("proposal-stdio", "agent:test:main", args_sha, now),
        )
        db.commit()
        db.close()
        self.args_sha = args_sha
        self.broker = AuthorityBroker(self.db_path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_prepare_rpc_shape(self):
        response = handle_request(
            self.broker,
            {
                "id": "req-1",
                "method": "kch.authority.prepare",
                "params": {
                    "envelopeHash": "a" * 64,
                    "leaseId": "lease-1",
                    "reservationId": "reservation-1",
                    "decisionId": "decision-1",
                    "intentId": "intent-1",
                    "policyHash": "b" * 64,
                    "epoch": 3,
                    "sessionId": "agent:test:main",
                    "toolName": "openclaw.agent",
                    "argsSha256": self.args_sha,
                    "ttlSeconds": 5,
                },
            },
        )
        self.assertTrue(response["ok"])
        self.assertEqual(response["id"], "req-1")
        self.assertTrue(response["result"]["active"])
        self.assertEqual(response["result"]["status"], "PREPARED")

    def test_unknown_method_fails_closed(self):
        response = handle_request(self.broker, {"id": "x", "method": "authority.magic", "params": {}})
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"]["code"], "METHOD_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
