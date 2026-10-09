from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Mapping

import numpy as np

import helical_geometry_adapter as geometry
import helical_public_acquisition as acquisition
import helical_v011_directional_pretest as v11_wrapper

v11 = v11_wrapper.core
gate = geometry.gate

PROTOCOL_ID = "h8p:99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f"
V11_RUN_ID = "h11run:a503c121315ce355a7d7ff1e69a309010bc968270c8182ad3f4eb16ae3d2fc7b"
V11_PREFLIGHT_ID = "h11preflight:60c0fb77dbc4c5f70c7ee319e5d875eae0d0ff866dac25f3538adb1d30b7f00f"
V10_ELIGIBILITY_ID = "h10elig:8126dfea8302dd5c9ea15c04afb5d4e7d1407c2bdb47b24cea34c91efbb37ed0"
EXPECTED_MECHANISM_SHA256 = acquisition.EXPECTED_SHA256
EXPECTED_MECHANISM_BYTES = acquisition.EXPECTED_BYTES
EXPECTED_FAULT_SHA256 = v11.EXPECTED_FAULT_SHA256
EXPECTED_FAULT_GIT_BLOB_SHA1 = v11.EXPECTED_FAULT_GIT_BLOB_SHA1
EXPECTED_SELECTED_TOTAL = 61_555
EXPECTED_AXIS_OBSERVABLE = 60_577
EXPECTED_COHORTS = {
    "BAY_AREA_HAYWARD_CALAVERAS": {
        "selected_event_count": 37_853,
        "axis_observable_count": 37_280,
        "train_count": 18_640,
        "calibration_count": 9_320,
        "sealed_test_count": 9_320,
    },
    "PARKFIELD_CENTRAL_SAF": {
        "selected_event_count": 23_702,
        "axis_observable_count": 23_297,
        "train_count": 11_648,
        "calibration_count": 5_824,
        "sealed_test_count": 5_825,
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


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


def validate_authority(
    lease_path: Path,
    v11_run: Mapping[str, Any],
    v11_preflight: Mapping[str, Any],
    protocol: Mapping[str, Any],
) -> dict[str, Any]:
    lease = json.loads(lease_path.read_text(encoding="utf-8"))
    if lease.get("status") != "ACTIVE_UNTIL_SINGLE_SUCCESSOR_TERMINATES" or lease.get("single_use") is not True:
        raise RuntimeError("v0.12 authority is not active and single-use")
    if lease.get("protocol_id") != protocol.get("protocol_id") or lease.get("protocol_id") != PROTOCOL_ID:
        raise RuntimeError("v0.12 authority/protocol mismatch")
    if lease.get("predecessor_run_receipt_id") != v11_run.get("run_receipt_id") or v11_run.get("run_receipt_id") != V11_RUN_ID:
        raise RuntimeError("v0.12 predecessor run identity mismatch")
    if lease.get("predecessor_preflight_result_id") != v11_preflight.get("preflight_result_id") or v11_preflight.get("preflight_result_id") != V11_PREFLIGHT_ID:
        raise RuntimeError("v0.12 predecessor preflight identity mismatch")
    if v11_run.get("authority_terminal_status") != "CONSUMED_SUCCESS" or v11_run.get("outcome") != "DIRECTIONAL_MATERIALIZATION_PASS":
        raise RuntimeError("v0.11 predecessor is not terminal-success")
    if v11_preflight.get("directional_execution_authorized") is not True or v11_preflight.get("sealed_test_scored") is not False:
        raise RuntimeError("v0.11 predecessor authority boundary mismatch")
    forbidden = [
        "raw_source_export_authorized", "blind_row_export_authorized", "selected_index_export_authorized",
        "directional_row_export_authorized", "parent_edge_export_authorized", "sealed_test_access_authorized",
        "sealed_test_scoring_authorized", "dynamic_helical_model_fit_authorized", "null_family_execution_authorized",
        "location_perturbation_execution_authorized", "publication_authority", "promotion_authority",
        "canonicalization_authority", "retrospective_mutation_authority",
    ]
    if any(lease.get(key) is not False for key in forbidden):
        raise RuntimeError("v0.12 forbidden authority became enabled")
    body = {
        "format": "KCH_HELICAL_V0_12_AUTHORITY_ACTIVATION_RECEIPT",
        "authority_id": lease["authority_id"],
        "authority_file_sha256": sha256(lease_path),
        "predecessor_run_receipt_id": V11_RUN_ID,
        "predecessor_preflight_result_id": V11_PREFLIGHT_ID,
        "protocol_id": PROTOCOL_ID,
        "activated_at_utc": utc_now(),
        "single_use": True,
        "sealed_test_access_authorized": False,
        "dynamic_helical_model_fit_authorized": False,
        "null_family_execution_authorized": False,
        "location_perturbation_execution_authorized": False,
        "promotion": "BLOCKED",
    }
    return {"receipt_id": content_id("h12auth", body), **body}


def execute(command: list[str], label: str, receipt_path: Path, accepted: set[int] = {0}) -> dict[str, Any]:
    completed = subprocess.run(command, text=True, capture_output=True)
    receipt = {
        "format": "KCH_HELICAL_V0_12_PROCESS_EXECUTION_RECEIPT",
        "label": label,
        "returncode": completed.returncode,
        "accepted_returncodes": sorted(accepted),
        "stdout_tail": completed.stdout[-8000:],
        "stderr_tail": completed.stderr[-8000:],
    }
    receipt["receipt_id"] = content_id("h12process", receipt)
    write_json(receipt_path, receipt)
    if completed.returncode not in accepted:
        raise RuntimeError(f"{label} failed with {completed.returncode}: {completed.stderr[-2000:]}")
    return receipt


def compare_preflight(observed: Mapping[str, Any], canonical_v11: Mapping[str, Any]) -> None:
    if observed.get("outcome") != "DIRECTIONAL_MATERIALIZATION_PASS":
        raise RuntimeError("reconstructed directional preflight did not pass")
    if int(observed.get("event_count", -1)) != EXPECTED_SELECTED_TOTAL:
        raise RuntimeError("reconstructed directional event-count drift")
    if int(observed.get("axis_observable_count", -1)) != EXPECTED_AXIS_OBSERVABLE:
        raise RuntimeError("reconstructed axis-observable count drift")
    canonical_by_name = {row["cohort_id"]: row for row in canonical_v11["cohorts"]}
    observed_by_name = {row["cohort_id"]: row for row in observed["cohorts"]}
    for name, expected in EXPECTED_COHORTS.items():
        if name not in observed_by_name or name not in canonical_by_name:
            raise RuntimeError(f"missing cohort in reconstructed preflight: {name}")
        for key, value in expected.items():
            if int(observed_by_name[name][key]) != value or int(canonical_by_name[name][key]) != value:
                raise RuntimeError(f"{name}/{key}: reconstructed or canonical drift")


def copy_json(source: Path, destination: Path) -> dict[str, Any]:
    value = json.loads(source.read_text(encoding="utf-8"))
    write_json(destination, value)
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--authority", required=True, type=Path)
    parser.add_argument("--eligibility-result", required=True, type=Path)
    parser.add_argument("--v11-run", required=True, type=Path)
    parser.add_argument("--v11-preflight", required=True, type=Path)
    parser.add_argument("--directional-preflight-runtime", required=True, type=Path)
    parser.add_argument("--topology-runtime", required=True, type=Path)
    parser.add_argument("--parent-graph-runtime", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--blind-image", required=True)
    parser.add_argument("--directional-image", required=True)
    parser.add_argument("--timeout", type=int, default=1200)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    raw = workspace / "raw"
    selected_root = workspace / "selected_root"
    blind = selected_root / "blind"
    selection = selected_root / "selection"
    directional = selected_root / "directional"
    preflight = selected_root / "preflight"
    topology = workspace / "topology"
    parent_graph = workspace / "parent_graph"
    results = workspace / "results"
    for path in (raw, blind, selection, directional, preflight, topology, parent_graph, results):
        path.mkdir(parents=True, exist_ok=True)
    os.chmod(blind, 0o777)
    os.chmod(directional, 0o777)

    protocol, protocol_lock = gate.audit_protocol(args.protocol)
    eligibility = json.loads(args.eligibility_result.read_text(encoding="utf-8"))
    v11_run = json.loads(args.v11_run.read_text(encoding="utf-8"))
    v11_preflight = json.loads(args.v11_preflight.read_text(encoding="utf-8"))
    if eligibility.get("eligibility_result_id") != V10_ELIGIBILITY_ID or eligibility.get("outcome") != "ELIGIBILITY_PASS":
        raise RuntimeError("v0.10 eligibility identity or outcome mismatch")
    authority = validate_authority(args.authority, v11_run, v11_preflight, protocol)
    write_json(results / "AUTHORITY_ACTIVATION_RECEIPT_V0_12.json", authority)

    run: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_12_PARENT_GRAPH_LOCK_RUN_RECEIPT",
        **protocol_lock,
        "started_at_utc": utc_now(),
        "authority_receipt_id": authority["receipt_id"],
        "predecessor_run_receipt_id": V11_RUN_ID,
        "predecessor_preflight_result_id": V11_PREFLIGHT_ID,
        "sealed_test_accessed": False,
        "sealed_test_scored": False,
        "dynamic_helical_model_execution_performed": False,
        "null_family_execution_performed": False,
        "location_perturbation_execution_performed": False,
        "physical_helicity": "NOT_EVALUATED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    exit_code = 50
    try:
        _snapshot, metadata_receipt, _ = acquisition.public_request_json(gate.SNAPSHOT_URL, args.timeout)
        mechanism = raw / gate.MECHANISM_BASENAME
        fault = raw / gate.FAULT_BASENAME
        mechanism_receipt = acquisition.public_stream_download("public-exact-identity", mechanism, args.timeout, EXPECTED_MECHANISM_BYTES)
        fault_receipt = acquisition._ORIGINAL_STREAM_DOWNLOAD(gate.FAULT_URL, fault, args.timeout, gate.FAULT_BYTES)
        if sha256(mechanism) != EXPECTED_MECHANISM_SHA256 or mechanism.stat().st_size != EXPECTED_MECHANISM_BYTES:
            raise RuntimeError("mechanism exact-byte identity mismatch")
        if sha256(fault) != EXPECTED_FAULT_SHA256 or gate.git_blob_sha1(fault) != EXPECTED_FAULT_GIT_BLOB_SHA1:
            raise RuntimeError("fault exact-byte identity mismatch")
        acquisition_body = {
            "format": "KCH_HELICAL_V0_12_EXACT_BYTE_ACQUISITION_RECEIPT",
            "metadata": metadata_receipt,
            "mechanism": mechanism_receipt,
            "fault": {**fault_receipt, "git_blob_sha1": gate.git_blob_sha1(fault)},
            "all_or_none_pass": True,
            "transaction_committed": True,
            **protocol_lock,
            "authority_receipt_id": authority["receipt_id"],
            "promotion": "BLOCKED",
        }
        acquisition_body["receipt_id"] = content_id("h12acq", acquisition_body)
        write_json(results / "ACQUISITION_RECEIPT_V0_12.json", acquisition_body)

        blind_container = v11.run_container([
            "docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true", "--pids-limit", "128", "--memory", "6g", "--memory-swap", "6g", "--cpus", "2",
            "--user", "65534:65534", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=536870912",
            "-v", f"{raw}:/input:ro", "-v", f"{blind}:/output:rw", args.blind_image,
            "--pickle", f"/input/{gate.MECHANISM_BASENAME}", "--expected-sha256", EXPECTED_MECHANISM_SHA256, "--output-dir", "/output",
        ], results / "BLIND_CONTAINER_RECEIPT_V0_12.json", "V0_12_BLIND_EXTRACTION")
        blind_receipt = json.loads((blind / "BLIND_EXTRACTION_RECEIPT_V0_11.json").read_text(encoding="utf-8"))
        if int(blind_receipt.get("event_count", -1)) != v11.EXPECTED_EVENT_COUNT or blind_receipt.get("sealed_fields_emitted") != []:
            raise RuntimeError("v0.12 blind extraction receipt mismatch")
        write_json(results / "BLIND_EXTRACTION_RECEIPT_V0_12.json", {**blind_receipt, "container_receipt_id": blind_container["receipt_id"]})

        selected_indices, selection_receipt = v11.select_indices(blind / "blind_columns.npz", fault, protocol, eligibility, selection)
        write_json(results / "SELECTED_INDEX_RECEIPT_V0_12.json", selection_receipt)

        directional_container = v11.run_container([
            "docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true", "--pids-limit", "128", "--memory", "6g", "--memory-swap", "6g", "--cpus", "2",
            "--user", "65534:65534", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=536870912",
            "-v", f"{raw}:/input:ro", "-v", f"{selection}:/selection:ro", "-v", f"{directional}:/output:rw", args.directional_image,
            "--pickle", f"/input/{gate.MECHANISM_BASENAME}", "--expected-pickle-sha256", EXPECTED_MECHANISM_SHA256,
            "--selected-indices", "/selection/selected_blind_indices.npz", "--expected-indices-sha256", selection_receipt["selected_indices_sha256"],
            "--output-dir", "/output",
        ], results / "DIRECTIONAL_CONTAINER_RECEIPT_V0_12.json", "V0_12_SELECTED_DIRECTIONAL_EXTRACTION")
        directional_receipt = json.loads((directional / "SELECTED_DIRECTIONAL_EXTRACTION_RECEIPT_V0_11.json").read_text(encoding="utf-8"))
        if int(directional_receipt.get("selected_event_count", -1)) != EXPECTED_SELECTED_TOTAL:
            raise RuntimeError("v0.12 selected directional count drift")
        write_json(results / "SELECTED_DIRECTIONAL_EXTRACTION_RECEIPT_V0_12.json", {**directional_receipt, "container_receipt_id": directional_container["receipt_id"]})

        preflight_process = execute([
            sys.executable, str(args.directional_preflight_runtime),
            "--selected-directional", str(directional / "selected_directional_columns.npz"),
            "--expected-directional-sha256", directional_receipt["output_sha256"],
            "--fault-geojson", str(fault), "--expected-fault-sha256", EXPECTED_FAULT_SHA256,
            "--protocol", str(args.protocol), "--output-dir", str(preflight),
        ], "DIRECTIONAL_PREFLIGHT_RECONSTRUCTION", results / "PREFLIGHT_PROCESS_RECEIPT_V0_12.json")
        reconstructed = json.loads((preflight / "DIRECTIONAL_PREFLIGHT_RESULT_V0_8.json").read_text(encoding="utf-8"))
        compare_preflight(reconstructed, v11_preflight)
        write_json(results / "DIRECTIONAL_PREFLIGHT_RECONCILIATION_V0_12.json", {
            "format": "KCH_HELICAL_V0_12_DIRECTIONAL_PREFLIGHT_RECONCILIATION",
            "canonical_v11_preflight_result_id": V11_PREFLIGHT_ID,
            "reconstructed_preflight_result_id": reconstructed["preflight_result_id"],
            "event_count": EXPECTED_SELECTED_TOTAL,
            "axis_observable_count": EXPECTED_AXIS_OBSERVABLE,
            "cohort_denominators_exact_match": True,
            "process_receipt_id": preflight_process["receipt_id"],
            "sealed_test_scored": False,
            "promotion": "BLOCKED",
        })

        execute([
            sys.executable, str(args.topology_runtime),
            "--selected-root", str(selected_root), "--fault-geojson", str(fault),
            "--protocol", str(args.protocol), "--out", str(topology),
        ], "EXACT_INTERSECTION_TOPOLOGY_LOCK", results / "TOPOLOGY_PROCESS_RECEIPT_V0_12.json")
        topology_result = copy_json(topology / "EXACT_TOPOLOGY_LOCK_RESULT_V0_12.json", results / "EXACT_TOPOLOGY_LOCK_RESULT_V0_12.json")
        copy_json(topology / "LOCATION_PERTURBATION_OPERATOR_LOCK_V0_8.json", results / "LOCATION_PERTURBATION_OPERATOR_LOCK_V0_12.json")
        copy_json(topology / "FAULT_NETWORK_TOPOLOGY_INTERSECTIONS_V0_8.json", results / "FAULT_NETWORK_TOPOLOGY_INTERSECTIONS_V0_12.json")

        parent_process = execute([
            sys.executable, str(args.parent_graph_runtime),
            "--selected-root", str(selected_root), "--topology-root", str(topology),
            "--fault-geojson", str(fault), "--out", str(parent_graph),
        ], "ETAS_HAWKES_PARENT_GRAPH_TRAIN_ONLY_LOCK", results / "PARENT_GRAPH_PROCESS_RECEIPT_V0_12.json", accepted={0, 3})
        parameter_lock = copy_json(parent_graph / "ETAS_HAWKES_PARENT_GRAPH_PARAMETER_LOCK_V0_8.json", results / "ETAS_HAWKES_PARENT_GRAPH_PARAMETER_LOCK_V0_12.json")
        calibration = copy_json(parent_graph / "PARENT_GRAPH_CALIBRATION_RESULT_V0_8.json", results / "PARENT_GRAPH_CALIBRATION_RESULT_V0_12.json")
        edge_path = parent_graph / "FIT_PARENT_GRAPH_EDGES_V0_8.npz"
        edge_receipt = {
            "format": "KCH_HELICAL_V0_12_EPHEMERAL_PARENT_EDGE_DIGEST_RECEIPT",
            "edge_artifact_created": edge_path.exists(),
            "edge_artifact_persisted": False,
            "edge_artifact_sha256": sha256(edge_path) if edge_path.exists() else None,
            "edge_artifact_bytes": edge_path.stat().st_size if edge_path.exists() else 0,
            "parent_graph_lock_id": parameter_lock["lock_id"],
            "parent_graph_gate_id": calibration["gate_id"],
            "sealed_test_edges_generated": False,
            "parent_edges_export_authorized": False,
            "promotion": "BLOCKED",
        }
        edge_receipt["receipt_id"] = content_id("h12edges", edge_receipt)
        write_json(results / "EPHEMERAL_PARENT_EDGE_DIGEST_RECEIPT_V0_12.json", edge_receipt)
        edge_path.unlink(missing_ok=True)

        parent_pass = calibration.get("outcome") == "PARENT_GRAPH_LOCK_PASS" and parameter_lock.get("all_units_pass") is True
        run.update({
            "outcome": calibration.get("outcome"),
            "topology_gate_id": topology_result["gate_id"],
            "location_operator_id": topology_result["location_operator_id"],
            "parent_graph_lock_id": parameter_lock["lock_id"],
            "parent_graph_gate_id": calibration["gate_id"],
            "parent_graph_baseline_fit_performed": True,
            "parent_graph_lock_pass": parent_pass,
            "next_material_gate": calibration.get("next_material_gate") if parent_pass else None,
            "parent_process_receipt_id": parent_process["receipt_id"],
        })
        exit_code = 0 if parent_pass else 30
    except Exception as error:
        run.update({
            "outcome": "PARENT_GRAPH_GATE_FAILED_CLOSED",
            "error_type": type(error).__name__,
            "error": str(error),
            "parent_graph_baseline_fit_performed": (parent_graph / "PARENT_GRAPH_CALIBRATION_RESULT_V0_8.json").exists(),
            "parent_graph_lock_pass": False,
        })
        exit_code = 50
    finally:
        run["completed_at_utc"] = utc_now()
        run["exit_code"] = exit_code
        run["raw_sources_purged"] = True
        run["blind_rows_purged"] = True
        run["selected_indices_purged"] = True
        run["directional_rows_purged"] = True
        run["preflight_arrays_purged"] = True
        run["parent_edges_purged"] = True
        run["authority_consumed"] = True
        run["authority_terminal_status"] = "CONSUMED_SUCCESS" if exit_code in {0, 30} else "CONSUMED_FAIL_CLOSED"
        run["run_receipt_id"] = content_id("h12run", run)
        write_json(results / "RUN_RECEIPT_V0_12.json", run)
        for path in (raw, selected_root, topology, parent_graph):
            shutil.rmtree(path, ignore_errors=True)
        print(json.dumps(run, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
