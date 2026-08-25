from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import (
    TRANSITIONS,
    ArtifactSpec,
    LifecycleState,
    canonical_json,
    sha256_json,
    sqlite_connection,
)

DDL = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    spec_json TEXT NOT NULL,
    state TEXT NOT NULL,
    artifact_root TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    head_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    seq INTEGER NOT NULL,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    previous_hash TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    UNIQUE(session_id, seq)
);
CREATE TABLE IF NOT EXISTS files (
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    path TEXT NOT NULL,
    bytes INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    PRIMARY KEY(session_id, path)
);
CREATE TABLE IF NOT EXISTS seals (
    session_id TEXT PRIMARY KEY REFERENCES sessions(session_id),
    seal_json TEXT NOT NULL,
    seal_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class EventStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(DDL)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite_connection(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @staticmethod
    def _event_hash(
        session_id: str,
        seq: int,
        timestamp: str,
        action: str,
        payload: dict[str, Any],
        previous_hash: str,
    ) -> str:
        return sha256_json(
            {
                "session_id": session_id,
                "seq": seq,
                "timestamp": timestamp,
                "action": action,
                "payload": payload,
                "previous_hash": previous_hash,
            }
        )

    def _append(
        self, connection: sqlite3.Connection, session_id: str, action: str, payload: dict[str, Any]
    ) -> str:
        row = connection.execute(
            "SELECT head_hash FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if row is None:
            raise KeyError(session_id)
        previous = str(row["head_hash"])
        seq = int(
            connection.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE session_id=?", (session_id,)
            ).fetchone()[0]
        )
        timestamp = now()
        event_hash = self._event_hash(session_id, seq, timestamp, action, payload, previous)
        connection.execute(
            "INSERT INTO events(session_id,seq,timestamp,action,payload_json,previous_hash,event_hash) VALUES(?,?,?,?,?,?,?)",
            (session_id, seq, timestamp, action, canonical_json(payload), previous, event_hash),
        )
        connection.execute(
            "UPDATE sessions SET head_hash=?,updated_at=? WHERE session_id=?",
            (event_hash, timestamp, session_id),
        )
        return event_hash

    def create(self, spec: ArtifactSpec) -> dict[str, Any]:
        session_id = f"CSI-{uuid.uuid4()}"
        timestamp = now()
        genesis = sha256_json(
            {"session_id": session_id, "spec": spec.to_dict(), "created_at": timestamp}
        )
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO sessions(session_id,spec_json,state,created_at,updated_at,head_hash) VALUES(?,?,?,?,?,?)",
                (
                    session_id,
                    canonical_json(spec.to_dict()),
                    LifecycleState.DRAFT.value,
                    timestamp,
                    timestamp,
                    genesis,
                ),
            )
            self._append(
                connection,
                session_id,
                "SESSION_CREATED",
                {"spec_hash": sha256_json(spec.to_dict())},
            )
            self._transition(
                connection, session_id, LifecycleState.SPECIFIED, {"validated_spec": True}
            )
            connection.commit()
        return self.get(session_id)

    def _transition(
        self,
        connection: sqlite3.Connection,
        session_id: str,
        target: LifecycleState,
        payload: dict[str, Any],
    ) -> None:
        row = connection.execute(
            "SELECT state FROM sessions WHERE session_id=?", (session_id,)
        ).fetchone()
        if row is None:
            raise KeyError(session_id)
        current = LifecycleState(str(row["state"]))
        if target not in TRANSITIONS[current]:
            raise ValueError(f"invalid lifecycle transition {current.value} -> {target.value}")
        connection.execute(
            "UPDATE sessions SET state=? WHERE session_id=?", (target.value, session_id)
        )
        self._append(
            connection,
            session_id,
            "STATE_TRANSITION",
            {"from": current.value, "to": target.value, **payload},
        )

    def transition(
        self, session_id: str, target: LifecycleState, payload: dict[str, Any]
    ) -> dict[str, Any]:
        with self.connect() as connection:
            self._transition(connection, session_id, target, payload)
            connection.commit()
        return self.get(session_id)

    def record_generation(
        self, session_id: str, artifact_root: Path, manifest: list[dict[str, Any]]
    ) -> dict[str, Any]:
        if not manifest:
            raise ValueError("generated artifact has no files")
        with self.connect() as connection:
            connection.execute("DELETE FROM files WHERE session_id=?", (session_id,))
            for item in manifest:
                connection.execute(
                    "INSERT INTO files(session_id,path,bytes,sha256) VALUES(?,?,?,?)",
                    (session_id, item["path"], item["bytes"], item["sha256"]),
                )
            connection.execute(
                "UPDATE sessions SET artifact_root=? WHERE session_id=?",
                (str(artifact_root.resolve()), session_id),
            )
            self._transition(
                connection,
                session_id,
                LifecycleState.GENERATED_STAGED,
                {"file_count": len(manifest), "manifest_hash": sha256_json(manifest)},
            )
            connection.commit()
        return self.get(session_id)

    def record_validation(self, session_id: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
        if not checks or not all(bool(check["passed"]) for check in checks):
            raise ValueError("cannot validate an artifact with missing or failed checks")
        return self.transition(
            session_id,
            LifecycleState.VALIDATED,
            {"check_count": len(checks), "checks_hash": sha256_json(checks)},
        )

    def record_seal(self, session_id: str, seal: dict[str, Any]) -> dict[str, Any]:
        seal_hash = sha256_json(seal)
        with self.connect() as connection:
            self._transition(
                connection,
                session_id,
                LifecycleState.SEALED_CANDIDATE,
                {"seal_hash": seal_hash, "installation_authorized": False},
            )
            connection.execute(
                "INSERT INTO seals(session_id,seal_json,seal_hash,created_at) VALUES(?,?,?,?)",
                (session_id, canonical_json(seal), seal_hash, now()),
            )
            connection.commit()
        return self.get(session_id)

    def get(self, session_id: str) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            if row is None:
                raise KeyError(session_id)
            files = [
                dict(item)
                for item in connection.execute(
                    "SELECT path,bytes,sha256 FROM files WHERE session_id=? ORDER BY path",
                    (session_id,),
                )
            ]
            seal = connection.execute(
                "SELECT seal_json,seal_hash,created_at FROM seals WHERE session_id=?", (session_id,)
            ).fetchone()
            return {
                "session_id": session_id,
                "spec": json.loads(str(row["spec_json"])),
                "state": str(row["state"]),
                "artifact_root": row["artifact_root"],
                "created_at": str(row["created_at"]),
                "updated_at": str(row["updated_at"]),
                "head_hash": str(row["head_hash"]),
                "files": files,
                "seal": None
                if seal is None
                else {
                    "body": json.loads(str(seal["seal_json"])),
                    "hash": seal["seal_hash"],
                    "created_at": seal["created_at"],
                },
            }

    def list_sessions(self) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            rows = connection.execute(
                "SELECT session_id,state,artifact_root,created_at,updated_at,head_hash FROM sessions ORDER BY created_at DESC"
            ).fetchall()
            return [dict(row) for row in rows]

    def verify_chain(self, session_id: str) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            session = connection.execute(
                "SELECT spec_json,created_at,head_hash FROM sessions WHERE session_id=?",
                (session_id,),
            ).fetchone()
            if session is None:
                raise KeyError(session_id)
            spec = json.loads(str(session["spec_json"]))
            previous = sha256_json(
                {"session_id": session_id, "spec": spec, "created_at": str(session["created_at"])}
            )
            events = connection.execute(
                "SELECT * FROM events WHERE session_id=? ORDER BY seq", (session_id,)
            ).fetchall()
            errors: list[str] = []
            for row in events:
                payload = json.loads(str(row["payload_json"]))
                expected = self._event_hash(
                    session_id,
                    int(row["seq"]),
                    str(row["timestamp"]),
                    str(row["action"]),
                    payload,
                    previous,
                )
                if str(row["previous_hash"]) != previous:
                    errors.append(f"event {row['seq']} previous hash mismatch")
                if str(row["event_hash"]) != expected:
                    errors.append(f"event {row['seq']} hash mismatch")
                previous = expected
            if previous != str(session["head_hash"]):
                errors.append("session head hash mismatch")
            return {
                "passed": not errors,
                "event_count": len(events),
                "head_hash": previous,
                "errors": errors,
            }
