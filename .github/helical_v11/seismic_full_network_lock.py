from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from bisect import bisect_left
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import networkx as nx
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, Point, shape
from shapely.ops import nearest_points
from shapely.strtree import STRtree

VARIANTS = {
    "STRICT": {"line_gap_km": 2.0, "endpoint_gap_km": 5.0},
    "PRIMARY": {"line_gap_km": 5.0, "endpoint_gap_km": 10.0},
    "LIBERAL": {"line_gap_km": 10.0, "endpoint_gap_km": 15.0},
}
SELECTED = ["BAY_AREA", "PARKFIELD_CENTRAL_SAF"]
MAX_PARENT_AGE_DAYS = 30.0
MAX_NETWORK_PATH_KM = 20.0
MAX_CANDIDATE_PARENTS = 20
SECOND_PATH_AMBIGUITY_RATIO = 1.10
ETAS = {"alpha": 1.0, "p": 1.1, "c_days": 0.05, "ell_km": 5.0}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def flatten(geometry: Any) -> Iterable[LineString]:
    if isinstance(geometry, LineString):
        yield geometry
    elif isinstance(geometry, MultiLineString):
        yield from geometry.geoms


def load_faults(path: Path) -> tuple[list[LineString], list[dict[str, Any]], list[bool]]:
    root = json.loads(path.read_text(encoding="utf-8"))
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3310", always_xy=True)
    lines: list[LineString] = []
    metadata: list[dict[str, Any]] = []
    reversed_flags: list[bool] = []
    for feature_index, feature in enumerate(root.get("features", [])):
        geometry = shape(feature.get("geometry"))
        props = feature.get("properties", {}) or {}
        for part_index, line in enumerate(flatten(geometry)):
            geographic = [(float(x), float(y)) for x, y, *rest in line.coords]
            if len(geographic) < 2:
                continue
            projected_original = LineString([transformer.transform(x, y) for x, y in geographic])
            minx, miny, maxx, maxy = projected_original.bounds
            if maxx < -600000 or minx > 800000 or maxy < -500000 or miny > 1800000:
                continue
            first, last = geographic[0], geographic[-1]
            reverse = (first[1] > last[1]) or (first[1] == last[1] and first[0] > last[0])
            canonical_geo = list(reversed(geographic)) if reverse else geographic
            canonical_line = LineString([transformer.transform(x, y) for x, y in canonical_geo])
            lines.append(canonical_line)
            reversed_flags.append(reverse)
            metadata.append({
                "fault_index": len(lines) - 1,
                "feature_index": feature_index,
                "part_index": part_index,
                "catalog_id": props.get("catalog_id"),
                "catalog_name": props.get("catalog_name"),
                "name": props.get("name"),
                "slip_type": props.get("slip_type"),
                "canonical_orientation": "SOUTH_TO_NORTH_THEN_WEST_TO_EAST",
                "reversed_from_provider_geometry": reverse,
                "length_km": canonical_line.length / 1000.0,
            })
    if not lines:
        raise RuntimeError("no California fault lines loaded")
    return lines, metadata, reversed_flags


def endpoint_gap(line_a: LineString, line_b: LineString) -> float:
    endpoints_a = [Point(line_a.coords[0]), Point(line_a.coords[-1])]
    endpoints_b = [Point(line_b.coords[0]), Point(line_b.coords[-1])]
    return min(a.distance(b) for a in endpoints_a for b in endpoints_b)


def all_connections(lines: list[LineString]) -> list[dict[str, Any]]:
    tree = STRtree(lines)
    maximum = max(max(config.values()) for config in VARIANTS.values()) * 1000.0
    output: list[dict[str, Any]] = []
    for left, line in enumerate(lines):
        for candidate in tree.query(line.buffer(maximum)):
            right = int(candidate)
            if right <= left:
                continue
            other = lines[right]
            line_gap = float(line.distance(other))
            endpoint = float(endpoint_gap(line, other))
            memberships = [
                name
                for name, config in VARIANTS.items()
                if line_gap <= config["line_gap_km"] * 1000.0 or endpoint <= config["endpoint_gap_km"] * 1000.0
            ]
            if not memberships:
                continue
            point_left, point_right = nearest_points(line, other)
            output.append({
                "left_fault_index": left,
                "right_fault_index": right,
                "line_gap_km": line_gap / 1000.0,
                "endpoint_gap_km": endpoint / 1000.0,
                "left_along_km": float(line.project(point_left)) / 1000.0,
                "right_along_km": float(other.project(point_right)) / 1000.0,
                "left_x": float(point_left.x),
                "left_y": float(point_left.y),
                "right_x": float(point_right.x),
                "right_y": float(point_right.y),
                "variants": memberships,
            })
    return output


def build_junction_graph(lines: list[LineString], connections: list[dict[str, Any]], variant: str) -> tuple[nx.Graph, dict[int, list[float]], dict[tuple[int, float], str]]:
    positions: dict[int, set[float]] = {index: {0.0, round(line.length / 1000.0, 6)} for index, line in enumerate(lines)}
    selected = [row for row in connections if variant in row["variants"]]
    for row in selected:
        positions[int(row["left_fault_index"])].add(round(float(row["left_along_km"]), 6))
        positions[int(row["right_fault_index"])].add(round(float(row["right_along_km"]), 6))
    graph = nx.Graph()
    node_map: dict[tuple[int, float], str] = {}
    ordered_positions: dict[int, list[float]] = {}
    for fault_index, values in positions.items():
        ordered = sorted(values)
        ordered_positions[fault_index] = ordered
        for position_index, along in enumerate(ordered):
            node = f"f{fault_index}:p{position_index}"
            node_map[(fault_index, along)] = node
            point = lines[fault_index].interpolate(along * 1000.0)
            graph.add_node(node, fault_index=fault_index, along_km=along, x=float(point.x), y=float(point.y))
        for index in range(len(ordered) - 1):
            left = node_map[(fault_index, ordered[index])]
            right = node_map[(fault_index, ordered[index + 1])]
            graph.add_edge(left, right, weight=ordered[index + 1] - ordered[index], kind="ALONG_FAULT")
    for row in selected:
        left_key = (int(row["left_fault_index"]), round(float(row["left_along_km"]), 6))
        right_key = (int(row["right_fault_index"]), round(float(row["right_along_km"]), 6))
        graph.add_edge(
            node_map[left_key],
            node_map[right_key],
            weight=float(row["line_gap_km"]),
            kind="JUNCTION_GAP",
        )
    return graph, ordered_positions, node_map


def anchors(fault_index: int, along_km: float, positions: dict[int, list[float]], node_map: dict[tuple[int, float], str]) -> list[tuple[str, float]]:
    values = positions[fault_index]
    location = bisect_left(values, along_km)
    indices = sorted(set([max(0, location - 1), min(len(values) - 1, location)]))
    return [(node_map[(fault_index, values[index])], abs(along_km - values[index])) for index in indices]


class DistanceOracle:
    def __init__(self, graph: nx.Graph, positions: dict[int, list[float]], node_map: dict[tuple[int, float], str]):
        self.graph = graph
        self.positions = positions
        self.node_map = node_map
        self.cache: dict[str, dict[str, float]] = {}

    def lengths(self, node: str) -> dict[str, float]:
        if node not in self.cache:
            self.cache[node] = nx.single_source_dijkstra_path_length(self.graph, node, cutoff=MAX_NETWORK_PATH_KM, weight="weight")
        return self.cache[node]

    def distance(self, left_fault: int, left_along: float, right_fault: int, right_along: float) -> float | None:
        if left_fault == right_fault:
            return abs(left_along - right_along)
        best = float("inf")
        for left_node, left_cost in anchors(left_fault, left_along, self.positions, self.node_map):
            distances = self.lengths(left_node)
            for right_node, right_cost in anchors(right_fault, right_along, self.positions, self.node_map):
                middle = distances.get(right_node)
                if middle is None:
                    continue
                total = left_cost + middle + right_cost
                if total < best:
                    best = total
        return None if not math.isfinite(best) or best > MAX_NETWORK_PATH_KM else best


def canonical_along(original: float, fault_index: int, lines: list[LineString], reversed_flags: list[bool]) -> float:
    length = lines[fault_index].length / 1000.0
    return length - original if reversed_flags[fault_index] else original


def candidate_support(frame: pd.DataFrame, oracle: DistanceOracle) -> pd.DataFrame:
    data = frame[frame["fault_index"] >= 0].copy()
    data["time_utc"] = pd.to_datetime(data["time_utc"], utc=True, errors="raise")
    data = data.sort_values(["time_utc", "event_id"], kind="stable").reset_index(drop=True)
    n = len(data)
    train_end = int(math.floor(0.5 * n))
    calibration_end = int(math.floor(0.75 * n))
    split = np.full(n, "TEST", dtype="U11")
    split[:train_end] = "TRAIN"
    split[train_end:calibration_end] = "CALIBRATION"
    data["split"] = split
    times = data["time_utc"].astype("int64").to_numpy(dtype=np.int64) / 1e9
    faults = data["fault_index"].to_numpy(dtype=int)
    along = data["canonical_along_km"].to_numpy(dtype=float)
    magnitudes = pd.to_numeric(data["magnitude"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    maximum_age = MAX_PARENT_AGE_DAYS * 86400.0
    active: deque[int] = deque()
    counts = np.zeros(n, dtype=np.int16)
    cross_counts = np.zeros(n, dtype=np.int16)
    top_weights = np.zeros(n, dtype=float)
    second_weights = np.zeros(n, dtype=float)
    for child in range(n):
        child_time = float(times[child])
        while active and child_time - float(times[active[0]]) > maximum_age:
            active.popleft()
        candidates: list[tuple[float, int, float]] = []
        for parent in reversed(active):
            distance = oracle.distance(int(faults[parent]), float(along[parent]), int(faults[child]), float(along[child]))
            if distance is None:
                continue
            delta_days = max((child_time - float(times[parent])) / 86400.0, 1e-9)
            weight = math.exp(ETAS["alpha"] * magnitudes[parent]) * (delta_days + ETAS["c_days"]) ** (-ETAS["p"]) * math.exp(-distance / ETAS["ell_km"])
            candidates.append((weight, parent, distance))
        candidates.sort(reverse=True)
        candidates = candidates[:MAX_CANDIDATE_PARENTS]
        counts[child] = len(candidates)
        cross_counts[child] = sum(int(faults[parent] != faults[child]) for _, parent, _ in candidates)
        if candidates:
            top_weights[child] = candidates[0][0]
        if len(candidates) > 1:
            second_weights[child] = candidates[1][0]
        active.append(child)
    data["full_network_candidate_parent_count"] = counts
    data["cross_segment_candidate_parent_count"] = cross_counts
    data["top_parent_weight"] = top_weights
    data["second_parent_weight"] = second_weights
    data["top_to_second_weight_ratio"] = np.divide(top_weights, second_weights, out=np.full(n, np.inf), where=second_weights > 0)
    data["parent_graph_available"] = counts > 0
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    geojson = args.preflight_root / "source" / "gem_active_faults_harmonized.geojson"
    report_path = args.preflight_root / "FAULT_ASSIGNMENT_PREFLIGHT_REPORT.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    if report.get("directional_angles_accessed") is not False or report.get("selected_for_future_directional_opening") != SELECTED:
        raise RuntimeError("preflight blind-state or cohort-selection mismatch")
    lines, metadata, reversed_flags = load_faults(geojson)
    if len(lines) != int(report["fault_line_count"]):
        raise RuntimeError("fault line ordering mismatch")
    connections = all_connections(lines)
    variant_summaries: dict[str, Any] = {}
    primary_graph = None
    primary_positions = None
    primary_map = None
    for variant in VARIANTS:
        graph, positions, node_map = build_junction_graph(lines, connections, variant)
        components = sorted((len(component) for component in nx.connected_components(graph)), reverse=True)
        variant_summaries[variant] = {
            "junction_connections": sum(variant in row["variants"] for row in connections),
            "graph_nodes": graph.number_of_nodes(),
            "graph_edges": graph.number_of_edges(),
            "connected_components": len(components),
            "largest_component_nodes": components[0] if components else 0,
        }
        if variant == "PRIMARY":
            primary_graph, primary_positions, primary_map = graph, positions, node_map
    assert primary_graph is not None and primary_positions is not None and primary_map is not None
    oracle = DistanceOracle(primary_graph, primary_positions, primary_map)
    cohort_summaries: list[dict[str, Any]] = []
    event_files: list[dict[str, Any]] = []
    all_selected: list[pd.DataFrame] = []
    for region in SELECTED:
        source = args.preflight_root / "assigned" / f"{region}.csv.gz"
        frame = pd.read_csv(source, low_memory=False)
        assigned = frame[frame["fault_index"] >= 0].copy()
        assigned["fault_index"] = assigned["fault_index"].astype(int)
        assigned["canonical_along_km"] = [
            canonical_along(float(along), int(fault), lines, reversed_flags)
            for along, fault in zip(assigned["along_fault_km"], assigned["fault_index"])
        ]
        supported = candidate_support(assigned, oracle)
        path = args.out / "cohorts" / f"{region}_FULL_NETWORK_SUPPORT.csv.gz"
        path.parent.mkdir(parents=True, exist_ok=True)
        supported.to_csv(path, index=False, compression="gzip")
        all_selected.append(supported[["region", "event_id", "split", "fault_index", "canonical_along_km", "time_utc", "magnitude"]].copy())
        test = supported[supported["split"] == "TEST"]
        available = int(test["parent_graph_available"].sum())
        cross = int((test["cross_segment_candidate_parent_count"] > 0).sum())
        summary = {
            "region": region,
            "assigned_events": int(len(supported)),
            "train_events": int((supported["split"] == "TRAIN").sum()),
            "calibration_events": int((supported["split"] == "CALIBRATION").sum()),
            "sealed_test_events": int(len(test)),
            "test_children_with_full_network_parent": available,
            "test_parent_support_fraction": available / max(len(test), 1),
            "test_children_with_cross_segment_candidate": cross,
            "cross_segment_candidate_fraction": cross / max(len(test), 1),
            "median_candidate_parents_test": float(test["full_network_candidate_parent_count"].median()) if len(test) else 0.0,
            "support_file_sha256": sha256_file(path),
        }
        cohort_summaries.append(summary)
        event_files.append({"region": region, "path": path.relative_to(args.out).as_posix(), "sha256": sha256_file(path)})
    selected_events = pd.concat(all_selected, ignore_index=True).sort_values(["region", "time_utc", "event_id"], kind="stable")
    selected_path = args.out / "SELECTED_EVENT_IDS_AND_SPLITS.csv"
    selected_events.to_csv(selected_path, index=False)
    graph_payload = {
        "variant": "PRIMARY",
        "nodes": [{"id": node, **attrs} for node, attrs in sorted(primary_graph.nodes(data=True))],
        "edges": [
            {"left": left, "right": right, **attrs}
            for left, right, attrs in sorted(primary_graph.edges(data=True), key=lambda item: (item[0], item[1]))
        ],
    }
    graph_path = args.out / "PRIMARY_JUNCTION_GRAPH.json.gz"
    with gzip.open(graph_path, "wt", encoding="utf-8", newline="\n") as handle:
        json.dump(graph_payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        handle.write("\n")
    metadata_path = args.out / "FAULT_SEGMENT_METADATA_CANONICAL.json"
    write_json(metadata_path, metadata)
    connections_path = args.out / "FAULT_CONNECTIONS_ALL_VARIANTS.json"
    write_json(connections_path, connections)
    all_authorized = all(row["test_children_with_full_network_parent"] >= 200 for row in cohort_summaries)
    body = {
        "format": "KCH_SEISMIC_FULL_NETWORK_LOCK_V1_1",
        "status": "LOCKED_BEFORE_DIRECTIONAL_PRODUCT_ACCESS",
        "locked_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "upstream_preflight_id": report["preflight_id"],
        "fault_network_sha256": sha256_file(geojson),
        "selected_cohorts": SELECTED,
        "topology_contract": {
            "variants": VARIANTS,
            "primary_variant": "PRIMARY",
            "canonical_segment_orientation": "SOUTH_TO_NORTH_THEN_WEST_TO_EAST",
            "junction_rule": "LINE_GAP_OR_ENDPOINT_GAP",
            "path_metric": "SHORTEST_PHYSICAL_LENGTH_ON_JUNCTION_GRAPH",
            "second_path_ambiguity_ratio": SECOND_PATH_AMBIGUITY_RATIO,
            "ambiguous_path_action": "ABSTAIN",
            "event_cloud_clustering": "FORBIDDEN",
        },
        "parent_contract": {
            "maximum_parent_age_days": MAX_PARENT_AGE_DAYS,
            "maximum_network_path_km": MAX_NETWORK_PATH_KM,
            "maximum_candidate_parents": MAX_CANDIDATE_PARENTS,
            "etas_weight_parameters": ETAS,
            "parameters_changed_after_directional_access": False,
        },
        "variant_summaries": variant_summaries,
        "cohorts": cohort_summaries,
        "event_files": event_files,
        "selected_event_file_sha256": sha256_file(selected_path),
        "primary_graph_sha256": sha256_file(graph_path),
        "segment_metadata_sha256": sha256_file(metadata_path),
        "connections_sha256": sha256_file(connections_path),
        "directional_products_accessed": False,
        "directional_opening_authorized": all_authorized,
        "scientific_model_execution_performed": False,
        "authority_ceiling": "NONE",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    body["network_lock_id"] = "s11net:" + hashlib.sha256(canonical(body)).hexdigest()
    write_json(args.out / "SEISMIC_FULL_NETWORK_LOCK_V1_1.json", body)
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0 if all_authorized else 3


if __name__ == "__main__":
    raise SystemExit(main())
