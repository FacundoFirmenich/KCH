from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import drms
import numpy as np
import pandas as pd
import requests

GOES_BASE = "https://data.ngdc.noaa.gov/platforms/solar-space-observing-satellites/goes/multi/l2/data/xrsf-l2-flrpt_science/csv/"
JSOC_SERIES = "hmi.sharp_cea_720s"
START = pd.Timestamp("2010-05-01T00:00:00Z")
END = pd.Timestamp("2025-12-31T23:59:59Z")
HORIZONS = {"M1_plus": [6, 12, 24, 48], "X1_plus": [12, 24, 48]}
KEYS = [
    "HARPNUM", "T_REC", "NOAA_AR", "NOAA_NUM", "NOAA_ARS", "QUALITY",
    "USFLUX", "MEANJZH", "ABSNJZH", "TOTUSJH", "MEANALP", "MEANSHR",
    "SHRGT45", "R_VALUE", "TOTUSJZ", "TOTPOT", "AREA_ACR", "LAT_FWT", "LON_FWT",
]
SIGNED = ["MEANJZH", "MEANALP"]
UNSIGNED = ["ABSNJZH", "TOTUSJH"]
BASELINE = ["USFLUX", "MEANSHR", "SHRGT45", "R_VALUE", "TOTUSJZ", "TOTPOT", "AREA_ACR"]
PERIODS = [
    ("TRAIN", pd.Timestamp("2010-05-01T00:00:00Z"), pd.Timestamp("2016-12-31T23:59:59Z")),
    ("CALIBRATION", pd.Timestamp("2017-01-01T00:00:00Z"), pd.Timestamp("2020-12-31T23:59:59Z")),
    ("TEST_A", pd.Timestamp("2021-01-01T00:00:00Z"), pd.Timestamp("2023-12-31T23:59:59Z")),
    ("TEST_B", pd.Timestamp("2024-01-01T00:00:00Z"), pd.Timestamp("2025-12-31T23:59:59Z")),
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def get(url: str) -> requests.Response:
    response = requests.get(url, headers={"User-Agent": "KCH-Helical-v1.0-MHD-census/2026-10-11"}, timeout=180)
    response.raise_for_status()
    return response


def tai_minus_utc(ts: pd.Timestamp) -> int:
    if ts < pd.Timestamp("2012-07-01T00:00:00Z"):
        return 34
    if ts < pd.Timestamp("2015-07-01T00:00:00Z"):
        return 35
    if ts < pd.Timestamp("2017-01-01T00:00:00Z"):
        return 36
    return 37


def parse_t_rec(value: Any) -> pd.Timestamp:
    raw = str(value).replace("_TAI", "").replace(".", "-", 2).replace("_", "T")
    ts = pd.Timestamp(raw, tz="UTC")
    return ts - pd.Timedelta(seconds=tai_minus_utc(ts))


def query_year(client: drms.Client, year: int, out: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    start = pd.Timestamp(f"{year}-01-01T00:00:00Z")
    end = pd.Timestamp(f"{year}-12-31T18:00:00Z")
    if year == 2010:
        start = START
    qstart = start.strftime("%Y.%m.%d_%H:%M_TAI")
    qend = end.strftime("%Y.%m.%d_%H:%M_TAI")
    qstr = f"{JSOC_SERIES}[][{qstart}-{qend}@6h]"
    frame = client.query(qstr, key=",".join(KEYS)).reset_index(drop=False)
    path = out / "jsoc_raw" / f"sharp_cea_6h_{year}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, lineterminator="\n")
    return frame, {
        "year": year,
        "query": qstr,
        "series": JSOC_SERIES,
        "keys": KEYS,
        "rows": int(len(frame)),
        "columns": list(frame.columns),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def acquire_goes(out: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    listing = get(GOES_BASE).content
    listing_path = out / "source" / "goes_flare_listing.html"
    listing_path.parent.mkdir(parents=True, exist_ok=True)
    listing_path.write_bytes(listing)
    names = sorted(set(re.findall(rb"sci_xrsf-l2-flrpt_geo_s\d+_e\d+_v[\d-]+\.csv", listing)))
    if not names:
        raise RuntimeError("no GOES science flare report in official listing")
    name = names[-1].decode("ascii")
    body = get(GOES_BASE + name).content
    path = out / "source" / name
    path.write_bytes(body)
    frame = pd.read_csv(path, low_memory=False)
    return frame, {
        "listing_url": GOES_BASE,
        "listing_bytes": len(listing),
        "listing_sha256": sha256_bytes(listing),
        "selected_file": name,
        "selected_url": GOES_BASE + name,
        "bytes": len(body),
        "sha256": sha256_bytes(body),
        "rows": int(len(frame)),
        "columns": list(frame.columns),
    }


def clean_goes(frame: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    data = frame.copy()
    for column in ["time", "start_time", "end_time"]:
        data[column] = pd.to_datetime(data[column], errors="coerce", utc=True)
    data["active_region_short"] = pd.to_numeric(data["active_region"], errors="coerce").round().astype("Int64")
    flare = data["flare_class"].astype(str).str.extract(r"^([ABCMX])(\d+(?:\.\d+)?)$")
    class_scale = {"A": 1e-8, "B": 1e-7, "C": 1e-6, "M": 1e-5, "X": 1e-4}
    data["class_letter"] = flare[0]
    data["class_number"] = pd.to_numeric(flare[1], errors="coerce")
    data["class_flux"] = data["class_letter"].map(class_scale) * data["class_number"]
    before = len(data)
    if "flare_id" in data.columns:
        nonnull = data["flare_id"].notna()
        with_id = data[nonnull].drop_duplicates(subset=["flare_id"], keep="last")
        without_id = data[~nonnull].drop_duplicates(subset=["start_time", "end_time", "flare_class", "active_region_short"], keep="last")
        data = pd.concat([with_id, without_id], ignore_index=True)
    else:
        data = data.drop_duplicates(subset=["start_time", "end_time", "flare_class", "active_region_short"], keep="last")
    data = data.sort_values(["active_region_short", "start_time", "time"], kind="stable")
    return data, {
        "rows_before_deduplication": int(before),
        "rows_after_deduplication": int(len(data)),
        "associated_active_region_rows": int(data["active_region_short"].notna().sum()),
        "M_or_X_rows": int((data["class_flux"] >= 1e-5).sum()),
        "X_rows": int((data["class_flux"] >= 1e-4).sum()),
    }


def period_for_interval(first: pd.Timestamp, last: pd.Timestamp) -> str | None:
    for name, start, end in PERIODS:
        if first >= start and last <= end:
            return name
    return None


def normal_required_n(delta: float, sd: float) -> int:
    z_alpha = 1.959963984540054
    z_power = 0.8416212335729143
    return int(math.ceil(((z_alpha + z_power) * sd / delta) ** 2))


def label_origins(origins: pd.DataFrame, flares: pd.DataFrame) -> pd.DataFrame:
    result = origins.copy()
    flare_lookup: dict[int, tuple[np.ndarray, np.ndarray]] = {}
    associated = flares[flares["active_region_short"].notna() & flares["start_time"].notna()].copy()
    for region, group in associated.groupby("active_region_short", sort=False):
        times = group["start_time"].astype("int64").to_numpy()
        fluxes = group["class_flux"].to_numpy(dtype=float)
        order = np.argsort(times, kind="stable")
        flare_lookup[int(region)] = (times[order], fluxes[order])
    origin_ns = result["origin_utc"].astype("int64").to_numpy()
    short_regions = result["active_region_short"].to_numpy(dtype=int)
    for target, horizons in HORIZONS.items():
        threshold = 1e-5 if target == "M1_plus" else 1e-4
        for horizon in horizons:
            labels = np.zeros(len(result), dtype=np.int8)
            horizon_ns = int(pd.Timedelta(hours=horizon).value)
            for index, (origin, region) in enumerate(zip(origin_ns, short_regions)):
                lookup = flare_lookup.get(int(region))
                if lookup is None:
                    continue
                times, fluxes = lookup
                left = np.searchsorted(times, origin, side="right")
                right = np.searchsorted(times, origin + horizon_ns, side="right")
                if right > left and np.nanmax(fluxes[left:right]) >= threshold:
                    labels[index] = 1
            result[f"label_{target}_{horizon}h"] = labels
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "format": "KCH_MHD_SOLAR_EXACT_SOURCE_CENSUS_V1",
        "started_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "state": "RUNNING",
    }
    try:
        goes_raw, goes_receipt = acquire_goes(out)
        goes, goes_cleaning = clean_goes(goes_raw)
        client = drms.Client()
        frames: list[pd.DataFrame] = []
        jsoc_receipts: list[dict[str, Any]] = []
        for year in range(2010, 2026):
            frame, receipt = query_year(client, year, out)
            frames.append(frame)
            jsoc_receipts.append(receipt)
        sharp = pd.concat(frames, ignore_index=True)
        raw_rows = len(sharp)
        sharp["origin_utc"] = sharp["T_REC"].map(parse_t_rec)
        numeric = ["HARPNUM", "NOAA_AR", "NOAA_NUM", "QUALITY"] + SIGNED + UNSIGNED + BASELINE + ["LAT_FWT", "LON_FWT"]
        for column in numeric:
            sharp[column] = pd.to_numeric(sharp[column], errors="coerce")
        sharp["active_region_short"] = (sharp["NOAA_AR"].astype("Int64") % 10000).astype("Int64")
        finite_required = np.isfinite(sharp[SIGNED + UNSIGNED + BASELINE + ["LON_FWT"]].to_numpy(dtype=float)).all(axis=1)
        common = (
            (sharp["origin_utc"] >= START)
            & (sharp["origin_utc"] <= END)
            & (sharp["NOAA_NUM"] == 1)
            & (sharp["NOAA_AR"] > 0)
            & (sharp["LON_FWT"].abs() <= 60.0)
            & finite_required
        )
        primary = common & (sharp["QUALITY"] == 0)
        sensitivity = common & sharp["QUALITY"].isin([0, 65536])
        census = sharp[primary].copy()
        sensitivity_count = int(sensitivity.sum())
        before_dedup = len(census)
        census["abs_lon"] = census["LON_FWT"].abs()
        census = census.sort_values(["NOAA_AR", "origin_utc", "abs_lon", "AREA_ACR", "HARPNUM"], ascending=[True, True, True, False, True], kind="stable")
        census = census.drop_duplicates(subset=["NOAA_AR", "origin_utc"], keep="first").drop(columns=["abs_lon"])
        duplicate_windows_removed = before_dedup - len(census)
        ar_spans = census.groupby("NOAA_AR")["origin_utc"].agg(["min", "max", "count"]).reset_index()
        ar_spans["period"] = [period_for_interval(first, last) for first, last in zip(ar_spans["min"], ar_spans["max"])]
        period_map = ar_spans.set_index("NOAA_AR")["period"]
        census["period"] = census["NOAA_AR"].map(period_map)
        cross_boundary_ars = int(ar_spans["period"].isna().sum())
        census = census[census["period"].notna()].copy()
        census = label_origins(census, goes)
        census_path = out / "MHD_SOLAR_CENSUS_WINDOWS.csv.gz"
        census.to_csv(census_path, index=False, compression="gzip")

        label_rows: list[dict[str, Any]] = []
        for period_name, _, _ in PERIODS:
            part = census[census["period"] == period_name]
            for target, horizons in HORIZONS.items():
                for horizon in horizons:
                    column = f"label_{target}_{horizon}h"
                    by_ar = part.groupby("NOAA_AR")[column].max()
                    label_rows.append({
                        "period": period_name,
                        "target": target,
                        "horizon_hours": horizon,
                        "windows": int(len(part)),
                        "positive_windows": int(part[column].sum()),
                        "window_prevalence": float(part[column].mean()) if len(part) else None,
                        "active_regions": int(part["NOAA_AR"].nunique()),
                        "positive_active_regions": int(by_ar.sum()),
                        "active_region_prevalence": float(by_ar.mean()) if len(by_ar) else None,
                    })
        label_table = pd.DataFrame(label_rows)
        label_path = out / "MHD_LABEL_CENSUS.csv"
        label_table.to_csv(label_path, index=False)

        feature_rows: list[dict[str, Any]] = []
        for period_name, _, _ in PERIODS:
            part = census[census["period"] == period_name]
            for feature in SIGNED + UNSIGNED + BASELINE:
                values = pd.to_numeric(part[feature], errors="coerce")
                mask = np.isfinite(values)
                feature_rows.append({
                    "period": period_name,
                    "feature": feature,
                    "channel": "SIGNED" if feature in SIGNED else ("UNSIGNED_CONTROL" if feature in UNSIGNED else "NONHELICAL_BASELINE"),
                    "windows": int(len(part)),
                    "finite_windows": int(mask.sum()),
                    "finite_fraction": float(mask.mean()) if len(part) else None,
                    "active_regions_with_finite": int(part.loc[mask, "NOAA_AR"].nunique()),
                })
        feature_table = pd.DataFrame(feature_rows)
        feature_path = out / "MHD_FEATURE_COMPLETENESS.csv"
        feature_table.to_csv(feature_path, index=False)

        power_rows: list[dict[str, Any]] = []
        for sd in [0.02, 0.05, 0.10, 0.20]:
            power_rows.append({
                "metric": "paired_logscore_difference",
                "material_delta": 0.01,
                "assumed_cluster_sd": sd,
                "required_independent_active_regions_80pct_power": normal_required_n(0.01, sd),
            })
        for prevalence in [0.01, 0.05, 0.10, 0.20]:
            delta = 0.05 * prevalence * (1.0 - prevalence)
            for sd in [0.01, 0.02, 0.05, 0.10]:
                power_rows.append({
                    "metric": "paired_brier_difference",
                    "target_prevalence": prevalence,
                    "material_delta": delta,
                    "assumed_cluster_sd": sd,
                    "required_independent_active_regions_80pct_power": normal_required_n(delta, sd),
                })
        power_table = pd.DataFrame(power_rows)
        power_path = out / "MHD_POWER_ENVELOPE.csv"
        power_table.to_csv(power_path, index=False)

        decisions: list[dict[str, Any]] = []
        required_ars = normal_required_n(0.01, 0.05)
        for target, horizons in HORIZONS.items():
            for horizon in horizons:
                tests = label_table[(label_table["period"].isin(["TEST_A", "TEST_B"])) & (label_table["target"] == target) & (label_table["horizon_hours"] == horizon)]
                min_ars = int(tests["active_regions"].min()) if len(tests) == 2 else 0
                min_positive = int(tests["positive_active_regions"].min()) if len(tests) == 2 else 0
                required_positive = 30 if target == "M1_plus" else 10
                passed = len(tests) == 2 and min_ars >= required_ars and min_positive >= required_positive
                decisions.append({
                    "target": target,
                    "horizon_hours": horizon,
                    "minimum_test_active_regions": min_ars,
                    "minimum_test_positive_active_regions": min_positive,
                    "required_active_regions_under_sd_0_05": required_ars,
                    "required_positive_active_regions": required_positive,
                    "census_power_decision": "GO" if passed else "UPPER_BOUND_OR_SECONDARY_ONLY",
                })
        decision_table = pd.DataFrame(decisions)
        decision_path = out / "MHD_TARGET_GO_NO_GO.csv"
        decision_table.to_csv(decision_path, index=False)

        source_manifest = {
            "jsoc": jsoc_receipts,
            "goes": goes_receipt,
            "goes_cleaning": goes_cleaning,
            "census_window_file": {"path": census_path.name, "bytes": census_path.stat().st_size, "sha256": sha256_file(census_path)},
            "label_census": {"path": label_path.name, "sha256": sha256_file(label_path)},
            "feature_completeness": {"path": feature_path.name, "sha256": sha256_file(feature_path)},
            "power_envelope": {"path": power_path.name, "sha256": sha256_file(power_path)},
            "target_decision": {"path": decision_path.name, "sha256": sha256_file(decision_path)},
        }
        write_json(out / "MHD_SOURCE_MANIFEST.json", source_manifest)
        report.update({
            "state": "CENSUS_AND_POWER_COMPLETE",
            "completed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "jsoc_raw_rows": int(raw_rows),
            "strict_primary_rows_before_dedup": int(before_dedup),
            "strict_primary_rows_after_dedup_and_boundary_filter": int(len(census)),
            "quality_0_or_65536_sensitivity_rows": sensitivity_count,
            "duplicate_windows_removed": int(duplicate_windows_removed),
            "cross_boundary_active_regions_removed": cross_boundary_ars,
            "unique_active_regions": int(census["NOAA_AR"].nunique()),
            "period_active_regions": {str(key): int(value) for key, value in census.groupby("period")["NOAA_AR"].nunique().items()},
            "target_decisions": decisions,
            "primary_model_execution_performed": False,
            "feature_outcome_association_evaluated": False,
            "authority_ceiling": "NONE",
        })
        report["census_id"] = "mhdc:" + sha256_bytes(canonical(report))
        write_json(out / "MHD_CENSUS_REPORT.json", report)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        report.update({
            "state": "FAIL_CLOSED",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "completed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "primary_model_execution_performed": False,
            "authority_ceiling": "NONE",
        })
        write_json(out / "MHD_CENSUS_REPORT.json", report)
        print(traceback.format_exc())
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
