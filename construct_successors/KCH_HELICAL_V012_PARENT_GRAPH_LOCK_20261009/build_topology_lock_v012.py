from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from pyproj import Transformer
from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPoint, Point, shape
from shapely.strtree import STRtree

PROTOCOL_ID = "h8p:99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f"
FAULT_SHA256 = "37babb516edfac22b5ae91744495d8546b3ae4676b4d4f68cc77da8222df20e1"
EXPECTED_EVENTS = 61_555


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def flatten(geometry: Any) -> Iterable[LineString]:
    if isinstance(geometry, LineString):
        yield geometry
    elif isinstance(geometry, MultiLineString):
        yield from geometry.geoms


def intersection_points(geometry: Any) -> list[Point]:
    if geometry.is_empty:
        return []
    if isinstance(geometry, Point):
        return [geometry]
    if isinstance(geometry, MultiPoint):
        return list(geometry.geoms)
    if isinstance(geometry, LineString):
        return [Point(geometry.coords[0]), geometry.interpolate(0.5, normalized=True), Point(geometry.coords[-1])]
    if isinstance(geometry, MultiLineString):
        result: list[Point] = []
        for item in geometry.geoms:
            result.extend(intersection_points(item))
        return result
    if isinstance(geometry, GeometryCollection):
        result = []
        for item in geometry.geoms:
            result.extend(intersection_points(item))
        return result
    return []


def load_lines(path: Path) -> list[LineString]:
    root = json.loads(path.read_text(encoding="utf-8"))
    if root.get("type") != "FeatureCollection":
        raise RuntimeError("fault source is not a FeatureCollection")
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3310", always_xy=True)
    lines: list[LineString] = []
    for feature in root.get("features", []):
        for line in flatten(shape(feature.get("geometry"))):
            coordinates = [transformer.transform(float(item[0]), float(item[1])) for item in line.coords]
            if len(coordinates) >= 2:
                lines.append(LineString(coordinates))
    if not lines:
        raise RuntimeError("fault source contains no line geometry")
    return lines


def components(selected: list[int], adjacency: dict[int, set[int]]) -> list[list[int]]:
    seen: set[int] = set()
    result: list[list[int]] = []
    for origin in selected:
        if origin in seen:
            continue
        stack = [origin]
        seen.add(origin)
        component: list[int] = []
        while stack:
            current = stack.pop()
            component.append(current)
            for neighbor in sorted(adjacency[current]):
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        result.append(sorted(component))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selected-root", required=True, type=Path)
    parser.add_argument("--fault-geojson", required=True, type=Path)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    if sha256(args.fault_geojson) != FAULT_SHA256:
        raise SystemExit("fault-network SHA-256 mismatch")
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("protocol_id") != PROTOCOL_ID:
        raise SystemExit("frozen protocol identity mismatch")

    selected_files = list(args.selected_root.rglob("selected_directional_columns.npz"))
    preflight_files = list(args.selected_root.rglob("directional_preflight_arrays.npz"))
    if len(selected_files) != 1 or len(preflight_files) != 1:
        raise SystemExit("selected/preflight artifact multiplicity drift")
    with np.load(selected_files[0], allow_pickle=False) as loaded:
        selected = {name: loaded[name].copy() for name in ["global_index", "cohort_code"]}
    with np.load(preflight_files[0], allow_pickle=False) as loaded:
        preflight = {name: loaded[name].copy() for name in ["global_index", "cohort_code", "fault_assignment", "axis_observable"]}
    if len(selected["global_index"]) != EXPECTED_EVENTS:
        raise SystemExit("selected event-count drift")
    if not np.array_equal(selected["global_index"], preflight["global_index"]):
        raise SystemExit("selected/preflight global-index alignment drift")

    lines = load_lines(args.fault_geojson)
    selected_lines = sorted(set(int(value) for value in preflight["fault_assignment"].tolist()))
    if min(selected_lines) < 0 or max(selected_lines) >= len(lines):
        raise SystemExit("selected fault index outside external network")
    local_geometries = [lines[index] for index in selected_lines]
    tree = STRtree(local_geometries)
    adjacency: dict[int, set[int]] = defaultdict(set)
    intersections: list[dict[str, Any]] = []

    for local_i, line_i in enumerate(local_geometries):
        global_i = selected_lines[local_i]
        adjacency[global_i]
        candidates = np.asarray(tree.query(line_i, predicate="intersects"), dtype=np.int64)
        for local_j in sorted(int(value) for value in candidates if int(value) > local_i):
            line_j = local_geometries[local_j]
            points = intersection_points(line_i.intersection(line_j))
            if not points:
                continue
            global_j = selected_lines[local_j]
            adjacency[global_i].add(global_j)
            adjacency[global_j].add(global_i)
            intersections.append({
                "line_i": global_i,
                "line_j": global_j,
                "point_count": len(points),
                "positions_i_km": [float(line_i.project(point) / 1000.0) for point in points],
                "positions_j_km": [float(line_j.project(point) / 1000.0) for point in points],
            })

    intersections.sort(key=lambda row: (row["line_i"], row["line_j"], row["point_count"]))
    network_components = components(selected_lines, adjacency)
    observable = np.asarray(preflight["axis_observable"], dtype=bool)
    cohort_code = np.asarray(preflight["cohort_code"], dtype=np.int16)
    topology_by_cohort = []
    for code, name in ((0, "BAY_AREA_HAYWARD_CALAVERAS"), (1, "PARKFIELD_CENTRAL_SAF")):
        members = np.flatnonzero((cohort_code == code) & observable)
        cohort_lines = sorted(set(int(preflight["fault_assignment"][index]) for index in members))
        component_ids = [idx for idx, component in enumerate(network_components) if set(component) & set(cohort_lines)]
        topology_by_cohort.append({
            "cohort_code": code,
            "cohort_id": name,
            "axis_observable_events": int(len(members)),
            "selected_fault_line_count": len(cohort_lines),
            "touched_component_count": len(component_ids),
            "multiline_component_event_fraction_not_computed": True,
        })

    operator = {
        "format": "KCH_HELICAL_V0_12_LOCATION_PERTURBATION_OPERATOR_CONTRACT_LOCK",
        "protocol_id": PROTOCOL_ID,
        "status": "CONTRACT_LOCKED_EXECUTION_DEFERRED",
        "representation": "CONSERVATIVE_ISOTROPIC_MAX_HORIZONTAL_PROJECTION_ENVELOPE",
        "horizontal_draw": "dx,dy iid Normal(0,horizontalError_km^2)",
        "vertical_draw": "dz Normal(0,depthError_km^2)",
        "full_covariance_claim": False,
        "missing_error_policy": "UNAVAILABLE_NO_IMPUTATION",
        "fault_reassignment": {
            "maximum_distance_km": float(protocol["blind_eligibility"]["fault_assignment"]["maximum_distance_km"]),
            "minimum_second_to_first_distance_ratio": float(protocol["blind_eligibility"]["fault_assignment"]["minimum_second_to_first_distance_ratio"]),
        },
        "scientific_replicates": int(protocol["observation_model"]["uncertainty_propagation_replicates"]),
        "engineering_replicates": 0,
        "crosswalk_materialized": False,
        "perturbation_draws_executed": False,
        "defer_reason": "PARENT_GRAPH_LOCK_DOES_NOT_CONSUME_LOCATION_PERTURBATION_DRAWS",
        "fault_topology": {
            "connection_rule": "EXACT_GEOMETRIC_INTERSECTION_ONLY_NO_GAP_TOLERANCE",
            "network_path_rule": "SHORTEST_PATH_ALONG_LINES_THROUGH_EXACT_INTERSECTIONS",
            "selected_line_count": len(selected_lines),
            "exact_intersection_pair_count": len(intersections),
            "component_count": len(network_components),
        },
        "sealed_test_scored": False,
        "scientific_dynamic_model_execution_performed": False,
        "authority_ceiling": "FINITE_PARENT_GRAPH_LOCK_ONLY",
        "promotion": "BLOCKED",
    }
    operator["operator_id"] = "h12locop:" + hashlib.sha256(canonical(operator)).hexdigest()

    result = {
        "format": "KCH_HELICAL_V0_12_EXACT_TOPOLOGY_LOCK_RESULT",
        "protocol_id": PROTOCOL_ID,
        "outcome": "EXACT_INTERSECTION_TOPOLOGY_LOCK_PASS",
        "fault_geojson_sha256": FAULT_SHA256,
        "selected_event_count": EXPECTED_EVENTS,
        "axis_observable_count": int(np.sum(observable)),
        "selected_fault_line_count": len(selected_lines),
        "exact_intersection_pair_count": len(intersections),
        "exact_intersection_point_count": int(sum(row["point_count"] for row in intersections)),
        "component_count": len(network_components),
        "largest_component_line_count": max((len(component) for component in network_components), default=0),
        "cohorts": topology_by_cohort,
        "location_operator_id": operator["operator_id"],
        "location_operator_executed": False,
        "sealed_test_scored": False,
        "scientific_dynamic_model_execution_performed": False,
        "next_material_gate": "ETAS_HAWKES_PARENT_GRAPH_TRAIN_ONLY_CALIBRATION_LOCK",
        "authority_ceiling": "FINITE_PARENT_GRAPH_LOCK_ONLY",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    result["gate_id"] = "h12topo:" + hashlib.sha256(canonical(result)).hexdigest()

    write_json(args.out / "FAULT_NETWORK_TOPOLOGY_INTERSECTIONS_V0_8.json", intersections)
    write_json(args.out / "LOCATION_PERTURBATION_OPERATOR_LOCK_V0_8.json", operator)
    write_json(args.out / "EXACT_TOPOLOGY_LOCK_RESULT_V0_12.json", result)
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
