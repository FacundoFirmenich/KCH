from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
from typing import Any
import uuid

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


def validate_transition_chain(path: Path) -> tuple[int, str | None]:
    previous: str | None = None
    count = 0
    if path.exists():
        with path.open("r", encoding="utf-8") as handle:
            for count, line in enumerate(handle, start=1):
                event = json.loads(line)
                observed = event.pop("event_hash", None)
                expected = hashlib.sha256(canonical_json_bytes(event)).hexdigest()
                if event.get("sequence") != count or event.get("previous_hash") != previous or observed != expected:
                    raise ValueError(f"invalid transition chain at sequence {count}")
                previous = observed
    return count, previous


def append_transition(path: Path, transition: dict[str, Any], previous_hash: str | None) -> str:
    count, observed_previous = validate_transition_chain(path)
    if observed_previous != previous_hash:
        raise ValueError("transition predecessor differs from verified chain tail")
    if {"sequence", "previous_hash", "event_hash"} & transition.keys():
        raise ValueError("transition may not override chain bookkeeping")
    body = {
        "sequence": count + 1,
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


def verify_content_id(value: dict[str, Any], key: str, prefix: str) -> None:
    body = dict(value)
    observed = body.pop(key, None)
    if observed != content_id(prefix, body):
        raise ValueError(f"invalid {key} content address")


def archive_previous_run(receipts: Path) -> Path | None:
    names = ("GATE_EXECUTION_RECEIPT_V0_9.json", "ACQUISITION_ATTEMPT_V0_9.json",
             "ACQUISITION_RECEIPT_V0_9.json", "RAW_SOURCE_CLEANUP_RECEIPT_V0_9_2.json", "logs")
    existing = [receipts / name for name in names if (receipts / name).exists()]
    if not existing:
        return None
    gate_path = receipts / names[0]
    cleanup_path = receipts / "RAW_SOURCE_CLEANUP_RECEIPT_V0_9_2.json"
    if gate_path.exists():
        previous = json.loads(gate_path.read_text(encoding="utf-8"))
        verify_content_id(previous, "gate_receipt_id", "h9gate")
        fallback_name = previous["gate_receipt_id"].replace(":", "-")
    elif cleanup_path.exists():
        previous = json.loads(cleanup_path.read_text(encoding="utf-8"))
        verify_content_id(previous, "receipt_id", "h9cleanup")
        fallback_name = previous["receipt_id"].replace(":", "-")
    else:
        raise ValueError("cannot archive prior execution files without a valid gate/cleanup receipt identity")
    execution_id = previous.get("execution_id", "")
    archive_name = execution_id if isinstance(execution_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", execution_id) else fallback_name
    destination = receipts / "history" / archive_name
    destination.mkdir(parents=True, exist_ok=False)
    for path in existing:
        os.replace(path, destination / path.name)
    return destination


def validate_semantic_hold(hold: dict[str, Any], mechanism_sha: str, npz_sha: str) -> None:
    verify_content_id(hold, "receipt_id", "h9semantichold")
    if hold.get("format") != "KCH_HELICAL_BLIND_INPUT_SEMANTIC_HOLD_V0_9_2":
        raise ValueError("unexpected semantic HOLD format")
    if hold.get("outcome") not in {"BLOCKED_UNCERTIFIED_EVENT_TYPE_ENCODING", "BLOCKED_BLIND_INPUT_SEMANTICS"}:
        raise ValueError("unexpected semantic HOLD outcome")
    if (hold.get("protocol_id"), hold.get("source_sha256"), hold.get("safe_npz_sha256")) != (PROTOCOL_ID, mechanism_sha, npz_sha):
        raise ValueError("semantic HOLD input lineage mismatch")
    if hold.get("authority_ceiling") != "NONE" or any(hold.get(key) is not False for key in (
        "scientific_eligibility_executed", "directional_fields_unsealed", "model_fitting_performed",
    )):
        raise ValueError("semantic HOLD authority/barrier mismatch")


def validate_eligibility_result(result: dict[str, Any], returncode: int, acquisition: dict[str, Any],
                                extraction: dict[str, Any], npz_receipt: dict[str, Any]) -> None:
    expected_outcome = {0: "ELIGIBILITY_PASS", 30: "NOT_IDENTIFIABLE_MECHANISM_COVERAGE"}.get(returncode)
    if expected_outcome is None or result.get("outcome") != expected_outcome:
        raise ValueError("eligibility result and process returncode disagree")
    if result.get("execution_authorized") is not (returncode == 0):
        raise ValueError("eligibility authority and process returncode disagree")
    verify_content_id(result, "transport_receipt_id", "h9eligtransport")
    original_keys = ("format", "protocol_id", "angle_fields_accessed", "sealed_fields", "candidate_results",
                     "selected_primary_cohorts", "execution_authorized", "outcome", "authority_ceiling")
    original = {key: result[key] for key in original_keys}
    if result.get("eligibility_result_id") != content_id("h8elig", original):
        raise ValueError("invalid scientific eligibility content address")
    if result.get("format") != "KCH_HELICAL_V0_8_BLIND_ELIGIBILITY_RESULT" or result.get("protocol_id") != PROTOCOL_ID:
        raise ValueError("eligibility result protocol/format mismatch")
    if result.get("authority_ceiling") != "NONE" or any(result.get(key) is not False for key in (
        "angle_fields_accessed", "directional_unsealing_performed", "model_fitting_performed",
    )):
        raise ValueError("eligibility result authority/barrier mismatch")
    transport = result.get("transport_successor", {})
    expected = {
        "protocol_id": PROTOCOL_ID, "protocol_file_sha256": PROTOCOL_FILE_SHA256,
        "safe_npz_sha256": extraction.get("output_sha256"),
        "extraction_receipt_id": extraction.get("receipt_id"),
        "safe_npz_verification_receipt_id": npz_receipt.get("receipt_id"),
        "acquisition_receipt_id": acquisition.get("receipt_id"),
        "mechanism_sha256": acquisition["source_receipts"]["mechanism"]["sha256"],
        "fault_sha256": acquisition["source_receipts"]["fault"]["sha256"],
        "fault_git_blob_sha1": acquisition["source_receipts"]["fault"]["git_blob_sha1"],
    }
    if any(transport.get(key) != value for key, value in expected.items()):
        raise ValueError("eligibility result input lineage mismatch")


def validate_unseal_request(request: dict[str, Any], result: dict[str, Any], acquisition: dict[str, Any],
                            extraction: dict[str, Any]) -> None:
    verify_content_id(request, "request_id", "h9unsealrequest")
    expected = {
        "format": "KCH_HELICAL_V0_9_DIRECTIONAL_UNSEAL_SUCCESSOR_REQUEST",
        "scientific_protocol_id": PROTOCOL_ID,
        "eligibility_result_id": result.get("eligibility_result_id"),
        "eligibility_transport_receipt_id": result.get("transport_receipt_id"),
        "selected_primary_cohorts": result.get("selected_primary_cohorts"),
        "acquisition_receipt_id": acquisition.get("receipt_id"),
        "extraction_receipt_id": extraction.get("receipt_id"),
        "protocol_file_sha256": PROTOCOL_FILE_SHA256,
        "authority_ceiling": "NONE",
    }
    if any(request.get(key) != value for key, value in expected.items()):
        raise ValueError("directional successor request lineage mismatch")
    if any(request.get(key) is not False for key in (
        "directional_unsealing_performed", "model_fitting_authorized", "scientific_interpretation_authorized",
    )) or any(request.get(key) is not True for key in ("requires_new_finite_authority", "requires_new_append_only_successor")):
        raise ValueError("directional successor request authority mismatch")


def _run_gate(args: argparse.Namespace) -> int:

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
    _, previous_transition = validate_transition_chain(transitions_path)
    previous_archive = archive_previous_run(receipts)
    steps: list[dict[str, Any]] = []
    started_at = utc_now()
    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_9_EXACT_BYTE_TO_BLIND_GATE_EXECUTION",
        "started_at_utc": started_at,
        "runtime_version": "0.9.2",
        "execution_id": args.execution_id,
        "raw_source_cleanup_requested": bool(args.purge_raw_after_gate),
        "previous_execution_archive": str(previous_archive) if previous_archive is not None else None,
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
    if eligibility_dir.exists():
        body.setdefault("quarantined", []).append(str(quarantine(eligibility_dir, workspace)))
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
    hold_path = eligibility_dir / "BLIND_INPUT_SEMANTIC_HOLD_V0_9_2.json"
    try:
        if eligibility_step["returncode"] == 31:
            if eligibility_path.exists():
                raise ValueError("HOLD process also emitted an eligibility result")
            hold = json.loads(hold_path.read_text(encoding="utf-8"))
            validate_semantic_hold(hold, mechanism_sha, extraction["output_sha256"])
            previous_transition = append_transition(
                transitions_path,
                {"at_utc": utc_now(), "state": hold["outcome"], "semantic_hold_receipt_id": hold["receipt_id"]},
                previous_transition,
            )
            body["outcome"] = hold["outcome"]
            body["semantic_hold_receipt_id"] = hold["receipt_id"]
            body["scientific_eligibility_executed"] = False
            body["final_transition_hash"] = previous_transition
            finalize_receipt(receipts, body)
            print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2))
            return 31
        if eligibility_step["returncode"] not in (0, 30):
            raise ValueError(f"unexpected eligibility process returncode {eligibility_step['returncode']}")
        if hold_path.exists():
            raise ValueError("eligibility process emitted both result and semantic HOLD")
        eligibility = json.loads(eligibility_path.read_text(encoding="utf-8"))
        validate_eligibility_result(eligibility, eligibility_step["returncode"], acquisition, extraction, npz_receipt)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        previous_transition = append_transition(
            transitions_path,
            {"at_utc": utc_now(), "state": "BLIND_ELIGIBILITY_EXECUTION_FAILURE", "returncode": eligibility_step["returncode"]},
            previous_transition,
        )
        body["outcome"] = "BLIND_ELIGIBILITY_EXECUTION_FAILURE"
        body["failure_reason"] = sanitize_text(str(exc))
        body["final_transition_hash"] = previous_transition
        finalize_receipt(receipts, body)
        print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2))
        return 21

    body["scientific_eligibility_executed"] = True
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
        if request_path.exists():
            body.setdefault("quarantined", []).append(str(quarantine(request_path, workspace)))
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
        try:
            if request_step["returncode"] != 0:
                raise ValueError(f"unseal request process returncode {request_step['returncode']}")
            request = json.loads(request_path.read_text(encoding="utf-8"))
            validate_unseal_request(request, eligibility, acquisition, extraction)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            body["outcome"] = "ELIGIBILITY_PASS_UNSEAL_REQUEST_FAILED"
            body["failure_reason"] = sanitize_text(str(exc))
            result_code = 22
        else:
            body["directional_unseal_request_id"] = request.get("request_id")
            body["outcome"] = "ELIGIBILITY_PASS_DIRECTIONAL_UNSEAL_REQUEST_READY"
            result_code = 0
    else:
        body["outcome"] = eligibility.get("outcome", "NOT_IDENTIFIABLE_MECHANISM_COVERAGE")
        result_code = 30

    body["final_transition_hash"] = previous_transition
    finalize_receipt(receipts, body)
    print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return result_code


def purge_raw_sources(workspace: Path, execution_id: str) -> bool:
    """Runs on every exit, with a standalone receipt even if the gate aborted early."""
    errors: dict[str, str] = {}
    observed_before: dict[str, bool] = {}
    names = ["exact_sources", "cache"] + [path.name for path in sorted(workspace.glob(".exact_sources_v09.*"))]
    for name in names:
        path = workspace / name
        observed_before[name] = path.exists() or path.is_symlink()
        try:
            if path.is_symlink():
                path.unlink()
            elif path.is_dir():
                shutil.rmtree(path)
            elif path.exists():
                path.unlink()
        except OSError as exc:
            errors[name] = sanitize_text(str(exc))
    remaining = [name for name in observed_before if (workspace / name).exists() or (workspace / name).is_symlink()]
    gate_id = None
    gate_path = workspace / "receipts" / "GATE_EXECUTION_RECEIPT_V0_9.json"
    try:
        gate = json.loads(gate_path.read_text(encoding="utf-8"))
        if gate.get("execution_id") == execution_id:
            verify_content_id(gate, "gate_receipt_id", "h9gate")
            gate_id = gate["gate_receipt_id"]
    except (OSError, ValueError, TypeError):
        pass
    cleanup = {
        "format": "KCH_HELICAL_RAW_SOURCE_CLEANUP_V0_9_2",
        "execution_id": execution_id,
        "completed_at_utc": utc_now(),
        "status": "PASS" if not errors and not remaining else "FAIL",
        "paths_present_before_cleanup": observed_before,
        "paths_remaining_after_cleanup": remaining,
        "errors": errors,
        "gate_receipt_id": gate_id,
        "complete_gate_receipt_available": gate_id is not None,
        "authority_ceiling": "NONE",
    }
    cleanup["receipt_id"] = content_id("h9cleanup", cleanup)
    write_json_atomic(workspace / "receipts" / "RAW_SOURCE_CLEANUP_RECEIPT_V0_9_2.json", cleanup)
    return cleanup["status"] == "PASS"


def main() -> int:
    parser = argparse.ArgumentParser(description="One transactional route from exact public bytes to blind eligibility; no directional unsealing or model fit")
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--execute-network", action="store_true")
    parser.add_argument("--network-timeout-seconds", type=int, default=300)
    parser.add_argument("--sandbox-timeout-seconds", type=int, default=2700)
    parser.add_argument("--sandbox-memory-mib", type=int, default=8192)
    parser.add_argument("--purge-raw-after-gate", action="store_true")
    args = parser.parse_args()
    args.execution_id = uuid.uuid4().hex
    cleanup_ok = True
    try:
        result_code = _run_gate(args)
    finally:
        if args.purge_raw_after_gate:
            cleanup_ok = purge_raw_sources(args.workspace.resolve(), args.execution_id)
    return result_code if cleanup_ok else 23


if __name__ == "__main__":
    raise SystemExit(main())
