from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

COHORTS = {
    0: ("BAY_AREA_HAYWARD_CALAVERAS", (36.85, 38.45, -122.75, -121.15)),
    1: ("PARKFIELD_CENTRAL_SAF", (35.45, 36.25, -121.05, -119.95)),
}
START_YEAR = 1981
END_YEAR = 2021
LIMIT = 20_000
MINIMUM_BOTH_ERRORS_FRACTION = 0.80
BLIND_REQUIRED = {
    "nc_sc", "ev_bl", "year", "month", "day", "hour", "minute", "second",
    "time_utc", "evid", "lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "npol", "prob",
}
SEALED = {
    "strike", "dip", "rake", "strike_orig", "dip_orig", "rake_orig",
    "ftype", "p_azi", "p_dip", "t_azi", "t_dip",
}
SELECTED_REQUIRED = {"global_index", "cohort_code", "event_time_epoch", "event_id"}


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def content_id(prefix: str, value: Any) -> str:
    return prefix + ":" + hashlib.sha256(canonical(value)).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def safe_url(url: str) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(url)
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "path": parsed.path,
        "query_keys": sorted(urllib.parse.parse_qs(parsed.query, keep_blank_values=True)),
        "query_values_recorded": False,
    }


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    value = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
    return 2.0 * radius * math.asin(min(1.0, math.sqrt(value)))


def get(url: str, timeout: int, retries: int = 5) -> tuple[bytes, dict[str, Any]]:
    error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "KCH-Helical-v0.14-ComCat-location-crosswalk",
                    "Accept": "application/geo+json,application/json",
                    "Accept-Encoding": "identity",
                },
            )
            started = time.monotonic()
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
                receipt = {
                    "status": int(response.status),
                    "requested": safe_url(url),
                    "effective": safe_url(response.geturl()),
                    "content_type": response.headers.get("Content-Type"),
                    "content_length_header": response.headers.get("Content-Length"),
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                    "bytes": len(body),
                    "sha256": sha256_bytes(body),
                    "elapsed_seconds": time.monotonic() - started,
                    "attempt": attempt + 1,
                    "credentials_supplied": False,
                }
                return body, receipt
        except Exception as exc:  # pragma: no cover - exercised remotely
            error = exc
            if attempt + 1 < retries:
                time.sleep(min(30.0, 2.0 ** attempt))
    raise RuntimeError(f"ComCat request failed after {retries} attempts: {safe_url(url)}: {error}")


def fetch_comcat(code: int, bbox: tuple[float, float, float, float], timeout: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    name, _ = COHORTS[code]
    lat_min, lat_max, lon_min, lon_max = bbox
    all_features: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for year in range(START_YEAR, END_YEAR + 1):
        offset = 1
        page = 0
        while True:
            params = {
                "format": "geojson",
                "starttime": f"{year}-01-01T00:00:00.000Z",
                "endtime": f"{year}-12-31T23:59:59.999Z",
                "minlatitude": f"{lat_min:.6f}",
                "maxlatitude": f"{lat_max:.6f}",
                "minlongitude": f"{lon_min:.6f}",
                "maxlongitude": f"{lon_max:.6f}",
                "orderby": "time-asc",
                "limit": str(LIMIT),
                "offset": str(offset),
            }
            url = "https://earthquake.usgs.gov/fdsnws/event/1/query?" + urllib.parse.urlencode(params)
            body, receipt = get(url, timeout)
            obj = json.loads(body)
            features = obj.get("features", [])
            if not isinstance(features, list):
                raise RuntimeError("ComCat response features is not a list")
            for feature in features:
                feature_id = str(feature.get("id"))
                if feature_id not in seen:
                    seen.add(feature_id)
                    all_features.append(feature)
            receipt.update({
                "cohort": name,
                "year": year,
                "page": page,
                "offset": offset,
                "feature_count": len(features),
            })
            receipts.append(receipt)
            if len(features) < LIMIT:
                break
            offset += LIMIT
            page += 1
    all_features.sort(key=lambda feature: (float(feature["properties"]["time"]), str(feature["id"])))
    return all_features, receipts


def aliases(feature: dict[str, Any]) -> set[str]:
    properties = feature["properties"]
    result = {str(feature["id"])}
    ids = properties.get("ids")
    if ids:
        result.update(value for value in str(ids).split(",") if value)
    code = properties.get("code")
    if code:
        result.add(str(code))
        result.add(str(properties.get("net", "")) + str(code))
    return result


def match(selected: list[dict[str, Any]], features: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    times = np.array([float(feature["properties"]["time"]) / 1000.0 for feature in features], dtype=float)
    results: list[dict[str, Any]] = []
    matched = 0
    with_horizontal = 0
    with_depth = 0
    with_both = 0
    ambiguous = 0
    alias_hits = 0
    for row in selected:
        event_time = float(row["epoch"])
        lower = bisect.bisect_left(times, event_time - 3.0)
        upper = bisect.bisect_right(times, event_time + 3.0)
        event_id = str(row["event_id"])
        ranked: list[tuple[Any, ...]] = []
        for feature in features[lower:upper]:
            properties = feature["properties"]
            coordinates = feature["geometry"]["coordinates"]
            dt = abs(float(properties["time"]) / 1000.0 - event_time)
            horizontal = haversine_km(row["lat"], row["lon"], float(coordinates[1]), float(coordinates[0]))
            depth_delta = abs(float(row["depth"]) - float(coordinates[2]))
            feature_magnitude = properties.get("mag")
            magnitude_delta = abs(float(row["mag"]) - float(feature_magnitude)) if feature_magnitude is not None else 9.0
            alias_hit = any(alias.endswith(event_id) for alias in aliases(feature))
            score = (dt / 1.0) ** 2 + (horizontal / 5.0) ** 2 + (depth_delta / 10.0) ** 2 + (magnitude_delta / 0.5) ** 2 - (4.0 if alias_hit else 0.0)
            if dt <= 2.0 and horizontal <= 15.0 and depth_delta <= 20.0 and magnitude_delta <= 1.5:
                ranked.append((score, dt, horizontal, depth_delta, magnitude_delta, str(feature["id"]), alias_hit, feature))
        ranked.sort(key=lambda value: (value[0], value[1], value[2], value[3], value[4], value[5]))
        record: dict[str, Any] = {
            "global_index": int(row["global_index"]),
            "cohort_code": int(row["cohort_code"]),
            "event_id": event_id,
            "matched": False,
            "candidate_count": len(ranked),
        }
        if ranked:
            best = ranked[0]
            margin = ranked[1][0] - best[0] if len(ranked) > 1 else None
            is_ambiguous = margin is not None and margin < 0.25 and not best[6]
            if is_ambiguous:
                ambiguous += 1
                record.update({"ambiguous": True, "best_score": best[0], "score_margin": margin})
            else:
                feature = best[7]
                properties = feature["properties"]
                coordinates = feature["geometry"]["coordinates"]
                horizontal_error = properties.get("horizontalError")
                depth_error = properties.get("depthError")
                record.update({
                    "matched": True,
                    "ambiguous": False,
                    "comcat_id": feature["id"],
                    "dt_seconds": best[1],
                    "horizontal_distance_km": best[2],
                    "depth_difference_km": best[3],
                    "magnitude_difference": best[4],
                    "alias_hit": bool(best[6]),
                    "match_score": best[0],
                    "score_margin": margin,
                    "comcat_lat": coordinates[1],
                    "comcat_lon": coordinates[0],
                    "comcat_depth": coordinates[2],
                    "horizontalError_km": horizontal_error,
                    "depthError_km": depth_error,
                    "locationSource": properties.get("locationSource"),
                    "net": properties.get("net"),
                    "status": properties.get("status"),
                })
                matched += 1
                alias_hits += int(bool(best[6]))
                if horizontal_error is not None:
                    with_horizontal += 1
                if depth_error is not None:
                    with_depth += 1
                if horizontal_error is not None and depth_error is not None:
                    with_both += 1
        results.append(record)
    denominator = max(len(selected), 1)
    summary = {
        "selected": len(selected),
        "matched": matched,
        "ambiguous": ambiguous,
        "alias_hits": alias_hits,
        "match_fraction": matched / denominator,
        "horizontal_error_count": with_horizontal,
        "horizontal_error_fraction": with_horizontal / denominator,
        "depth_error_count": with_depth,
        "depth_error_fraction": with_depth / denominator,
        "both_errors_count": with_both,
        "both_errors_fraction": with_both / denominator,
    }
    return results, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blind-npz", required=True, type=Path)
    parser.add_argument("--selected-indices", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    with np.load(args.blind_npz, allow_pickle=False) as loaded:
        observed = set(loaded.files)
        if observed != BLIND_REQUIRED or observed & SEALED:
            raise RuntimeError(f"blind schema/firewall mismatch: {sorted(observed)}")
        blind = {name: loaded[name] for name in BLIND_REQUIRED}
    with np.load(args.selected_indices, allow_pickle=False) as loaded:
        if not SELECTED_REQUIRED.issubset(set(loaded.files)):
            raise RuntimeError(f"selected index schema mismatch: {sorted(loaded.files)}")
        selected_arrays = {name: loaded[name] for name in loaded.files}

    global_index = np.asarray(selected_arrays["global_index"], dtype=np.int64)
    cohort_code = np.asarray(selected_arrays["cohort_code"], dtype=np.int64)
    event_time = np.asarray(selected_arrays["event_time_epoch"], dtype=np.float64)
    event_id = np.asarray(selected_arrays["event_id"]).astype(str)
    if len(global_index) != 61_555 or len(np.unique(global_index)) != 61_555:
        raise RuntimeError("selected index cardinality or uniqueness drift")
    if np.any(global_index < 0) or np.any(global_index >= len(blind["evid"])):
        raise RuntimeError("selected global index outside blind catalog")

    query_receipts: list[dict[str, Any]] = []
    crosswalk: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    for code, (name, bbox) in COHORTS.items():
        indices = np.flatnonzero(cohort_code == code)
        selected = [
            {
                "global_index": int(global_index[position]),
                "cohort_code": code,
                "event_id": str(event_id[position]),
                "epoch": float(event_time[position]),
                "lat": float(blind["lat_reloc"][global_index[position]]),
                "lon": float(blind["lon_reloc"][global_index[position]]),
                "depth": float(blind["dep_reloc"][global_index[position]]),
                "mag": float(blind["mag"][global_index[position]]),
                "nc_sc": str(blind["nc_sc"][global_index[position]]),
            }
            for position in indices
        ]
        features, receipts = fetch_comcat(code, bbox, args.timeout)
        query_receipts.extend(receipts)
        matched, summary = match(selected, features)
        crosswalk.extend(matched)
        summary["comcat_events_in_bbox"] = len(features)
        summaries[name] = summary

    write_json(args.output / "COMCAT_QUERY_RECEIPTS_V0_14.json", query_receipts)
    write_json(args.output / "COMCAT_LOCATION_UNCERTAINTY_CROSSWALK_ROWS_V0_14.json", crosswalk)

    outcome = (
        "LOCATION_UNCERTAINTY_CROSSWALK_PASS"
        if all(value["both_errors_fraction"] >= MINIMUM_BOTH_ERRORS_FRACTION for value in summaries.values())
        else "NOT_IDENTIFIABLE_LOCATION_UNCERTAINTY_COVERAGE"
    )
    result = {
        "format": "KCH_HELICAL_V0_14_COMCAT_LOCATION_UNCERTAINTY_GATE_RESULT",
        "outcome": outcome,
        "source_blind_npz_sha256": sha256_file(args.blind_npz),
        "selected_indices_sha256": sha256_file(args.selected_indices),
        "crosswalk_rows_sha256": sha256_file(args.output / "COMCAT_LOCATION_UNCERTAINTY_CROSSWALK_ROWS_V0_14.json"),
        "query_receipts_sha256": sha256_file(args.output / "COMCAT_QUERY_RECEIPTS_V0_14.json"),
        "crosswalk_row_count": len(crosswalk),
        "query_count": len(query_receipts),
        "match_rule": {
            "time_seconds": 2.0,
            "horizontal_km": 15.0,
            "depth_km": 20.0,
            "magnitude": 1.5,
            "score": "(dt/1)^2+(h/5)^2+(dz/10)^2+(dmag/0.5)^2-4*alias_hit",
            "ambiguity_margin": 0.25,
        },
        "minimum_both_errors_fraction": MINIMUM_BOTH_ERRORS_FRACTION,
        "cohorts": summaries,
        "blind_fields_accessed": sorted(BLIND_REQUIRED),
        "directional_fields_accessed": False,
        "sealed_test_accessed": False,
        "scientific_model_execution_performed": False,
        "physical_helicity": "NOT_EVALUATED",
        "authority_ceiling": "EXACT_COMCAT_LOCATION_UNCERTAINTY_CROSSWALK_ONLY",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    result["gate_id"] = content_id("h14loc", result)
    write_json(args.output / "COMCAT_LOCATION_UNCERTAINTY_GATE_RESULT_V0_14.json", result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if outcome == "LOCATION_UNCERTAINTY_CROSSWALK_PASS" else 30


if __name__ == "__main__":
    raise SystemExit(main())
