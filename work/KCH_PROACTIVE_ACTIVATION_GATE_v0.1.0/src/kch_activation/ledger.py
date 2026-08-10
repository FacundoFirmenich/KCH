from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from .canonical import canonical_json, sha256_json


SCHEMA = "kch.activation-ledger.v0.1.0"
PENDING = "ASK_USER"
EXECUTING = "EXECUTING"
FINAL_PROPOSAL_STATES = {
    "EXECUTED_ONCE",
    "DECLINED_ONCE",
    "NEVER_THIS_SESSION",
    "ALWAYS_THIS_SESSION_EXECUTED",
    "EXECUTION_FAILED",
    "EXPIRED",
    "BYPASSED_BY_NEW_PROMPT",
    "SESSION_CLOSED",
}


class ActivationLedger:
    def __init__(self, path: str | Path, *, now: Callable[[], int] | None = None):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.now = now or (lambda: int(time.time()))
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=30000")
        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self.connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events(
                    sequence INTEGER PRIMARY KEY,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE,
                    created_at INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS proposals(
                    proposal_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    event_id TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    question TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    fingerprint TEXT NOT NULL,
                    source_text TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    resolved_at INTEGER,
                    response TEXT,
                    UNIQUE(session_id,event_id,rule_id)
                );
                CREATE INDEX IF NOT EXISTS proposals_session_state ON proposals(session_id,state,created_at);
                CREATE TABLE IF NOT EXISTS policies(
                    session_id TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    policy TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY(session_id,rule_id,tool_name)
                );
                CREATE TABLE IF NOT EXISTS executions(
                    execution_id TEXT PRIMARY KEY,
                    proposal_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    arguments_json TEXT NOT NULL,
                    result_sha256 TEXT,
                    state TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    FOREIGN KEY(proposal_id) REFERENCES proposals(proposal_id)
                );
                """
            )
            row = connection.execute("SELECT value FROM metadata WHERE key='schema'").fetchone()
            if row is None:
                connection.execute("INSERT INTO metadata(key,value) VALUES('schema',?)", (SCHEMA,))
            elif row[0] != SCHEMA:
                raise ValueError(f"activation ledger schema mismatch: {row[0]}")

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _append(self, connection: sqlite3.Connection, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        last = connection.execute("SELECT sequence,event_hash FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
        sequence = 1 if last is None else int(last["sequence"]) + 1
        previous_hash = "GENESIS" if last is None else str(last["event_hash"])
        created_at = self.now()
        core = {
            "schema": "kch.activation-event.v0.1.0",
            "sequence": sequence,
            "event_type": event_type,
            "payload": payload,
            "previous_hash": previous_hash,
            "created_at": created_at,
        }
        event_hash = sha256_json(core)
        connection.execute(
            "INSERT INTO events(sequence,event_type,payload_json,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?)",
            (sequence, event_type, canonical_json(payload), previous_hash, event_hash, created_at),
        )
        return {**core, "event_hash": event_hash}

    def expire_pending(self, session_id: str) -> None:
        now = self.now()
        with self.transaction() as connection:
            rows = connection.execute(
                "SELECT proposal_id FROM proposals WHERE session_id=? AND state=? AND expires_at<=?",
                (session_id, PENDING, now),
            ).fetchall()
            for row in rows:
                connection.execute(
                    "UPDATE proposals SET state='EXPIRED',resolved_at=?,response='EXPIRED',source_text='' WHERE proposal_id=?",
                    (now, row["proposal_id"]),
                )
                self._append(connection, "ACTIVATION_PROPOSAL_EXPIRED", {"session_id": session_id, "proposal_id": row["proposal_id"]})

    def pending(self, session_id: str) -> dict[str, Any] | None:
        self.expire_pending(session_id)
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM proposals WHERE session_id=? AND state=? ORDER BY created_at DESC,proposal_id DESC LIMIT 1",
                (session_id, PENDING),
            ).fetchone()
        return self._proposal(row) if row else None

    @staticmethod
    def _proposal(row: sqlite3.Row) -> dict[str, Any]:
        value = dict(row)
        value["arguments"] = json.loads(value.pop("arguments_json"))
        return value

    def get_proposal(self, session_id: str, proposal_id: str) -> dict[str, Any]:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM proposals WHERE session_id=? AND proposal_id=?",
                (session_id, proposal_id),
            ).fetchone()
        if row is None:
            raise ValueError("unknown activation proposal")
        return self._proposal(row)

    def proposal_for_event(self, session_id: str, event_id: str, rule_id: str) -> dict[str, Any] | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT * FROM proposals WHERE session_id=? AND event_id=? AND rule_id=?",
                (session_id, event_id, rule_id),
            ).fetchone()
        return self._proposal(row) if row else None

    def create_proposal(self, proposal: dict[str, Any]) -> dict[str, Any]:
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO proposals(
                    proposal_id,session_id,event_id,rule_id,tool_name,arguments_json,question,reason,
                    confidence,fingerprint,source_text,state,created_at,expires_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    proposal["proposal_id"], proposal["session_id"], proposal["event_id"], proposal["rule_id"],
                    proposal["tool_name"], canonical_json(proposal["arguments"]), proposal["question"], proposal["reason"],
                    proposal["confidence"], proposal["fingerprint"], proposal["source_text"], PENDING, proposal["created_at"], proposal["expires_at"],
                ),
            )
            event_payload = {k: proposal[k] for k in proposal if k not in {"question", "source_text"}}
            event_payload["source_text_sha256"] = sha256_json({"text": proposal["source_text"]})
            event = self._append(connection, "ACTIVATION_PROPOSED", event_payload)
        return {**proposal, "state": PENDING, "event_hash": event["event_hash"]}

    def bypass_pending(self, session_id: str, proposal_id: str) -> None:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT state FROM proposals WHERE session_id=? AND proposal_id=?",
                (session_id, proposal_id),
            ).fetchone()
            if row is None or row["state"] != PENDING:
                return
            now = self.now()
            connection.execute(
                "UPDATE proposals SET state='BYPASSED_BY_NEW_PROMPT',resolved_at=?,response='BYPASSED_BY_NEW_PROMPT',source_text='' WHERE proposal_id=?",
                (now, proposal_id),
            )
            self._append(connection, "ACTIVATION_BYPASSED", {"session_id": session_id, "proposal_id": proposal_id})

    def policy(self, session_id: str, rule_id: str, tool_name: str) -> str | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT policy FROM policies WHERE session_id=? AND rule_id=? AND tool_name=?",
                (session_id, rule_id, tool_name),
            ).fetchone()
        return str(row[0]) if row else None

    def set_policy(self, session_id: str, rule_id: str, tool_name: str, policy: str) -> None:
        if policy not in {"NEVER_THIS_SESSION", "ALWAYS_THIS_SESSION"}:
            raise ValueError("invalid session activation policy")
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO policies(session_id,rule_id,tool_name,policy,created_at) VALUES(?,?,?,?,?)
                ON CONFLICT(session_id,rule_id,tool_name) DO UPDATE SET policy=excluded.policy,created_at=excluded.created_at""",
                (session_id, rule_id, tool_name, policy, self.now()),
            )
            self._append(connection, "ACTIVATION_SESSION_POLICY_SET", {"session_id": session_id, "rule_id": rule_id, "tool_name": tool_name, "policy": policy})

    def resolve(self, session_id: str, proposal_id: str, response: str, state: str) -> dict[str, Any]:
        if state not in FINAL_PROPOSAL_STATES:
            raise ValueError("invalid final proposal state")
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM proposals WHERE session_id=? AND proposal_id=?",
                (session_id, proposal_id),
            ).fetchone()
            if row is None:
                raise ValueError("unknown activation proposal")
            if row["state"] != PENDING:
                raise ValueError("activation proposal is no longer pending")
            now = self.now()
            connection.execute(
                "UPDATE proposals SET state=?,resolved_at=?,response=?,source_text='' WHERE proposal_id=?",
                (state, now, response, proposal_id),
            )
            event = self._append(
                connection,
                "ACTIVATION_RESPONSE_RECORDED",
                {"session_id": session_id, "proposal_id": proposal_id, "rule_id": row["rule_id"], "tool_name": row["tool_name"], "response": response, "state": state},
            )
        return {**self.get_proposal(session_id, proposal_id), "event_hash": event["event_hash"]}

    def claim_execution(self, session_id: str, proposal_id: str, response: str) -> dict[str, Any]:
        """Atomically consume a proposal before calling a read-only tool."""
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM proposals WHERE session_id=? AND proposal_id=?",
                (session_id, proposal_id),
            ).fetchone()
            if row is None:
                raise ValueError("unknown activation proposal")
            if row["state"] != PENDING:
                raise ValueError("activation proposal is no longer pending")
            connection.execute(
                "UPDATE proposals SET state=?,response=? WHERE proposal_id=?",
                (EXECUTING, response, proposal_id),
            )
            event = self._append(
                connection,
                "ACTIVATION_EXECUTION_CLAIMED",
                {"session_id": session_id, "proposal_id": proposal_id, "response": response},
            )
        return {**self.get_proposal(session_id, proposal_id), "event_hash": event["event_hash"]}

    def finish_execution(self, session_id: str, proposal_id: str, state: str) -> dict[str, Any]:
        if state not in {"EXECUTED_ONCE", "ALWAYS_THIS_SESSION_EXECUTED", "EXECUTION_FAILED"}:
            raise ValueError("invalid execution terminal state")
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM proposals WHERE session_id=? AND proposal_id=?",
                (session_id, proposal_id),
            ).fetchone()
            if row is None:
                raise ValueError("unknown activation proposal")
            if row["state"] != EXECUTING:
                raise ValueError("activation proposal has not been claimed for execution")
            now = self.now()
            connection.execute(
                "UPDATE proposals SET state=?,resolved_at=?,source_text='' WHERE proposal_id=?",
                (state, now, proposal_id),
            )
            event = self._append(
                connection,
                "ACTIVATION_EXECUTION_FINALIZED",
                {"session_id": session_id, "proposal_id": proposal_id, "response": row["response"], "state": state},
            )
        return {**self.get_proposal(session_id, proposal_id), "event_hash": event["event_hash"]}

    def record_execution(self, proposal: dict[str, Any], execution_id: str, state: str, result_sha256: str | None) -> dict[str, Any]:
        if state not in {"PASS", "FAIL"}:
            raise ValueError("invalid execution state")
        with self.transaction() as connection:
            connection.execute(
                "INSERT INTO executions(execution_id,proposal_id,session_id,rule_id,tool_name,arguments_json,result_sha256,state,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    execution_id, proposal["proposal_id"], proposal["session_id"], proposal["rule_id"], proposal["tool_name"],
                    canonical_json(proposal["arguments"]), result_sha256, state, self.now(),
                ),
            )
            event = self._append(
                connection,
                "ACTIVATION_TOOL_EXECUTED" if state == "PASS" else "ACTIVATION_TOOL_EXECUTION_FAILED",
                {"execution_id": execution_id, "proposal_id": proposal["proposal_id"], "session_id": proposal["session_id"], "rule_id": proposal["rule_id"], "tool_name": proposal["tool_name"], "result_sha256": result_sha256, "state": state},
            )
        return {"execution_id": execution_id, "event_hash": event["event_hash"], "state": state}

    def question_count(self, session_id: str) -> int:
        with self.connection() as connection:
            row = connection.execute("SELECT COUNT(*) FROM proposals WHERE session_id=?", (session_id,)).fetchone()
        return int(row[0])

    def rule_question_count(self, session_id: str, rule_id: str) -> int:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM proposals WHERE session_id=? AND rule_id=?",
                (session_id, rule_id),
            ).fetchone()
        return int(row[0])

    def latest_resolution_time(self, session_id: str, rule_id: str) -> int | None:
        with self.connection() as connection:
            row = connection.execute(
                "SELECT MAX(resolved_at) FROM proposals WHERE session_id=? AND rule_id=? AND resolved_at IS NOT NULL",
                (session_id, rule_id),
            ).fetchone()
        return int(row[0]) if row and row[0] is not None else None

    def record_suppression(self, session_id: str, event_id: str, rule_id: str, tool_name: str, reason: str) -> None:
        with self.transaction() as connection:
            self._append(connection, "ACTIVATION_SUPPRESSED", {"session_id": session_id, "event_id": event_id, "rule_id": rule_id, "tool_name": tool_name, "reason": reason})

    def close_session(self, session_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            now = self.now()
            pending = connection.execute(
                "SELECT proposal_id FROM proposals WHERE session_id=? AND state=?",
                (session_id, PENDING),
            ).fetchall()
            connection.execute(
                "UPDATE proposals SET state='SESSION_CLOSED',resolved_at=?,response='SESSION_CLOSED',source_text='' WHERE session_id=? AND state=?",
                (now, session_id, PENDING),
            )
            removed = connection.execute("DELETE FROM policies WHERE session_id=?", (session_id,)).rowcount
            event = self._append(connection, "ACTIVATION_SESSION_CLOSED", {"session_id": session_id, "pending_closed": len(pending), "session_policies_removed": removed})
        return {"session_id": session_id, "pending_closed": len(pending), "session_policies_removed": removed, "event_hash": event["event_hash"]}

    def status(self, session_id: str | None = None) -> dict[str, Any]:
        where = " WHERE session_id=?" if session_id else ""
        params = (session_id,) if session_id else ()
        with self.connection() as connection:
            proposals = connection.execute("SELECT state,COUNT(*) AS n FROM proposals" + where + " GROUP BY state", params).fetchall()
            policies = connection.execute("SELECT policy,COUNT(*) AS n FROM policies" + where + " GROUP BY policy", params).fetchall()
            executions = connection.execute("SELECT state,COUNT(*) AS n FROM executions" + where + " GROUP BY state", params).fetchall()
        return {
            "schema": "kch.activation-status.v0.1.0",
            "session_id": session_id or "ALL",
            "proposals": {row["state"]: int(row["n"]) for row in proposals},
            "policies": {row["policy"]: int(row["n"]) for row in policies},
            "executions": {row["state"]: int(row["n"]) for row in executions},
            "integrity": self.verify(),
        }

    def verify(self) -> dict[str, Any]:
        defects: list[str] = []
        previous_hash = "GENESIS"
        with self.connection() as connection:
            rows = connection.execute("SELECT * FROM events ORDER BY sequence").fetchall()
        expected_sequence = 1
        for row in rows:
            if row["sequence"] != expected_sequence:
                defects.append(f"SEQUENCE:{row['sequence']}")
            payload = json.loads(row["payload_json"])
            core = {
                "schema": "kch.activation-event.v0.1.0",
                "sequence": row["sequence"],
                "event_type": row["event_type"],
                "payload": payload,
                "previous_hash": row["previous_hash"],
                "created_at": row["created_at"],
            }
            if row["previous_hash"] != previous_hash:
                defects.append(f"PREVIOUS_HASH:{row['sequence']}")
            if sha256_json(core) != row["event_hash"]:
                defects.append(f"EVENT_HASH:{row['sequence']}")
            previous_hash = row["event_hash"]
            expected_sequence += 1
        return {"gate": "PASS" if not defects else "FAIL", "defects": defects, "event_count": len(rows), "head_hash": previous_hash}
