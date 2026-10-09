from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import drms
import numpy as np
import pandas as pd
from astropy.time import Time

EXPECTED_PROTOCOL_ID = "mhd002:6de1592567ccc3ffc269d3cd668c81bb2677d9f473e43539e4d603c0b41f98ea"
EXPECTED_CENSUS_ID = "mhd001census:4726c460b748f4829ac903366d1941f332b0e34d751d3447b33aa6088a0515f4"
SERIES = "hmi.Mharp_720s"
KEYS = ["HARPNUM", "T_REC", "NOAA_AR", "NOAA_ARS", "QUALITY", "LON_FWT", "LAT_FWT"]
CADENCE = "6h"


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def normalized_region(value: Any) -> int | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        number = int(float(str(value).strip())) % 10000
    except (TypeError, ValueError):
        return None
    return number if 1 <= number <= 9999 else None


def parse_region_list(value: Any) -> set[int]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return set()
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null", "0", "0.0", "[]"}:
        return set()
    result: set[int] = set()
    for token in re.findall(r"\d+(?:\.0+)?", text):
        region = normalized_region(token)
        if region is not None:
            result.add(region)
    return result


def parse_trec_naive(value: str) -> datetime:
    return datetime.strptime(str(value), "%Y.%m.%d_%H:%M:%S_TAI")


def tai_to_utc(value: str) -> datetime:
    isot = parse_trec_naive(value).strftime("%Y-%m-%dT%H:%M:%S")
    converted = Time(isot, format="isot", scale="tai").utc.to_datetime(timezone=timezone.utc)
    return converted if converted.tzinfo else converted.replace(tzinfo=timezone.utc)


def parse_flare_start(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if len(series) and float(numeric.notna().mean()) >= 0.95:
        finite = numeric.dropna().abs()
        if finite.empty:
            return pd.Series(pd.NaT, index=series.index, dtype="datetime64[ns, UTC]")
        median = float(finite.median())
        unit = "ns" if median >= 1e17 else "us" if median >= 1e14 else "ms" if median >= 1e11 else "s"
        return pd.to_datetime(numeric, unit=unit, errors="coerce", utc=True)
    return pd.to_datetime(series.astype(str).str.strip(), errors="coerce", utc=True)


def query_interval(client: drms.Client, start: datetime, stop: datetime, depth: int = 0):
    duration_days = max(1, int(math.ceil((stop - start).total_seconds() / 86400.0)))
    query = f"{SERIES}[][{start.strftime('%Y.%m.%d_%H:%M:%S_TAI')}/{duration_days}d@{CADENCE}]"
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            frame = client.query(query, key=",".join(KEYS))
            if frame is None:
                frame = pd.DataFrame(columns=KEYS)
            return [(start, stop, query, frame.reset_index(drop=True), attempt + 1, depth)]
        except Exception as exc:
            last_error = exc
            time.sleep(2.0 * (attempt + 1))
    interval = stop - start
    if interval > timedelta(days=2):
        midpoint = start + interval / 2
        return query_interval(client, start, midpoint, depth + 1) + query_interval(client, midpoint, stop, depth + 1)
    raise RuntimeError(f"JSOC query failed at minimum interval: {query}: {last_error!r}")


def verify_development_census(census_dir: Path) -> tuple[dict[str, Any], set[int]]:
    census = json.loads((census_dir / "BLIND_HARP_CENSUS.json").read_text(encoding="utf-8"))
    if census.get("census_id") != EXPECTED_CENSUS_ID:
        raise RuntimeError("development census identity mismatch")
    harps: set[int] = set()
    for receipt in census["chunk_receipts"]:
        path = census_dir / receipt["csv"]
        if sha256(path) != receipt["csv_sha256"]:
            raise RuntimeError(f"development census chunk mismatch: {path.name}")
        frame = pd.read_csv(path, usecols=["HARPNUM"], low_memory=False)
        harps.update(int(value) for value in pd.to_numeric(frame["HARPNUM"], errors="coerce").dropna().astype(int).tolist())
    return census, harps


def load_noaa_flares(csv_path: Path, metadata_path: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    algorithm = str(metadata.get("global_attributes", {}).get("flrpt_algorithm_version"))
    if algorithm != "1-0-1":
        raise RuntimeError(f"NOAA algorithm-version drift: {algorithm!r}")
    variables = metadata.get("variable_attributes", {})
    required = {"start_time", "flare_class", "active_region"}
    if not required.issubset(set(variables)):
        raise RuntimeError(f"metadata missing required variables: {sorted(required-set(variables))}")
    frame = pd.read_csv(csv_path, low_memory=False)
    frame.columns = [str(column).strip() for column in frame.columns]
    if not required.issubset(set(frame.columns)):
        raise RuntimeError(f"CSV missing required columns: {sorted(required-set(frame.columns))}")
    start = parse_flare_start(frame["start_time"])
    flare_class = frame["flare_class"].astype(str).str.strip().str.upper()
    active_region = pd.to_numeric(frame["active_region"], errors="coerce").map(normalized_region)
    admitted = start.notna() & active_region.notna() & flare_class.str.startswith(("M", "X"), na=False)
    flares = pd.DataFrame({"start_utc": start[admitted], "flare_class": flare_class[admitted], "region": active_region[admitted].astype(int)})
    flares = flares.drop_duplicates(subset=["start_utc", "flare_class", "region"]).sort_values(["region", "start_utc", "flare_class"], kind="stable").reset_index(drop=True)
    return flares, {
        "source_rows": int(len(frame)),
        "admitted_mx_region_rows": int(len(flares)),
        "first_start_utc": flares.start_utc.min().isoformat() if len(flares) else None,
        "last_start_utc": flares.start_utc.max().isoformat() if len(flares) else None,
        "algorithm_version": algorithm,
    }


def label_records(records: pd.DataFrame, flares: pd.DataFrame, hours: float) -> pd.DataFrame:
    times_by_region: dict[int, list[pd.Timestamp]] = {}
    classes_by_region: dict[int, list[str]] = {}
    for region, group in flares.groupby("region", sort=True):
        times_by_region[int(region)] = list(group.start_utc)
        classes_by_region[int(region)] = list(group.flare_class)
    labels = np.zeros(len(records), dtype=np.int8)
    next_start = [""] * len(records)
    next_class = [""] * len(records)
    horizon = pd.Timedelta(hours=hours)
    for index, row in enumerate(records.itertuples(index=False)):
        times = times_by_region.get(int(row.normalized_noaa_region))
        if not times:
            continue
        instant = pd.Timestamp(row.time_utc)
        candidate = bisect.bisect_right(times, instant)
        if candidate < len(times) and times[candidate] <= instant + horizon:
            labels[index] = 1
            next_start[index] = times[candidate].isoformat()
            next_class[index] = classes_by_region[int(row.normalized_noaa_region)][candidate]
    output = records.copy()
    output["mx24h"] = labels
    output["next_mx_start_utc"] = next_start
    output["next_mx_class"] = next_class
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--development-census-dir", required=True, type=Path)
    parser.add_argument("--noaa-csv", required=True, type=Path)
    parser.add_argument("--noaa-metadata", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("protocol_id") != EXPECTED_PROTOCOL_ID or protocol.get("status") != "LOCKED_BEFORE_2026_HARP_METADATA_LABEL_OR_SHARP_FEATURE_ACCESS":
        raise RuntimeError("MHD002 protocol identity/state mismatch")
    development_census, development_harps = verify_development_census(args.development_census_dir)

    start = datetime.fromisoformat(protocol["prospective_pilot"]["time_range_tai"][0]).replace(tzinfo=timezone.utc)
    stop = datetime.fromisoformat(protocol["prospective_pilot"]["time_range_tai"][1]).replace(tzinfo=timezone.utc)
    client = drms.Client()
    frames: list[pd.DataFrame] = []
    receipts: list[dict[str, Any]] = []
    cursor = start
    sequence = 0
    while cursor < stop:
        interval_stop = min(cursor + timedelta(days=31), stop)
        for sub_start, sub_stop, query, frame, attempts, depth in query_interval(client, cursor, interval_stop):
            sequence += 1
            path = args.output_dir / f"pilot_chunk_{sequence:03d}_{sub_start:%Y%m%d}_{sub_stop:%Y%m%d}.csv"
            frame.to_csv(path, index=False)
            receipts.append({"query": query, "records": int(len(frame)), "file": path.name, "bytes": path.stat().st_size, "sha256": sha256(path), "attempts": attempts, "split_depth": depth})
            if len(frame):
                frames.append(frame)
        cursor = interval_stop
    records = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=KEYS)
    records = records.drop_duplicates(subset=["HARPNUM", "T_REC"], keep="first").copy()
    records["tai_naive"] = records["T_REC"].map(parse_trec_naive)
    records = records[(records.tai_naive >= start.replace(tzinfo=None)) & (records.tai_naive < stop.replace(tzinfo=None))].copy()
    records["QUALITY_num"] = pd.to_numeric(records["QUALITY"], errors="coerce")
    records["LON_num"] = pd.to_numeric(records["LON_FWT"], errors="coerce")
    records["primary_region"] = records["NOAA_AR"].map(normalized_region)
    records["region_list"] = records["NOAA_ARS"].map(parse_region_list)
    records["region_unambiguous"] = [primary is not None and (not regions or regions == {primary}) for primary, regions in zip(records.primary_region, records.region_list)]
    records["new_harp"] = ~pd.to_numeric(records.HARPNUM, errors="coerce").fillna(-1).astype(int).isin(development_harps)
    passed = records[
        records.QUALITY_num.eq(protocol["harp_filter"]["quality_equals"])
        & records.LON_num.abs().le(float(protocol["harp_filter"]["maximum_absolute_lon_fwt_deg"]))
        & records.primary_region.notna()
        & records.region_unambiguous
        & records.new_harp
    ].copy()
    passed["HARPNUM"] = pd.to_numeric(passed.HARPNUM, errors="raise").astype(int)
    passed["normalized_noaa_region"] = passed.primary_region.astype(int)
    passed["time_utc"] = passed.T_REC.map(tai_to_utc)
    passed = passed.sort_values(["HARPNUM", "time_utc", "T_REC"], kind="stable")

    flares, flare_report = load_noaa_flares(args.noaa_csv, args.noaa_metadata)
    labeled = label_records(passed[["HARPNUM", "T_REC", "time_utc", "normalized_noaa_region"]].copy(), flares, float(protocol["label_rule"]["window_hours"]))
    labels_path = args.output_dir / "MHD002_2026_PILOT_LABELS.csv"
    labeled.to_csv(labels_path, index=False)
    harp_labels = labeled.groupby("HARPNUM", sort=True).mx24h.max() if len(labeled) else pd.Series(dtype=int)
    positive_harps = int(harp_labels.sum()) if len(harp_labels) else 0
    unique_harps = int(len(harp_labels))
    negative_harps = unique_harps - positive_harps
    gates = {
        "minimum_unique_harps": unique_harps >= int(protocol["prospective_pilot"]["minimum_unique_harps"]),
        "minimum_positive_harps": positive_harps >= int(protocol["prospective_pilot"]["minimum_positive_harps"]),
        "minimum_negative_harps": negative_harps >= int(protocol["prospective_pilot"]["minimum_negative_harps"]),
    }
    outcome = "PILOT_LABEL_IDENTIFIABILITY_PASS" if all(gates.values()) else "PROSPECTIVE_PILOT_INSUFFICIENT_POWER"
    body = {
        "format": "KCH_MHD002_2026_BLIND_PILOT_LABEL_GATE",
        "protocol_id": protocol["protocol_id"],
        "development_census_id": development_census["census_id"],
        "development_harp_count_excluded": int(len(development_harps)),
        "pilot_time_range_tai": protocol["prospective_pilot"]["time_range_tai"],
        "query_receipts": receipts,
        "raw_unique_record_count": int(len(records)),
        "locked_filter_record_count": int(len(passed)),
        "unique_harp_count": unique_harps,
        "positive_harp_count": positive_harps,
        "negative_harp_count": negative_harps,
        "positive_record_count": int(labeled.mx24h.sum()) if len(labeled) else 0,
        "record_count": int(len(labeled)),
        "positive_record_fraction": float(labeled.mx24h.mean()) if len(labeled) else 0.0,
        "flare_report": flare_report,
        "noaa_csv": {"file": args.noaa_csv.name, "bytes": args.noaa_csv.stat().st_size, "sha256": sha256(args.noaa_csv)},
        "noaa_metadata": {"file": args.noaa_metadata.name, "bytes": args.noaa_metadata.stat().st_size, "sha256": sha256(args.noaa_metadata)},
        "label_file": {"file": labels_path.name, "bytes": labels_path.stat().st_size, "sha256": sha256(labels_path)},
        "gate_checks": gates,
        "outcome": outcome,
        "helicity_keywords_accessed": False,
        "sharp_feature_values_accessed": False,
        "scientific_model_execution_performed": False,
        "may_support_replicated_physical_claim": False,
        "physical_helicity": "NOT_EVALUATED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "authority_ceiling": "NONE",
    }
    body["result_id"] = "mhd002pilot:" + hashlib.sha256(canonical(body)).hexdigest()
    write_json(args.output_dir / "MHD002_2026_BLIND_PILOT_RESULT.json", body)
    print(json.dumps({"result_id": body["result_id"], "outcome": outcome, "record_count": body["record_count"], "unique_harp_count": unique_harps, "positive_harp_count": positive_harps, "negative_harp_count": negative_harps, "gate_checks": gates, "helicity_keywords_accessed": False}, indent=2, sort_keys=True))
    return 0 if all(gates.values()) else 3


if __name__ == "__main__":
    raise SystemExit(main())
