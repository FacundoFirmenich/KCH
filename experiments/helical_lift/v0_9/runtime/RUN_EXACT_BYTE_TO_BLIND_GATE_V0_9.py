from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any

from common_v09 import (
    SECRET_NAME_FRAGMENTS,
    canonical_json_bytes,
    content_id,
    sanitize_text,
    sha256_file,
    utc_now,
    write_json_atomic,
)

PROTOCOL_ID = "h8p:99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f"
PROTOCOL_FILE_SHA256 = "9c988d22a0d0453e645677a8788bc4064b57991e1ec1a44001d5098d12388246"
MECHANISM_BASENAME = "focmec_ca_final.pickle"
FAULT_BASENAME = "gem_active_faults_harmonized.geojson"


def scrubbed_environment() -> tuple[dict[str, str], list[str]]:
    env: dict[str, str] = {}
    removed: list[str] = []
    for name, value in os.environ.items():
        if any(fragment in name.lower() for fragment in SECRET_NAME_FRAGMENTS):
            removed.append(name)
        else:
            env[name] = value
    env["PYTHONNOUSERSITE"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONHASHSEED"] = "0"
    return env, sorted(removed)


def run_step(name: str, command: list[str], logs_dir: Path, *, env: dict[str, str]) -> dict[str, Any]:
    logs_dir.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    started = time.monotonic()
    completed = subprocess.run(command, capture_output=True, text=True, env=env)
    elapsed = time.monotonic() - started
    stdout = sanitize_text(completed.stdout)
    stderr = sanitize_text(completed.stderr)
    (logs_dir / f"{name}.stdout.txt").write_text(stdout, encoding="utf-8")
    (logs_dir / f"{name}.stderr.txt").write_text(stderr, encoding="utf-8")
    return {
        "name": name,
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "elapsed_seconds": elapsed,
        "returncode": completed.returncode,
        "command": [str(item) for item in command],
        "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
    }


def audit_protocol(path: Path) -> dict[str, str]:
    raw = path.read_bytes()
    physical = hashlib.sha256(raw).hexdigest()
    if physical != PROTOCOL_FILE_SHA256:
        raise RuntimeError(f"locked protocol physical hash mismatch: {physical}")
    protocol = json.loads(raw.decode("utf-8"))
    stripped = dict(protocol)
    protocol_id = stripped.pop("protocol_id")
    declared = stripped.pop("protocol_sha256")
    calculated = hashlib.sha256(canonical_json_bytes(stripped)).hexdigest()
    if protocol_id != PROTOCOL_ID or declared != calculated or protocol_id != f"h8p:{calculated}":
        raise RuntimeError("locked protocol content-address mismatch")
    return {
        "protocol_id": protocol_id,
        "protocol_content_sha256": calculated,
        "protocol_file_sha256": physical,
    }


def append_transition(path: Path, transition: dict[str, Any], previous_hash: str | None) -> str:
    body = {
        "sequence": sum(1 for _ in path.open("r", encoding="utf-8")) + 1 if path.exists() else 1,
        "previous_hash": previous_hash,
        **transition,
    }
    event_hash = hashlib.sha256(canonical_json_bytes(body)).hexdigest()
    body["event_hash"] = event_hash
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return event_hash


def blind_outputs_valid(blind: Path, mechanism_sha: str) -> bool:
    try:
        extraction = json.loads((blind / "EXTRACTION_RECEIPT_V0_9.json").read_text(encoding="utf-8"))
        verification = json.loads((blind / "SAFE_NPZ_VERIFICATION_RECEIPT_V0_9.json").read_text(encoding="utf-8"))
        npz = blind / "blind_columns.npz"
        return (
            extraction.get("source_sha256") == mechanism_sha
            and extraction.get("output_sha256") == sha256_file(npz)
            and verification.get("status") == "PASS"
            and verification.get("npz_sha256") == extraction.get("output_sha256")
        )
    except Exception:
        return False


def quarantine(path: Path, workspace: Path) -> Path:
    destination = workspace / "quarantine" / f"{path.name}.{utc_now().replace(':', '').replace('-', '')}"
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(path, destination)
    return destination


def finalize_receipt(receipts_dir: Path, body: dict[str, Any]) -> None:
    body["completed_at_utc"] = utc_now()
    body["gate_receipt_id"] = content_id("h9gate", body)
    write_json_atomic(receipts_dir / "GATE_EXECUTION_RECEIPT_V0_9.json", body)


def main() -> int:
    parser = argparse.ArgumentParser(description="One transactional route from exact public bytes to blind eligibility; no directional unsealing or model fit")
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--execute-network", action="store_true")
    parser.add_argument("--network-timeout-seconds", type=int, default=300)
    parser.add_argument("--sandbox-timeout-seconds", type=int, default=2700)
    parser.add_argument("--sandbox-memory-mib", type=int, default=8192)
    parser.add_argument("--purge-raw-after-gate", action="store_true")
    args = parser.parse_args()

    runtime = Path(__file__).resolve().parent
    package_root = runtime.parent
    protocol = package_root / "source_lock" / "HELICAL_DYNAMIC_MARKED_POINT_PROCESS_GATE_V0_8_LOCKED.json"
    workspace = args.workspace.resolve()
    receipts = workspace / "receipts"
    logs = receipts / "logs"
    transitions_path = receipts / "STATE_TRANSITIONS_V0_9.jsonl"
    workspace.mkdir(parents=True, exist_ok=True)
    receipts.mkdir(parents=True, exist_ok=True)
    lock = audit_protocol(protocol)
    env, removed_env_names = scrubbed_environment()
    previous_transition: str | None = None
    steps: list[dict[str, Any]] = []
    started_at = utc_now()
    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_9_EXACT_BYTE_TO_BLIND_GATE_EXECUTION",
        "started_at_utc": started_at,
        "runtime_version": "0.9.0",
        **lock,
        "execute_network_explicit": bool(args.execute_network),
        "environment_secret_names_removed": removed_env_names,
        "steps": steps,
        "directional_fields_unsealed": False,
        "model_fitting_performed": False,
        "scientific_execution_performed": False,
        "physical_helicity": "NOT_EVALUATED",
        "authority_ceiling": "NONE",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }

    previous_transition = append_transition(
        transitions_path,
        {"at_utc": utc_now(), "state": "PROTOCOL_LOCK_VERIFIED", "protocol_id": PROTOCOL_ID},
        previous_transition,
    )

    acquire_command = [
        sys.executable,
        str(runtime / "ACQUIRE_EXACT_SOURCES_V0_9.py"),
        "--workspace", str(workspace),
        "--timeout-seconds", str(args.network_timeout_seconds),
    ]
    if args.execute_network:
        acquire_command.append("--execute-network")
    acquisition_step = run_step("01_acquisition", acquire_command, logs, env=env)
    steps.append(acquisition_step)
    attempt = json.loads((receipts / "ACQUISITION_ATTEMPT_V0_9.json").read_text(encoding="utf-8"))
    body["acquisition_attempt_receipt_id"] = attempt.get("receipt_id")
    previous_transition = append_transition(
        transitions_path,
        {"at_utc": utc_now(), "state": attempt.get("outcome"), "receipt_id": attempt.get("receipt_id")},
        previous_transition,
    )

    if acquisition_step["returncode"] != 0:
        body["outcome"] = attempt.get("outcome", "BLOCKED_EXACT_BYTE_ACQUISITION")
        body["all_or_none_pass"] = False
        body["final_transition_hash"] = previous_transition
        finalize_receipt(receipts, body)
        print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2))
        return 4 if body["outcome"] == "DRY_RUN_NO_EFFECT" else 10

    exact = workspace / "exact_sources"
    acquisition_receipt_path = exact / "ACQUISITION_RECEIPT_V0_9.json"
    acquisition = json.loads(acquisition_receipt_path.read_text(encoding="utf-8"))
    if acquisition.get("outcome") != "EXACT_BYTE_ACQUISITION_PASS":
        raise RuntimeError("acquisition command returned zero without PASS receipt")
    shutil.copy2(acquisition_receipt_path, receipts / acquisition_receipt_path.name)
    body["acquisition_receipt_id"] = acquisition.get("receipt_id")
    body["all_or_none_pass"] = True

    mechanism = exact / MECHANISM_BASENAME
    fault = exact / FAULT_BASENAME
    mechanism_sha = acquisition["source_receipts"]["mechanism"]["sha256"]

    blind = workspace / "blind"
    if blind.exists() and not blind_outputs_valid(blind, mechanism_sha):
        body.setdefault("quarantined", []).append(str(quarantine(blind, workspace)))
    if not blind.exists():
        blind.mkdir(parents=True)
        extraction_command = [
            "bash", str(runtime / "RUN_HARDENED_PICKLE_EXTRACTION_V0_9.sh"),
            "--input", str(mechanism),
            "--expected-sha256", mechanism_sha,
            "--output-dir", str(blind),
            "--memory-mib", str(args.sandbox_memory_mib),
            "--timeout-seconds", str(args.sandbox_timeout_seconds),
        ]
        extraction_step = run_step("02_sandbox_extraction", extraction_command, logs, env=env)
        steps.append(extraction_step)
        if extraction_step["returncode"] != 0:
            previous_transition = append_transition(
                transitions_path,
                {"at_utc": utc_now(), "state": "BLOCKED_PICKLE_SANDBOX", "returncode": extraction_step["returncode"]},
                previous_transition,
            )
            body["outcome"] = "BLOCKED_PICKLE_SANDBOX"
            body["final_transition_hash"] = previous_transition
            finalize_receipt(receipts, body)
            print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2))
            return 20
    else:
        steps.append({"name": "02_sandbox_extraction", "returncode": 0, "idempotent_reuse": True})

    extraction = json.loads((blind / "EXTRACTION_RECEIPT_V0_9.json").read_text(encoding="utf-8"))
    npz_receipt = json.loads((blind / "SAFE_NPZ_VERIFICATION_RECEIPT_V0_9.json").read_text(encoding="utf-8"))
    body["extraction_receipt_id"] = extraction.get("receipt_id")
    body["safe_npz_verification_receipt_id"] = npz_receipt.get("receipt_id")
    previous_transition = append_transition(
        transitions_path,
        {
            "at_utc": utc_now(),
            "state": "SAFE_BLIND_NPZ_READY",
            "extraction_receipt_id": extraction.get("receipt_id"),
            "npz_receipt_id": npz_receipt.get("receipt_id"),
        },
        previous_transition,
    )

    eligibility_dir = workspace / "eligibility"
    eligibility_dir.mkdir(parents=True, exist_ok=True)
    eligibility_path = eligibility_dir / "BLIND_ELIGIBILITY_RESULT_V0_9.json"
    eligibility_command = [
        sys.executable,
        str(runtime / "RUN_BLIND_ELIGIBILITY_SAFE_NPZ_V0_9.py"),
        "--protocol", str(protocol),
        "--safe-npz", str(blind / "blind_columns.npz"),
        "--extraction-receipt", str(blind / "EXTRACTION_RECEIPT_V0_9.json"),
        "--safe-npz-receipt", str(blind / "SAFE_NPZ_VERIFICATION_RECEIPT_V0_9.json"),
        "--acquisition-receipt", str(acquisition_receipt_path),
        "--fault-geojson", str(fault),
        "--output", str(eligibility_path),
    ]
    eligibility_step = run_step("03_blind_eligibility", eligibility_command, logs, env=env)
    steps.append(eligibility_step)
    if not eligibility_path.exists():
        previous_transition = append_transition(
            transitions_path,
            {"at_utc": utc_now(), "state": "BLIND_ELIGIBILITY_EXECUTION_FAILURE", "returncode": eligibility_step["returncode"]},
            previous_transition,
        )
        body["outcome"] = "BLIND_ELIGIBILITY_EXECUTION_FAILURE"
        body["final_transition_hash"] = previous_transition
        finalize_receipt(receipts, body)
        print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2))
        return 21

    eligibility = json.loads(eligibility_path.read_text(encoding="utf-8"))
    body["eligibility_result_id"] = eligibility.get("eligibility_result_id")
    body["eligibility_transport_receipt_id"] = eligibility.get("transport_receipt_id")
    body["selected_primary_cohorts"] = eligibility.get("selected_primary_cohorts")
    body["eligibility_outcome"] = eligibility.get("outcome")
    previous_transition = append_transition(
        transitions_path,
        {
            "at_utc": utc_now(),
            "state": eligibility.get("outcome"),
            "eligibility_result_id": eligibility.get("eligibility_result_id"),
            "selected_primary_cohorts": eligibility.get("selected_primary_cohorts"),
        },
        previous_transition,
    )

    if eligibility.get("outcome") == "ELIGIBILITY_PASS":
        request_path = eligibility_dir / "DIRECTIONAL_UNSEAL_REQUEST_V0_9.json"
        request_command = [
            sys.executable,
            str(runtime / "PREPARE_DIRECTIONAL_UNSEAL_REQUEST_V0_9.py"),
            "--eligibility-result", str(eligibility_path),
            "--acquisition-receipt", str(acquisition_receipt_path),
            "--extraction-receipt", str(blind / "EXTRACTION_RECEIPT_V0_9.json"),
            "--protocol", str(protocol),
            "--output", str(request_path),
        ]
        request_step = run_step("04_prepare_unseal_request", request_command, logs, env=env)
        steps.append(request_step)
        if request_step["returncode"] != 0:
            body["outcome"] = "ELIGIBILITY_PASS_UNSEAL_REQUEST_FAILED"
            result_code = 22
        else:
            request = json.loads(request_path.read_text(encoding="utf-8"))
            body["directional_unseal_request_id"] = request.get("request_id")
            body["outcome"] = "ELIGIBILITY_PASS_DIRECTIONAL_UNSEAL_REQUEST_READY"
            result_code = 0
    else:
        body["outcome"] = eligibility.get("outcome", "NOT_IDENTIFIABLE_MECHANISM_COVERAGE")
        result_code = 30

    if args.purge_raw_after_gate:
        shutil.rmtree(exact)
        shutil.rmtree(workspace / "cache", ignore_errors=True)
        body["raw_sources_purged_after_receipt_copy"] = True
    else:
        body["raw_sources_purged_after_receipt_copy"] = False

    body["final_transition_hash"] = previous_transition
    finalize_receipt(receipts, body)
    print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return result_code


if __name__ == "__main__":
    raise SystemExit(main())
