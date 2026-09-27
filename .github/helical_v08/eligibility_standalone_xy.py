from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import pickle
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray
from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, Point, shape
from shapely.strtree import STRtree

def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")


ALLOWED_FIELDS = (
    "num", "nc_sc", "ev_bl", "year", "month", "day", "hour", "minute", "second",
    "time_utc", "evid", "lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "npol", "prob",
)
SEALED_FIELDS = (
    "strike", "dip", "rake", "strike_orig", "dip_orig", "rake_orig",
    "ftype", "p_azi", "p_dip", "t_azi", "t_dip",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _as_array(value: Any) -> NDArray[Any]:
    array = np.asarray(value)
    if array.ndim == 0:
        array = array.reshape(1)
    return array


def _extract_mapping(payload: Any) -> Mapping[str, Any]:
    if isinstance(payload, Mapping):
        return payload
    if hasattr(payload, "to_dict"):
        candidate = payload.to_dict()
        if isinstance(candidate, Mapping):
            return candidate
    raise TypeError(f"unsupported focal-mechanism pickle root: {type(payload)!r}")


def load_allowed_columns(pickle_path: Path, *, expected_sha256: str | None = None) -> dict[str, NDArray[Any]]:
    observed_sha = sha256_file(pickle_path)
    if expected_sha256 is not None and observed_sha != expected_sha256:
        raise ValueError(f"mechanism catalog SHA-256 mismatch: {observed_sha}")
    with pickle_path.open("rb") as fh:
        root = _extract_mapping(pickle.load(fh))
    missing = [field for field in ALLOWED_FIELDS if field not in root]
    if missing:
        raise KeyError(f"missing required blind-eligibility fields: {missing}")
    lengths = {field: len(_as_array(root[field])) for field in ALLOWED_FIELDS}
    if len(set(lengths.values())) != 1:
        raise ValueError(f"field-length mismatch: {lengths}")
    return {field: _as_array(root[field]).copy() for field in ALLOWED_FIELDS}


def _parse_time(columns: Mapping[str, NDArray[Any]]) -> NDArray[np.float64]:
    if "time_utc" in columns:
        raw = columns["time_utc"]
        parsed: list[float] = []
        ok = True
        for value in raw:
            try:
                if isinstance(value, datetime):
                    dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
                else:
                    text = str(value).replace("Z", "+00:00")
                    dt = datetime.fromisoformat(text)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                parsed.append(dt.timestamp())
            except Exception:
                ok = False
                break
        if ok:
            return np.asarray(parsed, dtype=float)
    result = []
    for values in zip(
        columns["year"], columns["month"], columns["day"],
        columns["hour"], columns["minute"], columns["second"],
    ):
        year, month, day, hour, minute = [int(x) for x in values[:5]]
        second = float(values[5])
        whole = int(math.floor(second))
        micro = int(round((second - whole) * 1_000_000))
        dt = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
        result.append(dt.timestamp() + whole + micro / 1_000_000)
    return np.asarray(result, dtype=float)


def quality_mask(columns: Mapping[str, NDArray[Any]], protocol: Mapping[str, Any]) -> NDArray[np.bool_]:
    rule = protocol["blind_eligibility"]["quality_filter"]
    mask = np.ones(len(columns["evid"]), dtype=bool)
    event_type = np.asarray(columns["ev_bl"]).astype(str)
    if rule["earthquake_not_blast"]:
        mask &= np.char.lower(event_type) != "b"
        mask &= np.char.lower(event_type) != "blast"
    mask &= np.asarray(columns["uncer"], dtype=float) <= float(rule["maximum_mechanism_uncertainty_deg"])
    mask &= np.asarray(columns["npol"], dtype=float) >= float(rule["minimum_number_of_polarities"])
    mask &= np.asarray(columns["prob"], dtype=float) >= float(rule["minimum_solution_probability"])
    lat = np.asarray(columns["lat_reloc"], dtype=float)
    lon = np.asarray(columns["lon_reloc"], dtype=float)
    depth = np.asarray(columns["dep_reloc"], dtype=float)
    mask &= np.isfinite(lat) & np.isfinite(lon) & np.isfinite(depth)
    return mask


@dataclass(frozen=True)
class FaultIndex:
    geometries: tuple[LineString, ...]
    properties: tuple[dict[str, Any], ...]
    tree: STRtree
    transformer: Transformer


def _flatten_lines(geometry: Any) -> Iterable[LineString]:
    if isinstance(geometry, LineString):
        yield geometry
    elif isinstance(geometry, MultiLineString):
        yield from geometry.geoms


def load_fault_index(geojson_path: Path, *, expected_sha256: str | None = None) -> FaultIndex:
    observed_sha = sha256_file(geojson_path)
    if expected_sha256 is not None and observed_sha != expected_sha256:
        raise ValueError(f"fault network SHA-256 mismatch: {observed_sha}")
    root = json.loads(geojson_path.read_text(encoding="utf-8"))
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3310", always_xy=True)
    lines: list[LineString] = []
    properties: list[dict[str, Any]] = []
    for feature in root.get("features", []):
        geom = shape(feature.get("geometry"))
        props = dict(feature.get("properties") or {})
        for line in _flatten_lines(geom):
            coords = [transformer.transform(float(coord[0]), float(coord[1])) for coord in line.coords]
            if len(coords) >= 2:
                lines.append(LineString(coords))
                properties.append(props)
    if not lines:
        raise ValueError("fault network contains no line geometries")
    return FaultIndex(tuple(lines), tuple(properties), STRtree(lines), transformer)


def assign_faults(
    lat: NDArray[np.float64],
    lon: NDArray[np.float64],
    fault_index: FaultIndex,
    *,
    max_distance_km: float,
    ambiguity_ratio: float,
) -> dict[str, NDArray[Any]]:
    n = len(lat)
    assigned = np.full(n, -1, dtype=np.int64)
    nearest_km = np.full(n, np.nan, dtype=float)
    second_km = np.full(n, np.nan, dtype=float)
    for i, (la, lo) in enumerate(zip(lat, lon)):
        x, y = fault_index.transformer.transform(float(lo), float(la))
        point = Point(x, y)
        candidates = np.asarray(
            fault_index.tree.query(point, predicate="dwithin", distance=max_distance_km * 2000.0),
            dtype=np.int64,
        )
        if len(candidates) == 0:
            continue
        distances = sorted(
            ((float(point.distance(fault_index.geometries[int(idx)])) / 1000.0, int(idx)) for idx in candidates),
            key=lambda item: (item[0], item[1]),
        )
        d1, idx1 = distances[0]
        d2 = distances[1][0] if len(distances) > 1 else math.inf
        nearest_km[i] = d1
        second_km[i] = d2
        if d1 <= max_distance_km and (math.isinf(d2) or d2 / max(d1, 1e-9) >= ambiguity_ratio):
            assigned[i] = idx1
    return {"fault_index": assigned, "nearest_km": nearest_km, "second_km": second_km}


def blind_eligibility(
    columns: Mapping[str, NDArray[Any]],
    fault_index: FaultIndex,
    protocol: Mapping[str, Any],
) -> dict[str, Any]:
    mask_quality = quality_mask(columns, protocol)
    lat = np.asarray(columns["lat_reloc"], dtype=float)
    lon = np.asarray(columns["lon_reloc"], dtype=float)
    times = _parse_time(columns)
    assignment_rule = protocol["blind_eligibility"]["fault_assignment"]
    candidate_rows: list[dict[str, Any]] = []
    for candidate in protocol["candidate_cohorts"]:
        lat_min, lat_max, lon_min, lon_max = [float(x) for x in candidate["bbox"]]
        spatial = (lat >= lat_min) & (lat <= lat_max) & (lon >= lon_min) & (lon <= lon_max)
        candidate_mask = mask_quality & spatial
        indices = np.flatnonzero(candidate_mask)
        if len(indices):
            assignment = assign_faults(
                lat[indices], lon[indices], fault_index,
                max_distance_km=float(assignment_rule["maximum_distance_km"]),
                ambiguity_ratio=float(assignment_rule["minimum_second_to_first_distance_ratio"]),
            )
            assigned = assignment["fault_index"] >= 0
            assigned_count = int(np.sum(assigned))
            coverage = assigned_count / len(indices)
            selected_times = times[indices][assigned]
            span_years = (
                (float(np.max(selected_times)) - float(np.min(selected_times))) / (365.2425 * 86400.0)
                if len(selected_times) >= 2
                else 0.0
            )
        else:
            assigned_count = 0
            coverage = 0.0
            span_years = 0.0
        eligible = (
            assigned_count >= int(protocol["blind_eligibility"]["minimum_eligible_events"])
            and assigned_count * float(protocol["future_only_split"]["sealed_test"])
            >= int(protocol["blind_eligibility"]["minimum_test_events"])
            and span_years >= float(protocol["blind_eligibility"]["minimum_time_span_years"])
            and coverage >= float(protocol["blind_eligibility"]["minimum_fault_assignment_coverage"])
        )
        candidate_rows.append(
            {
                "candidate_id": candidate["id"],
                "role": candidate["role"],
                "quality_and_bbox_count": int(len(indices)),
                "unambiguous_fault_assigned_count": assigned_count,
                "fault_assignment_coverage": float(coverage),
                "time_span_years": float(span_years),
                "eligible": bool(eligible),
            }
        )
    primary = [row for row in candidate_rows if row["role"] == "PRIMARY" and row["eligible"]]
    primary.sort(key=lambda row: (-row["unambiguous_fault_assigned_count"], row["candidate_id"]))
    selected = primary[:3]
    minimum = int(protocol["blind_eligibility"]["minimum_primary_cohorts_to_execute"])
    body = {
        "format": "KCH_HELICAL_V0_8_BLIND_ELIGIBILITY_RESULT",
        "protocol_id": protocol["protocol_id"],
        "angle_fields_accessed": False,
        "sealed_fields": list(SEALED_FIELDS),
        "candidate_results": candidate_rows,
        "selected_primary_cohorts": [row["candidate_id"] for row in selected],
        "execution_authorized": len(selected) >= minimum,
        "outcome": "ELIGIBILITY_PASS" if len(selected) >= minimum else "NOT_IDENTIFIABLE_MECHANISM_COVERAGE",
        "authority_ceiling": "NONE",
    }
    return {"eligibility_result_id": "h8elig:" + hashlib.sha256(canonical_json_bytes(body)).hexdigest(), **body}
