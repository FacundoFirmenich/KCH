from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
from numpy.typing import NDArray
from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, Point, shape
from shapely.strtree import STRtree

ALLOWED = (
    "num", "nc_sc", "ev_bl", "year", "month", "day", "hour", "minute", "second",
    "time_utc", "evid", "lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "npol", "prob",
)
EVENT_FIELDS = tuple(name for name in ALLOWED if name != "num")
SEALED_FIELDS = (
    "strike", "dip", "rake", "strike_orig", "dip_orig", "rake_orig",
    "ftype", "p_azi", "p_dip", "t_azi", "t_dip",
)
CHUNK = 8 * 1024 * 1024


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def audit_protocol(path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    raw = path.read_bytes()
    protocol = json.loads(raw.decode("utf-8"))
    stripped = dict(protocol)
    protocol_id = stripped.pop("protocol_id")
    declared_hash = stripped.pop("protocol_sha256")
    calculated = hashlib.sha256(canonical(stripped)).hexdigest()
    if protocol_id != f"h8p:{calculated}" or declared_hash != calculated:
        raise RuntimeError("protocol content-address mismatch")
    if protocol.get("status") != "LOCKED_BEFORE_REAL_MECHANISM_ANGLE_ACCESS":
        raise RuntimeError("protocol is not in the required locked state")
    return protocol, {
        "protocol_id": protocol_id,
        "protocol_content_sha256": calculated,
        "protocol_file_sha256": hashlib.sha256(raw).hexdigest(),
    }


def parse_time(columns: Mapping[str, NDArray[Any]]) -> NDArray[np.float64]:
    raw = columns["time_utc"]
    parsed: list[float] = []
    ok = True
    for value in raw:
        try:
            text = str(value).strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            parsed.append(dt.timestamp())
        except Exception:
            ok = False
            break
    if ok:
        return np.asarray(parsed, dtype=float)
    result: list[float] = []
    for values in zip(columns["year"], columns["month"], columns["day"], columns["hour"], columns["minute"], columns["second"]):
        year, month, day, hour, minute = [int(float(x)) for x in values[:5]]
        second = float(values[5])
        whole = int(math.floor(second))
        micro = int(round((second - whole) * 1_000_000))
        dt = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
        result.append(dt.timestamp() + whole + micro / 1_000_000)
    return np.asarray(result, dtype=float)


def quality_mask(columns: Mapping[str, NDArray[Any]], protocol: Mapping[str, Any]) -> NDArray[np.bool_]:
    rule = protocol["blind_eligibility"]["quality_filter"]
    n = len(columns["evid"])
    mask = np.ones(n, dtype=bool)
    event_type = np.char.lower(np.char.strip(np.asarray(columns["ev_bl"]).astype(str)))
    if rule["earthquake_not_blast"]:
        earthquake_tokens = np.asarray(["e", "eq", "earthquake", "local earthquake", "le"])
        # Unknown codebook values are conservatively excluded rather than guessed.
        mask &= np.isin(event_type, earthquake_tokens)
    uncer = np.asarray(columns["uncer"], dtype=float)
    npol = np.asarray(columns["npol"], dtype=float)
    prob = np.asarray(columns["prob"], dtype=float)
    mask &= np.isfinite(uncer) & (uncer <= float(rule["maximum_mechanism_uncertainty_deg"]))
    mask &= np.isfinite(npol) & (npol >= float(rule["minimum_number_of_polarities"]))
    mask &= np.isfinite(prob) & (prob >= float(rule["minimum_solution_probability"]))
    lat = np.asarray(columns["lat_reloc"], dtype=float)
    lon = np.asarray(columns["lon_reloc"], dtype=float)
    depth = np.asarray(columns["dep_reloc"], dtype=float)
    mask &= np.isfinite(lat) & np.isfinite(lon) & np.isfinite(depth)
    return mask


@dataclass(frozen=True)
class FaultIndex:
    geometries: tuple[LineString, ...]
    tree: STRtree
    transformer: Transformer


def flatten_lines(geometry: Any) -> Iterable[LineString]:
    if isinstance(geometry, LineString):
        yield geometry
    elif isinstance(geometry, MultiLineString):
        yield from geometry.geoms


def load_fault_index(path: Path, expected_sha256: str) -> FaultIndex:
    observed = sha256_file(path)
    if observed != expected_sha256:
        raise RuntimeError(f"fault network SHA-256 mismatch: {observed}")
    root = json.loads(path.read_text(encoding="utf-8"))
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3310", always_xy=True)
    lines: list[LineString] = []
    for feature in root.get("features", []):
        geometry = shape(feature.get("geometry"))
        for line in flatten_lines(geometry):
            coords = [transformer.transform(x, y) for x, y in line.coords]
            if len(coords) >= 2:
                lines.append(LineString(coords))
    if not lines:
        raise RuntimeError("fault network contains no line geometries")
    return FaultIndex(tuple(lines), STRtree(lines), transformer)


def assign_faults(lat: NDArray[np.float64], lon: NDArray[np.float64], index: FaultIndex, *, max_distance_km: float, ambiguity_ratio: float) -> NDArray[np.int64]:
    assigned = np.full(len(lat), -1, dtype=np.int64)
    for i, (la, lo) in enumerate(zip(lat, lon)):
        x, y = index.transformer.transform(float(lo), float(la))
        point = Point(x, y)
        candidates = np.asarray(index.tree.query(point, predicate="dwithin", distance=max_distance_km * 1000.0), dtype=np.int64)
        if len(candidates) == 0:
            continue
        distances = sorted(((float(point.distance(index.geometries[int(j)])) / 1000.0, int(j)) for j in candidates), key=lambda item: (item[0], item[1]))
        d1, j1 = distances[0]
        d2 = distances[1][0] if len(distances) > 1 else math.inf
        if d1 <= max_distance_km and (math.isinf(d2) or d2 / max(d1, 1e-9) >= ambiguity_ratio):
            assigned[i] = j1
    return assigned


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--safe-npz", required=True, type=Path)
    parser.add_argument("--extraction-receipt", required=True, type=Path)
    parser.add_argument("--acquisition-receipt", required=True, type=Path)
    parser.add_argument("--fault-geojson", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    protocol, lock = audit_protocol(args.protocol)
    acquisition = json.loads(args.acquisition_receipt.read_text(encoding="utf-8"))
    extraction = json.loads(args.extraction_receipt.read_text(encoding="utf-8"))
    if acquisition.get("outcome") != "EXACT_BYTE_ACQUISITION_PASS" or acquisition.get("all_or_none_pass") is not True:
        raise RuntimeError("acquisition receipt is not PASS")
    if extraction.get("sealed_fields_emitted") != [] or extraction.get("angle_fields_accessed_by_outer_selection") is not False:
        raise RuntimeError("blind barrier violation")
    if extraction.get("output_sha256") != sha256_file(args.safe_npz):
        raise RuntimeError("safe NPZ hash mismatch")
    mechanism_sha = acquisition["mechanism_receipt"]["sha256"]
    if extraction.get("source_sha256") != mechanism_sha:
        raise RuntimeError("mechanism lineage mismatch")
    fault_sha = acquisition["fault_receipt"]["sha256"]
    if sha256_file(args.fault_geojson) != fault_sha:
        raise RuntimeError("fault lineage mismatch")

    with np.load(args.safe_npz, allow_pickle=False) as loaded:
        if set(loaded.files) != set(ALLOWED):
            raise RuntimeError(f"unexpected safe NPZ fields: {loaded.files}")
        columns = {name: loaded[name] for name in ALLOWED}
    lengths = {name: len(columns[name]) for name in EVENT_FIELDS}
    if len(set(lengths.values())) != 1:
        raise RuntimeError(f"event field length mismatch: {lengths}")

    fault_index = load_fault_index(args.fault_geojson, fault_sha)
    mask_quality = quality_mask(columns, protocol)
    lat = np.asarray(columns["lat_reloc"], dtype=float)
    lon = np.asarray(columns["lon_reloc"], dtype=float)
    times = parse_time(columns)
    assignment_rule = protocol["blind_eligibility"]["fault_assignment"]
    rows: list[dict[str, Any]] = []
    for candidate in protocol["candidate_cohorts"]:
        lat_min, lat_max, lon_min, lon_max = map(float, candidate["bbox"])
        spatial = (lat >= lat_min) & (lat <= lat_max) & (lon >= lon_min) & (lon <= lon_max)
        indices = np.flatnonzero(mask_quality & spatial)
        if len(indices):
            assigned = assign_faults(
                lat[indices], lon[indices], fault_index,
                max_distance_km=float(assignment_rule["maximum_distance_km"]),
                ambiguity_ratio=float(assignment_rule["minimum_second_to_first_distance_ratio"]),
            ) >= 0
            assigned_count = int(np.sum(assigned))
            coverage = assigned_count / len(indices)
            selected_times = times[indices][assigned]
            span_years = ((float(np.max(selected_times)) - float(np.min(selected_times))) / (365.2425 * 86400.0)) if len(selected_times) >= 2 else 0.0
        else:
            assigned_count, coverage, span_years = 0, 0.0, 0.0
        eligible = (
            assigned_count >= int(protocol["blind_eligibility"]["minimum_eligible_events"])
            and assigned_count * float(protocol["future_only_split"]["sealed_test"]) >= int(protocol["blind_eligibility"]["minimum_test_events"])
            and span_years >= float(protocol["blind_eligibility"]["minimum_time_span_years"])
            and coverage >= float(protocol["blind_eligibility"]["minimum_fault_assignment_coverage"])
        )
        rows.append({
            "candidate_id": candidate["id"], "role": candidate["role"],
            "quality_and_bbox_count": int(len(indices)),
            "unambiguous_fault_assigned_count": assigned_count,
            "fault_assignment_coverage": float(coverage),
            "time_span_years": float(span_years),
            "eligible": bool(eligible),
        })

    primary = sorted((row for row in rows if row["role"] == "PRIMARY" and row["eligible"]), key=lambda row: (-row["unambiguous_fault_assigned_count"], row["candidate_id"]))
    selected = primary[:3]
    minimum = int(protocol["blind_eligibility"]["minimum_primary_cohorts_to_execute"])
    if len(selected) >= minimum:
        outcome = "ELIGIBILITY_PASS"
    else:
        prelim = [row for row in rows if row["role"] == "PRIMARY" and row["quality_and_bbox_count"] >= int(protocol["blind_eligibility"]["minimum_eligible_events"])]
        outcome = "NOT_IDENTIFIABLE_FAULT_ASSIGNMENT" if len(prelim) >= minimum else "NOT_IDENTIFIABLE_MECHANISM_COVERAGE"

    ev_bl_values, ev_bl_counts = np.unique(np.asarray(columns["ev_bl"]).astype(str), return_counts=True)
    body = {
        "format": "KCH_HELICAL_V0_9_BLIND_ELIGIBILITY_RESULT",
        **lock,
        "executed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "source_lineage": {
            "mechanism_sha256": mechanism_sha,
            "fault_sha256": fault_sha,
            "safe_npz_sha256": extraction["output_sha256"],
            "acquisition_receipt_id": acquisition["receipt_id"],
            "extraction_receipt_id": extraction["receipt_id"],
        },
        "angle_fields_accessed": False,
        "sealed_fields": list(SEALED_FIELDS),
        "event_count": int(len(columns["evid"])),
        "quality_pass_count": int(np.sum(mask_quality)),
        "event_type_counts": {str(k): int(v) for k, v in zip(ev_bl_values, ev_bl_counts)},
        "fault_geometry_count": int(len(fault_index.geometries)),
        "candidate_results": rows,
        "selected_primary_cohorts": [row["candidate_id"] for row in selected],
        "execution_authorized": len(selected) >= minimum,
        "outcome": outcome,
        "directional_unsealing_authorized": outcome == "ELIGIBILITY_PASS",
        "scientific_model_fitting_authorized": False,
        "physical_helicity_evaluated": False,
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "authority_ceiling": "NONE",
        "software_versions": {
            "numpy": importlib.metadata.version("numpy"),
            "shapely": importlib.metadata.version("shapely"),
            "pyproj": importlib.metadata.version("pyproj"),
        },
    }
    body["eligibility_result_id"] = "h9elig:" + hashlib.sha256(canonical(body)).hexdigest()
    write_json(args.output, body)
    print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
