from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .canonical import canonical_json, sha256_json


class KwanPromptsError(ValueError):
    pass


class KwanPromptsLedger:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    raw_sha256 TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    ingest_event_hash TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS adjudications (
                    adjudication_id TEXT PRIMARY KEY,
                    message_id TEXT NOT NULL,
                    record_json TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    FOREIGN KEY(message_id) REFERENCES messages(message_id)
                );
                """
            )

    def append_event(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        with self._connect() as connection:
            last = connection.execute("SELECT event_hash FROM events ORDER BY seq DESC LIMIT 1").fetchone()
            prev_hash = last["event_hash"] if last else "GENESIS"
            event_id = "evt-" + sha256_json([event_type, payload, prev_hash])[:32]
            body = {
                "event_id": event_id,
                "event_type": event_type,
                "payload": payload,
                "prev_hash": prev_hash,
            }
            event_hash = sha256_json(body)
            try:
                connection.execute(
                    "INSERT INTO events(event_id,event_type,payload_json,prev_hash,event_hash) VALUES(?,?,?,?,?)",
                    (event_id, event_type, canonical_json(payload), prev_hash, event_hash),
                )
            except sqlite3.IntegrityError as exc:
                existing = connection.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
                if existing and existing["event_hash"] == event_hash:
                    return {"event_id": event_id, "event_hash": event_hash, "idempotent": True}
                raise KwanPromptsError("event collision") from exc
            return {"event_id": event_id, "event_hash": event_hash, "idempotent": False}

    def put_message(self, record: dict[str, Any]) -> dict[str, Any]:
        message_id = str(record["message_id"])
        with self._connect() as connection:
            existing = connection.execute("SELECT * FROM messages WHERE message_id=?", (message_id,)).fetchone()
            if existing:
                prior = json.loads(existing["record_json"])
                if prior == record:
                    return {"message_id": message_id, "event_hash": existing["ingest_event_hash"], "idempotent": True}
                raise KwanPromptsError("message_id already exists with different content or provenance")
        event = self.append_event("MESSAGE_INGESTED", record)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO messages(message_id,raw_sha256,record_json,ingest_event_hash) VALUES(?,?,?,?)",
                (message_id, record["raw_sha256"], canonical_json(record), event["event_hash"]),
            )
        return {"message_id": message_id, "event_hash": event["event_hash"], "idempotent": False}

    def get_message(self, message_id: str) -> dict[str, Any]:
        with self._connect() as connection:
            row = connection.execute("SELECT record_json FROM messages WHERE message_id=?", (message_id,)).fetchone()
        if not row:
            raise KwanPromptsError("unknown message_id")
        return json.loads(row["record_json"])

    def list_messages(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute("SELECT record_json FROM messages ORDER BY rowid").fetchall()
        return [json.loads(row["record_json"]) for row in rows]

    def add_adjudication(self, record: dict[str, Any]) -> dict[str, Any]:
        self.get_message(record["message_id"])
        event = self.append_event("MESSAGE_ADJUDICATED", record)
        with self._connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO adjudications(adjudication_id,message_id,record_json,event_hash) VALUES(?,?,?,?)",
                    (record["adjudication_id"], record["message_id"], canonical_json(record), event["event_hash"]),
                )
            except sqlite3.IntegrityError as exc:
                row = connection.execute(
                    "SELECT record_json,event_hash FROM adjudications WHERE adjudication_id=?",
                    (record["adjudication_id"],),
                ).fetchone()
                if row and json.loads(row["record_json"]) == record:
                    return {"event_hash": row["event_hash"], "idempotent": True}
                raise KwanPromptsError("adjudication_id collision") from exc
        return {"event_hash": event["event_hash"], "idempotent": False}

    def verify(self) -> dict[str, Any]:
        with self._connect() as connection:
            events = connection.execute("SELECT * FROM events ORDER BY seq").fetchall()
            messages = connection.execute("SELECT * FROM messages ORDER BY rowid").fetchall()
            adjudications = connection.execute("SELECT * FROM adjudications ORDER BY rowid").fetchall()
        previous = "GENESIS"
        defects: list[str] = []
        for row in events:
            payload = json.loads(row["payload_json"])
            body = {
                "event_id": row["event_id"],
                "event_type": row["event_type"],
                "payload": payload,
                "prev_hash": row["prev_hash"],
            }
            if row["prev_hash"] != previous:
                defects.append(f"PREV_HASH:{row['seq']}")
            if sha256_json(body) != row["event_hash"]:
                defects.append(f"EVENT_HASH:{row['seq']}")
            previous = row["event_hash"]
        event_hashes = {row["event_hash"] for row in events}
        for row in messages:
            record = json.loads(row["record_json"])
            if record.get("raw_sha256") != row["raw_sha256"]:
                defects.append(f"MESSAGE_PROJECTION_HASH:{row['message_id']}")
            if row["ingest_event_hash"] not in event_hashes:
                defects.append(f"MESSAGE_EVENT_MISSING:{row['message_id']}")
        for row in adjudications:
            if row["event_hash"] not in event_hashes:
                defects.append(f"ADJUDICATION_EVENT_MISSING:{row['adjudication_id']}")
        return {
            "schema": "kwanprompts.ledger-verification.v0.1.0",
            "gate": "PASS" if not defects else "FAIL",
            "event_count": len(events),
            "message_count": len(messages),
            "adjudication_count": len(adjudications),
            "head_hash": previous,
            "defects": defects,
        }

