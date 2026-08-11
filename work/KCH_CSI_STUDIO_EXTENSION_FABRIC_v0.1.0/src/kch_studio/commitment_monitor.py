from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class CommitmentMonitor:
    """Background reconciliation of every promised process/log/artifact watch."""

    ERRORS = ("traceback", "gatefailure", "fatal", "uncaught exception")

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "monitor.sqlite3"
        self.callback: Callable[[dict[str, Any]], Any] | None = None
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        with self.connect() as con:
            con.execute("CREATE TABLE IF NOT EXISTS commitments(id TEXT PRIMARY KEY,label TEXT,pid INTEGER,logs TEXT,artifacts TEXT,poll INTEGER,status TEXT,last_check REAL,alerted INTEGER,observation TEXT)")

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db, timeout=20)
        con.row_factory = sqlite3.Row
        return con

    def set_alert_callback(self, callback: Callable[[dict[str, Any]], Any]) -> None:
        self.callback = callback

    def register(self, *, label: str, pid: int, logs: list[str], artifacts: list[str], poll_seconds: int = 10) -> dict[str, Any]:
        if not label or pid <= 0 or poll_seconds < 1:
            raise ValueError("label, positive pid and poll_seconds required")
        identifier = f"MONITOR-{uuid.uuid4()}"
        with self.connect() as con:
            con.execute("INSERT INTO commitments VALUES(?,?,?,?,?,?,?,?,?,?)", (identifier,label,pid,json.dumps(logs),json.dumps(artifacts),poll_seconds,"MONITORING",0,0,"{}"))
        return {"commitment_id":identifier,"initial_observation":self.check(identifier),"promised_monitoring_active":True}

    @staticmethod
    def _tail(path: Path) -> str:
        if not path.is_file():
            return ""
        with path.open("rb") as source:
            source.seek(max(0, path.stat().st_size - 65536))
            return source.read().decode("utf-8", errors="replace")

    def check(self, identifier: str) -> dict[str, Any]:
        with self.connect() as con:
            row = con.execute("SELECT * FROM commitments WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise KeyError(identifier)
        logs = [Path(x) for x in json.loads(row["logs"])]
        artifacts = [Path(x) for x in json.loads(row["artifacts"])]
        running = process_exists(int(row["pid"]))
        markers = sorted({m for p in logs for m in self.ERRORS if m in self._tail(p).lower()})
        artifact_state = {str(p):p.is_file() for p in artifacts}
        status = "MONITORING" if running else "FAILED_ALERT_REQUIRED" if markers else "COMPLETED_ALERT_REQUIRED" if artifacts and all(artifact_state.values()) else "TERMINATED_MISSING_ARTIFACT_ALERT_REQUIRED"
        emit = status != "MONITORING" and not bool(row["alerted"])
        observation = {"commitment_id":identifier,"checked_at":now(),"process_running":running,"status":status,"error_markers":markers,"artifacts":artifact_state,"alert_emitted_now":emit}
        with self.connect() as con:
            con.execute("UPDATE commitments SET status=?,last_check=?,alerted=?,observation=? WHERE id=?", (status,time.time(),int(emit or row["alerted"]),json.dumps(observation),identifier))
        if emit and self.callback:
            self.callback({"type":"commitment.monitor.alert","authority":"KCH_SYSTEM","observation":observation})
        return observation

    def check_all(self) -> list[dict[str, Any]]:
        with self.connect() as con:
            ids = [str(x[0]) for x in con.execute("SELECT id FROM commitments WHERE status='MONITORING'")]
        return [self.check(x) for x in ids]

    def start(self) -> dict[str, Any]:
        if self.thread and self.thread.is_alive():
            return {"running":True,"already_running":True}
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._loop, daemon=True, name="kch-commitment-monitor")
        self.thread.start()
        return {"running":True,"already_running":False}

    def _loop(self) -> None:
        while not self.stop_event.wait(1):
            with self.connect() as con:
                due = [str(x[0]) for x in con.execute("SELECT id FROM commitments WHERE status='MONITORING' AND ?-last_check>=poll", (time.time(),))]
            for identifier in due:
                self.check(identifier)

    def stop(self, timeout: float = 5) -> dict[str, Any]:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout)
        return {"running":bool(self.thread and self.thread.is_alive())}

    def status(self) -> dict[str, Any]:
        with self.connect() as con:
            counts = {str(x[0]):int(x[1]) for x in con.execute("SELECT status,COUNT(*) FROM commitments GROUP BY status")}
        return {"schema":"kch.commitment-monitor-status.v0.1.0","background_running":bool(self.thread and self.thread.is_alive()),"counts":counts,"claim_ceiling":"LOCAL_PROCESS_LOG_ARTIFACT_MONITORING_ONLY"}
