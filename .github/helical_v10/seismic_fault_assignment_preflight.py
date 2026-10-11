from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, Point, shape
from shapely.strtree import STRtree

MAX_DISTANCE_KM = 10.0
MIN_SECOND_TO_FIRST_RATIO = 1.5
MAX_PARENT_AGE_DAYS = 30.0
MAX_NETWORK_PATH_KM = 20.0
MAX_PARENTS = 20
MIN_ASSIGNED_EVENTS = 800
MIN_COVERAGE = 0.75
MIN_TEST_CHILDREN_WITH_PARENT = 200
PRIMARY_REGIONS = ["BAY_AREA", "PARKFIELD_CENTRAL_SAF", "MENDOCINO_TRIPLE_JUNCTION", "NORTHERN_WALKER_LANE"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def flatten(geometry: Any) -> Iterable[LineString]:
    if isinstance(geometry, LineString):
        yield geometry
    elif isinstance(geometry, MultiLineString):
        yield from geometry.geoms


def load_faults(path: Path) -> tuple[list[LineString], list[dict[str, Any]], Transformer]:
    root = json.loads(path.read_text(encoding="utf-8"))
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3310", always_xy=True)
    lines: list[LineString] = []
    metadata: list[dict[str, Any]] = []
    for feature_index, feature in enumerate(root.get("features", [])):
        geometry = shape(feature.get("geometry"))
        props = feature.get("properties", {}) or {}
        for part_index, line in enumerate(flatten(geometry)):
            coords = [transformer.transform(float(x), float(y)) for x, y, *rest in line.coords]
            if len(coords) < 2:
                continue
            projected = LineString(coords)
            minx, miny, maxx, maxy = projected.bounds
            # California-oriented envelope with buffer; excludes global lines irrelevant to candidates.
            if maxx < -600000 or minx > 800000 or maxy < -500000 or miny > 1800000:
                continue
            lines.append(projected)
            metadata.append({
                "feature_index": feature_index,
                "part_index": part_index,
                "catalog_id": props.get("catalog_id"),
                "catalog_name": props.get("catalog_name"),
                "name": props.get("name"),
                "slip_type": props.get("slip_type"),
            })
    if not lines:
        raise RuntimeError("no fault lines survived projected California envelope")
    return lines, metadata, transformer


def assign_events(frame: pd.DataFrame, lines: list[LineString], transformer: Transformer) -> pd.DataFrame:
    tree = STRtree(lines)
    rows: list[dict[str, Any]] = []
    for source_index, row in frame.iterrows():
        x, y = transformer.transform(float(row["longitude"]), float(row["latitude"]))
        point = Point(x, y)
        candidates = tree.query(point.buffer(MAX_DISTANCE_KM * 1000.0))
        if len(candidates) == 0:
            rows.append({"source_index": int(source_index), "fault_index": -1, "nearest_km": None, "second_km": None, "along_fault_km": None, "reason": "NO_FAULT_WITHIN_10KM"})
            continue
        pairs = sorted((float(lines[int(index)].distance(point)) / 1000.0, int(index)) for index in candidates)
        nearest_km, nearest_index = pairs[0]
        second_km = pairs[1][0] if len(pairs) > 1 else float("inf")
        ratio = float("inf") if nearest_km <= 1e-12 else second_km / nearest_km
        if nearest_km > MAX_DISTANCE_KM:
            fault_index = -1; reason = "NO_FAULT_WITHIN_10KM"; along = None
        elif ratio < MIN_SECOND_TO_FIRST_RATIO:
            fault_index = -1; reason = "AMBIGUOUS_NEAREST_FAULT"; along = None
        else:
            fault_index = nearest_index; reason = "ASSIGNED"; along = float(lines[nearest_index].project(point)) / 1000.0
        rows.append({
            "source_index": int(source_index),
            "fault_index": int(fault_index),
            "nearest_km": nearest_km,
            "second_km": None if math.isinf(second_km) else second_km,
            "along_fault_km": along,
            "reason": reason,
        })
    assigned = pd.DataFrame(rows).set_index("source_index")
    return frame.join(assigned, how="left")


def parent_support(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame[frame["fault_index"] >= 0].copy()
    data = data.sort_values(["time_utc", "event_id"], kind="stable").reset_index(drop=True)
    data["candidate_parent_count"] = 0
    maximum_age_seconds = MAX_PARENT_AGE_DAYS * 86400.0
    histories: dict[int, deque[tuple[float, float]]] = defaultdict(deque)
    counts = np.zeros(len(data), dtype=np.int16)
    epochs = pd.to_datetime(data["time_utc"], utc=True).astype("int64").to_numpy(dtype=np.int64) / 1e9
    along = data["along_fault_km"].to_numpy(dtype=float)
    faults = data["fault_index"].to_numpy(dtype=int)
    for child in range(len(data)):
        queue = histories[int(faults[child])]
        child_time = float(epochs[child])
        while queue and child_time - queue[0][0] > maximum_age_seconds:
            queue.popleft()
        count = 0
        for parent_time, parent_along in reversed(queue):
            if abs(float(along[child]) - parent_along) <= MAX_NETWORK_PATH_KM:
                count += 1
                if count >= MAX_PARENTS:
                    break
        counts[child] = count
        queue.append((child_time, float(along[child])))
    data["candidate_parent_count"] = counts
    data["parent_available"] = counts > 0
    n = len(data)
    train_end = int(math.floor(0.5 * n))
    calibration_end = int(math.floor(0.75 * n))
    split = np.full(n, "TEST", dtype="U11")
    split[:train_end] = "TRAIN"
    split[train_end:calibration_end] = "CALIBRATION"
    data["split"] = split
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--census-root", type=Path, required=True)
    parser.add_argument("--fault-geojson", type=Path, required=True)
    parser.add_argument("--expected-fault-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    if sha256_file(args.fault_geojson) != args.expected_fault_sha256:
        raise SystemExit("fault network SHA-256 mismatch")
    census_report = json.loads((args.census_root / "SEISMIC_BLIND_CENSUS_REPORT.json").read_text(encoding="utf-8"))
    if census_report.get("directional_angles_accessed") is not False:
        raise SystemExit("upstream blind firewall violation")
    lines, metadata, transformer = load_faults(args.fault_geojson)
    summaries: list[dict[str, Any]] = []
    metadata_path = args.out / "FAULT_LINE_METADATA.json"
    write_json(metadata_path, metadata)
    for region in PRIMARY_REGIONS:
        source = args.census_root / "blind_events" / f"{region}.csv.gz"
        frame = pd.read_csv(source, low_memory=False)
        frame["time_utc"] = pd.to_datetime(frame["time_utc"], utc=True, errors="raise")
        assigned = assign_events(frame, lines, transformer)
        supported = parent_support(assigned)
        assigned_path = args.out / "assigned" / f"{region}.csv.gz"
        assigned_path.parent.mkdir(parents=True, exist_ok=True)
        assigned.to_csv(assigned_path, index=False, compression="gzip")
        support_path = args.out / "parent_support" / f"{region}.csv.gz"
        support_path.parent.mkdir(parents=True, exist_ok=True)
        supported.to_csv(support_path, index=False, compression="gzip")
        assigned_count = int((assigned["fault_index"] >= 0).sum())
        coverage = assigned_count / max(len(assigned), 1)
        test = supported[supported["split"] == "TEST"]
        test_with_parent = int(test["parent_available"].sum())
        test_parent_fraction = test_with_parent / max(len(test), 1)
        eligible = assigned_count >= MIN_ASSIGNED_EVENTS and coverage >= MIN_COVERAGE and test_with_parent >= MIN_TEST_CHILDREN_WITH_PARENT
        summaries.append({
            "region": region,
            "blind_events": int(len(frame)),
            "assigned_events": assigned_count,
            "fault_assignment_coverage": coverage,
            "ambiguous_events": int((assigned["reason"] == "AMBIGUOUS_NEAREST_FAULT").sum()),
            "unassigned_distance_events": int((assigned["reason"] == "NO_FAULT_WITHIN_10KM").sum()),
            "unique_fault_segments": int(assigned.loc[assigned["fault_index"] >= 0, "fault_index"].nunique()),
            "train_events": int((supported["split"] == "TRAIN").sum()),
            "calibration_events": int((supported["split"] == "CALIBRATION").sum()),
            "sealed_test_events": int(len(test)),
            "sealed_test_children_with_same_segment_parent": test_with_parent,
            "sealed_test_parent_support_fraction": test_parent_fraction,
            "median_candidate_parents_test": float(test["candidate_parent_count"].median()) if len(test) else 0.0,
            "eligible_for_directional_opening": bool(eligible),
            "assigned_file_sha256": sha256_file(assigned_path),
            "parent_support_file_sha256": sha256_file(support_path),
        })
    summary = pd.DataFrame(summaries).sort_values(["eligible_for_directional_opening", "assigned_events", "region"], ascending=[False, False, True])
    summary_path = args.out / "FAULT_ASSIGNMENT_PARENT_SUPPORT_SUMMARY.csv"
    summary.to_csv(summary_path, index=False)
    eligible = summary[summary["eligible_for_directional_opening"]]
    selected = eligible.head(3)["region"].tolist()
    outcome = "FAULT_ASSIGNMENT_PREFLIGHT_PASS" if len(eligible) >= 2 else "NOT_IDENTIFIABLE_FAULT_ASSIGNMENT_OR_PARENT_GRAPH"
    report = {
        "format": "KCH_HELICAL_V1_0_POST2021_FAULT_ASSIGNMENT_PREFLIGHT",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "upstream_census_id": census_report.get("census_id"),
        "fault_network_sha256": sha256_file(args.fault_geojson),
        "fault_line_count": len(lines),
        "assignment_contract": {
            "maximum_distance_km": MAX_DISTANCE_KM,
            "minimum_second_to_first_distance_ratio": MIN_SECOND_TO_FIRST_RATIO,
            "ambiguous_event_action": "ABSTAIN",
            "event_cloud_clustering_for_topology": "FORBIDDEN",
        },
        "parent_support_contract": {
            "same_segment_only_diagnostic": True,
            "maximum_parent_age_days": MAX_PARENT_AGE_DAYS,
            "maximum_path_km": MAX_NETWORK_PATH_KM,
            "maximum_candidate_parents": MAX_PARENTS,
        },
        "cohorts": summaries,
        "eligible_primary_cohorts": eligible["region"].tolist(),
        "selected_for_future_directional_opening": selected,
        "outcome": outcome,
        "directional_angles_accessed": False,
        "product_details_accessed": False,
        "scientific_model_execution_performed": False,
        "authority_ceiling": "NONE",
    }
    report["preflight_id"] = "s9f:" + sha256_bytes(canonical(report))
    write_json(args.out / "FAULT_ASSIGNMENT_PREFLIGHT_REPORT.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if outcome == "FAULT_ASSIGNMENT_PREFLIGHT_PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
