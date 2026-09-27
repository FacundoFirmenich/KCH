from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any

import numpy as np


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("kch_v08_eligibility", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load eligibility module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--eligibility-result", required=True, type=Path)
    parser.add_argument("--eligibility-module", required=True, type=Path)
    parser.add_argument("--blind-npz", required=True, type=Path)
    parser.add_argument("--fault-geojson", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    eligibility = json.loads(args.eligibility_result.read_text(encoding="utf-8"))
    if eligibility.get("protocol_id") != protocol.get("protocol_id"):
        raise SystemExit("eligibility/protocol identity mismatch")
    if eligibility.get("outcome") != "ELIGIBILITY_PASS" or eligibility.get("execution_authorized") is not True:
        raise SystemExit("blind eligibility did not authorize directional materialization")
    if eligibility.get("angle_fields_accessed") is not False:
        raise SystemExit("upstream blind firewall violation")

    module = load_module(args.eligibility_module)
    with np.load(args.blind_npz, allow_pickle=False) as z:
        columns = {name: z[name] for name in z.files}
    fault_index = module.load_fault_index(args.fault_geojson)
    quality = module.quality_mask(columns, protocol)
    times = module._parse_time(columns)
    event_ids = np.asarray(columns["evid"]).astype(str)
    lat = np.asarray(columns["lat_reloc"], dtype=float)
    lon = np.asarray(columns["lon_reloc"], dtype=float)
    rule = protocol["blind_eligibility"]["fault_assignment"]

    candidates = {row["id"]: row for row in protocol["candidate_cohorts"]}
    result_rows = {row["candidate_id"]: row for row in eligibility["candidate_results"]}
    selected_ids = list(eligibility["selected_primary_cohorts"])
    if selected_ids != ["BAY_AREA_HAYWARD_CALAVERAS", "PARKFIELD_CENTRAL_SAF"]:
        raise SystemExit(f"unexpected selected cohort order: {selected_ids}")

    output_rows: list[dict[str, Any]] = []
    global_parts: list[np.ndarray] = []
    cohort_parts: list[np.ndarray] = []
    fault_parts: list[np.ndarray] = []
    nearest_parts: list[np.ndarray] = []
    second_parts: list[np.ndarray] = []
    time_parts: list[np.ndarray] = []
    event_parts: list[np.ndarray] = []

    for code, cohort_id in enumerate(selected_ids):
        candidate = candidates[cohort_id]
        expected = result_rows[cohort_id]
        lat_min, lat_max, lon_min, lon_max = [float(x) for x in candidate["bbox"]]
        spatial = (lat >= lat_min) & (lat <= lat_max) & (lon >= lon_min) & (lon <= lon_max)
        raw_indices = np.flatnonzero(quality & spatial)
        assignment = module.assign_faults(
            lat[raw_indices],
            lon[raw_indices],
            fault_index,
            max_distance_km=float(rule["maximum_distance_km"]),
            ambiguity_ratio=float(rule["minimum_second_to_first_distance_ratio"]),
        )
        admitted = assignment["fault_index"] >= 0
        global_index = raw_indices[admitted]
        assigned_fault = np.asarray(assignment["fault_index"], dtype=np.int64)[admitted]
        nearest = np.asarray(assignment["nearest_km"], dtype=float)[admitted]
        second = np.asarray(assignment["second_km"], dtype=float)[admitted]
        order = np.lexsort((event_ids[global_index], times[global_index]))
        global_index = global_index[order]
        assigned_fault = assigned_fault[order]
        nearest = nearest[order]
        second = second[order]
        selected_times = times[global_index]
        selected_events = event_ids[global_index]

        if int(len(raw_indices)) != int(expected["quality_and_bbox_count"]):
            raise SystemExit(f"{cohort_id}: quality/bbox count drift")
        if int(len(global_index)) != int(expected["unambiguous_fault_assigned_count"]):
            raise SystemExit(f"{cohort_id}: assigned count drift")
        coverage = len(global_index) / max(len(raw_indices), 1)
        if abs(coverage - float(expected["fault_assignment_coverage"])) > 1e-15:
            raise SystemExit(f"{cohort_id}: coverage drift")
        if len(np.unique(global_index)) != len(global_index):
            raise SystemExit(f"{cohort_id}: duplicate selected indices")

        global_parts.append(global_index.astype(np.int64))
        cohort_parts.append(np.full(len(global_index), code, dtype=np.int16))
        fault_parts.append(assigned_fault.astype(np.int64))
        nearest_parts.append(nearest.astype(np.float64))
        second_parts.append(second.astype(np.float64))
        time_parts.append(selected_times.astype(np.float64))
        event_parts.append(selected_events.astype(np.str_))
        output_rows.append(
            {
                "cohort_code": code,
                "cohort_id": cohort_id,
                "quality_and_bbox_count": int(len(raw_indices)),
                "selected_count": int(len(global_index)),
                "coverage": float(coverage),
                "first_time_epoch": float(selected_times[0]),
                "last_time_epoch": float(selected_times[-1]),
                "first_event_id": str(selected_events[0]),
                "last_event_id": str(selected_events[-1]),
            }
        )

    global_index = np.concatenate(global_parts)
    cohort_code = np.concatenate(cohort_parts)
    fault_assignment = np.concatenate(fault_parts)
    nearest_km = np.concatenate(nearest_parts)
    second_km = np.concatenate(second_parts)
    event_time_epoch = np.concatenate(time_parts)
    event_id = np.concatenate(event_parts)
    if len(np.unique(global_index)) != len(global_index):
        raise SystemExit("selected cohorts overlap in global event indices")

    npz_path = args.output_dir / "selected_blind_indices.npz"
    np.savez_compressed(
        npz_path,
        global_index=global_index,
        cohort_code=cohort_code,
        fault_assignment=fault_assignment,
        nearest_km=nearest_km,
        second_km=second_km,
        event_time_epoch=event_time_epoch,
        event_id=event_id,
    )
    with np.load(npz_path, allow_pickle=False) as check:
        if any(check[name].dtype.hasobject for name in check.files):
            raise SystemExit("object dtype forbidden in selected-index artifact")
        if not all(len(check[name]) == len(global_index) for name in check.files):
            raise SystemExit("selected-index artifact length mismatch")

    body = {
        "format": "KCH_HELICAL_V0_8_SELECTED_INDEX_RECEIPT",
        "protocol_id": protocol["protocol_id"],
        "eligibility_result_id": eligibility["eligibility_result_id"],
        "blind_npz_sha256": sha256(args.blind_npz),
        "fault_geojson_sha256": sha256(args.fault_geojson),
        "selected_indices_sha256": sha256(npz_path),
        "selected_indices_bytes": npz_path.stat().st_size,
        "selected_total": int(len(global_index)),
        "unselected_total": int(len(columns["evid"]) - len(global_index)),
        "cohorts": output_rows,
        "selection_order": "TIME_THEN_EVENT_ID_WITHIN_LOCKED_COHORT_ORDER",
        "directional_fields_accessed": False,
        "sealed_fields_observed": [],
        "source_values_changed": False,
        "authority_ceiling": "NONE",
    }
    body["receipt_id"] = "h8select:" + hashlib.sha256(canonical(body)).hexdigest()
    (args.output_dir / "SELECTED_INDEX_RECEIPT_V0_8.json").write_text(
        json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
