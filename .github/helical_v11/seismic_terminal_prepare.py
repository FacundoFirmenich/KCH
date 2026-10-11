from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
from bisect import bisect_left
from collections import deque
from pathlib import Path
from typing import Any, Iterable

import networkx as nx
import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, Point, shape

DAY = 86400.0
MAX_AGE = 30.0 * DAY
MAX_DIST = 20.0
COHORT_CODES = {"BAY_AREA": 0, "PARKFIELD_CENTRAL_SAF": 1}
SPLIT_CODES = {"TRAIN": 0, "CALIBRATION": 1, "TEST": 2}


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


def load_faults(path: Path) -> tuple[list[LineString], Transformer]:
    root = json.loads(path.read_text(encoding="utf-8"))
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3310", always_xy=True)
    lines: list[LineString] = []
    for feature in root.get("features", []):
        for line in flatten(shape(feature.get("geometry"))):
            geographic = [(float(x), float(y)) for x, y, *rest in line.coords]
            if len(geographic) < 2:
                continue
            original = LineString([transformer.transform(x, y) for x, y in geographic])
            minx, miny, maxx, maxy = original.bounds
            if maxx < -600000 or minx > 800000 or maxy < -500000 or miny > 1800000:
                continue
            first, last = geographic[0], geographic[-1]
            reverse = (first[1] > last[1]) or (first[1] == last[1] and first[0] > last[0])
            canonical_geo = list(reversed(geographic)) if reverse else geographic
            lines.append(LineString([transformer.transform(x, y) for x, y in canonical_geo]))
    return lines, transformer


def tangent_at(line: LineString, along_km: float) -> np.ndarray:
    distance = float(np.clip(along_km * 1000.0, 0.0, line.length))
    epsilon = min(250.0, max(25.0, line.length / 100.0))
    left = line.interpolate(max(0.0, distance - epsilon))
    right = line.interpolate(min(line.length, distance + epsilon))
    dx = float(right.x - left.x)
    dy = float(right.y - left.y)
    norm = math.hypot(dx, dy)
    if norm <= 1e-12:
        raise RuntimeError("degenerate local fault tangent")
    return np.array([dy / norm, dx / norm, 0.0], dtype=float)


def p_axis(strike_deg: np.ndarray, dip_deg: np.ndarray, rake_deg: np.ndarray) -> np.ndarray:
    strike = np.deg2rad(strike_deg.astype(float))
    dip = np.deg2rad(dip_deg.astype(float))
    rake = np.deg2rad(rake_deg.astype(float))
    strike_vector = np.stack([np.cos(strike), np.sin(strike), np.zeros_like(strike)], axis=1)
    down_dip = np.stack(
        [-np.sin(strike) * np.cos(dip), np.cos(strike) * np.cos(dip), np.sin(dip)],
        axis=1,
    )
    normal = np.cross(strike_vector, down_dip)
    normal /= np.linalg.norm(normal, axis=1)[:, None]
    slip = np.cos(rake)[:, None] * strike_vector + np.sin(rake)[:, None] * down_dip
    slip /= np.linalg.norm(slip, axis=1)[:, None]
    axis = normal - slip
    axis /= np.linalg.norm(axis, axis=1)[:, None]
    return axis


def graph_from_payload(path: Path) -> tuple[nx.Graph, dict[int, list[float]], dict[tuple[int, float], str]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    graph = nx.Graph()
    positions: dict[int, list[float]] = {}
    node_map: dict[tuple[int, float], str] = {}
    for row in payload["nodes"]:
        node = str(row["id"])
        fault = int(row["fault_index"])
        along = float(row["along_km"])
        graph.add_node(node, **{key: value for key, value in row.items() if key != "id"})
        positions.setdefault(fault, []).append(along)
        node_map[(fault, along)] = node
    for fault in positions:
        positions[fault] = sorted(positions[fault])
    for row in payload["edges"]:
        graph.add_edge(str(row["left"]), str(row["right"]), weight=float(row["weight"]), kind=row.get("kind"))
    return graph, positions, node_map


def anchors(fault: int, along: float, positions: dict[int, list[float]], node_map: dict[tuple[int, float], str]) -> list[tuple[str, float]]:
    values = positions[fault]
    location = bisect_left(values, along)
    indices = sorted(set([max(0, location - 1), min(len(values) - 1, location)]))
    return [(node_map[(fault, values[index])], abs(along - values[index])) for index in indices]


class Oracle:
    def __init__(self, graph: nx.Graph, positions: dict[int, list[float]], node_map: dict[tuple[int, float], str]):
        self.graph = graph
        self.positions = positions
        self.node_map = node_map
        self.cache: dict[str, dict[str, float]] = {}

    def lengths(self, node: str) -> dict[str, float]:
        if node not in self.cache:
            self.cache[node] = nx.single_source_dijkstra_path_length(self.graph, node, cutoff=MAX_DIST, weight="weight")
        return self.cache[node]

    def distance(self, left_fault: int, left_along: float, right_fault: int, right_along: float) -> float | None:
        if left_fault == right_fault:
            distance = abs(left_along - right_along)
            return distance if distance <= MAX_DIST else None
        best = float("inf")
        for left_node, left_cost in anchors(left_fault, left_along, self.positions, self.node_map):
            lengths = self.lengths(left_node)
            for right_node, right_cost in anchors(right_fault, right_along, self.positions, self.node_map):
                middle = lengths.get(right_node)
                if middle is not None:
                    best = min(best, left_cost + middle + right_cost)
        return best if math.isfinite(best) and best <= MAX_DIST else None


def candidate_arrays(frame: pd.DataFrame, oracle: Oracle, tangents: np.ndarray, x: np.ndarray, y: np.ndarray) -> dict[str, np.ndarray]:
    starts = [0]
    parents: list[int] = []
    dt_values: list[float] = []
    distances: list[float] = []
    signs: list[float] = []
    curvature: list[float] = []
    for cohort_code in sorted(frame["cohort_code"].unique()):
        cohort_indices = frame.index[frame["cohort_code"] == cohort_code].to_numpy(dtype=int)
        cohort_indices = cohort_indices[np.argsort(frame.loc[cohort_indices, "event_time_epoch"].to_numpy(dtype=float), kind="stable")]
        active: deque[int] = deque()
        for child in cohort_indices:
            child_time = float(frame.at[child, "event_time_epoch"])
            while active and child_time - float(frame.at[active[0], "event_time_epoch"]) > MAX_AGE:
                active.popleft()
            child_fault = int(frame.at[child, "fault_assignment"])
            child_along = float(frame.at[child, "along_fault_km"])
            for parent in active:
                distance = oracle.distance(
                    int(frame.at[parent, "fault_assignment"]),
                    float(frame.at[parent, "along_fault_km"]),
                    child_fault,
                    child_along,
                )
                if distance is None:
                    continue
                dt_days = (child_time - float(frame.at[parent, "event_time_epoch"])) / DAY
                displacement = np.array([y[child] - y[parent], x[child] - x[parent]])
                child_tangent = tangents[child, :2]
                sign = 1.0 if float(np.dot(displacement, child_tangent)) >= 0.0 else -1.0
                parent_tangent = tangents[parent, :2] * sign
                target_tangent = child_tangent * sign
                cross = parent_tangent[0] * target_tangent[1] - parent_tangent[1] * target_tangent[0]
                dot = float(np.dot(parent_tangent, target_tangent))
                parents.append(int(parent))
                dt_values.append(float(dt_days))
                distances.append(float(distance))
                signs.append(sign)
                curvature.append(float(math.atan2(cross, dot)))
            starts.append(len(parents))
            active.append(int(child))
    # starts were appended by cohort-sorted child order, not dataframe index order. Rebuild by index.
    slices: dict[int, tuple[int, int]] = {}
    cursor = 0
    starts_iter = iter(starts[1:])
    # Recompute order consistently and map cumulative slices.
    cumulative_previous = 0
    for cohort_code in sorted(frame["cohort_code"].unique()):
        cohort_indices = frame.index[frame["cohort_code"] == cohort_code].to_numpy(dtype=int)
        cohort_indices = cohort_indices[np.argsort(frame.loc[cohort_indices, "event_time_epoch"].to_numpy(dtype=float), kind="stable")]
        for child in cohort_indices:
            cumulative = next(starts_iter)
            slices[int(child)] = (cumulative_previous, cumulative)
            cumulative_previous = cumulative
    ordered_starts = np.zeros(len(frame) + 1, dtype=np.int64)
    ordered_parent: list[int] = []
    ordered_dt: list[float] = []
    ordered_distance: list[float] = []
    ordered_sign: list[float] = []
    ordered_curvature: list[float] = []
    parent_array = np.asarray(parents, dtype=np.int64)
    dt_array = np.asarray(dt_values, dtype=float)
    distance_array = np.asarray(distances, dtype=float)
    sign_array = np.asarray(signs, dtype=float)
    curvature_array = np.asarray(curvature, dtype=float)
    for child in range(len(frame)):
        start, end = slices.get(child, (0, 0))
        ordered_parent.extend(parent_array[start:end].tolist())
        ordered_dt.extend(dt_array[start:end].tolist())
        ordered_distance.extend(distance_array[start:end].tolist())
        ordered_sign.extend(sign_array[start:end].tolist())
        ordered_curvature.extend(curvature_array[start:end].tolist())
        ordered_starts[child + 1] = len(ordered_parent)
    return {
        "candidate_starts": ordered_starts,
        "candidate_parent": np.asarray(ordered_parent, dtype=np.int64),
        "candidate_dt_days": np.asarray(ordered_dt, dtype=float),
        "candidate_distance_km": np.asarray(ordered_distance, dtype=float),
        "candidate_sign": np.asarray(ordered_sign, dtype=float),
        "candidate_curvature": np.asarray(ordered_curvature, dtype=float),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--network-root", type=Path, required=True)
    parser.add_argument("--directional-root", type=Path, required=True)
    parser.add_argument("--fault-geojson", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    lock = json.loads((args.network_root / "SEISMIC_FULL_NETWORK_LOCK_V1_1.json").read_text(encoding="utf-8"))
    acquisition = json.loads((args.directional_root / "SEISMIC_DIRECTIONAL_ACQUISITION_V1_1.json").read_text(encoding="utf-8"))
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol["network_lock_id"] != lock["network_lock_id"] or acquisition["network_lock_id"] != lock["network_lock_id"]:
        raise RuntimeError("network/protocol/acquisition identity mismatch")
    if acquisition.get("directional_coverage_gate_pass") is not True:
        raise RuntimeError("directional acquisition coverage gate failed")
    lines, transformer = load_faults(args.fault_geojson)
    if len(lines) != 625:
        raise RuntimeError(f"fault line ordering mismatch: {len(lines)}")
    mechanisms = pd.read_csv(args.directional_root / "SELECTED_DIRECTIONAL_MECHANISMS.csv.gz", low_memory=False)
    support_frames = []
    for region in lock["selected_cohorts"]:
        support_frames.append(pd.read_csv(args.network_root / "cohorts" / f"{region}_FULL_NETWORK_SUPPORT.csv.gz", low_memory=False))
    support = pd.concat(support_frames, ignore_index=True)
    merged = support.merge(
        mechanisms.drop(columns=[column for column in mechanisms.columns if column in support.columns and column not in {"region", "event_id"}]),
        on=["region", "event_id"], how="left", validate="one_to_one",
    )
    merged = merged[merged["parse_status"] == "PASS"].copy()
    merged["time_utc"] = pd.to_datetime(merged["time_utc"], format="mixed", utc=True, errors="raise")
    merged = merged.sort_values(["region", "time_utc", "event_id"], kind="stable").reset_index(drop=True)
    merged["cohort_code"] = merged["region"].map(COHORT_CODES).astype(int)
    merged["split_code"] = merged["split"].map(SPLIT_CODES).astype(int)
    merged["event_time_epoch"] = merged["time_utc"].astype("int64") / 1e9
    merged["year"] = merged["time_utc"].dt.year.astype(int)
    merged["fault_assignment"] = merged["fault_index"].astype(int)
    merged["along_fault_km"] = merged["canonical_along_km"].astype(float)
    tangents = np.vstack([
        tangent_at(lines[int(fault)], float(along))
        for fault, along in zip(merged["fault_assignment"], merged["along_fault_km"])
    ])
    p1 = p_axis(merged["np1_strike"].to_numpy(float), merged["np1_dip"].to_numpy(float), merged["np1_rake"].to_numpy(float))
    p2 = p_axis(merged["np2_strike"].to_numpy(float), merged["np2_dip"].to_numpy(float), merged["np2_rake"].to_numpy(float))
    equivalence = np.abs(np.sum(p1 * p2, axis=1))
    down = np.array([0.0, 0.0, 1.0])
    e1 = np.cross(np.broadcast_to(down, tangents.shape), tangents)
    e1 /= np.linalg.norm(e1, axis=1)[:, None]
    e2 = np.cross(tangents, e1)
    px = np.sum(p1 * e1, axis=1)
    py = np.sum(p1 * e2, axis=1)
    projection = np.sqrt(px * px + py * py)
    observable = (equivalence >= float(protocol["observation_model"]["nodal_plane_equivalence_minimum_absolute_dot"])) & (projection >= float(protocol["observation_model"]["minimum_axis_projection"]))
    projected = [transformer.transform(float(lon), float(lat)) for lon, lat in zip(merged["longitude"], merged["latitude"])]
    event_x = np.asarray([value[0] for value in projected], dtype=float)
    event_y = np.asarray([value[1] for value in projected], dtype=float)
    graph, positions, node_map = graph_from_payload(args.network_root / "PRIMARY_JUNCTION_GRAPH.json.gz")
    candidates = candidate_arrays(merged, Oracle(graph, positions, node_map), tangents, event_x, event_y)
    max_evid = max(len(str(value)) for value in merged["event_id"])
    directional_path = args.out / "SEISMIC_TERMINAL_DIRECTIONAL_V1_1.npz"
    preflight_path = args.out / "SEISMIC_TERMINAL_PREFLIGHT_V1_1.npz"
    np.savez_compressed(
        directional_path,
        strike=merged["np1_strike"].to_numpy(float),
        dip=merged["np1_dip"].to_numpy(float),
        rake=merged["np1_rake"].to_numpy(float),
        mag=pd.to_numeric(merged["magnitude"], errors="coerce").fillna(0.0).to_numpy(float),
        uncer=np.full(len(merged), float(protocol["observation_model"]["primary_mechanism_angle_sigma_deg"]), dtype=float),
        year=merged["year"].to_numpy(int),
        event_time_epoch=merged["event_time_epoch"].to_numpy(float),
        cohort_code=merged["cohort_code"].to_numpy(np.int8),
        split_code=merged["split_code"].to_numpy(np.int8),
        fault_assignment=merged["fault_assignment"].to_numpy(int),
        nearest_km=pd.to_numeric(merged["nearest_km"], errors="coerce").to_numpy(float),
        second_km=pd.to_numeric(merged["second_km"], errors="coerce").to_numpy(float),
        evid=merged["event_id"].astype(f"U{max_evid}").to_numpy(),
        nodal_plane_equivalence=equivalence,
    )
    np.savez_compressed(
        preflight_path,
        axis_observable=observable.astype(bool),
        projection_norm=projection,
        tangent_ned=tangents,
        along_fault_km=merged["along_fault_km"].to_numpy(float),
        event_x=event_x,
        event_y=event_y,
        **candidates,
    )
    cohort_report = []
    for region, code in COHORT_CODES.items():
        mask = merged["cohort_code"].to_numpy(int) == code
        test = mask & (merged["split_code"].to_numpy(int) == 2)
        cohort_report.append({
            "region": region,
            "parsed_events": int(mask.sum()),
            "observable_events": int(np.sum(mask & observable)),
            "observable_fraction": float(np.mean(observable[mask])) if mask.any() else 0.0,
            "sealed_test_parsed_events": int(test.sum()),
            "sealed_test_observable_events": int(np.sum(test & observable)),
            "candidate_edges": int(sum(candidates["candidate_starts"][np.flatnonzero(mask) + 1] - candidates["candidate_starts"][np.flatnonzero(mask)])),
        })
    report = {
        "format": "KCH_SEISMIC_TERMINAL_INPUT_MATERIALIZATION_V1_1",
        "network_lock_id": lock["network_lock_id"],
        "directional_acquisition_id": acquisition["directional_acquisition_id"],
        "protocol_sha256": sha256_file(args.protocol),
        "fault_network_sha256": sha256_file(args.fault_geojson),
        "cohorts": cohort_report,
        "total_parsed_events": len(merged),
        "total_axis_observable_events": int(observable.sum()),
        "nodal_plane_equivalence_failures": int(np.sum(equivalence < float(protocol["observation_model"]["nodal_plane_equivalence_minimum_absolute_dot"]))),
        "projection_failures": int(np.sum(projection < float(protocol["observation_model"]["minimum_axis_projection"]))),
        "candidate_edge_count": int(len(candidates["candidate_parent"])),
        "directional_npz": {"path": directional_path.name, "sha256": sha256_file(directional_path)},
        "preflight_npz": {"path": preflight_path.name, "sha256": sha256_file(preflight_path)},
        "scientific_model_execution_performed": False,
        "authority_ceiling": "NONE",
    }
    report["materialization_id"] = "s11mat:" + hashlib.sha256(canonical(report)).hexdigest()
    write_json(args.out / "SEISMIC_TERMINAL_INPUT_MATERIALIZATION_V1_1.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
