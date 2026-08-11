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
from kch_studio.full_read_contract import FullReadService
from kch_studio.permissions import PermissionGovernor


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


def source_manifest(root: Path) -> dict[str, Any]:
    rows = []
    for directory in ("src", "tests", "scripts"):
        for path in sorted((root / directory).rglob("*")):
            if not path.is_file():
                continue
            if any(part in {"__pycache__", ".pytest_cache", ".pytest-tmp"} for part in path.parts):
                continue
            raw = path.read_bytes()
            rows.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                }
            )
    encoded = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "file_count": len(rows),
        "total_bytes": sum(row["bytes"] for row in rows),
        "manifest_sha256": hashlib.sha256(encoded).hexdigest(),
        "files": rows,
    }


def pytest_counts(text: str) -> dict[str, Any]:
    patterns = {
        "passed": r"(\d+) passed",
        "failed": r"(\d+) failed",
        "skipped": r"(\d+) skipped",
        "errors": r"(\d+) errors?",
    }
    counts: dict[str, int | None] = {}
    for key, pattern in patterns.items():
        matches = re.findall(pattern, text)
        counts[key] = int(matches[-1]) if matches else (0 if key != "passed" else None)
    terminal_lines = [line.strip() for line in text.splitlines() if " passed" in line or " failed" in line]
    return {
        **counts,
        "terminal_summary": terminal_lines[-1] if terminal_lines else None,
        "counts_estimable": counts["passed"] is not None,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    source_root = Path(args.source_root).resolve()
    monitor_root = Path(args.monitor_root).resolve()
    basetemp = Path(args.basetemp).resolve()
    ground_truth = json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))
    before = source_manifest(source_root)
    permissions = PermissionGovernor(monitor_root / "permissions")
    reader = FullReadService(source_root, permissions)
    items = [
        {
            "path": item["path"],
            "expected_sha256": item["sha256"],
            "expected_evidence_spans": item["expected_evidence_spans"],
        }
        for item in ground_truth["files"]
    ]
    batch = reader.read_batch(
        items,
        requested_order="SOURCE_NATIVE_ORDER",
        max_return_bytes_per_file=1_048_576,
        max_batch_return_bytes=5_242_880,
    )
    verification = reader.verify_batch(batch)
    monitor = CommitmentMonitor(monitor_root / "commitments")
    launch = monitor.launch(
        label="KCH_PREPILOT_020_COMPLETE_SOURCE_SUITE",
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
        cwd=str(source_root),
        environment={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"},
        expected_exit_codes=[0],
        poll_seconds=1,
    )
    waited = monitor.wait_terminal(
        launch["commitment_id"],
        timeout_seconds=float(args.timeout_seconds),
        poll_seconds=0.5,
    )
    evidence = monitor.evidence(launch["commitment_id"])
    stdout_path = Path(launch["stdout_path"])
    stdout = stdout_path.read_text(encoding="utf-8", errors="replace") if stdout_path.is_file() else ""
    terminal_path = Path(launch["terminal_receipt"])
    terminal_receipt = (
        json.loads(terminal_path.read_text(encoding="utf-8"))
        if terminal_path.is_file()
        else None
    )
    after = source_manifest(source_root)
    observation = waited["observation"]
    counts = pytest_counts(stdout)
    gates = {
        "full_read_batch": batch["gate"] == "PASS",
        "full_read_source_verification": verification["gate"]
        == "PASS_VERIFIED_AGAINST_SOURCE",
        "semantic_exact_spans": batch["semantic_evidence_gate"] == "PASS"
        and verification["semantic_batch_claim_allowed"] is True,
        "terminal_observed": waited["gate"] == "TERMINAL_OBSERVED",
        "exit_zero": observation["exit_code"] == 0,
        "pytest_counts_estimable": counts["counts_estimable"],
        "source_unchanged_during_gate": before["manifest_sha256"]
        == after["manifest_sha256"],
        "terminal_receipt_embedded": terminal_receipt is not None,
        "phl_not_executed": True,
    }
    payload = {
        "schema": "kch.prepilot020-component-gate-result.v0.1.0",
        "prepilot_id": "KCH_PREPILOT_020",
        "executed_at": now(),
        "gate": "PASS" if all(gates.values()) else "FAIL",
        "gates": gates,
        "full_read_batch": batch,
        "full_read_source_verification": verification,
        "monitor_launch": launch,
        "monitor_wait": waited,
        "monitor_evidence": evidence,
        "terminal_receipt": terminal_receipt,
        "pytest": counts,
        "source_manifest_before_execution": before,
        "source_manifest_after_execution": after,
        "source_mutation_detected_during_gate": before["manifest_sha256"]
        != after["manifest_sha256"],
        "phl_authorized": True,
        "phl_training_executed": False,
        "phl_real_executed": False,
        "claim_ceiling": (
            "ONE_LOCAL_PREPILOT020_COMPONENT_INTEGRATION_GATE_FULL_READ_AND_OWNED_TERMINAL_"
            "SUPERVISION_ONLY"
        ),
    }
    return {**payload, "sha256": canonical_sha256(payload)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--monitor-root", required=True)
    parser.add_argument("--basetemp", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=600)
    args = parser.parse_args()
    result = run(args)
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "gate": result["gate"],
                "output": str(output),
                "sha256": result["sha256"],
                "pytest": result["pytest"],
                "monitor_status": result["monitor_wait"]["observation"]["status"],
                "exit_code": result["monitor_wait"]["observation"]["exit_code"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if result["gate"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
