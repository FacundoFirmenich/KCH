from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import io
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime
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


def to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "" or text.lower() in {"nan", "null", "none"}:
        return None
    try:
        result = float(text)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def epoch(value: str) -> float:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()


def normalize_event_id(value: Any) -> str:
    text = str(value).strip()
    if text.endswith(".0"):
        stem = text[:-2]
        if stem.lstrip("-").isdigit():
            return stem
    return text


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
                    "User-Agent": "KCH-Helical-v0.14.2-FDSN-CSV-location-crosswalk",
                    "Accept": "text/csv,text/plain",
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
        except Exception as exc:  # pragma: no cover - remote path
            error = exc
            if attempt + 1 < retries:
                time.sleep(min(30.0, 2.0 ** attempt))
    raise RuntimeError(f"FDSN CSV request failed after {retries} attempts: {safe_url(url)}: {error}")


def fetch_catalog(code: int, bbox: tuple[float, float, float, float], timeout: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    name, _ = COHORTS[code]
    lat_min, lat_max, lon_min, lon_max = bbox
    events: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for year in range(START_YEAR, END_YEAR + 1):
        offset = 1
        page = 0
        while True:
            params = {
                "format": "csv",
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
            rows = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig", errors="strict"))))
            required_columns = {"time", "latitude", "longitude", "depth", "mag", "net", "id", "locationSource", "horizontalError", "depthError"}
            observed_columns = set(rows[0]) if rows else set(csv.DictReader(io.StringIO(body.decode("utf-8-sig", errors="strict"))).fieldnames or [])
            if not required_columns.issubset(observed_columns):
                raise RuntimeError(f"FDSN CSV schema missing required columns: {sorted(required_columns - observed_columns)}")
            for row in rows:
                event_id = str(row.get("id", "")).strip()
                if not event_id or event_id in seen:
                    continue
                latitude = to_float(row.get("latitude"))
                longitude = to_float(row.get("longitude"))
                depth = to_float(row.get("depth"))
                if latitude is None or longitude is None or depth is None:
                    continue
                seen.add(event_id)
                events.append({
                    "id": event_id,
                    "time": epoch(str(row["time"])),
                    "lat": latitude,
                    "lon": longitude,
                    "depth": depth,
                    "mag": to_float(row.get("mag")),
                    "net": row.get("net"),
                    "locationSource": row.get("locationSource"),
                    "horizontalError": to_float(row.get("horizontalError")),
                    "depthError": to_float(row.get("depthError")),
                    "status": row.get("status"),
                })
            receipt.update({
                "representation": "USGS_FDSN_CSV",
                "cohort": name,
                "year": year,
                "page": page,
                "offset": offset,
                "row_count": len(rows),
                "schema_columns": sorted(observed_columns),
                "horizontal_error_nonmissing": sum(to_float(row.get("horizontalError")) is not None for row in rows),
                "depth_error_nonmissing": sum(to_float(row.get("depthError")) is not None for row in rows),
            })
            receipts.append(receipt)
            if len(rows) < LIMIT:
                break
            offset += LIMIT
            page += 1
    events.sort(key=lambda event: (event["time"], event["id"]))
    return events, receipts


def match(selected: list[dict[str, Any]], events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    times = np.array([event["time"] for event in events], dtype=float)
    results: list[dict[str, Any]] = []
    matched = horizontal_count = depth_count = both_count = ambiguous = alias_hits = 0
    for row in selected:
        event_time = float(row["epoch"])
        lower = bisect.bisect_left(times, event_time - 3.0)
        upper = bisect.bisect_right(times, event_time + 3.0)
        event_id = normalize_event_id(row["event_id"])
        ranked: list[tuple[Any, ...]] = []
        for event in events[lower:upper]:
            dt = abs(float(event["time"]) - event_time)
            horizontal = haversine_km(row["lat"], row["lon"], event["lat"], event["lon"])
            depth_delta = abs(float(row["depth"]) - float(event["depth"]))
            magnitude_delta = abs(float(row["mag"]) - float(event["mag"])) if event["mag"] is not None else 9.0
            alias_hit = bool(event_id) and str(event["id"]).endswith(event_id)
            score = (dt / 1.0) ** 2 + (horizontal / 5.0) ** 2 + (depth_delta / 10.0) ** 2 + (magnitude_delta / 0.5) ** 2 - (4.0 if alias_hit else 0.0)
            if dt <= 2.0 and horizontal <= 15.0 and depth_delta <= 20.0 and magnitude_delta <= 1.5:
                ranked.append((score, dt, horizontal, depth_delta, magnitude_delta, str(event["id"]), alias_hit, event))
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
                event = best[7]
                matched += 1
                alias_hits += int(bool(best[6]))
                horizontal_error = event["horizontalError"]
                depth_error = event["depthError"]
                horizontal_count += int(horizontal_error is not None)
                depth_count += int(depth_error is not None)
                both_count += int(horizontal_error is not None and depth_error is not None)
                record.update({
                    "matched": True,
                    "ambiguous": False,
                    "comcat_id": event["id"],
                    "dt_seconds": best[1],
                    "horizontal_distance_km": best[2],
                    "depth_difference_km": best[3],
                    "magnitude_difference": best[4],
                    "alias_hit": bool(best[6]),
                    "match_score": best[0],
                    "score_margin": margin,
                    "horizontalError_km": horizontal_error,
                    "depthError_km": depth_error,
                    "locationSource": event["locationSource"],
                    "net": event["net"],
                    "status": event["status"],
                })
        results.append(record)
    denominator = max(len(selected), 1)
    matched_denominator = max(matched, 1)
    summary = {
        "selected": len(selected),
        "matched": matched,
        "ambiguous": ambiguous,
        "alias_hits": alias_hits,
        "match_fraction": matched / denominator,
        "horizontal_error_count": horizontal_count,
        "horizontal_error_fraction": horizontal_count / denominator,
        "horizontal_error_among_matched_fraction": horizontal_count / matched_denominator,
        "depth_error_count": depth_count,
        "depth_error_fraction": depth_count / denominator,
        "depth_error_among_matched_fraction": depth_count / matched_denominator,
        "both_errors_count": both_count,
        "both_errors_fraction": both_count / denominator,
        "both_errors_among_matched_fraction": both_count / matched_denominator,
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
        positions = np.flatnonzero(cohort_code == code)
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
            }
            for position in positions
        ]
        catalog, receipts = fetch_catalog(code, bbox, args.timeout)
        query_receipts.extend(receipts)
        matched, summary = match(selected, catalog)
        crosswalk.extend(matched)
        summary["comcat_events_in_bbox"] = len(catalog)
        summaries[name] = summary

    query_path = args.output / "COMCAT_QUERY_RECEIPTS_V0_14.json"
    rows_path = args.output / "COMCAT_LOCATION_UNCERTAINTY_CROSSWALK_ROWS_V0_14.json"
    write_json(query_path, query_receipts)
    write_json(rows_path, crosswalk)

    outcome = (
        "LOCATION_UNCERTAINTY_CROSSWALK_PASS"
        if all(summary["both_errors_fraction"] >= MINIMUM_BOTH_ERRORS_FRACTION for summary in summaries.values())
        else "NOT_IDENTIFIABLE_LOCATION_UNCERTAINTY_COVERAGE"
    )
    result = {
        "format": "KCH_HELICAL_V0_14_2_COMCAT_CSV_LOCATION_UNCERTAINTY_GATE_RESULT",
        "representation": "USGS_FDSN_CSV",
        "observation_adapter_change": "GEOJSON_SUMMARY_TO_FDSN_CSV_BULK",
        "outcome": outcome,
        "source_blind_npz_sha256": sha256_file(args.blind_npz),
        "selected_indices_sha256": sha256_file(args.selected_indices),
        "crosswalk_rows_sha256": sha256_file(rows_path),
        "query_receipts_sha256": sha256_file(query_path),
        "crosswalk_row_count": len(crosswalk),
        "query_count": len(query_receipts),
        "match_rule": {
            "ambiguity_margin": 0.25,
            "depth_km": 20.0,
            "horizontal_km": 15.0,
            "magnitude": 1.5,
            "score": "(dt/1)^2+(h/5)^2+(dz/10)^2+(dmag/0.5)^2-4*alias_hit",
            "time_seconds": 2.0,
            "changed_from_v0_14_1": False,
        },
        "minimum_both_errors_fraction": MINIMUM_BOTH_ERRORS_FRACTION,
        "coverage_threshold_changed_from_v0_14_1": False,
        "cohorts": summaries,
        "blind_fields_accessed": sorted(BLIND_REQUIRED),
        "directional_fields_accessed": False,
        "sealed_test_accessed": False,
        "scientific_model_execution_performed": False,
        "physical_helicity": "NOT_EVALUATED",
        "authority_ceiling": "EXACT_COMCAT_CSV_LOCATION_UNCERTAINTY_CROSSWALK_ONLY",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    result["gate_id"] = content_id("h142loccsv", result)
    write_json(args.output / "COMCAT_LOCATION_UNCERTAINTY_GATE_RESULT_V0_14.json", result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if outcome == "LOCATION_UNCERTAINTY_CROSSWALK_PASS" else 30


if __name__ == "__main__":
    raise SystemExit(main())
