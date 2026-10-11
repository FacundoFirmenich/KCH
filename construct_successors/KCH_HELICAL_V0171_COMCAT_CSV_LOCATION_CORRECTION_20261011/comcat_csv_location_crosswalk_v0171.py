from __future__ import annotations

import bisect
import csv
import hashlib
import io
import json
import math
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

COHORTS = {
    0: ("BAY_AREA_HAYWARD_CALAVERAS", (36.85, 38.45, -122.75, -121.15)),
    1: ("PARKFIELD_CENTRAL_SAF", (35.45, 36.25, -121.05, -119.95)),
}
START_YEAR, END_YEAR = 1981, 2021
LIMIT = 20000
CSV_REQUIRED_COLUMNS = {
    "time", "latitude", "longitude", "depth", "mag", "net", "id",
    "locationSource", "horizontalError", "depthError", "status",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    value = (
        math.sin(dphi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    )
    return 2.0 * radius * math.asin(min(1.0, math.sqrt(value)))


def get(url: str, retries: int = 4) -> tuple[bytes, dict[str, Any]]:
    error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "KCH-Helical-v0.17.1-ComCat-CSV-correction",
                    "Accept-Encoding": "identity",
                    "Accept": "text/csv,application/csv;q=0.9,text/plain;q=0.8",
                },
            )
            with urllib.request.urlopen(request, timeout=180) as response:
                body = response.read()
                return body, {
                    "status": int(response.status),
                    "effective_url": response.geturl(),
                    "headers": dict(response.headers.items()),
                    "bytes": len(body),
                    "sha256": sha256_bytes(body),
                }
        except Exception as exc:
            error = exc
            time.sleep(2**attempt)
    raise RuntimeError(f"request failed after {retries} attempts: {url}: {error}")


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    number = float(text)
    return number if math.isfinite(number) else None


def parse_epoch_seconds(value: str) -> float:
    text = value.strip()
    if not text:
        raise ValueError("empty ComCat CSV time")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def row_to_feature(row: dict[str, str]) -> dict[str, Any]:
    event_id = str(row["id"]).strip()
    if not event_id:
        raise ValueError("empty ComCat CSV id")
    net = str(row.get("net", "")).strip()
    code = event_id[len(net):] if net and event_id.startswith(net) else event_id
    epoch = parse_epoch_seconds(row["time"])
    longitude = parse_float(row["longitude"])
    latitude = parse_float(row["latitude"])
    depth = parse_float(row["depth"])
    if longitude is None or latitude is None or depth is None:
        raise ValueError(f"non-finite ComCat geometry for {event_id}")
    return {
        "type": "Feature",
        "id": event_id,
        "geometry": {
            "type": "Point",
            "coordinates": [longitude, latitude, depth],
        },
        "properties": {
            "time": epoch * 1000.0,
            "mag": parse_float(row.get("mag")),
            "net": net,
            "code": code,
            "ids": event_id,
            "locationSource": str(row.get("locationSource", "")).strip() or None,
            "horizontalError": parse_float(row.get("horizontalError")),
            "depthError": parse_float(row.get("depthError")),
            "status": str(row.get("status", "")).strip() or None,
        },
    }


def parse_csv_features(body: bytes) -> tuple[list[dict[str, Any]], tuple[str, ...]]:
    if not body.strip():
        return [], tuple()
    text = body.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    columns = tuple(reader.fieldnames or ())
    missing = sorted(CSV_REQUIRED_COLUMNS - set(columns))
    if missing:
        raise RuntimeError(f"ComCat CSV schema missing required columns: {missing}")
    features = [row_to_feature(row) for row in reader]
    return features, columns


def fetch_comcat(
    out: Path,
    code: int,
    bbox: tuple[float, float, float, float],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    name, _ = COHORTS[code]
    lat_min, lat_max, lon_min, lon_max = bbox
    all_features: list[dict[str, Any]] = []
    receipts: list[dict[str, Any]] = []
    seen: set[str] = set()
    observed_columns: set[str] = set()

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
            url = (
                "https://earthquake.usgs.gov/fdsnws/event/1/query?"
                + urllib.parse.urlencode(params)
            )
            body, receipt = get(url)
            raw_dir = out / "raw" / name
            raw_dir.mkdir(parents=True, exist_ok=True)
            path = raw_dir / f"{year}_p{page:03d}.csv"
            path.write_bytes(body)

            features, columns = parse_csv_features(body)
            observed_columns.update(columns)
            for feature in features:
                event_id = str(feature["id"])
                if event_id not in seen:
                    seen.add(event_id)
                    all_features.append(feature)

            receipt.update(
                {
                    "cohort": name,
                    "year": year,
                    "page": page,
                    "offset": offset,
                    "url": url,
                    "path": str(path.relative_to(out)),
                    "format": "csv",
                    "row_count": len(features),
                    "csv_columns": list(columns),
                }
            )
            receipts.append(receipt)
            if len(features) < LIMIT:
                break
            offset += LIMIT
            page += 1

    missing_overall = sorted(CSV_REQUIRED_COLUMNS - observed_columns)
    if missing_overall:
        raise RuntimeError(
            f"ComCat CSV schema never exposed required columns: {missing_overall}"
        )
    all_features.sort(
        key=lambda feature: (
            float(feature["properties"]["time"]),
            str(feature["id"]),
        )
    )
    return all_features, receipts


def aliases(feature: dict[str, Any]) -> set[str]:
    properties = feature["properties"]
    output = {str(feature["id"])}
    ids = properties.get("ids")
    if ids:
        output.update(item for item in str(ids).split(",") if item)
    code = properties.get("code")
    if code:
        output.add(str(code))
        output.add(str(properties.get("net", "")) + str(code))
    return output


def match(
    selected: list[dict[str, Any]],
    features: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    # Frozen v0.8 ranking, thresholds, ambiguity rule, and tie order.
    times = np.array(
        [float(feature["properties"]["time"]) / 1000.0 for feature in features],
        dtype=float,
    )
    results: list[dict[str, Any]] = []
    matched = 0
    with_horizontal = 0
    with_depth = 0
    with_both = 0
    ambiguous = 0

    for row in selected:
        event_time = float(row["epoch"])
        lower = bisect.bisect_left(times, event_time - 3.0)
        upper = bisect.bisect_right(times, event_time + 3.0)
        evid = str(int(row["evid"]))
        ranked: list[tuple[Any, ...]] = []

        for feature in features[lower:upper]:
            properties = feature["properties"]
            coordinates = feature["geometry"]["coordinates"]
            delta_time = abs(float(properties["time"]) / 1000.0 - event_time)
            horizontal = haversine_km(
                row["lat"], row["lon"], float(coordinates[1]), float(coordinates[0])
            )
            delta_depth = abs(float(row["depth"]) - float(coordinates[2]))
            preferred_mag = properties.get("mag")
            delta_mag = (
                abs(float(row["mag"]) - float(preferred_mag))
                if preferred_mag is not None else 9.0
            )
            alias_hit = any(alias.endswith(evid) for alias in aliases(feature))
            score = (
                (delta_time / 1.0) ** 2 + (horizontal / 5.0) ** 2
                + (delta_depth / 10.0) ** 2 + (delta_mag / 0.5) ** 2
                - (4.0 if alias_hit else 0.0)
            )
            if (
                delta_time <= 2.0 and horizontal <= 15.0
                and delta_depth <= 20.0 and delta_mag <= 1.5
            ):
                ranked.append((score, delta_time, horizontal, delta_depth,
                               delta_mag, str(feature["id"]), alias_hit, feature))

        ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4], item[5]))
        record: dict[str, Any] = {
            "global_index": int(row["global_index"]),
            "cohort_code": int(row["cohort_code"]),
            "evid": evid,
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
                    "ids": properties.get("ids"),
                })
                matched += 1
                if horizontal_error is not None:
                    with_horizontal += 1
                if depth_error is not None:
                    with_depth += 1
                if horizontal_error is not None and depth_error is not None:
                    with_both += 1
        results.append(record)

    denominator = max(len(selected), 1)
    return results, {
        "selected": len(selected),
        "matched": matched,
        "ambiguous": ambiguous,
        "match_fraction": matched / denominator,
        "horizontal_error_fraction": with_horizontal / denominator,
        "depth_error_fraction": with_depth / denominator,
        "both_errors_fraction": with_both / denominator,
    }
