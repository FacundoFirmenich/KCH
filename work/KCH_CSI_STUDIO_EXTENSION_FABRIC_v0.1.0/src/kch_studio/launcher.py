from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import closing
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .contracts import canonical_json, sha256_json, sqlite_connection
from .proactive import ProgrammedDispatcher, ProgrammedPolicy

DDL = """
CREATE TABLE IF NOT EXISTS launcher_events (
    event_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    event_json TEXT NOT NULL,
    event_hash TEXT NOT NULL,
    state TEXT NOT NULL,
    result_json TEXT,
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS launcher_runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    stopped_at TEXT,
    state TEXT NOT NULL,
    policy_revision INTEGER NOT NULL,
    capability_manifest_hash TEXT NOT NULL
);
"""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class Capability:
    name: str
    purpose: str
    mode: str
    event_types: tuple[str, ...]
    mutating: bool
    external_side_effect: bool

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["event_types"] = list(self.event_types)
        return value


class ProactiveLauncher:
    """Persistent background event launcher; enabled by default in KCH runtimes."""

    def __init__(
        self,
        root: str | Path,
        policy: ProgrammedPolicy,
        handlers: dict[str, Callable[[dict[str, Any]], Any]],
        capabilities: list[Capability],
    ) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "launcher.sqlite3"
        self.policy = policy
        self.handlers = dict(handlers)
        self.capabilities = {item.name: item for item in capabilities}
        missing = set(self.handlers) - set(self.capabilities)
        if missing:
            raise ValueError(f"capability descriptors missing for handlers: {sorted(missing)}")
        self.dispatcher = ProgrammedDispatcher(policy, handlers)
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.run_id: str | None = None
        with self.connect() as connection:
            connection.executescript(DDL)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite_connection(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def manifest(self) -> dict[str, Any]:
        items = [
            item.to_dict()
            for item in sorted(self.capabilities.values(), key=lambda value: value.name)
        ]
        rules = self.policy.state()["rules"]
        rule_tools = {
            rule["then"].get("tool")
            for rule in rules
            if rule.get("enabled") and isinstance(rule.get("then", {}).get("tool"), str)
        }
        dynamic_launcher = any(
            isinstance(rule.get("then", {}).get("tool"), dict)
            for rule in rules
            if rule.get("enabled")
        )
        coverage = []
        for item in items:
            if item["name"] in rule_tools:
                state = "DEFAULT_DIRECT_RULE"
            elif dynamic_launcher:
                state = "USER_PROGRAMMABLE_DYNAMIC_ROUTE"
            else:
                state = "UNBOUND"
            coverage.append({"capability": item["name"], "coverage": state})
        return {
            "schema": "kch.proactive-capability-manifest.v0.1.0",
            "capabilities": items,
            "capability_count": len(items),
            "coverage": coverage,
            "unbound": [item["capability"] for item in coverage if item["coverage"] == "UNBOUND"],
            "background_launcher_enabled_by_default": True,
            "host_event_bridge_required": True,
            "manifest_hash": sha256_json(items),
        }

    def start(self) -> dict[str, Any]:
        if self._thread and self._thread.is_alive():
            return self.status()
        self._stop.clear()
        manifest = self.manifest()
        if manifest["unbound"]:
            raise ValueError(
                f"proactive capability coverage has blind spots: {manifest['unbound']}"
            )
        self.run_id = f"RUN-{uuid.uuid4()}"
        state = self.policy.state()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO launcher_runs VALUES(?,?,?,?,?,?)",
                (
                    self.run_id,
                    utc_now(),
                    None,
                    "RUNNING",
                    int(state["revision"]),
                    manifest["manifest_hash"],
                ),
            )
            connection.commit()
        self._thread = threading.Thread(
            target=self._loop, name="kch-proactive-launcher", daemon=True
        )
        self._thread.start()
        return {
            **self.status(),
            "announcement": self.policy.session_announcement()
            if state["announce_on_session_start"]
            else None,
            "announcement_suppressed_by_user": not state["announce_on_session_start"],
        }

    def stop(self, timeout: float = 5.0) -> dict[str, Any]:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout)
        if self.run_id:
            with self.connect() as connection:
                connection.execute(
                    "UPDATE launcher_runs SET stopped_at=?,state=? WHERE run_id=?",
                    (utc_now(), "STOPPED", self.run_id),
                )
                connection.commit()
        return self.status()

    def publish(self, event: dict[str, Any]) -> dict[str, Any]:
        if not str(event.get("type", "")).strip():
            raise ValueError("launcher event requires a type")
        event_id = f"EVENT-{uuid.uuid4()}"
        envelope = {"event_id": event_id, **event}
        timestamp = utc_now()
        with self.connect() as connection:
            connection.execute(
                "INSERT INTO launcher_events VALUES(?,?,?,?,?,?,?)",
                (
                    event_id,
                    timestamp,
                    canonical_json(envelope),
                    sha256_json(envelope),
                    "QUEUED",
                    None,
                    None,
                ),
            )
            connection.commit()
        self._wake.set()
        return {"event_id": event_id, "state": "QUEUED", "event_hash": sha256_json(envelope)}

    def _claim(self) -> dict[str, Any] | None:
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM launcher_events WHERE state='QUEUED' ORDER BY timestamp,event_id LIMIT 1"
            ).fetchone()
            if row is None:
                connection.rollback()
                return None
            connection.execute(
                "UPDATE launcher_events SET state='RUNNING' WHERE event_id=?", (row["event_id"],)
            )
            connection.commit()
            return {"event_id": str(row["event_id"]), "event": json.loads(str(row["event_json"]))}

    def run_once(self) -> dict[str, Any] | None:
        claimed = self._claim()
        if claimed is None:
            return None
        results = self.dispatcher.dispatch_all(claimed["event"])
        state = (
            "COMPLETED"
            if not any(item["state"] == "EXECUTION_FAILED_PRESERVED" for item in results)
            else "COMPLETED_WITH_FAILURES"
        )
        with self.connect() as connection:
            connection.execute(
                "UPDATE launcher_events SET state=?,result_json=?,completed_at=? WHERE event_id=?",
                (state, canonical_json(results), utc_now(), claimed["event_id"]),
            )
            connection.commit()
        return {"event_id": claimed["event_id"], "state": state, "results": results}

    def _loop(self) -> None:
        while not self._stop.is_set():
            processed = self.run_once()
            if processed is None:
                self._wake.wait(0.5)
                self._wake.clear()

    def wait(self, event_id: str, timeout: float = 10.0) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with closing(self.connect()) as connection:
                row = connection.execute(
                    "SELECT * FROM launcher_events WHERE event_id=?", (event_id,)
                ).fetchone()
                if row is None:
                    raise KeyError(event_id)
                if row["state"] not in {"QUEUED", "RUNNING"}:
                    return {
                        "event_id": event_id,
                        "state": str(row["state"]),
                        "results": json.loads(str(row["result_json"])),
                    }
            time.sleep(0.02)
        raise TimeoutError(event_id)

    def status(self) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            counts = {
                str(row["state"]): int(row["n"])
                for row in connection.execute(
                    "SELECT state,COUNT(*) AS n FROM launcher_events GROUP BY state"
                )
            }
        return {
            "schema": "kch.proactive-launcher-status.v0.1.0",
            "run_id": self.run_id,
            "running": bool(self._thread and self._thread.is_alive()),
            "enabled_by_default": True,
            "event_counts": counts,
            "coverage": self.manifest(),
        }
