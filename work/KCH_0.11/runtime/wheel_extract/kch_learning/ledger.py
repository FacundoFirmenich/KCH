from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .canonical import LearningError


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _ClosingConnection(sqlite3.Connection):
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class LearningLedger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, factory=_ClosingConnection)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS events (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS decisions (
                    decision_id TEXT PRIMARY KEY,
                    record_json TEXT NOT NULL,
                    record_hash TEXT NOT NULL,
                    registered_event_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    channel TEXT NOT NULL,
                    initiator TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    state TEXT NOT NULL,
                    exclusive INTEGER NOT NULL,
                    decision_id TEXT,
                    started_at TEXT NOT NULL,
                    closed_at TEXT
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    decision_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    record_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS training_packets (
                    packet_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    packet_json TEXT NOT NULL,
                    packet_hash TEXT NOT NULL,
                    activation_state TEXT NOT NULL,
                    event_hash TEXT NOT NULL
                );
                """
            )

    def _append_event(self, connection: sqlite3.Connection, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        previous = connection.execute("SELECT event_hash FROM events ORDER BY sequence DESC LIMIT 1").fetchone()
        previous_hash = previous[0] if previous else "GENESIS"
        body = {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "occurred_at": _now(),
            "payload": payload,
            "previous_hash": previous_hash,
        }
        event_hash = _sha(_canonical(body))
        connection.execute(
            "INSERT INTO events(event_id,event_type,occurred_at,payload_json,previous_hash,event_hash) VALUES(?,?,?,?,?,?)",
            (body["event_id"], event_type, body["occurred_at"], _canonical(payload), previous_hash, event_hash),
        )
        return {**body, "event_hash": event_hash}

    def register_decision(self, record: dict[str, Any]) -> dict[str, Any]:
        decision_id = str(record.get("decision_id", "")).strip()
        if not decision_id:
            raise LearningError("decision_id is required")
        normalized = {**record, "decision_id": decision_id}
        record_json = _canonical(normalized)
        record_hash = _sha(record_json)
        with self._connect() as connection:
            existing = connection.execute("SELECT record_hash FROM decisions WHERE decision_id=?", (decision_id,)).fetchone()
            if existing:
                if existing[0] != record_hash:
                    raise LearningError("decision_id collision with different content")
                return {"decision_id": decision_id, "record_hash": record_hash, "idempotent": True}
            event = self._append_event(connection, "DECISION_REGISTERED", {"decision_id": decision_id, "record_hash": record_hash})
            connection.execute(
                "INSERT INTO decisions(decision_id,record_json,record_hash,registered_event_hash) VALUES(?,?,?,?)",
                (decision_id, record_json, record_hash, event["event_hash"]),
            )
        return {"decision_id": decision_id, "record_hash": record_hash, "idempotent": False}

    def decision(self, decision_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT record_json,record_hash FROM decisions WHERE decision_id=?", (decision_id,)).fetchone()
        if not row:
            raise LearningError(f"unknown decision_id: {decision_id}")
        return {"record": json.loads(row["record_json"]), "record_hash": row["record_hash"]}

    def list_decisions(self, component: str | None = None, reviewed: bool | None = None) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                """SELECT d.record_json,d.record_hash,
                (SELECT COUNT(*) FROM feedback f WHERE f.decision_id=d.decision_id AND f.channel='PHL') AS phl_reviews
                FROM decisions d ORDER BY d.decision_id"""
            ).fetchall()
        output = []
        for row in rows:
            record = json.loads(row["record_json"])
            if component and record.get("component") != component:
                continue
            if reviewed is not None and (row["phl_reviews"] > 0) != reviewed:
                continue
            output.append({**record, "record_hash": row["record_hash"], "phl_reviews": row["phl_reviews"]})
        return output

    def active_phl_session(self) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT session_id FROM sessions WHERE channel='PHL' AND state='ACTIVE' ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        return row[0] if row else None

    def start_session(self, channel: str, initiator: str, trigger: str, *, exclusive: bool, decision_id: str | None = None) -> dict[str, Any]:
        session_id = str(uuid4())
        started_at = _now()
        with self._connect() as connection:
            if channel == "PHL" and connection.execute("SELECT 1 FROM sessions WHERE channel='PHL' AND state='ACTIVE'").fetchone():
                raise LearningError("an active PHL session already holds the exclusive training lock")
            event = self._append_event(
                connection,
                "LEARNING_SESSION_STARTED",
                {"session_id": session_id, "channel": channel, "initiator": initiator, "trigger": trigger, "exclusive": exclusive, "decision_id": decision_id},
            )
            connection.execute(
                "INSERT INTO sessions(session_id,channel,initiator,trigger,state,exclusive,decision_id,started_at) VALUES(?,?,?,?,?,?,?,?)",
                (session_id, channel, initiator, trigger, "ACTIVE", int(exclusive), decision_id, started_at),
            )
        return {"session_id": session_id, "channel": channel, "state": "ACTIVE", "exclusive": exclusive, "event_hash": event["event_hash"]}

    def session(self, session_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        if not row:
            raise LearningError(f"unknown session_id: {session_id}")
        return dict(row)

    def close_session(self, session_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT state FROM sessions WHERE session_id=?", (session_id,)).fetchone()
            if not row:
                raise LearningError(f"unknown session_id: {session_id}")
            if row[0] == "CLOSED":
                return {"session_id": session_id, "state": "CLOSED", "idempotent": True}
            event = self._append_event(connection, "LEARNING_SESSION_CLOSED", {"session_id": session_id})
            connection.execute("UPDATE sessions SET state='CLOSED',closed_at=? WHERE session_id=?", (_now(), session_id))
        return {"session_id": session_id, "state": "CLOSED", "idempotent": False, "event_hash": event["event_hash"]}

    def add_feedback(self, session_id: str, decision_id: str, channel: str, actor: str, record: dict[str, Any]) -> dict[str, Any]:
        feedback_id = str(uuid4())
        record_json = _canonical(record)
        record_hash = _sha(record_json)
        with self._connect() as connection:
            session = connection.execute("SELECT channel,state FROM sessions WHERE session_id=?", (session_id,)).fetchone()
            if not session or session["state"] != "ACTIVE" or session["channel"] != channel:
                raise LearningError("feedback requires an active session of the same channel")
            if not connection.execute("SELECT 1 FROM decisions WHERE decision_id=?", (decision_id,)).fetchone():
                raise LearningError(f"unknown decision_id: {decision_id}")
            event = self._append_event(
                connection,
                "LEARNING_FEEDBACK_RECORDED",
                {"feedback_id": feedback_id, "session_id": session_id, "decision_id": decision_id, "channel": channel, "actor": actor, "record_hash": record_hash},
            )
            connection.execute(
                "INSERT INTO feedback(feedback_id,session_id,decision_id,channel,actor,record_json,record_hash,event_hash) VALUES(?,?,?,?,?,?,?,?)",
                (feedback_id, session_id, decision_id, channel, actor, record_json, record_hash, event["event_hash"]),
            )
        return {"feedback_id": feedback_id, "record_hash": record_hash, "event_hash": event["event_hash"]}

    def feedback_for_session(self, session_id: str) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT * FROM feedback WHERE session_id=? ORDER BY rowid", (session_id,)).fetchall()
        return [{**dict(row), "record": json.loads(row["record_json"])} for row in rows]

    def store_packet(self, session_id: str, packet: dict[str, Any]) -> dict[str, Any]:
        packet_id = str(uuid4())
        packet_json = _canonical(packet)
        packet_hash = _sha(packet_json)
        with self._connect() as connection:
            event = self._append_event(connection, "TRAINING_PACKET_COMPILED", {"packet_id": packet_id, "session_id": session_id, "packet_hash": packet_hash})
            connection.execute(
                "INSERT INTO training_packets(packet_id,session_id,packet_json,packet_hash,activation_state,event_hash) VALUES(?,?,?,?,?,?)",
                (packet_id, session_id, packet_json, packet_hash, "PENDING_REPLAY_AND_USER_APPROVAL", event["event_hash"]),
            )
        return {"packet_id": packet_id, "packet_hash": packet_hash, "activation_state": "PENDING_REPLAY_AND_USER_APPROVAL"}

    def verify(self) -> dict[str, Any]:
        defects: list[str] = []
        previous = "GENESIS"
        with self._connect() as connection:
            events = connection.execute("SELECT * FROM events ORDER BY sequence").fetchall()
            decisions = connection.execute("SELECT * FROM decisions ORDER BY decision_id").fetchall()
            feedback = connection.execute("SELECT * FROM feedback ORDER BY rowid").fetchall()
        for row in events:
            body = {
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "occurred_at": row["occurred_at"],
                "payload": json.loads(row["payload_json"]),
                "previous_hash": row["previous_hash"],
            }
            if row["previous_hash"] != previous or _sha(_canonical(body)) != row["event_hash"]:
                defects.append(f"EVENT_CHAIN:{row['sequence']}")
            previous = row["event_hash"]
        for row in decisions:
            if _sha(row["record_json"]) != row["record_hash"]:
                defects.append(f"DECISION_PROJECTION:{row['decision_id']}")
        for row in feedback:
            if _sha(row["record_json"]) != row["record_hash"]:
                defects.append(f"FEEDBACK_PROJECTION:{row['feedback_id']}")
        return {
            "gate": "PASS" if not defects else "FAIL",
            "defects": defects,
            "event_count": len(events),
            "decision_count": len(decisions),
            "feedback_count": len(feedback),
            "head_hash": previous,
        }
