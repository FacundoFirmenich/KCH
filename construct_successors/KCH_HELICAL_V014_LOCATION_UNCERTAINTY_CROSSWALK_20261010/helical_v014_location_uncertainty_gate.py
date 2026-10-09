from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Mapping

import numpy as np

import helical_geometry_adapter as geometry
import helical_public_acquisition as acquisition
import helical_v011_directional_pretest as v11

GATE = geometry.gate
CORE = v11.core
EXPECTED_FAULT_SHA256 = "37babb516edfac22b5ae91744495d8546b3ae4676b4d4f68cc77da8222df20e1"
EXPECTED_ELIGIBILITY_ID = "h10elig:8126dfea8302dd5c9ea15c04afb5d4e7d1407c2bdb47b24cea34c91efbb37ed0"
EXPECTED_PARENT_RUN_ID = "h12run:34cae48f62b3909ffd032e8259cf15d85c4fd738dd67847ee766bb7124627089"
EXPECTED_LOCATION_OPERATOR_ID = "h12locop:6b3fcf56d1f427d107e5e5dbb264aba02f871c93708a5796074fd0916d89b1b5"
EXPECTED_SCHEMA_RESULT_ID = "h132schema:8dc7030b5c46ffa67b5acb94ba294c8c050767c153565fbb1a6431d6d0143b1a"
EXPECTED_SELECTED = 61_555
EXPECTED_COUNTS = {
    "BAY_AREA_HAYWARD_CALAVERAS": 37_853,
    "PARKFIELD_CENTRAL_SAF": 23_702,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def content_id(prefix: str, value: Any) -> str:
    return prefix + ":" + hashlib.sha256(canonical(value)).hexdigest()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def validate_authority(path: Path, protocol: Mapping[str, Any], eligibility: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    lease = json.loads(path.read_text(encoding="utf-8"))
    if lease.get("status") != "ACTIVE_UNTIL_SINGLE_SUCCESSOR_TERMINATES" or lease.get("single_use") is not True:
        raise RuntimeError("v0.14 authority is not active and single-use")
    exact = {
        "scope": "EXACT_COMCAT_LOCATION_UNCERTAINTY_CROSSWALK_ONLY",
        "protocol_id": protocol.get("protocol_id"),
        "upstream_eligibility_result_id": eligibility.get("eligibility_result_id"),
        "upstream_parent_graph_run_receipt_id": EXPECTED_PARENT_RUN_ID,
        "upstream_location_operator_id": EXPECTED_LOCATION_OPERATOR_ID,
        "upstream_exact_source_schema_result_id": EXPECTED_SCHEMA_RESULT_ID,
    }
    for key, expected in exact.items():
        if lease.get(key) != expected:
            raise RuntimeError(f"authority lineage mismatch at {key}: {lease.get(key)!r} != {expected!r}")
    forbidden = (
        "raw_source_export_authorized", "selected_row_export_authorized", "crosswalk_row_export_authorized",
        "directional_unsealing_authorized", "sealed_test_access_authorized", "sealed_test_scoring_authorized",
        "scientific_model_fit_authorized", "null_runtime_execution_authorized", "publication_authority",
        "promotion_authority", "canonicalization_authority", "retrospective_mutation_authority",
    )
    for key in forbidden:
        if lease.get(key) is not False:
            raise RuntimeError(f"authority boundary drift at {key}")
    receipt = {
        "format": "KCH_HELICAL_V0_14_AUTHORITY_ACTIVATION_RECEIPT",
        "authority_id": lease["authority_id"],
        "authority_file_sha256": sha256(path),
        "scope": lease["scope"],
        "protocol_id": protocol["protocol_id"],
        "eligibility_result_id": eligibility["eligibility_result_id"],
        "location_operator_id": EXPECTED_LOCATION_OPERATOR_ID,
        "activated_at_utc": utc_now(),
        "single_use": True,
        "sealed_test_access_authorized": False,
        "scientific_model_fit_authorized": False,
        "promotion": "BLOCKED",
    }
    return lease, {"receipt_id": content_id("h14auth", receipt), **receipt}


def validate_eligibility(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("eligibility_result_id") != EXPECTED_ELIGIBILITY_ID or value.get("outcome") != "ELIGIBILITY_PASS":
        raise RuntimeError("upstream eligibility result mismatch")
    if value.get("selected_primary_cohorts") != list(EXPECTED_COUNTS):
        raise RuntimeError("upstream selected cohort order mismatch")
    observed = {row["candidate_id"]: int(row["unambiguous_fault_assigned_count"]) for row in value["candidate_results"]}
    for cohort, expected in EXPECTED_COUNTS.items():
        if observed.get(cohort) != expected:
            raise RuntimeError(f"upstream selected count mismatch for {cohort}")
    return value


def acquire_exact(raw: Path, timeout: int) -> dict[str, Any]:
    raw.mkdir(parents=True, exist_ok=True)
    snapshot, metadata_receipt, _ = acquisition.public_request_json(GATE.SNAPSHOT_URL, timeout)
    if snapshot.get("id") != GATE.DATASET_ID or int(snapshot.get("version")) != GATE.DATASET_VERSION:
        raise RuntimeError("exact mechanism metadata identity drift")
    mechanism = raw / GATE.MECHANISM_BASENAME
    mechanism_receipt = acquisition.public_stream_download(
        acquisition.EXPECTED_DOWNLOAD_URL,
        mechanism,
        timeout,
        acquisition.EXPECTED_BYTES,
    )
    fault = raw / GATE.FAULT_BASENAME
    fault_receipt = acquisition.public_stream_download(GATE.FAULT_URL, fault, timeout, GATE.FAULT_BYTES)
    if sha256(mechanism) != acquisition.EXPECTED_SHA256 or mechanism.stat().st_size != acquisition.EXPECTED_BYTES:
        raise RuntimeError("exact mechanism payload identity mismatch")
    if sha256(fault) != EXPECTED_FAULT_SHA256:
        raise RuntimeError("fault GeoJSON SHA-256 mismatch")
    if GATE.git_blob_sha1(fault) != GATE.FAULT_GIT_BLOB_SHA1:
        raise RuntimeError("fault GeoJSON Git blob identity mismatch")
    receipt = {
        "format": "KCH_HELICAL_V0_14_EXACT_SOURCE_ACQUISITION_RECEIPT",
        "mechanism": {
            "bytes": mechanism.stat().st_size,
            "sha256": sha256(mechanism),
            "provider_identity_match": mechanism_receipt.get("provider_identity_match"),
            "file_id": mechanism_receipt.get("file_id"),
            "content_id": mechanism_receipt.get("content_id"),
        },
        "fault_network": {
            "bytes": fault.stat().st_size,
            "sha256": sha256(fault),
            "git_blob_sha1": GATE.git_blob_sha1(fault),
            "commit": GATE.FAULT_COMMIT,
            "path": GATE.FAULT_PATH,
        },
        "metadata_adapter": metadata_receipt.get("adapter"),
        "credentials_supplied": False,
        "raw_source_export_authorized": False,
        "authority_ceiling": "EXACT_COMCAT_LOCATION_UNCERTAINTY_CROSSWALK_ONLY",
    }
    return {"receipt_id": content_id("h14acq", receipt), **receipt, "_mechanism_path": mechanism, "_fault_path": fault}


def blind_extract(image: str, mechanism: Path, output: Path, timeout: int) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    os.chmod(output, 0o777)
    command = [
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
        "--pids-limit", "128", "--memory", "6g", "--memory-swap", "6g", "--cpus", "2",
        "--user", "65534:65534", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=268435456",
        "-v", f"{mechanism.parent}:/input:ro", "-v", f"{output}:/output:rw",
        image,
        "--pickle", f"/input/{mechanism.name}",
        "--expected-sha256", acquisition.EXPECTED_SHA256,
        "--output-dir", "/output",
    ]
    started = time.monotonic()
    completed = subprocess.run(command, text=True, capture_output=True, timeout=timeout)
    process = {
        "format": "KCH_HELICAL_V0_14_BLIND_CONTAINER_RECEIPT",
        "image": image,
        "image_id": subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", image], text=True).strip(),
        "returncode": completed.returncode,
        "elapsed_seconds": time.monotonic() - started,
        "network_mode": "NONE",
        "read_only_root": True,
        "capabilities_dropped": "ALL",
        "no_new_privileges": True,
        "non_root_uid": 65534,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }
    process["receipt_id"] = content_id("h14blindcontainer", process)
    if completed.returncode != 0:
        raise RuntimeError(f"networkless blind extraction failed: {completed.stderr[-1500:]}")
    extraction_path = output / "BLIND_EXTRACTION_RECEIPT_V0_11.json"
    blind_npz = output / "blind_columns.npz"
    extraction = json.loads(extraction_path.read_text(encoding="utf-8"))
    if extraction.get("directional_fields_accessed") is not False or extraction.get("sealed_fields_emitted") != []:
        raise RuntimeError("blind extraction firewall violation")
    if extraction.get("event_count") != CORE.EXPECTED_EVENT_COUNT:
        raise RuntimeError("blind catalog event-count drift")
    if sha256(blind_npz) != extraction.get("output_sha256"):
        raise RuntimeError("blind NPZ hash mismatch")
    with np.load(blind_npz, allow_pickle=False) as loaded:
        if set(loaded.files) & CORE.REMAINING_SEALED:
            raise RuntimeError("sealed field present in blind NPZ")
        if any(loaded[name].dtype.hasobject or loaded[name].dtype.kind == "O" for name in loaded.files):
            raise RuntimeError("unsafe object array in blind NPZ")
    return {"container": process, "extraction": extraction, "npz": blind_npz}


def reconstruct_selection(blind_npz: Path, fault: Path, protocol: Mapping[str, Any], eligibility: Mapping[str, Any], output: Path) -> tuple[Path, dict[str, Any]]:
    selected_npz, legacy = CORE.select_indices(blind_npz, fault, protocol, eligibility, output)
    counts = {row["cohort_id"]: int(row["selected_count"]) for row in legacy["cohorts"]}
    if int(legacy["selected_total"]) != EXPECTED_SELECTED or counts != EXPECTED_COUNTS:
        raise RuntimeError("selected non-directional reconstruction drift")
    successor = {
        "format": "KCH_HELICAL_V0_14_SELECTED_NONDIRECTIONAL_RECONSTRUCTION_RECEIPT",
        "protocol_id": protocol["protocol_id"],
        "eligibility_result_id": eligibility["eligibility_result_id"],
        "operator_source": "V0_11_SELECT_INDICES_EXACT_REUSE_WITH_NARROWER_V0_14_AUTHORITY",
        "legacy_operator_receipt_id": legacy["receipt_id"],
        "blind_npz_sha256": sha256(blind_npz),
        "fault_geojson_sha256": sha256(fault),
        "selected_indices_sha256": sha256(selected_npz),
        "selected_indices_bytes": selected_npz.stat().st_size,
        "selected_total": EXPECTED_SELECTED,
        "cohort_counts": counts,
        "directional_fields_accessed": False,
        "sealed_test_accessed": False,
        "row_values_persisted": False,
        "authority_ceiling": "EXACT_COMCAT_LOCATION_UNCERTAINTY_CROSSWALK_ONLY",
        "promotion": "BLOCKED",
    }
    return selected_npz, {"receipt_id": content_id("h14select", successor), **successor}


def run_crosswalk(runtime: Path, blind_npz: Path, selected_npz: Path, output: Path, timeout: int) -> tuple[int, dict[str, Any], dict[str, Any]]:
    output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    completed = subprocess.run(
        [
            "python", str(runtime),
            "--blind-npz", str(blind_npz),
            "--selected-indices", str(selected_npz),
            "--output", str(output),
            "--timeout", str(timeout),
        ],
        text=True,
        capture_output=True,
    )
    process = {
        "format": "KCH_HELICAL_V0_14_CROSSWALK_PROCESS_RECEIPT",
        "runtime_sha256": sha256(runtime),
        "returncode": completed.returncode,
        "elapsed_seconds": time.monotonic() - started,
        "stdout_tail": completed.stdout[-6000:],
        "stderr_tail": completed.stderr[-6000:],
        "network_scope": "PUBLIC_USGS_COMCAT_QUERY_ONLY",
        "credentials_supplied": False,
    }
    process["receipt_id"] = content_id("h14crossprocess", process)
    if completed.returncode not in {0, 30}:
        raise RuntimeError(f"ComCat crosswalk failed: {completed.stderr[-2000:]}")
    result = json.loads((output / "COMCAT_LOCATION_UNCERTAINTY_GATE_RESULT_V0_14.json").read_text(encoding="utf-8"))
    expected = "LOCATION_UNCERTAINTY_CROSSWALK_PASS" if completed.returncode == 0 else "NOT_IDENTIFIABLE_LOCATION_UNCERTAINTY_COVERAGE"
    if result.get("outcome") != expected:
        raise RuntimeError("crosswalk result/exit-code mismatch")
    if result.get("directional_fields_accessed") is not False or result.get("sealed_test_accessed") is not False:
        raise RuntimeError("crosswalk breached directional/test firewall")
    return completed.returncode, result, process


def aggregate_query_summary(path: Path) -> dict[str, Any]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    per_cohort: dict[str, dict[str, Any]] = {}
    for row in rows:
        cohort = str(row["cohort"])
        state = per_cohort.setdefault(cohort, {"query_count": 0, "feature_count_sum": 0, "response_bytes_sum": 0, "response_sha256s": []})
        state["query_count"] += 1
        state["feature_count_sum"] += int(row["feature_count"])
        state["response_bytes_sum"] += int(row["bytes"])
        state["response_sha256s"].append(row["sha256"])
    body = {
        "format": "KCH_HELICAL_V0_14_COMCAT_QUERY_SUMMARY_RECEIPT",
        "query_receipts_sha256": sha256(path),
        "query_count": len(rows),
        "per_cohort": per_cohort,
        "query_values_persisted": False,
        "row_values_persisted": False,
        "credentials_supplied": False,
    }
    return {"receipt_id": content_id("h14querysummary", body), **body}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--authority", required=True, type=Path)
    parser.add_argument("--eligibility-result", required=True, type=Path)
    parser.add_argument("--crosswalk-runtime", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--blind-image", required=True)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    raw = workspace / "raw"
    blind = workspace / "blind"
    selection = workspace / "selection"
    crosswalk = workspace / "crosswalk"
    results = workspace / "results"
    results.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    exit_code = 50
    outcome = "FAIL_CLOSED"
    run: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_14_LOCATION_UNCERTAINTY_RUN_RECEIPT",
        "started_at_utc": started,
        "sealed_test_accessed": False,
        "sealed_test_scored": False,
        "directional_fields_accessed": False,
        "scientific_model_execution_performed": False,
        "null_runtime_execution_performed": False,
        "physical_helicity": "NOT_EVALUATED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    authority_receipt: dict[str, Any] | None = None
    try:
        protocol, protocol_lock = GATE.audit_protocol(args.protocol)
        eligibility = validate_eligibility(args.eligibility_result)
        _, authority_receipt = validate_authority(args.authority, protocol, eligibility)
        acquisition_receipt = acquire_exact(raw, args.timeout)
        mechanism = acquisition_receipt.pop("_mechanism_path")
        fault = acquisition_receipt.pop("_fault_path")
        extracted = blind_extract(args.blind_image, mechanism, blind, args.timeout * 5)
        selected_npz, selection_receipt = reconstruct_selection(extracted["npz"], fault, protocol, eligibility, selection)
        crosswalk_code, gate_result, crosswalk_process = run_crosswalk(
            args.crosswalk_runtime,
            extracted["npz"],
            selected_npz,
            crosswalk,
            args.timeout,
        )
        query_summary = aggregate_query_summary(crosswalk / "COMCAT_QUERY_RECEIPTS_V0_14.json")
        write_json(results / "AUTHORITY_ACTIVATION_RECEIPT_V0_14.json", authority_receipt)
        write_json(results / "EXACT_SOURCE_ACQUISITION_RECEIPT_V0_14.json", acquisition_receipt)
        write_json(results / "BLIND_CONTAINER_RECEIPT_V0_14.json", extracted["container"])
        safe_extraction = {
            key: value for key, value in extracted["extraction"].items()
            if key not in {"stdout", "stderr"}
        }
        write_json(results / "BLIND_EXTRACTION_RECEIPT_V0_14.json", safe_extraction)
        write_json(results / "SELECTED_NONDIRECTIONAL_RECONSTRUCTION_RECEIPT_V0_14.json", selection_receipt)
        write_json(results / "COMCAT_QUERY_SUMMARY_RECEIPT_V0_14.json", query_summary)
        write_json(results / "COMCAT_CROSSWALK_PROCESS_RECEIPT_V0_14.json", crosswalk_process)
        write_json(results / "COMCAT_LOCATION_UNCERTAINTY_GATE_RESULT_V0_14.json", gate_result)
        outcome = gate_result["outcome"]
        exit_code = crosswalk_code
        run.update({
            **protocol_lock,
            "outcome": outcome,
            "exit_code": exit_code,
            "authority_receipt_id": authority_receipt["receipt_id"],
            "acquisition_receipt_id": acquisition_receipt["receipt_id"],
            "selection_receipt_id": selection_receipt["receipt_id"],
            "query_summary_receipt_id": query_summary["receipt_id"],
            "crosswalk_process_receipt_id": crosswalk_process["receipt_id"],
            "location_uncertainty_gate_id": gate_result["gate_id"],
            "selected_event_count": EXPECTED_SELECTED,
            "crosswalk_row_count": gate_result["crosswalk_row_count"],
            "next_material_gate": (
                "CALIBRATION_ONLY_FULL_RUNTIME_QUALIFICATION_NO_TEST_ACCESS"
                if outcome == "LOCATION_UNCERTAINTY_CROSSWALK_PASS"
                else "STOP_SPECIFICATION_NOT_IDENTIFIABLE_LOCATION_UNCERTAINTY_COVERAGE"
            ),
        })
    except Exception as exc:
        run.update({"outcome": "FAIL_CLOSED", "exit_code": 50, "error_type": type(exc).__name__, "error": str(exc)})
        exit_code = 50
    finally:
        purge_before = {}
        for name, path in (("raw", raw), ("blind", blind), ("selection", selection), ("crosswalk", crosswalk)):
            if path.exists():
                purge_before[name] = {"exists": True, "files": sum(1 for item in path.rglob("*") if item.is_file())}
                shutil.rmtree(path)
            else:
                purge_before[name] = {"exists": False, "files": 0}
        purge = {
            "format": "KCH_HELICAL_V0_14_EPHEMERAL_PURGE_RECEIPT",
            "before": purge_before,
            "after": {name: path.exists() for name, path in (("raw", raw), ("blind", blind), ("selection", selection), ("crosswalk", crosswalk))},
            "raw_sources_purged": not raw.exists(),
            "blind_rows_purged": not blind.exists(),
            "selected_indices_purged": not selection.exists(),
            "crosswalk_rows_purged": not crosswalk.exists(),
            "row_values_persisted": False,
            "sealed_test_values_persisted": False,
        }
        purge["receipt_id"] = content_id("h14purge", purge)
        write_json(results / "EPHEMERAL_PURGE_RECEIPT_V0_14.json", purge)
        run.update({
            "completed_at_utc": utc_now(),
            "authority_consumed": authority_receipt is not None,
            "authority_terminal_status": "CONSUMED_SUCCESS" if exit_code in {0, 30} else "CONSUMED_FAIL_CLOSED",
            "raw_sources_purged": purge["raw_sources_purged"],
            "blind_rows_purged": purge["blind_rows_purged"],
            "selected_indices_purged": purge["selected_indices_purged"],
            "crosswalk_rows_purged": purge["crosswalk_rows_purged"],
            "purge_receipt_id": purge["receipt_id"],
        })
        run["run_receipt_id"] = content_id("h14run", run)
        write_json(results / "RUN_RECEIPT_V0_14.json", run)
        print(json.dumps(run, ensure_ascii=False, sort_keys=True, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
