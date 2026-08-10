from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class TransportError(RuntimeError):
    pass


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TransportGuard:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as connection:
            connection.execute(
                """CREATE TABLE IF NOT EXISTS dispatches(
                    dispatch_id TEXT PRIMARY KEY,
                    envelope_json TEXT NOT NULL,
                    envelope_sha256 TEXT NOT NULL,
                    state TEXT NOT NULL,
                    prepared_at TEXT NOT NULL,
                    sent_at TEXT,
                    native_request_turn_id TEXT,
                    received_at TEXT,
                    native_response_turn_id TEXT,
                    response_text TEXT,
                    response_sha256 TEXT
                )"""
            )

    def prepare(self, envelope: dict[str, Any]) -> dict[str, Any]:
        required = {
            "schema", "dispatch_id", "order_id", "target_node_id", "target_native_uri", "nonce",
            "authority_granted", "forbidden_actions", "expected_receipt_schema", "payload_disclosure", "retry_policy",
        }
        if set(envelope) != required or envelope["schema"] != "kch.sco.host-dispatch-envelope.v0.2.0":
            raise TransportError("invalid dispatch envelope")
        envelope_json = canonical(envelope)
        envelope_hash = hashlib.sha256(envelope_json.encode("utf-8")).hexdigest()
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM dispatches WHERE dispatch_id=?", (envelope["dispatch_id"],)).fetchone()
            if row:
                if row["envelope_sha256"] != envelope_hash:
                    raise TransportError("dispatch_id collision")
                return {"dispatch_id": envelope["dispatch_id"], "state": row["state"], "should_send": row["state"] == "PREPARED", "idempotent_replay": True, "envelope_sha256": envelope_hash}
            connection.execute(
                "INSERT INTO dispatches(dispatch_id,envelope_json,envelope_sha256,state,prepared_at) VALUES(?,?,?,?,?)",
                (envelope["dispatch_id"], envelope_json, envelope_hash, "PREPARED", now()),
            )
        return {"dispatch_id": envelope["dispatch_id"], "state": "PREPARED", "should_send": True, "idempotent_replay": False, "envelope_sha256": envelope_hash}

    def mark_sent(self, dispatch_id: str, native_request_turn_id: str) -> dict[str, Any]:
        if not native_request_turn_id.strip():
            raise TransportError("native_request_turn_id is required")
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM dispatches WHERE dispatch_id=?", (dispatch_id,)).fetchone()
            if not row:
                raise TransportError("unknown dispatch")
            if row["state"] in {"SENT", "RECEIVED"}:
                if row["native_request_turn_id"] != native_request_turn_id:
                    raise TransportError("native request turn collision")
                return {"dispatch_id": dispatch_id, "state": row["state"], "idempotent_replay": True}
            connection.execute("UPDATE dispatches SET state='SENT',sent_at=?,native_request_turn_id=? WHERE dispatch_id=?", (now(), native_request_turn_id, dispatch_id))
        return {"dispatch_id": dispatch_id, "state": "SENT", "idempotent_replay": False}

    def ingest(self, dispatch_id: str, native_response_turn_id: str, response_text: str) -> dict[str, Any]:
        try:
            response = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise TransportError("native response is not JSON") from exc
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT * FROM dispatches WHERE dispatch_id=?", (dispatch_id,)).fetchone()
            if not row or row["state"] not in {"SENT", "RECEIVED"}:
                raise TransportError("dispatch was not sent")
            envelope = json.loads(row["envelope_json"])
            required = {
                "schema", "dispatch_id", "order_id", "node_state", "nonce", "authority_exercised",
                "forbidden_actions_observed", "result", "limitations",
            }
            if set(response) != required:
                raise TransportError("receipt fields mismatch")
            if response["schema"] != envelope["expected_receipt_schema"] or response["dispatch_id"] != dispatch_id or response["order_id"] != envelope["order_id"] or response["nonce"] != envelope["nonce"]:
                raise TransportError("receipt identity mismatch")
            if not set(response["authority_exercised"]).issubset(envelope["authority_granted"]):
                raise TransportError("receipt authority escalation")
            if set(response["forbidden_actions_observed"]) != set(envelope["forbidden_actions"]):
                raise TransportError("receipt does not attest every forbidden action")
            response_hash = hashlib.sha256(response_text.encode("utf-8")).hexdigest()
            if row["state"] == "RECEIVED":
                if row["native_response_turn_id"] != native_response_turn_id or row["response_sha256"] != response_hash:
                    raise TransportError("native response collision")
                return {"dispatch_id": dispatch_id, "state": "RECEIVED", "idempotent_replay": True, "response_sha256": response_hash, "receipt": response}
            connection.execute(
                "UPDATE dispatches SET state='RECEIVED',received_at=?,native_response_turn_id=?,response_text=?,response_sha256=? WHERE dispatch_id=?",
                (now(), native_response_turn_id, response_text, response_hash, dispatch_id),
            )
        return {"dispatch_id": dispatch_id, "state": "RECEIVED", "idempotent_replay": False, "response_sha256": response_hash, "receipt": response}

    def status(self, dispatch_id: str) -> dict[str, Any]:
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute("SELECT * FROM dispatches WHERE dispatch_id=?", (dispatch_id,)).fetchone()
        if not row:
            raise TransportError("unknown dispatch")
        return {key: row[key] for key in row.keys() if key != "response_text"} | {"response_present": row["response_text"] is not None}

    def verify(self) -> dict[str, Any]:
        defects = []
        with sqlite3.connect(self.path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute("SELECT * FROM dispatches ORDER BY dispatch_id").fetchall()
        for row in rows:
            if hashlib.sha256(row["envelope_json"].encode("utf-8")).hexdigest() != row["envelope_sha256"]:
                defects.append(f"ENVELOPE:{row['dispatch_id']}")
            if row["state"] == "RECEIVED" and (row["response_text"] is None or hashlib.sha256(row["response_text"].encode("utf-8")).hexdigest() != row["response_sha256"]):
                defects.append(f"RESPONSE:{row['dispatch_id']}")
        return {"gate": "PASS" if not defects else "FAIL", "defects": defects, "dispatches": len(rows), "received": sum(row["state"] == "RECEIVED" for row in rows)}
