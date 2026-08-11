from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from kch_studio.commitment_monitor import CommitmentMonitor


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def source_manifest(root: Path) -> dict[str, Any]:
    files = []
    roots = [
        root / "src",
        root / "tests",
        root / "scripts",
        root / "governance",
        root / "docs",
    ]
    single = [root / "pyproject.toml", root / "README_ES.md"]
    paths = single + [path for base in roots for path in base.rglob("*") if path.is_file()]
    for path in sorted(paths):
        if any(
            part in {"__pycache__", ".pytest_cache", ".pytest-tmp"}
            for part in path.parts
        ):
            continue
        raw = path.read_bytes()
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return {
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "manifest_sha256": canonical_sha256(files),
        "files": files,
    }


def counts(text: str) -> dict[str, Any]:
    def last(pattern: str) -> int | None:
        found = re.findall(pattern, text)
        return int(found[-1]) if found else None

    summaries = [
        line.strip()
        for line in text.splitlines()
        if " passed" in line or " failed" in line or " error" in line
    ]
    return {
        "passed": last(r"(\d+) passed"),
        "failed": last(r"(\d+) failed") or 0,
        "errors": last(r"(\d+) errors?") or 0,
        "skipped": last(r"(\d+) skipped") or 0,
        "terminal_summary": summaries[-1] if summaries else None,
    }


def run_one(
    monitor: CommitmentMonitor,
    *,
    label: str,
    argv: list[str],
    cwd: Path,
    timeout_seconds: float,
) -> dict[str, Any]:
    launch = monitor.launch(
        label=label,
        argv=argv,
        cwd=str(cwd),
        environment={
            "PYTHONUTF8": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": "src",
        },
        expected_exit_codes=[0],
        poll_seconds=1,
    )
    waited = monitor.wait_terminal(
        launch["commitment_id"],
        timeout_seconds=timeout_seconds,
        poll_seconds=0.5,
    )
    evidence = monitor.evidence(launch["commitment_id"])
    stdout_path = Path(launch["stdout_path"])
    stderr_path = Path(launch["stderr_path"])
    return {
        "launch": launch,
        "wait": waited,
        "evidence": evidence,
        "stdout": stdout_path.read_text(encoding="utf-8", errors="replace")
        if stdout_path.is_file()
        else "",
        "stderr": stderr_path.read_text(encoding="utf-8", errors="replace")
        if stderr_path.is_file()
        else "",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--monitor-root", required=True)
    parser.add_argument("--basetemp", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=900)
    parser.add_argument("--attempt", type=int, required=True)
    args = parser.parse_args()

    candidate = Path(args.candidate).resolve()
    monitor_root = Path(args.monitor_root).resolve()
    basetemp = Path(args.basetemp).resolve()
    output = Path(args.output).resolve()
    monitor_root.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    before = source_manifest(candidate)
    monitor = CommitmentMonitor(monitor_root)
    pytest_result = run_one(
        monitor,
        label=f"KCH_R21_FULL_SOURCE_PYTEST_ATTEMPT_{args.attempt:02d}",
        argv=[
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--basetemp",
            str(basetemp),
        ],
        cwd=candidate,
        timeout_seconds=args.timeout_seconds,
    )
    pytest_observation = pytest_result["wait"]["observation"]
    pytest_counts = counts(pytest_result["stdout"])

    ruff_result = None
    if pytest_observation["exit_code"] == 0:
        ruff_result = run_one(
            monitor,
            label=f"KCH_R21_FULL_SOURCE_RUFF_ATTEMPT_{args.attempt:02d}",
            argv=[sys.executable, "-m", "ruff", "check", "."],
            cwd=candidate,
            timeout_seconds=args.timeout_seconds,
        )
    after = source_manifest(candidate)
    pytest_pass = (
        pytest_result["wait"]["gate"] == "TERMINAL_OBSERVED"
        and pytest_observation["status"] == "COMPLETED_PASS"
        and pytest_observation["exit_code"] == 0
        and pytest_counts["passed"] is not None
        and pytest_counts["failed"] == 0
        and pytest_counts["errors"] == 0
    )
    ruff_observation = ruff_result["wait"]["observation"] if ruff_result else None
    ruff_pass = bool(
        ruff_result
        and ruff_result["wait"]["gate"] == "TERMINAL_OBSERVED"
        and ruff_observation["status"] == "COMPLETED_PASS"
        and ruff_observation["exit_code"] == 0
    )
    checks = {
        "pytest_terminal_pass": pytest_pass,
        "ruff_terminal_pass": ruff_pass,
        "source_unchanged_during_gate": before["manifest_sha256"]
        == after["manifest_sha256"],
        "pytest_not_relaunched": pytest_observation["relaunch_performed"] is False,
        "ruff_not_relaunched": bool(
            ruff_observation and ruff_observation["relaunch_performed"] is False
        ),
        "phl_not_executed": True,
    }
    payload: dict[str, Any] = {
        "schema": "kch.r21-durable-full-source-gate.v0.1.0",
        "attempt": args.attempt,
        "executed_at": now(),
        "gate": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "pytest": {**pytest_result, "counts": pytest_counts},
        "ruff": ruff_result,
        "source_manifest_before": before,
        "source_manifest_after": after,
        "phl_authorized": True,
        "phl_training_executed": False,
        "phl_real_executed": False,
        "claim_ceiling": "R21_LOCAL_FULL_SOURCE_REGRESSION_ONLY",
    }
    sealed = {**payload, "sha256": canonical_sha256(payload)}
    output.write_text(
        json.dumps(sealed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "gate": sealed["gate"],
                "pytest": pytest_counts,
                "pytest_status": pytest_observation["status"],
                "pytest_exit_code": pytest_observation["exit_code"],
                "ruff_status": ruff_observation["status"]
                if ruff_observation
                else None,
                "ruff_exit_code": ruff_observation["exit_code"]
                if ruff_observation
                else None,
                "output": str(output),
                "sha256": sealed["sha256"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if sealed["gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
