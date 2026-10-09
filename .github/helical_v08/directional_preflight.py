from __future__ import annotations

import argparse
from collections import defaultdict, deque
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, Point, shape

COHORT_NAMES = {
    0: "BAY_AREA_HAYWARD_CALAVERAS",
    1: "PARKFIELD_CENTRAL_SAF",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


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
    down_dip = np.array(
        [-math.sin(phi) * math.cos(delta), math.cos(phi) * math.cos(delta), math.sin(delta)],
        dtype=float,
    )
    normal = normalize(np.cross(strike, down_dip))
    slip = normalize(math.cos(lam) * strike + math.sin(lam) * down_dip)
    tensor = np.outer(slip, normal) + np.outer(normal, slip)
    tensor = 0.5 * (tensor + tensor.T)
    tensor -= np.trace(tensor) / 3.0 * np.eye(3)
    return tensor / np.linalg.norm(tensor, ord="fro")


def flatten_lines(geometry: Any) -> Iterable[LineString]:
    if isinstance(geometry, LineString):
        yield geometry
    elif isinstance(geometry, MultiLineString):
        yield from geometry.geoms


def load_projected_lines(path: Path) -> tuple[list[LineString], Transformer]:
    root = json.loads(path.read_text(encoding="utf-8"))
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3310", always_xy=True)
    lines: list[LineString] = []
    for feature in root.get("features", []):
        geometry = shape(feature.get("geometry"))
        for line in flatten_lines(geometry):
            coordinates = [
                transformer.transform(float(coordinate[0]), float(coordinate[1]))
                for coordinate in line.coords
            ]
            if len(coordinates) >= 2:
                lines.append(LineString(coordinates))
    if not lines:
        raise ValueError("fault network contains no projected lines")
    return lines, transformer


def tangent_and_coordinate(line: LineString, point: Point) -> tuple[np.ndarray, float]:
    position = float(line.project(point))
    length = float(line.length)
    step = min(100.0, max(5.0, length * 1e-5))
    before = line.interpolate(max(0.0, position - step))
    after = line.interpolate(min(length, position + step))
    east = float(after.x - before.x)
    north = float(after.y - before.y)
    tangent_ned = normalize(np.array([north, east, 0.0], dtype=float))
    return tangent_ned, position / 1000.0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected-directional", required=True, type=Path)
    parser.add_argument("--expected-directional-sha256", required=True)
    parser.add_argument("--fault-geojson", required=True, type=Path)
    parser.add_argument("--expected-fault-sha256", required=True)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if sha256(args.selected_directional) != args.expected_directional_sha256:
        raise SystemExit("selected directional SHA-256 mismatch")
    if sha256(args.fault_geojson) != args.expected_fault_sha256:
        raise SystemExit("fault-network SHA-256 mismatch")
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    with np.load(args.selected_directional, allow_pickle=False) as z:
        data = {name: z[name] for name in z.files}

    required = {
        "strike", "dip", "rake", "lat_reloc", "lon_reloc", "event_time_epoch", "mag", "uncer",
        "prob", "npol", "evid", "cohort_code", "fault_assignment", "nearest_km", "second_km",
        "global_index",
    }
    missing = sorted(required - set(data))
    if missing:
        raise SystemExit(f"missing selected directional fields: {missing}")
    n = len(data["evid"])
    if n != 61555:
        raise SystemExit(f"selected event count drift: {n}")
    if any(len(data[name]) != n for name in required):
        raise SystemExit("selected directional field-length mismatch")

    lines, transformer = load_projected_lines(args.fault_geojson)
    fault_assignment = np.asarray(data["fault_assignment"], dtype=np.int64)
    if np.min(fault_assignment) < 0 or np.max(fault_assignment) >= len(lines):
        raise SystemExit("fault assignment outside reconstructed network")

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
    for index in range(n):
        x, y = transformer.transform(float(lon[index]), float(lat[index]))
        tangent_i, coordinate = tangent_and_coordinate(lines[int(fault_assignment[index])], Point(x, y))
        tangent[index] = tangent_i
        along_km[index] = coordinate
        try:
            tensor = double_couple_tensor(strike[index], dip[index], rake[index])
            values, vectors = np.linalg.eigh(tensor)
            p_axis = vectors[:, int(np.argmin(values))]
            projection = math.sqrt(max(0.0, 1.0 - float(np.dot(p_axis, tangent_i)) ** 2))
            projection_norm[index] = projection
            tensor_valid[index] = True
            axis_observable[index] = projection >= float(protocol["observation_model"]["minimum_axis_projection"])
        except Exception:
            continue

    maximum_age_seconds = float(protocol["parent_graph"]["maximum_parent_age_days"]) * 86400.0
    maximum_path_km = float(protocol["parent_graph"]["maximum_network_path_km"])
    maximum_parents = int(protocol["parent_graph"]["maximum_candidate_parents_per_event"])
    candidate_parent_count = np.zeros(n, dtype=np.int16)
    same_segment_children = np.zeros(n, dtype=bool)

    for code in sorted(set(int(value) for value in cohort_code.tolist())):
        members = np.flatnonzero(cohort_code == code)
        order = members[np.argsort(times[members], kind="stable")]
        history: dict[int, deque[tuple[float, float, int]]] = defaultdict(deque)
        for child in order:
            fault = int(fault_assignment[child])
            queue = history[fault]
            child_time = float(times[child])
            while queue and child_time - queue[0][0] > maximum_age_seconds:
                queue.popleft()
            count = 0
            for parent_time, parent_along, _parent_index in reversed(queue):
                if abs(float(along_km[child]) - parent_along) <= maximum_path_km:
                    count += 1
                    if count >= maximum_parents:
                        break
            candidate_parent_count[child] = count
            same_segment_children[child] = count > 0
            queue.append((child_time, float(along_km[child]), int(child)))

    preflight_arrays = args.output_dir / "directional_preflight_arrays.npz"
    np.savez_compressed(
        preflight_arrays,
        global_index=np.asarray(data["global_index"], dtype=np.int64),
        cohort_code=cohort_code,
        fault_assignment=fault_assignment,
        tangent_ned=tangent,
        along_fault_km=along_km,
        projection_norm=projection_norm,
        tensor_valid=tensor_valid,
        axis_observable=axis_observable,
        same_segment_candidate_parent_count=candidate_parent_count,
        same_segment_parent_available=same_segment_children,
    )

    cohort_results: list[dict[str, Any]] = []
    all_ready = True
    for code, cohort_id in COHORT_NAMES.items():
        members = np.flatnonzero(cohort_code == code)
        observable = members[axis_observable[members]]
        chronological = observable[np.argsort(times[observable], kind="stable")]
        train_end = int(math.floor(0.5 * len(chronological)))
        calibration_end = int(math.floor(0.75 * len(chronological)))
        test_count = len(chronological) - calibration_end
        parent_children = int(np.sum(same_segment_children[chronological]))
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
            "same_segment_candidate_parent_child_count": parent_children,
            "same_segment_candidate_parent_child_fraction": float(parent_children / max(len(chronological), 1)),
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
        "format": "KCH_HELICAL_V0_8_DIRECTIONAL_PREFLIGHT_RESULT",
        "protocol_id": protocol["protocol_id"],
        "selected_directional_sha256": sha256(args.selected_directional),
        "fault_geojson_sha256": sha256(args.fault_geojson),
        "preflight_arrays_sha256": sha256(preflight_arrays),
        "preflight_arrays_bytes": preflight_arrays.stat().st_size,
        "event_count": int(n),
        "tensor_valid_count": int(np.sum(tensor_valid)),
        "axis_observable_count": int(np.sum(axis_observable)),
        "axis_observable_fraction": float(np.mean(axis_observable)),
        "cohorts": cohort_results,
        "same_segment_parent_diagnostic_scope": "CONSERVATIVE_SUBSET_NOT_FULL_NETWORK_GRAPH",
        "directional_execution_authorized": bool(all_ready),
        "outcome": "DIRECTIONAL_MATERIALIZATION_PASS" if all_ready else "NOT_IDENTIFIABLE_MECHANISM_COVERAGE",
        "scientific_model_execution_performed": False,
        "physical_helicity": "NOT_EVALUATED",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "authority_ceiling": "NONE",
    }
    body["preflight_result_id"] = "h8preflight:" + hashlib.sha256(canonical(body)).hexdigest()
    (args.output_dir / "DIRECTIONAL_PREFLIGHT_RESULT_V0_8.json").write_text(
        json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if all_ready else 3


if __name__ == "__main__":
    raise SystemExit(main())
