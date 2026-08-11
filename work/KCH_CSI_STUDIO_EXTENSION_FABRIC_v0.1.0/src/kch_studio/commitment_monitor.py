from __future__ import annotations

import ctypes
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def canonical_sha256(payload: dict[str, Any]) -> str:
    body = dict(payload)
    body.pop("sha256", None)
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_metadata(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"exists": False, "bytes": None, "sha256": None}
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return {"exists": True, "bytes": size, "sha256": digest.hexdigest()}


def process_identity(pid: int) -> str | None:
    """Return an OS creation token so PID reuse cannot satisfy a commitment."""
    if pid <= 0:
        return None
    if os.name == "nt":
        process_query_limited_information = 0x1000

        class FileTime(ctypes.Structure):
            _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]

        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information,
            False,
            pid,
        )
        if not handle:
            return None
        try:
            created = FileTime()
            exited = FileTime()
            kernel = FileTime()
            user = FileTime()
            ok = ctypes.windll.kernel32.GetProcessTimes(
                handle,
                ctypes.byref(created),
                ctypes.byref(exited),
                ctypes.byref(kernel),
                ctypes.byref(user),
            )
            if not ok:
                return None
            ticks = (int(created.high) << 32) | int(created.low)
            return f"windows-filetime:{ticks}"
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    proc_stat = Path(f"/proc/{pid}/stat")
    if proc_stat.is_file():
        try:
            text = proc_stat.read_text(encoding="utf-8")
            fields_after_comm = text[text.rfind(")") + 2 :].split()
            return f"procfs-starttime:{fields_after_comm[19]}"
        except (IndexError, OSError, UnicodeError):
            return None
    try:
        os.kill(pid, 0)
    except OSError:
        return None
    return None


def process_exists(pid: int, expected_identity: str | None = None) -> bool:
    if pid <= 0:
        return False
    observed = process_identity(pid)
    if observed is not None:
        return expected_identity in (None, "", observed)
    if expected_identity:
        return False
    if os.name == "nt":
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
    """Durable process/log/artifact supervision with terminal evidence custody."""

    SCHEMA = "kch.commitment-monitor.v0.2.0"
    ERRORS = ("traceback", "gatefailure", "fatal", "uncaught exception")
    TERMINAL_STATUSES = {
        "COMPLETED_PASS",
        "COMPLETED_FAIL",
        "MONITOR_WORKER_FAILED",
        "TERMINAL_EVIDENCE_INVALID_ALERT_REQUIRED",
        "FAILED_MARKER_NO_TERMINAL_RECEIPT",
        "TERMINATED_ARTIFACTS_WITHOUT_EXIT_CODE",
        "TERMINATED_MISSING_ARTIFACT_ALERT_REQUIRED",
        "TERMINATED_WITHOUT_EXIT_EVIDENCE",
    }
    SENSITIVE_ENV_MARKERS = ("TOKEN", "PASSWORD", "SECRET", "CREDENTIAL", "PRIVATE_KEY")
    STARTUP_RECEIPT_TIMEOUT_SECONDS = 5.0

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "monitor.sqlite3"
        self.callback: Callable[[dict[str, Any]], Any] | None = None
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        with self.connect() as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS commitments("
                "id TEXT PRIMARY KEY,label TEXT,pid INTEGER,logs TEXT,artifacts TEXT,"
                "poll INTEGER,status TEXT,last_check REAL,alerted INTEGER,observation TEXT)"
            )
            columns = {str(row[1]) for row in con.execute("PRAGMA table_info(commitments)")}
            migrations = {
                "process_token": "TEXT NOT NULL DEFAULT ''",
                "terminal_receipt": "TEXT NOT NULL DEFAULT ''",
                "expected_exit_codes": "TEXT NOT NULL DEFAULT '[0]'",
                "mode": "TEXT NOT NULL DEFAULT 'EXTERNAL_PID'",
                "created_at": "TEXT NOT NULL DEFAULT ''",
                "updated_at": "TEXT NOT NULL DEFAULT ''",
                "check_seq": "INTEGER NOT NULL DEFAULT 0",
                "monitor_errors": "INTEGER NOT NULL DEFAULT 0",
                "terminal_result": "TEXT NOT NULL DEFAULT '{}'",
            }
            for name, declaration in migrations.items():
                if name not in columns:
                    con.execute(f"ALTER TABLE commitments ADD COLUMN {name} {declaration}")

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db, timeout=20)
        con.row_factory = sqlite3.Row
        return con

    def set_alert_callback(self, callback: Callable[[dict[str, Any]], Any]) -> None:
        self.callback = callback

    @staticmethod
    def _tail(path: Path) -> str:
        if not path.is_file():
            return ""
        with path.open("rb") as source:
            source.seek(max(0, path.stat().st_size - 65536))
            return source.read().decode("utf-8", errors="replace")

    @staticmethod
    def _atomic_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
        sealed = {**payload, "sha256": canonical_sha256(payload)}
        temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(sealed, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        os.replace(temporary, path)
        return sealed

    def _persist(
        self,
        *,
        identifier: str,
        label: str,
        pid: int,
        logs: list[str],
        artifacts: list[str],
        poll_seconds: int,
        process_token: str | None,
        terminal_receipt: str | None,
        expected_exit_codes: list[int],
        mode: str,
    ) -> None:
        timestamp = now()
        with self.connect() as con:
            con.execute(
                "INSERT INTO commitments("
                "id,label,pid,logs,artifacts,poll,status,last_check,alerted,observation,"
                "process_token,terminal_receipt,expected_exit_codes,mode,created_at,"
                "updated_at,check_seq,monitor_errors,terminal_result"
                ") VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    identifier,
                    label,
                    pid,
                    json.dumps(logs),
                    json.dumps(artifacts),
                    poll_seconds,
                    "MONITORING",
                    0,
                    0,
                    "{}",
                    process_token or "",
                    terminal_receipt or "",
                    json.dumps(sorted(set(expected_exit_codes))),
                    mode,
                    timestamp,
                    timestamp,
                    0,
                    0,
                    "{}",
                ),
            )

    def register(
        self,
        *,
        label: str,
        pid: int,
        logs: list[str],
        artifacts: list[str],
        poll_seconds: int = 10,
        terminal_receipt: str | None = None,
        expected_exit_codes: list[int] | None = None,
    ) -> dict[str, Any]:
        if not label or pid <= 0 or poll_seconds < 1:
            raise ValueError("label, positive pid and poll_seconds required")
        exit_codes = [int(code) for code in (expected_exit_codes or [0])]
        identifier = f"MONITOR-{uuid.uuid4()}"
        token = process_identity(pid)
        self._persist(
            identifier=identifier,
            label=label,
            pid=pid,
            logs=[str(Path(path).resolve()) for path in logs],
            artifacts=[str(Path(path).resolve()) for path in artifacts],
            poll_seconds=poll_seconds,
            process_token=token,
            terminal_receipt=str(Path(terminal_receipt).resolve()) if terminal_receipt else None,
            expected_exit_codes=exit_codes,
            mode="EXTERNAL_PID",
        )
        return {
            "schema": self.SCHEMA,
            "commitment_id": identifier,
            "process_identity_captured": token is not None,
            "initial_observation": self.check(identifier),
            "promised_monitoring_active": True,
        }

    @staticmethod
    def _running_receipt(path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            return {"valid": False, "failure": f"UNREADABLE:{type(exc).__name__}"}
        if not isinstance(payload, dict):
            return {"valid": False, "failure": "NOT_OBJECT"}
        claimed = str(payload.get("sha256", ""))
        actual = canonical_sha256(payload)
        schema_ok = payload.get("schema") == "kch.monitored-process-running.v0.1.0"
        valid = bool(claimed) and claimed == actual and schema_ok
        return {
            "valid": valid,
            "failure": None if valid else "CANONICAL_OR_SCHEMA_MISMATCH",
            "claimed_sha256": claimed,
            "actual_sha256": actual,
            "payload": payload if valid else None,
        }

    def launch(
        self,
        *,
        label: str,
        argv: list[str],
        cwd: str,
        environment: dict[str, str] | None = None,
        expected_artifacts: list[str] | None = None,
        expected_exit_codes: list[int] | None = None,
        poll_seconds: int = 2,
    ) -> dict[str, Any]:
        if not label or not argv or not all(isinstance(item, str) and item for item in argv):
            raise ValueError("label and non-empty shell-free argv are required")
        if poll_seconds < 1:
            raise ValueError("poll_seconds must be positive")
        working_directory = Path(cwd).resolve()
        if not working_directory.is_dir():
            raise FileNotFoundError(working_directory)
        env = {str(key): str(value) for key, value in (environment or {}).items()}
        sensitive = sorted(
            key
            for key in env
            if any(marker in key.upper() for marker in self.SENSITIVE_ENV_MARKERS)
        )
        if sensitive:
            raise ValueError(
                "secret-like environment overrides are prohibited; use the finite account broker"
            )
        identifier = f"MONITOR-{uuid.uuid4()}"
        execution_root = self.root / identifier
        execution_root.mkdir(parents=True, exist_ok=False)
        stdout_path = execution_root / "stdout.log"
        stderr_path = execution_root / "stderr.log"
        terminal_path = execution_root / "terminal.json"
        running_path = execution_root / "running.json"
        request_path = execution_root / "request.json"
        artifacts = [
            str((working_directory / path).resolve())
            if not Path(path).is_absolute()
            else str(Path(path).resolve())
            for path in (expected_artifacts or [])
        ]
        exit_codes = [int(code) for code in (expected_exit_codes or [0])]
        request = self._atomic_json(
            request_path,
            {
                "schema": "kch.monitored-process-request.v0.1.0",
                "commitment_id": identifier,
                "argv": argv,
                "cwd": str(working_directory),
                "environment": env,
                "environment_keys": sorted(env),
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "terminal_path": str(terminal_path),
                "running_path": str(running_path),
                "expected_artifacts": artifacts,
                "created_at": now(),
            },
        )
        worker_script = Path(__file__).with_name("monitored_process_worker.py")
        popen_kwargs: dict[str, Any] = {
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "close_fds": True,
        }
        if os.name == "nt":
            popen_kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
        worker = subprocess.Popen(
            [sys.executable, str(worker_script), str(request_path)],
            cwd=str(working_directory),
            **popen_kwargs,
        )
        launcher_pid = worker.pid
        worker_pid = launcher_pid
        worker_pid_source = "POPEN_LAUNCHER_PID"
        startup_receipt_sha256: str | None = None
        deadline = time.monotonic() + self.STARTUP_RECEIPT_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            running_receipt = self._running_receipt(running_path)
            if running_receipt and running_receipt["valid"]:
                payload = running_receipt["payload"]
                if (
                    payload.get("commitment_id") == identifier
                    and payload.get("request_sha256") == request["sha256"]
                    and int(payload.get("worker_pid", 0)) > 0
                ):
                    worker_pid = int(payload["worker_pid"])
                    worker_pid_source = "CANONICAL_RUNNING_RECEIPT"
                    startup_receipt_sha256 = str(running_receipt["actual_sha256"])
                    break
            terminal_receipt = self._terminal_receipt(terminal_path)
            if terminal_receipt and terminal_receipt["valid"]:
                payload = terminal_receipt["payload"]
                if (
                    payload.get("commitment_id") == identifier
                    and payload.get("request_sha256") == request["sha256"]
                    and int(payload.get("worker_pid", 0)) > 0
                ):
                    worker_pid = int(payload["worker_pid"])
                    worker_pid_source = "CANONICAL_TERMINAL_RECEIPT"
                    startup_receipt_sha256 = str(terminal_receipt["actual_sha256"])
                    break
            time.sleep(0.01)
        token = process_identity(worker_pid)
        self._persist(
            identifier=identifier,
            label=label,
            pid=worker_pid,
            logs=[str(stdout_path), str(stderr_path)],
            artifacts=artifacts,
            poll_seconds=poll_seconds,
            process_token=token,
            terminal_receipt=str(terminal_path),
            expected_exit_codes=exit_codes,
            mode="OWNED_SUPERVISOR",
        )
        return {
            "schema": "kch.monitored-process-launch.v0.1.0",
            "commitment_id": identifier,
            "launcher_pid": launcher_pid,
            "worker_pid": worker_pid,
            "worker_pid_source": worker_pid_source,
            "launcher_worker_pid_match": launcher_pid == worker_pid,
            "startup_receipt_sha256": startup_receipt_sha256,
            "process_identity": token,
            "process_identity_captured": token is not None,
            "request_sha256": request["sha256"],
            "environment_keys": sorted(env),
            "stdout_path": str(stdout_path),
            "stderr_path": str(stderr_path),
            "terminal_receipt": str(terminal_path),
            "initial_observation": self.check(identifier),
            "shell_used": False,
            "relaunch_performed": False,
        }

    @staticmethod
    def _terminal_receipt(path: Path) -> dict[str, Any] | None:
        if not path.is_file():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            return {"valid": False, "failure": f"UNREADABLE:{type(exc).__name__}"}
        if not isinstance(payload, dict):
            return {"valid": False, "failure": "NOT_OBJECT"}
        claimed = str(payload.get("sha256", ""))
        actual = canonical_sha256(payload)
        schema_ok = payload.get("schema") == "kch.monitored-process-terminal.v0.1.0"
        valid = bool(claimed) and claimed == actual and schema_ok
        return {
            "valid": valid,
            "failure": None if valid else "CANONICAL_OR_SCHEMA_MISMATCH",
            "claimed_sha256": claimed,
            "actual_sha256": actual,
            "payload": payload if valid else None,
        }

    def check(self, identifier: str) -> dict[str, Any]:
        with self.connect() as con:
            row = con.execute("SELECT * FROM commitments WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise KeyError(identifier)
        logs = [Path(path) for path in json.loads(row["logs"])]
        artifacts = [Path(path) for path in json.loads(row["artifacts"])]
        expected_codes = {int(code) for code in json.loads(row["expected_exit_codes"])}
        terminal_path = Path(row["terminal_receipt"]) if row["terminal_receipt"] else None
        terminal_receipt = self._terminal_receipt(terminal_path) if terminal_path else None
        observed_identity = process_identity(int(row["pid"]))
        expected_identity = str(row["process_token"] or "")
        identity_match = not expected_identity or expected_identity == observed_identity
        running = process_exists(int(row["pid"]), expected_identity or None)
        markers = sorted(
            {marker for path in logs for marker in self.ERRORS if marker in self._tail(path).lower()}
        )
        artifact_state = {str(path): file_metadata(path) for path in artifacts}
        exit_code: int | None = None
        terminal = False
        receipt_summary: dict[str, Any] | None = None
        if terminal_receipt is not None:
            receipt_summary = {
                key: value
                for key, value in terminal_receipt.items()
                if key != "payload"
            }
            if not terminal_receipt["valid"]:
                status = "TERMINAL_EVIDENCE_INVALID_ALERT_REQUIRED"
                terminal = True
            else:
                payload = terminal_receipt["payload"]
                if int(payload.get("worker_pid", -1)) != int(row["pid"]):
                    status = "TERMINAL_EVIDENCE_INVALID_ALERT_REQUIRED"
                    receipt_summary["failure"] = "WORKER_PID_MISMATCH"
                    terminal = True
                elif payload.get("status") == "WORKER_ERROR":
                    status = "MONITOR_WORKER_FAILED"
                    terminal = True
                else:
                    exit_code = int(payload["exit_code"])
                    status = "COMPLETED_PASS" if exit_code in expected_codes else "COMPLETED_FAIL"
                    terminal = True
        elif running:
            status = "MONITORING"
        elif markers:
            status = "FAILED_MARKER_NO_TERMINAL_RECEIPT"
            terminal = True
        elif artifacts and all(item["exists"] for item in artifact_state.values()):
            status = "TERMINATED_ARTIFACTS_WITHOUT_EXIT_CODE"
            terminal = True
        elif artifacts:
            status = "TERMINATED_MISSING_ARTIFACT_ALERT_REQUIRED"
            terminal = True
        else:
            status = "TERMINATED_WITHOUT_EXIT_EVIDENCE"
            terminal = True
        emit = terminal and not bool(row["alerted"])
        observation = {
            "schema": "kch.commitment-observation.v0.2.0",
            "commitment_id": identifier,
            "checked_at": now(),
            "check_sequence": int(row["check_seq"]) + 1,
            "mode": row["mode"],
            "worker_pid": int(row["pid"]),
            "process_running": running,
            "expected_process_identity": expected_identity or None,
            "observed_process_identity": observed_identity,
            "process_identity_match": identity_match,
            "status": status,
            "terminal": terminal,
            "exit_code": exit_code,
            "expected_exit_codes": sorted(expected_codes),
            "error_markers": markers,
            "logs": {str(path): file_metadata(path) for path in logs},
            "artifacts": artifact_state,
            "terminal_receipt": receipt_summary,
            "alert_emitted_now": emit,
            "relaunch_performed": False,
        }
        terminal_result = observation if terminal else {}
        with self.connect() as con:
            con.execute(
                "UPDATE commitments SET status=?,last_check=?,alerted=?,observation=?,"
                "updated_at=?,check_seq=?,terminal_result=? WHERE id=?",
                (
                    status,
                    time.time(),
                    int(emit or row["alerted"]),
                    json.dumps(observation, ensure_ascii=False),
                    now(),
                    observation["check_sequence"],
                    json.dumps(terminal_result, ensure_ascii=False),
                    identifier,
                ),
            )
        if emit and self.callback:
            try:
                self.callback(
                    {
                        "type": "commitment.monitor.alert",
                        "authority": "KCH_SYSTEM",
                        "observation": observation,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - callback cannot kill evidence reconciliation
                self._record_reconciliation_error(identifier, exc, phase="ALERT_CALLBACK")
        return observation

    def _record_reconciliation_error(
        self,
        identifier: str,
        exc: Exception,
        *,
        phase: str = "CHECK",
    ) -> dict[str, Any]:
        observation = {
            "schema": "kch.commitment-reconciliation-error.v0.1.0",
            "commitment_id": identifier,
            "checked_at": now(),
            "status": "RECONCILIATION_ERROR_RETRY_REQUIRED",
            "terminal": False,
            "phase": phase,
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
        }
        with self.connect() as con:
            con.execute(
                "UPDATE commitments SET monitor_errors=monitor_errors+1,last_check=?,"
                "updated_at=?,observation=? WHERE id=?",
                (time.time(), now(), json.dumps(observation), identifier),
            )
        return observation

    def check_all(self) -> list[dict[str, Any]]:
        with self.connect() as con:
            identifiers = [
                str(row[0])
                for row in con.execute("SELECT id FROM commitments WHERE status='MONITORING'")
            ]
        observations = []
        for identifier in identifiers:
            try:
                observations.append(self.check(identifier))
            except Exception as exc:  # noqa: BLE001 - isolate one broken commitment
                observations.append(self._record_reconciliation_error(identifier, exc))
        return observations

    def active_ids(self) -> list[str]:
        """Return only commitments whose latest reconciled state remains MONITORING."""
        self.check_all()
        with self.connect() as con:
            return [
                str(row[0])
                for row in con.execute(
                    "SELECT id FROM commitments WHERE status='MONITORING' ORDER BY id"
                )
            ]

    def wait_terminal(
        self,
        identifier: str,
        *,
        timeout_seconds: float,
        poll_seconds: float = 0.25,
    ) -> dict[str, Any]:
        if timeout_seconds <= 0 or poll_seconds <= 0:
            raise ValueError("positive timeout_seconds and poll_seconds required")
        started = time.monotonic()
        checks = 0
        while True:
            observation = self.check(identifier)
            checks += 1
            if observation["terminal"]:
                return {
                    "schema": "kch.commitment-wait.v0.1.0",
                    "gate": "TERMINAL_OBSERVED",
                    "terminal": True,
                    "checks": checks,
                    "elapsed_seconds": round(time.monotonic() - started, 6),
                    "observation": observation,
                    "relaunch_performed": False,
                }
            elapsed = time.monotonic() - started
            if elapsed >= timeout_seconds:
                return {
                    "schema": "kch.commitment-wait.v0.1.0",
                    "gate": "WAIT_TIMEOUT_COMMITMENT_REMAINS_ACTIVE",
                    "terminal": False,
                    "checks": checks,
                    "elapsed_seconds": round(elapsed, 6),
                    "observation": observation,
                    "relaunch_performed": False,
                }
            time.sleep(min(poll_seconds, max(0.0, timeout_seconds - elapsed)))

    def evidence(self, identifier: str) -> dict[str, Any]:
        observation = self.check(identifier)
        with self.connect() as con:
            row = con.execute("SELECT * FROM commitments WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise KeyError(identifier)
        payload = {
            "schema": "kch.commitment-evidence.v0.1.0",
            "commitment_id": identifier,
            "label": row["label"],
            "mode": row["mode"],
            "worker_pid": int(row["pid"]),
            "process_token": row["process_token"] or None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "status": row["status"],
            "monitor_errors": int(row["monitor_errors"]),
            "check_sequence": int(row["check_seq"]),
            "latest_observation": observation,
            "claim_ceiling": (
                "LOCAL_OWNED_OR_REGISTERED_PROCESS_TERMINAL_EVIDENCE_ONLY_"
                "NOT_GENERAL_EXECUTION_SUCCESS"
            ),
        }
        return {**payload, "sha256": canonical_sha256(payload)}

    def start(self) -> dict[str, Any]:
        if self.thread and self.thread.is_alive():
            return {"running": True, "already_running": True}
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="kch-commitment-monitor",
        )
        self.thread.start()
        return {"running": True, "already_running": False}

    def _loop(self) -> None:
        while not self.stop_event.wait(1):
            try:
                with self.connect() as con:
                    due = [
                        str(row[0])
                        for row in con.execute(
                            "SELECT id FROM commitments WHERE status='MONITORING' "
                            "AND ?-last_check>=poll",
                            (time.time(),),
                        )
                    ]
            except sqlite3.Error:
                continue
            for identifier in due:
                try:
                    self.check(identifier)
                except Exception as exc:  # noqa: BLE001 - keep the monitor alive
                    self._record_reconciliation_error(identifier, exc)

    def stop(self, timeout: float = 5) -> dict[str, Any]:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout)
        return {"running": bool(self.thread and self.thread.is_alive())}

    def status(self) -> dict[str, Any]:
        with self.connect() as con:
            counts = {
                str(row[0]): int(row[1])
                for row in con.execute("SELECT status,COUNT(*) FROM commitments GROUP BY status")
            }
            monitor_errors = int(
                con.execute("SELECT COALESCE(SUM(monitor_errors),0) FROM commitments").fetchone()[0]
            )
        return {
            "schema": "kch.commitment-monitor-status.v0.2.0",
            "background_running": bool(self.thread and self.thread.is_alive()),
            "counts": counts,
            "monitor_errors": monitor_errors,
            "terminal_receipt_schema": "kch.monitored-process-terminal.v0.1.0",
            "claim_ceiling": (
                "LOCAL_PROCESS_IDENTITY_LOG_ARTIFACT_AND_TERMINAL_RECEIPT_MONITORING_ONLY"
            ),
        }
