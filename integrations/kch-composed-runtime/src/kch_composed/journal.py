"""Durable scoped sessions and conservative effect receipts.

A persisted STARTED call means the process may have crossed an external effect
boundary. Its outcome cannot be inferred from a crash, so it is never replayed
automatically. SQLite commits the call projection and its journal event together.
Scope is supplied by the trusted host; this module is not an identity provider.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import threading
from typing import Any

from .memory import _canonical_json


class JournalIntegrityError(RuntimeError):
    pass


class UncertainEffectError(RuntimeError):
    pass


class SessionConfigurationError(ValueError):
    pass


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class SessionJournal:
    def __init__(self, path: str | Path, principal: str, workspace: str,
                 session: str, configuration: dict) -> None:
        if any(not isinstance(x, str) or not x.strip() for x in (principal, workspace, session)):
            raise ValueError("principal, workspace and session must be explicit")
        if not isinstance(configuration, dict):
            raise TypeError("configuration must be a dict")
        self.scope = {"principal": principal, "workspace": workspace, "session": session}
        self._key = _hash(self.scope)
        # Serialize now to detach caller-owned objects and reject nonfinite data.
        self.configuration = json.loads(_canonical_json(configuration))
        self._configuration_hash = _hash({"scope": self.scope, "configuration": self.configuration})
        path = str(path)
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._db = sqlite3.connect(path, timeout=30, isolation_level=None, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA busy_timeout=30000")
        self._db.executescript("""
        CREATE TABLE IF NOT EXISTS session_configuration (
          scope_key TEXT PRIMARY KEY, scope TEXT NOT NULL,
          configuration TEXT NOT NULL, sha256 TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS session_events (
          scope_key TEXT NOT NULL REFERENCES session_configuration(scope_key),
          seq INTEGER NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL,
          occurred_at TEXT NOT NULL, previous_sha256 TEXT NOT NULL, sha256 TEXT NOT NULL,
          PRIMARY KEY(scope_key,seq)
        );
        CREATE TABLE IF NOT EXISTS session_calls (
          scope_key TEXT NOT NULL REFERENCES session_configuration(scope_key),
          call_id TEXT NOT NULL, name TEXT NOT NULL, args TEXT NOT NULL,
          request_sha256 TEXT NOT NULL, status TEXT NOT NULL, result TEXT,
          started_seq INTEGER NOT NULL, finished_seq INTEGER,
          PRIMARY KEY(scope_key,call_id)
        );
        CREATE TABLE IF NOT EXISTS session_heads (
          scope_key TEXT PRIMARY KEY REFERENCES session_configuration(scope_key),
          seq INTEGER NOT NULL, sha256 TEXT NOT NULL
        );
        """)
        try:
            with self._tx(write=True):
                row = self._db.execute("SELECT * FROM session_configuration WHERE scope_key=?",
                                       (self._key,)).fetchone()
                if row is None:
                    self._db.execute("INSERT INTO session_configuration VALUES (?,?,?,?)",
                        (self._key, _canonical_json(self.scope), _canonical_json(self.configuration),
                         self._configuration_hash))
                    self._db.execute("INSERT INTO session_heads VALUES (?,?,?)",
                                     (self._key, 0, self._configuration_hash))
                else:
                    # Verify stored integrity before declaring a legitimate mismatch.
                    stored_scope = json.loads(row["scope"])
                    stored_configuration = json.loads(row["configuration"])
                    if (_hash(stored_scope) != self._key or _hash({"scope": stored_scope,
                            "configuration": stored_configuration}) != row["sha256"]):
                        raise JournalIntegrityError("session configuration integrity failed")
                    if row["sha256"] != self._configuration_hash:
                        raise SessionConfigurationError("existing session configuration is immutable; use a successor session")
                self._verify()
        except BaseException:
            self._db.close()
            raise

    @contextmanager
    def _tx(self, *, write: bool = False):
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield
                self._db.execute("COMMIT")
            except BaseException:
                self._db.execute("ROLLBACK")
                raise

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def __enter__(self) -> SessionJournal:
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _event(self, row: sqlite3.Row) -> dict:
        return {"seq": row["seq"], "kind": row["kind"], "payload": json.loads(row["payload"]),
                "occurred_at": row["occurred_at"], "previous_sha256": row["previous_sha256"],
                "sha256": row["sha256"]}

    def _call(self, row: sqlite3.Row) -> dict:
        return {"call_id": row["call_id"], "name": row["name"], "args": json.loads(row["args"]),
                "request_sha256": row["request_sha256"], "status": row["status"],
                "result": None if row["result"] is None else json.loads(row["result"]),
                "started_seq": row["started_seq"], "finished_seq": row["finished_seq"]}

    def _verify(self) -> list[dict]:
        try:
            cfg = self._db.execute("SELECT * FROM session_configuration WHERE scope_key=?",
                                   (self._key,)).fetchone()
            if (cfg is None or cfg["sha256"] != self._configuration_hash
                    or json.loads(cfg["scope"]) != self.scope
                    or json.loads(cfg["configuration"]) != self.configuration
                    or _hash({"scope": json.loads(cfg["scope"]),
                              "configuration": json.loads(cfg["configuration"])}) != cfg["sha256"]):
                raise JournalIntegrityError("session configuration integrity failed")
            events = [self._event(row) for row in self._db.execute(
                "SELECT * FROM session_events WHERE scope_key=? ORDER BY seq", (self._key,))]
            previous = self._configuration_hash
            calls: dict[str, dict] = {}
            for seq, event in enumerate(events, 1):
                core = {k: v for k, v in event.items() if k != "sha256"}
                if (event["seq"] != seq or event["previous_sha256"] != previous
                        or _hash({"scope": self.scope, **core}) != event["sha256"]):
                    raise JournalIntegrityError(f"event chain integrity failed at sequence {seq}")
                previous = event["sha256"]
                payload = event["payload"]
                if event["kind"] == "call.started":
                    call_id = payload["call_id"]
                    request = {"call_id": call_id, "name": payload["name"], "args": payload["args"]}
                    if call_id in calls or payload["request_sha256"] != _hash(request):
                        raise JournalIntegrityError("call start is duplicated or mismatched")
                    calls[call_id] = {**request, "request_sha256": payload["request_sha256"],
                                      "status": "STARTED", "result": None,
                                      "started_seq": seq, "finished_seq": None}
                elif event["kind"] == "call.finished":
                    call_id = payload["call_id"]
                    if (call_id not in calls or calls[call_id]["status"] != "STARTED"
                            or payload["status"] not in ("DONE", "FAILED")
                            or payload["request_sha256"] != calls[call_id]["request_sha256"]):
                        raise JournalIntegrityError("invalid call completion transition")
                    calls[call_id].update(status=payload["status"], result=payload["result"], finished_seq=seq)
            stored_calls = {row["call_id"]: self._call(row) for row in self._db.execute(
                "SELECT * FROM session_calls WHERE scope_key=?", (self._key,))}
            if stored_calls != calls:
                raise JournalIntegrityError("call projection differs from journal receipts")
            head = self._db.execute("SELECT seq,sha256 FROM session_heads WHERE scope_key=?",
                                    (self._key,)).fetchone()
            if head is None or head["seq"] != len(events) or head["sha256"] != previous:
                raise JournalIntegrityError("journal head differs; history may be truncated")
            return events
        except (KeyError, TypeError, ValueError) as exc:
            raise JournalIntegrityError("malformed journal data") from exc

    def verify(self) -> bool:
        with self._tx():
            self._verify()
            return True

    def events(self) -> list[dict]:
        with self._tx():
            return self._verify()

    def messages(self) -> list[dict]:
        return [event["payload"] for event in self.events() if event["kind"] == "message"]

    def _append(self, kind: str, payload: Any) -> dict:
        last = self._db.execute("SELECT seq,sha256 FROM session_events WHERE scope_key=? "
                                "ORDER BY seq DESC LIMIT 1", (self._key,)).fetchone()
        event = {"seq": 1 if last is None else last["seq"] + 1, "kind": kind,
                 "payload": json.loads(_canonical_json(payload)),
                 "occurred_at": datetime.now(timezone.utc).isoformat(),
                 "previous_sha256": self._configuration_hash if last is None else last["sha256"]}
        event["sha256"] = _hash({"scope": self.scope, **event})
        self._db.execute("INSERT INTO session_events VALUES (?,?,?,?,?,?,?)",
                         (self._key, event["seq"], event["kind"], _canonical_json(event["payload"]),
                          event["occurred_at"], event["previous_sha256"], event["sha256"]))
        self._db.execute("UPDATE session_heads SET seq=?,sha256=? WHERE scope_key=?",
                         (event["seq"], event["sha256"], self._key))
        return event

    def append(self, kind: str, payload: Any) -> dict:
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError("event kind must be explicit")
        if kind in ("call.started", "call.finished"):
            raise ValueError("call events require call_begin/call_finish")
        with self._tx(write=True):
            self._verify()
            return self._append(kind, payload)

    def call_begin(self, call_id: str, name: str, args: dict) -> dict:
        if any(not isinstance(x, str) or not x.strip() for x in (call_id, name)):
            raise ValueError("call_id and name must be explicit")
        if not isinstance(args, dict):
            raise TypeError("call args must be a dict")
        args = json.loads(_canonical_json(args))
        request = {"call_id": call_id, "name": name, "args": args}
        request_sha256 = _hash(request)
        with self._tx(write=True):
            self._verify()
            row = self._db.execute("SELECT * FROM session_calls WHERE scope_key=? AND call_id=?",
                                   (self._key, call_id)).fetchone()
            if row is not None:
                call = self._call(row)
                if call["request_sha256"] != request_sha256:
                    raise ValueError("call_id already belongs to a different request")
                if call["status"] == "STARTED":
                    raise UncertainEffectError(f"call {call_id} has no durable completion; automatic replay is forbidden")
                return call
            event = self._append("call.started", {**request, "request_sha256": request_sha256})
            self._db.execute("INSERT INTO session_calls VALUES (?,?,?,?,?,?,?,?,?)",
                             (self._key, call_id, name, _canonical_json(args), request_sha256,
                              "STARTED", None, event["seq"], None))
            return {**request, "request_sha256": request_sha256, "status": "STARTED", "result": None,
                    "started_seq": event["seq"], "finished_seq": None}

    def call_finish(self, call_id: str, result: Any, status: str = "DONE") -> dict:
        if status not in ("DONE", "FAILED"):
            raise ValueError("completion status must be DONE or FAILED")
        result = json.loads(_canonical_json(result))
        with self._tx(write=True):
            self._verify()
            row = self._db.execute("SELECT * FROM session_calls WHERE scope_key=? AND call_id=?",
                                   (self._key, call_id)).fetchone()
            if row is None:
                raise KeyError("call unavailable in this scope")
            call = self._call(row)
            if call["status"] != "STARTED":
                if call["status"] == status and _canonical_json(call["result"]) == _canonical_json(result):
                    return call
                raise ValueError("terminal call receipt is immutable")
            event = self._append("call.finished", {"call_id": call_id,
                                 "request_sha256": call["request_sha256"], "status": status, "result": result})
            self._db.execute("UPDATE session_calls SET status=?,result=?,finished_seq=? "
                             "WHERE scope_key=? AND call_id=?",
                             (status, _canonical_json(result), event["seq"], self._key, call_id))
            return {**call, "status": status, "result": result, "finished_seq": event["seq"]}

    def calls(self) -> list[dict]:
        with self._tx():
            self._verify()
            return [self._call(row) for row in self._db.execute(
                "SELECT * FROM session_calls WHERE scope_key=? ORDER BY started_seq", (self._key,))]
