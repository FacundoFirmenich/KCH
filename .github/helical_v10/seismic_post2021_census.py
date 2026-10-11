from __future__ import annotations

import argparse
import hashlib
import json
import math
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import requests

BASE = "https://earthquake.usgs.gov/fdsnws/event/1/query"
START = "2022-01-01"
END = "2026-10-11"
REGIONS = {
    "BAY_AREA": (36.5, -123.5, 38.8, -120.5),
    "PARKFIELD_CENTRAL_SAF": (35.0, -121.5, 36.7, -119.3),
    "MENDOCINO_TRIPLE_JUNCTION": (39.0, -126.0, 42.0, -122.0),
    "NORTHERN_WALKER_LANE": (36.5, -120.5, 40.5, -116.0),
    "SOUTHERN_CALIFORNIA_CONTROL": (32.0, -121.0, 36.5, -113.5),
}
PRODUCTS = ["focal-mechanism", "moment-tensor"]
YEARS = [2022, 2023, 2024, 2025, 2026]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def fetch(params: dict[str, Any]) -> requests.Response:
    response = requests.get(
        BASE,
        params=params,
        headers={"User-Agent": "KCH-Helical-v1.0-post2021-blind-census/2026-10-11"},
        timeout=180,
    )
    response.raise_for_status()
    return response


def query_region_year(region: str, bbox: tuple[float, float, float, float], product: str, year: int, out: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    minlat, minlon, maxlat, maxlon = bbox
    start = f"{year}-01-01"
    end = f"{year + 1}-01-01" if year < 2026 else END
    params = {
        "format": "geojson",
        "starttime": start,
        "endtime": end,
        "minlatitude": minlat,
        "minlongitude": minlon,
        "maxlatitude": maxlat,
        "maxlongitude": maxlon,
        "producttype": product,
        "eventtype": "earthquake",
        "orderby": "time-asc",
        "limit": 20000,
    }
    response = fetch(params)
    body = response.content
    path = out / "raw" / region / f"{product}_{year}.geojson"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    root = response.json()
    features = root.get("features", [])
    if len(features) >= 20000:
        raise RuntimeError(f"{region}/{product}/{year}: query reached API limit")
    return features, {
        "region": region,
        "producttype": product,
        "year": year,
        "effective_url": response.url,
        "http_status": response.status_code,
        "bytes": len(body),
        "sha256": sha256_bytes(body),
        "feature_count": len(features),
        "metadata_count": root.get("metadata", {}).get("count"),
    }


def feature_row(feature: dict[str, Any], product: str) -> dict[str, Any]:
    props = feature.get("properties", {})
    coordinates = feature.get("geometry", {}).get("coordinates", [None, None, None])
    return {
        "event_id": str(feature.get("id")),
        "time_epoch_ms": int(props.get("time")) if props.get("time") is not None else None,
        "updated_epoch_ms": int(props.get("updated")) if props.get("updated") is not None else None,
        "longitude": coordinates[0] if len(coordinates) > 0 else None,
        "latitude": coordinates[1] if len(coordinates) > 1 else None,
        "depth_km": coordinates[2] if len(coordinates) > 2 else None,
        "magnitude": props.get("mag"),
        "magnitude_type": props.get("magType"),
        "network": props.get("net"),
        "code": props.get("code"),
        "status": props.get("status"),
        "event_type": props.get("type"),
        "types": props.get("types"),
        f"has_{product.replace('-', '_')}": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "format": "KCH_SEISMIC_POST2021_BLIND_CENSUS_V1",
        "started_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "date_window": [START, END],
        "directional_product_payloads_opened": False,
        "state": "RUNNING",
    }
    try:
        receipts: list[dict[str, Any]] = []
        region_rows: dict[str, dict[str, dict[str, Any]]] = {region: {} for region in REGIONS}
        for region, bbox in REGIONS.items():
            for product in PRODUCTS:
                for year in YEARS:
                    features, receipt = query_region_year(region, bbox, product, year, out)
                    receipts.append(receipt)
                    for feature in features:
                        row = feature_row(feature, product)
                        event_id = row["event_id"]
                        current = region_rows[region].setdefault(event_id, {"event_id": event_id})
                        for key, value in row.items():
                            if key.startswith("has_"):
                                current[key] = bool(current.get(key, False) or value)
                            elif current.get(key) is None and value is not None:
                                current[key] = value
                            elif key not in current:
                                current[key] = value
        receipt_path = out / "COMCAT_QUERY_RECEIPTS.csv"
        pd.DataFrame(receipts).to_csv(receipt_path, index=False)

        event_frames: list[pd.DataFrame] = []
        census_rows: list[dict[str, Any]] = []
        power_rows: list[dict[str, Any]] = []
        for region, by_id in region_rows.items():
            frame = pd.DataFrame(list(by_id.values()))
            for field in ["has_focal_mechanism", "has_moment_tensor"]:
                if field not in frame:
                    frame[field] = False
                frame[field] = frame[field].fillna(False).astype(bool)
            frame["time_utc"] = pd.to_datetime(frame["time_epoch_ms"], unit="ms", utc=True, errors="coerce")
            frame = frame.sort_values(["time_utc", "event_id"], kind="stable")
            frame["region"] = region
            blind_fields = [
                "region", "event_id", "time_utc", "time_epoch_ms", "updated_epoch_ms",
                "longitude", "latitude", "depth_km", "magnitude", "magnitude_type",
                "network", "code", "status", "event_type", "types",
                "has_focal_mechanism", "has_moment_tensor",
            ]
            frame = frame[blind_fields]
            event_frames.append(frame)
            path = out / "blind_events" / f"{region}.csv.gz"
            path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(path, index=False, compression="gzip")

            event_count = len(frame)
            time_valid = frame["time_utc"].notna()
            span_years = None
            if time_valid.any():
                span_years = (frame.loc[time_valid, "time_utc"].max() - frame.loc[time_valid, "time_utc"].min()).total_seconds() / (365.2425 * 86400)
            focal = int(frame["has_focal_mechanism"].sum())
            moment = int(frame["has_moment_tensor"].sum())
            both = int((frame["has_focal_mechanism"] & frame["has_moment_tensor"]).sum())
            reviewed = int((frame["status"].astype(str).str.lower() == "reviewed").sum())
            train_end = int(math.floor(0.5 * event_count))
            calibration_end = int(math.floor(0.75 * event_count))
            test_events = event_count - calibration_end
            census_rows.append({
                "region": region,
                "unique_events_with_directional_product": event_count,
                "focal_mechanism_events": focal,
                "moment_tensor_events": moment,
                "both_products": both,
                "reviewed_events": reviewed,
                "time_span_years": span_years,
                "chronological_train_events": train_end,
                "chronological_calibration_events": calibration_end - train_end,
                "chronological_sealed_test_events": test_events,
                "blind_event_file": path.name,
                "blind_event_file_sha256": sha256_file(path),
            })
            for retention in [0.50, 0.65, 0.80, 0.90]:
                expected_edges = int(math.floor(test_events * retention))
                power_rows.append({
                    "region": region,
                    "event_count": event_count,
                    "sealed_test_events": test_events,
                    "assumed_parent_graph_retention": retention,
                    "expected_test_children_with_parent": expected_edges,
                    "minimum_required_test_edges": 200,
                    "edge_count_gate": "PASS" if expected_edges >= 200 else "FAIL",
                })

        combined = pd.concat(event_frames, ignore_index=True)
        combined_path = out / "BLIND_POST2021_EVENT_CENSUS.csv.gz"
        combined.to_csv(combined_path, index=False, compression="gzip")
        census = pd.DataFrame(census_rows)
        census_path = out / "POST2021_COHORT_CENSUS.csv"
        census.to_csv(census_path, index=False)
        power = pd.DataFrame(power_rows)
        power_path = out / "POST2021_POWER_ATTRITION_ENVELOPE.csv"
        power.to_csv(power_path, index=False)

        primary_regions = ["BAY_AREA", "PARKFIELD_CENTRAL_SAF", "MENDOCINO_TRIPLE_JUNCTION", "NORTHERN_WALKER_LANE"]
        eligible = census[
            census["region"].isin(primary_regions)
            & (census["unique_events_with_directional_product"] >= 800)
            & (census["chronological_sealed_test_events"] >= 200)
        ].sort_values("unique_events_with_directional_product", ascending=False)
        robust_retention = power[
            power["region"].isin(primary_regions)
            & (power["assumed_parent_graph_retention"] == 0.80)
            & (power["edge_count_gate"] == "PASS")
        ]
        decision = "BLIND_CENSUS_PASS" if len(eligible) >= 2 and robust_retention["region"].nunique() >= 2 else "INSUFFICIENT_NEW_DATA_POWER"
        selected = eligible.head(3)["region"].tolist()

        manifest = {
            "query_receipts": {"path": receipt_path.name, "sha256": sha256_file(receipt_path)},
            "combined_blind_events": {"path": combined_path.name, "bytes": combined_path.stat().st_size, "sha256": sha256_file(combined_path)},
            "cohort_census": {"path": census_path.name, "sha256": sha256_file(census_path)},
            "power_envelope": {"path": power_path.name, "sha256": sha256_file(power_path)},
        }
        write_json(out / "SEISMIC_SOURCE_MANIFEST.json", manifest)
        report.update({
            "state": "BLIND_CENSUS_COMPLETE",
            "completed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "outcome": decision,
            "regions_evaluated": list(REGIONS),
            "eligible_primary_cohorts": eligible["region"].tolist(),
            "selected_for_future_fault_assignment_preflight": selected,
            "eligible_primary_count": int(len(eligible)),
            "retention_0_80_pass_primary_count": int(robust_retention["region"].nunique()),
            "directional_angles_accessed": False,
            "product_details_accessed": False,
            "scientific_model_execution_performed": False,
            "authority_ceiling": "NONE",
        })
        report["census_id"] = "s9c:" + sha256_bytes(canonical(report))
        write_json(out / "SEISMIC_BLIND_CENSUS_REPORT.json", report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        report.update({
            "state": "FAIL_CLOSED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "directional_angles_accessed": False,
            "scientific_model_execution_performed": False,
            "authority_ceiling": "NONE",
        })
        write_json(out / "SEISMIC_BLIND_CENSUS_REPORT.json", report)
        print(traceback.format_exc())
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
