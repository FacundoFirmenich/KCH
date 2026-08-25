from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


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


def atomic_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    sealed = {**payload, "sha256": canonical_sha256(payload)}
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(
        json.dumps(sealed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(temporary, path)
    return sealed


def validate_request(path: Path) -> dict[str, Any]:
    request = json.loads(path.read_text(encoding="utf-8"))
    if request.get("schema") != "kch.monitored-process-request.v0.1.0":
        raise ValueError("unsupported monitored-process request schema")
    if request.get("sha256") != canonical_sha256(request):
        raise ValueError("monitored-process request canonical hash mismatch")
    argv = request.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(x, str) and x for x in argv):
        raise ValueError("request argv must be a non-empty string array")
    return request


def run(request_path: Path) -> int:
    request: dict[str, Any] | None = None
    terminal_path: Path | None = None
    started_monotonic = time.monotonic()
    try:
        request = validate_request(request_path)
        terminal_path = Path(request["terminal_path"])
        running_path = Path(request["running_path"])
        stdout_path = Path(request["stdout_path"])
        stderr_path = Path(request["stderr_path"])
        cwd = Path(request["cwd"])
        if not cwd.is_dir():
            raise FileNotFoundError(cwd)
        environment = os.environ.copy()
        environment.update({str(k): str(v) for k, v in request["environment"].items()})
        started_at = now()
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                request["argv"],
                cwd=str(cwd),
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                shell=False,
                close_fds=True,
            )
            atomic_json(
                running_path,
                {
                    "schema": "kch.monitored-process-running.v0.1.0",
                    "commitment_id": request["commitment_id"],
                    "worker_pid": os.getpid(),
                    "child_pid": process.pid,
                    "started_at": started_at,
                    "request_sha256": request["sha256"],
                },
            )
            exit_code = process.wait()
        finished_at = now()
        artifacts = {
            str(Path(path)): file_metadata(Path(path))
            for path in request["expected_artifacts"]
        }
        atomic_json(
            terminal_path,
            {
                "schema": "kch.monitored-process-terminal.v0.1.0",
                "commitment_id": request["commitment_id"],
                "worker_pid": os.getpid(),
                "child_pid": process.pid,
                "request_sha256": request["sha256"],
                "argv": request["argv"],
                "cwd": str(cwd),
                "environment_keys": request["environment_keys"],
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_seconds": round(time.monotonic() - started_monotonic, 6),
                "status": "EXIT_ZERO" if exit_code == 0 else "EXIT_NONZERO",
                "exit_code": exit_code,
                "stdout": file_metadata(stdout_path),
                "stderr": file_metadata(stderr_path),
                "artifacts": artifacts,
                "shell_used": False,
            },
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - the terminal failure receipt is the contract
        if terminal_path is None and request is not None and request.get("terminal_path"):
            terminal_path = Path(request["terminal_path"])
        if terminal_path is not None:
            atomic_json(
                terminal_path,
                {
                    "schema": "kch.monitored-process-terminal.v0.1.0",
                    "commitment_id": request.get("commitment_id") if request else None,
                    "worker_pid": os.getpid(),
                    "child_pid": None,
                    "request_sha256": request.get("sha256") if request else None,
                    "started_at": None,
                    "finished_at": now(),
                    "duration_seconds": round(time.monotonic() - started_monotonic, 6),
                    "status": "WORKER_ERROR",
                    "exit_code": None,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:500],
                    "shell_used": False,
                },
            )
        return 70


def main() -> int:
    if len(sys.argv) != 2:
        return 64
    return run(Path(sys.argv[1]).resolve())


if __name__ == "__main__":
    raise SystemExit(main())
