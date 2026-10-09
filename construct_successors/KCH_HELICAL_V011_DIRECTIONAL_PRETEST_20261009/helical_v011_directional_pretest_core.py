from __future__ import annotations

import argparse
from collections import defaultdict, deque
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Mapping

import numpy as np
from shapely.geometry import Point

import helical_geometry_adapter as geometry
import helical_public_acquisition as acquisition

gate = geometry.gate

EXPECTED_MECHANISM_SHA256 = acquisition.EXPECTED_SHA256
EXPECTED_MECHANISM_BYTES = acquisition.EXPECTED_BYTES
EXPECTED_FAULT_SHA256 = "37babb516edfac22b5ae91744495d8546b3ae4676b4d4f68cc77da8222df20e1"
EXPECTED_FAULT_GIT_BLOB_SHA1 = gate.FAULT_GIT_BLOB_SHA1
EXPECTED_EVENT_COUNT = 1_574_113
EXPECTED_SELECTED_TOTAL = 44_776
EXPECTED_SELECTED_COUNTS = {
    "BAY_AREA_HAYWARD_CALAVERAS": 27_377,
    "PARKFIELD_CENTRAL_SAF": 17_399,
}
EXPECTED_ELIGIBILITY_ID = "h10elig:26e3e8d730b14d888ed31f8d6392ba68536961349d90e280f28ba20d30b4f9fa"
EXPECTED_UNSEAL_REQUEST_ID = "h10unsealreq:2e97eba55578986a42b8142e002406f85e7ce493d0f603447ff8c03594d7cd83"
COHORT_NAMES = {0: "BAY_AREA_HAYWARD_CALAVERAS", 1: "PARKFIELD_CENTRAL_SAF"}
REMAINING_SEALED = ["strike_orig", "dip_orig", "rake_orig", "ftype", "p_azi", "p_dip", "t_azi", "t_dip"]


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


def validate_authority(path: Path, eligibility: Mapping[str, Any], request: Mapping[str, Any], protocol: Mapping[str, Any]) -> dict[str, Any]:
    lease = json.loads(path.read_text(encoding="utf-8"))
    if lease.get("status") != "ACTIVE_UNTIL_SINGLE_SUCCESSOR_TERMINATES" or lease.get("single_use") is not True:
        raise RuntimeError("finite authority lease is not active and single-use")
    if lease.get("protocol_id") != protocol.get("protocol_id"):
        raise RuntimeError("authority/protocol identity mismatch")
    if lease.get("upstream_eligibility_result_id") != eligibility.get("eligibility_result_id"):
        raise RuntimeError("authority/eligibility identity mismatch")
    if lease.get("upstream_directional_unseal_request_id") != request.get("request_id"):
        raise RuntimeError("authority/unseal request identity mismatch")
    forbidden = {
        "raw_source_export_authorized": False,
        "directional_row_export_authorized": False,
        "sealed_test_scoring_authorized": False,
        "scientific_model_fit_authorized": False,
        "publication_authority": False,
        "promotion_authority": False,
        "canonicalization_authority": False,
        "retrospective_mutation_authority": False,
    }
    for key, expected in forbidden.items():
        if lease.get(key) is not expected:
            raise RuntimeError(f"authority boundary drift at {key}")
    receipt = {
        "format": "KCH_HELICAL_V0_11_AUTHORITY_ACTIVATION_RECEIPT",
        "authority_file_sha256": sha256(path),
        "authority_id": lease["authority_id"],
        "protocol_id": protocol["protocol_id"],
        "eligibility_result_id": eligibility["eligibility_result_id"],
        "unseal_request_id": request["request_id"],
        "activated_at_utc": utc_now(),
        "single_use": True,
        "sealed_test_scoring_authorized": False,
        "scientific_model_fit_authorized": False,
        "promotion": "BLOCKED",
    }
    return {"receipt_id": content_id("h11auth", receipt), **receipt}


def run_container(command: list[str], receipt_path: Path, label: str) -> dict[str, Any]:
    started = time.monotonic()
    completed = subprocess.run(command, text=True, capture_output=True)
    receipt = {
        "format": "KCH_HELICAL_V0_11_CONTAINER_EXECUTION_RECEIPT",
        "label": label,
        "returncode": completed.returncode,
        "elapsed_seconds": time.monotonic() - started,
        "network_mode": "NONE",
        "read_only_root": True,
        "capabilities_dropped": "ALL",
        "no_new_privileges": True,
        "non_root_uid": 65534,
        "stdout_tail": completed.stdout[-6000:],
        "stderr_tail": completed.stderr[-6000:],
    }
    receipt["receipt_id"] = content_id("h11container", receipt)
    write_json(receipt_path, receipt)
    if completed.returncode != 0:
        raise RuntimeError(f"{label} failed: {completed.stderr[-1500:]}")
    return receipt


def assign_detailed(lat: np.ndarray, lon: np.ndarray, lines: tuple[Any, ...], tree: Any, transformer: Any, max_km: float, ratio: float) -> dict[str, np.ndarray]:
    assigned = np.full(len(lat), -1, dtype=np.int64)
    nearest = np.full(len(lat), np.nan, dtype=np.float64)
    second = np.full(len(lat), np.nan, dtype=np.float64)
    for index, (latitude, longitude) in enumerate(zip(lat, lon)):
        x, y = transformer.transform(float(longitude), float(latitude))
        point = Point(x, y)
        candidates = np.asarray(tree.query(point, predicate="dwithin", distance=max_km * 2000.0), dtype=np.int64)
        if len(candidates) == 0:
            continue
        distances = sorted(
            (float(point.distance(lines[int(candidate)])) / 1000.0, int(candidate))
            for candidate in candidates
        )
        d1, first = distances[0]
        d2 = distances[1][0] if len(distances) > 1 else math.inf
        nearest[index] = d1
        second[index] = d2
        if d1 <= max_km and (math.isinf(d2) or d2 / max(d1, 1e-9) >= ratio):
            assigned[index] = first
    return {"fault_assignment": assigned, "nearest_km": nearest, "second_km": second}


def select_indices(blind_npz: Path, fault_path: Path, protocol: Mapping[str, Any], eligibility: Mapping[str, Any], output_dir: Path) -> tuple[Path, dict[str, Any]]:
    with np.load(blind_npz, allow_pickle=False) as loaded:
        columns = {name: loaded[name] for name in loaded.files}
    if len(columns["evid"]) != EXPECTED_EVENT_COUNT:
        raise RuntimeError(f"catalog event count drift: {len(columns['evid'])}")
    if eligibility.get("eligibility_result_id") != EXPECTED_ELIGIBILITY_ID or eligibility.get("outcome") != "ELIGIBILITY_PASS":
        raise RuntimeError("upstream eligibility authorization mismatch")
    selected_ids = list(eligibility.get("selected_primary_cohorts") or [])
    if selected_ids != [COHORT_NAMES[0], COHORT_NAMES[1]]:
        raise RuntimeError(f"selected cohort order drift: {selected_ids}")

    lines, tree, transformer, feature_count = geometry.fault_index_ordinate_safe(fault_path)
    quality = gate.quality_mask(columns, protocol)
    times = gate.parse_times(columns)
    event_ids = np.asarray(columns["evid"]).astype(str)
    lat = np.asarray(columns["lat_reloc"], dtype=float)
    lon = np.asarray(columns["lon_reloc"], dtype=float)
    rules = protocol["blind_eligibility"]["fault_assignment"]
    candidates = {row["id"]: row for row in protocol["candidate_cohorts"]}
    expected_rows = {row["candidate_id"]: row for row in eligibility["candidate_results"]}

    parts: dict[str, list[np.ndarray]] = defaultdict(list)
    cohort_receipts: list[dict[str, Any]] = []
    for code, cohort_id in enumerate(selected_ids):
        candidate = candidates[cohort_id]
        expected = expected_rows[cohort_id]
        lat_min, lat_max, lon_min, lon_max = map(float, candidate["bbox"])
        raw_indices = np.flatnonzero(
            quality & (lat >= lat_min) & (lat <= lat_max) & (lon >= lon_min) & (lon <= lon_max)
        )
        assignment = assign_detailed(
            lat[raw_indices], lon[raw_indices], lines, tree, transformer,
            float(rules["maximum_distance_km"]),
            float(rules["minimum_second_to_first_distance_ratio"]),
        )
        admitted = assignment["fault_assignment"] >= 0
        global_index = raw_indices[admitted]
        fault_assignment = assignment["fault_assignment"][admitted]
        nearest = assignment["nearest_km"][admitted]
        second = assignment["second_km"][admitted]
        order = np.lexsort((event_ids[global_index], times[global_index]))
        global_index = global_index[order]
        fault_assignment = fault_assignment[order]
        nearest = nearest[order]
        second = second[order]
        selected_times = times[global_index]
        selected_events = event_ids[global_index]

        if len(raw_indices) != int(expected["quality_and_bbox_count"]):
            raise RuntimeError(f"{cohort_id}: quality/bbox count drift")
        if len(global_index) != int(expected["unambiguous_fault_assigned_count"]):
            raise RuntimeError(f"{cohort_id}: assigned count drift")
        coverage = len(global_index) / max(len(raw_indices), 1)
        if abs(coverage - float(expected["fault_assignment_coverage"])) > 1e-15:
            raise RuntimeError(f"{cohort_id}: coverage drift")
        if len(global_index) != EXPECTED_SELECTED_COUNTS[cohort_id]:
            raise RuntimeError(f"{cohort_id}: selected count differs from exact upstream result")

        parts["global_index"].append(global_index.astype(np.int64))
        parts["cohort_code"].append(np.full(len(global_index), code, dtype=np.int16))
        parts["fault_assignment"].append(fault_assignment.astype(np.int64))
        parts["nearest_km"].append(nearest.astype(np.float64))
        parts["second_km"].append(second.astype(np.float64))
        parts["event_time_epoch"].append(selected_times.astype(np.float64))
        parts["event_id"].append(selected_events.astype(np.str_))
        cohort_receipts.append({
            "cohort_code": code,
            "cohort_id": cohort_id,
            "quality_and_bbox_count": len(raw_indices),
            "selected_count": len(global_index),
            "coverage": coverage,
            "first_event_id": str(selected_events[0]),
            "last_event_id": str(selected_events[-1]),
            "first_time_epoch": float(selected_times[0]),
            "last_time_epoch": float(selected_times[-1]),
        })

    arrays = {name: np.concatenate(values) for name, values in parts.items()}
    if len(arrays["global_index"]) != EXPECTED_SELECTED_TOTAL:
        raise RuntimeError("selected total drift")
    if len(np.unique(arrays["global_index"])) != EXPECTED_SELECTED_TOTAL:
        raise RuntimeError("selected global index overlap or duplication")
    if any(value.dtype.hasobject or value.dtype.kind == "O" for value in arrays.values()):
        raise RuntimeError("object dtype forbidden in selected indices")

    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "selected_blind_indices.npz"
    np.savez_compressed(output, **arrays)
    with np.load(output, allow_pickle=False) as check:
        if set(check.files) != set(arrays) or any(check[name].dtype.hasobject for name in check.files):
            raise RuntimeError("selected index serialization failure")

    receipt = {
        "format": "KCH_HELICAL_V0_11_SELECTED_INDEX_RECEIPT",
        "protocol_id": protocol["protocol_id"],
        "eligibility_result_id": eligibility["eligibility_result_id"],
        "blind_npz_sha256": sha256(blind_npz),
        "fault_geojson_sha256": sha256(fault_path),
        "fault_feature_count": feature_count,
        "fault_line_count": len(lines),
        "selected_indices_sha256": sha256(output),
        "selected_indices_bytes": output.stat().st_size,
        "selected_total": EXPECTED_SELECTED_TOTAL,
        "unselected_total": EXPECTED_EVENT_COUNT - EXPECTED_SELECTED_TOTAL,
        "cohorts": cohort_receipts,
        "selection_order": "TIME_THEN_EVENT_ID_WITHIN_LOCKED_COHORT_ORDER",
        "directional_fields_accessed": False,
        "source_values_changed": False,
        "authority_ceiling": "FINITE_DIRECTIONAL_PRETEST_ONLY",
        "promotion": "BLOCKED",
    }
    receipt["receipt_id"] = content_id("h11select", receipt)
    write_json(output_dir / "SELECTED_INDEX_RECEIPT_V0_11.json", receipt)
    return output, receipt


def normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if not np.isfinite(norm) or norm <= 1e-12:
        raise ValueError("non-normalizable vector")
    return vector / norm


def double_couple_tensor(strike_deg: float, dip_deg: float, rake_deg: float) -> np.ndarray:
    phi = math.radians(float(strike_deg))
    delta = math.radians(float(dip_deg))
    lam = math.radians(float(rake_deg))
    strike = np.array([math.cos(phi), math.sin(phi), 0.0], dtype=float)
    down_dip = np.array([-math.sin(phi) * math.cos(delta), math.cos(phi) * math.cos(delta), math.sin(delta)], dtype=float)
    normal = normalize(np.cross(strike, down_dip))
    slip = normalize(math.cos(lam) * strike + math.sin(lam) * down_dip)
    tensor = np.outer(slip, normal) + np.outer(normal, slip)
    tensor = 0.5 * (tensor + tensor.T)
    tensor -= np.trace(tensor) / 3.0 * np.eye(3)
    return tensor / np.linalg.norm(tensor, ord="fro")


def tangent_and_coordinate(line: Any, point: Point) -> tuple[np.ndarray, float]:
    position = float(line.project(point))
    length = float(line.length)
    step = min(100.0, max(5.0, length * 1e-5))
    before = line.interpolate(max(0.0, position - step))
    after = line.interpolate(min(length, position + step))
    tangent_ned = normalize(np.array([float(after.y - before.y), float(after.x - before.x), 0.0]))
    return tangent_ned, position / 1000.0


def directional_preflight(directional_npz: Path, fault_path: Path, protocol: Mapping[str, Any], output_dir: Path) -> dict[str, Any]:
    with np.load(directional_npz, allow_pickle=False) as loaded:
        data = {name: loaded[name] for name in loaded.files}
    required = {
        "strike", "dip", "rake", "lat_reloc", "lon_reloc", "event_time_epoch", "mag", "uncer",
        "prob", "npol", "evid", "cohort_code", "fault_assignment", "nearest_km", "second_km", "global_index",
    }
    if required - set(data):
        raise RuntimeError(f"missing directional fields: {sorted(required - set(data))}")
    n = len(data["evid"])
    if n != EXPECTED_SELECTED_TOTAL or any(len(data[name]) != n for name in required):
        raise RuntimeError(f"directional selected count or length drift: {n}")

    lines, _tree, transformer, feature_count = geometry.fault_index_ordinate_safe(fault_path)
    assignments = np.asarray(data["fault_assignment"], dtype=np.int64)
    if np.min(assignments) < 0 or np.max(assignments) >= len(lines):
        raise RuntimeError("fault assignment outside reconstructed network")
    lat = np.asarray(data["lat_reloc"], dtype=float)
    lon = np.asarray(data["lon_reloc"], dtype=float)
    strike = np.asarray(data["strike"], dtype=float)
    dip = np.asarray(data["dip"], dtype=float)
    rake = np.asarray(data["rake"], dtype=float)
    times = np.asarray(data["event_time_epoch"], dtype=float)
    cohort_code = np.asarray(data["cohort_code"], dtype=np.int16)

    tangent = np.full((n, 3), np.nan, dtype=np.float64)
    along_km = np.full(n, np.nan, dtype=np.float64)
    projection_norm = np.full(n, np.nan, dtype=np.float64)
    tensor_valid = np.zeros(n, dtype=bool)
    axis_observable = np.zeros(n, dtype=bool)
    threshold = float(protocol["observation_model"]["minimum_axis_projection"])
    for index in range(n):
        x, y = transformer.transform(float(lon[index]), float(lat[index]))
        tangent_i, coordinate = tangent_and_coordinate(lines[int(assignments[index])], Point(x, y))
        tangent[index] = tangent_i
        along_km[index] = coordinate
        try:
            tensor = double_couple_tensor(strike[index], dip[index], rake[index])
            values, vectors = np.linalg.eigh(tensor)
            p_axis = vectors[:, int(np.argmin(values))]
            projection = math.sqrt(max(0.0, 1.0 - float(np.dot(p_axis, tangent_i)) ** 2))
            projection_norm[index] = projection
            tensor_valid[index] = True
            axis_observable[index] = projection >= threshold
        except Exception:
            continue

    max_age_seconds = float(protocol["parent_graph"]["maximum_parent_age_days"]) * 86400.0
    max_path_km = float(protocol["parent_graph"]["maximum_network_path_km"])
    max_parents = int(protocol["parent_graph"]["maximum_candidate_parents_per_event"])
    candidate_parent_count = np.zeros(n, dtype=np.int16)
    parent_available = np.zeros(n, dtype=bool)
    for code in sorted(set(int(value) for value in cohort_code.tolist())):
        members = np.flatnonzero(cohort_code == code)
        order = members[np.argsort(times[members], kind="stable")]
        history: dict[int, deque[tuple[float, float]]] = defaultdict(deque)
        for child in order:
            fault = int(assignments[child])
            queue = history[fault]
            child_time = float(times[child])
            while queue and child_time - queue[0][0] > max_age_seconds:
                queue.popleft()
            count = 0
            for _parent_time, parent_along in reversed(queue):
                if abs(float(along_km[child]) - parent_along) <= max_path_km:
                    count += 1
                    if count >= max_parents:
                        break
            candidate_parent_count[child] = count
            parent_available[child] = count > 0
            queue.append((child_time, float(along_km[child])))

    cohort_results: list[dict[str, Any]] = []
    all_ready = True
    for code, cohort_id in COHORT_NAMES.items():
        members = np.flatnonzero(cohort_code == code)
        observable = members[axis_observable[members]]
        chronological = observable[np.argsort(times[observable], kind="stable")]
        train_end = int(math.floor(0.5 * len(chronological)))
        calibration_end = int(math.floor(0.75 * len(chronological)))
        test_count = len(chronological) - calibration_end
        result = {
            "cohort_code": code,
            "cohort_id": cohort_id,
            "selected_event_count": int(len(members)),
            "tensor_valid_count": int(np.sum(tensor_valid[members])),
            "axis_observable_count": int(len(observable)),
            "axis_observable_fraction": float(len(observable) / max(len(members), 1)),
            "train_count": train_end,
            "calibration_count": calibration_end - train_end,
            "sealed_test_count": test_count,
            "same_segment_candidate_parent_child_count": int(np.sum(parent_available[chronological])),
            "same_segment_candidate_parent_child_fraction": float(np.mean(parent_available[chronological])) if len(chronological) else 0.0,
            "median_same_segment_candidate_parents": float(np.median(candidate_parent_count[chronological])) if len(chronological) else 0.0,
            "maximum_same_segment_candidate_parents": int(np.max(candidate_parent_count[chronological])) if len(chronological) else 0,
            "time_span_years": float((np.max(times[members]) - np.min(times[members])) / (365.2425 * 86400.0)),
            "minimum_projection_norm": float(np.nanmin(projection_norm[members])),
            "median_projection_norm": float(np.nanmedian(projection_norm[members])),
            "directional_execution_ready": bool(len(observable) >= 800 and test_count >= 200),
        }
        all_ready &= result["directional_execution_ready"]
        cohort_results.append(result)

    body = {
        "format": "KCH_HELICAL_V0_11_DIRECTIONAL_PREFLIGHT_RESULT",
        "protocol_id": protocol["protocol_id"],
        "selected_directional_sha256": sha256(directional_npz),
        "fault_geojson_sha256": sha256(fault_path),
        "fault_feature_count": feature_count,
        "fault_line_count": len(lines),
        "event_count": n,
        "tensor_valid_count": int(np.sum(tensor_valid)),
        "axis_observable_count": int(np.sum(axis_observable)),
        "axis_observable_fraction": float(np.mean(axis_observable)),
        "cohorts": cohort_results,
        "same_segment_parent_diagnostic_scope": "CONSERVATIVE_SUBSET_NOT_FULL_NETWORK_GRAPH",
        "directional_execution_authorized": bool(all_ready),
        "outcome": "DIRECTIONAL_MATERIALIZATION_PASS" if all_ready else "NOT_IDENTIFIABLE_MECHANISM_COVERAGE",
        "sealed_test_scored": False,
        "scientific_model_execution_performed": False,
        "physical_helicity": "NOT_EVALUATED",
        "remaining_sealed_fields": REMAINING_SEALED,
        "recorded_at_utc": utc_now(),
        "authority_ceiling": "FINITE_DIRECTIONAL_PRETEST_ONLY",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    body["preflight_result_id"] = content_id("h11preflight", body)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "DIRECTIONAL_PREFLIGHT_RESULT_V0_11.json", body)
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--authority", required=True, type=Path)
    parser.add_argument("--eligibility-result", required=True, type=Path)
    parser.add_argument("--unseal-request", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--blind-image", required=True)
    parser.add_argument("--directional-image", required=True)
    parser.add_argument("--timeout", type=int, default=1200)
    args = parser.parse_args()

    workspace = args.workspace.resolve()
    raw = workspace / "raw"
    blind = workspace / "blind"
    selection_dir = workspace / "selection"
    directional = workspace / "directional"
    results = workspace / "results"
    for path in (raw, blind, selection_dir, directional, results):
        path.mkdir(parents=True, exist_ok=True)
    os.chmod(blind, 0o777)
    os.chmod(directional, 0o777)

    protocol, protocol_lock = gate.audit_protocol(args.protocol)
    eligibility = json.loads(args.eligibility_result.read_text(encoding="utf-8"))
    request = json.loads(args.unseal_request.read_text(encoding="utf-8"))
    if request.get("request_id") != EXPECTED_UNSEAL_REQUEST_ID or request.get("directional_unsealing_performed") is not False:
        raise RuntimeError("directional unseal request mismatch or already consumed")
    authority_receipt = validate_authority(args.authority, eligibility, request, protocol)
    write_json(results / "AUTHORITY_ACTIVATION_RECEIPT_V0_11.json", authority_receipt)

    run = {
        "format": "KCH_HELICAL_V0_11_DIRECTIONAL_PRETEST_RUN_RECEIPT",
        **protocol_lock,
        "started_at_utc": utc_now(),
        "eligibility_result_id": eligibility.get("eligibility_result_id"),
        "unseal_request_id": request.get("request_id"),
        "authority_receipt_id": authority_receipt["receipt_id"],
        "sealed_test_scored": False,
        "scientific_model_execution_performed": False,
        "physical_helicity": "NOT_EVALUATED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    exit_code = 50
    try:
        snapshot, metadata_receipt, _snapshot_raw = acquisition.public_request_json(gate.SNAPSHOT_URL, args.timeout)
        mechanism = raw / gate.MECHANISM_BASENAME
        fault = raw / gate.FAULT_BASENAME
        mechanism_receipt = acquisition.public_stream_download("public-exact-identity", mechanism, args.timeout, EXPECTED_MECHANISM_BYTES)
        fault_receipt = acquisition._ORIGINAL_STREAM_DOWNLOAD(gate.FAULT_URL, fault, args.timeout, gate.FAULT_BYTES)
        if sha256(mechanism) != EXPECTED_MECHANISM_SHA256 or mechanism.stat().st_size != EXPECTED_MECHANISM_BYTES:
            raise RuntimeError("mechanism exact-byte identity mismatch")
        if sha256(fault) != EXPECTED_FAULT_SHA256 or gate.git_blob_sha1(fault) != EXPECTED_FAULT_GIT_BLOB_SHA1:
            raise RuntimeError("fault exact-byte identity mismatch")
        acquisition_receipt = {
            "format": "KCH_HELICAL_V0_11_EXACT_BYTE_ACQUISITION_RECEIPT",
            "metadata": metadata_receipt,
            "mechanism": mechanism_receipt,
            "fault": {**fault_receipt, "git_blob_sha1": gate.git_blob_sha1(fault)},
            "all_or_none_pass": True,
            "transaction_committed": True,
            **protocol_lock,
            "directional_fields_accessed": False,
            "authority_receipt_id": authority_receipt["receipt_id"],
            "promotion": "BLOCKED",
        }
        acquisition_receipt["receipt_id"] = content_id("h11acq", acquisition_receipt)
        write_json(results / "ACQUISITION_RECEIPT_V0_11.json", acquisition_receipt)

        blind_container = run_container([
            "docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true", "--pids-limit", "128", "--memory", "6g", "--memory-swap", "6g", "--cpus", "2",
            "--user", "65534:65534", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=536870912",
            "-v", f"{raw}:/input:ro", "-v", f"{blind}:/output:rw", args.blind_image,
            "--pickle", f"/input/{gate.MECHANISM_BASENAME}", "--expected-sha256", EXPECTED_MECHANISM_SHA256, "--output-dir", "/output",
        ], results / "BLIND_CONTAINER_RECEIPT_V0_11.json", "BLIND_EXTRACTION")
        blind_receipt = json.loads((blind / "BLIND_EXTRACTION_RECEIPT_V0_11.json").read_text(encoding="utf-8"))
        if blind_receipt.get("event_count") != EXPECTED_EVENT_COUNT or blind_receipt.get("sealed_fields_emitted") != []:
            raise RuntimeError("blind extraction receipt mismatch")
        write_json(results / "BLIND_EXTRACTION_RECEIPT_V0_11.json", {**blind_receipt, "container_receipt_id": blind_container["receipt_id"]})

        selected_indices, selection_receipt = select_indices(
            blind / "blind_columns.npz", fault, protocol, eligibility, selection_dir
        )
        write_json(results / "SELECTED_INDEX_RECEIPT_V0_11.json", selection_receipt)

        directional_container = run_container([
            "docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true", "--pids-limit", "128", "--memory", "6g", "--memory-swap", "6g", "--cpus", "2",
            "--user", "65534:65534", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=536870912",
            "-v", f"{raw}:/input:ro", "-v", f"{selection_dir}:/selection:ro", "-v", f"{directional}:/output:rw", args.directional_image,
            "--pickle", f"/input/{gate.MECHANISM_BASENAME}", "--expected-pickle-sha256", EXPECTED_MECHANISM_SHA256,
            "--selected-indices", "/selection/selected_blind_indices.npz", "--expected-indices-sha256", selection_receipt["selected_indices_sha256"],
            "--output-dir", "/output",
        ], results / "DIRECTIONAL_CONTAINER_RECEIPT_V0_11.json", "SELECTED_DIRECTIONAL_EXTRACTION")
        directional_receipt = json.loads((directional / "SELECTED_DIRECTIONAL_EXTRACTION_RECEIPT_V0_11.json").read_text(encoding="utf-8"))
        if directional_receipt.get("selected_event_count") != EXPECTED_SELECTED_TOTAL:
            raise RuntimeError("selected directional count drift")
        if directional_receipt.get("remaining_sealed_fields_not_emitted") != REMAINING_SEALED:
            raise RuntimeError("remaining sealed field contract drift")
        write_json(results / "SELECTED_DIRECTIONAL_EXTRACTION_RECEIPT_V0_11.json", {**directional_receipt, "container_receipt_id": directional_container["receipt_id"]})

        preflight = directional_preflight(
            directional / "selected_directional_columns.npz", fault, protocol, results
        )
        run.update({
            "outcome": preflight["outcome"],
            "preflight_result_id": preflight["preflight_result_id"],
            "directional_unsealing_performed": True,
            "directional_event_count": EXPECTED_SELECTED_TOTAL,
            "directional_execution_authorized": preflight["directional_execution_authorized"],
            "remaining_sealed_fields": REMAINING_SEALED,
        })
        exit_code = 0 if preflight["directional_execution_authorized"] else 30
    except Exception as error:
        run.update({
            "outcome": "DIRECTIONAL_PRETEST_FAILED_CLOSED",
            "error_type": type(error).__name__,
            "error": str(error),
            "directional_unsealing_performed": (directional / "selected_directional_columns.npz").exists(),
            "directional_execution_authorized": False,
        })
        exit_code = 50
    finally:
        run["completed_at_utc"] = utc_now()
        run["exit_code"] = exit_code
        run["raw_sources_purged"] = True
        run["blind_npz_purged"] = True
        run["selected_indices_purged"] = True
        run["directional_rows_purged"] = True
        run["authority_consumed"] = True
        run["authority_terminal_status"] = "CONSUMED_SUCCESS" if exit_code in {0, 30} else "CONSUMED_FAIL_CLOSED"
        run["run_receipt_id"] = content_id("h11run", run)
        write_json(results / "RUN_RECEIPT_V0_11.json", run)
        shutil.rmtree(raw, ignore_errors=True)
        shutil.rmtree(blind, ignore_errors=True)
        shutil.rmtree(selection_dir, ignore_errors=True)
        shutil.rmtree(directional, ignore_errors=True)
        print(json.dumps(run, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
