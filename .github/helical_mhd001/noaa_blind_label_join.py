from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from astropy.time import Time

EXPECTED_PROTOCOL_ID = "mhd001label:7c328525d4096c9b780d8bf21b58e063a81b14da0de710a022ca2bd55bad2960"
EXPECTED_CENSUS_ID = "mhd001census:4726c460b748f4829ac903366d1941f332b0e34d751d3447b33aa6088a0515f4"


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def parse_trec_naive(value: str) -> datetime:
    return datetime.strptime(str(value), "%Y.%m.%d_%H:%M:%S_TAI")


def tai_to_utc(value: str) -> datetime:
    isot = datetime.strptime(str(value), "%Y.%m.%d_%H:%M:%S_TAI").strftime("%Y-%m-%dT%H:%M:%S")
    converted = Time(isot, format="isot", scale="tai").utc.to_datetime(timezone=timezone.utc)
    return converted if converted.tzinfo is not None else converted.replace(tzinfo=timezone.utc)


def partition_of_tai(value: datetime, partitions: dict[str, list[str]]) -> str | None:
    for name, bounds in partitions.items():
        if datetime.fromisoformat(bounds[0]) <= value < datetime.fromisoformat(bounds[1]):
            return name
    return None


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
    regions: set[int] = set()
    for token in re.findall(r"\d+(?:\.0+)?", text):
        region = normalized_region(token)
        if region is not None:
            regions.add(region)
    return regions


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


def verify_census(census_dir: Path) -> tuple[dict[str, Any], pd.DataFrame]:
    census_path = census_dir / "BLIND_HARP_CENSUS.json"
    census = json.loads(census_path.read_text(encoding="utf-8"))
    if census.get("census_id") != EXPECTED_CENSUS_ID:
        raise RuntimeError(f"census identity mismatch: {census.get('census_id')}")
    summary_path = census_dir / "BLIND_HARP_SUMMARY.csv"
    if sha256(summary_path) != census["summary_csv_sha256"]:
        raise RuntimeError("blind HARP summary SHA-256 mismatch")
    frames: list[pd.DataFrame] = []
    required = {"HARPNUM", "T_REC", "NOAA_AR", "NOAA_ARS", "QUALITY", "LON_FWT", "LAT_FWT"}
    for receipt in census["chunk_receipts"]:
        path = census_dir / receipt["csv"]
        if sha256(path) != receipt["csv_sha256"]:
            raise RuntimeError(f"census chunk SHA-256 mismatch: {path.name}")
        frame = pd.read_csv(path, low_memory=False)
        missing = sorted(required - set(frame.columns))
        if missing:
            raise RuntimeError(f"{path.name}: missing columns {missing}")
        frames.append(frame[list(required)])
    combined = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["HARPNUM", "T_REC"], keep="first")
    if len(combined) != int(census["unique_record_count"]):
        raise RuntimeError(f"census unique-record drift: {len(combined)} != {census['unique_record_count']}")
    return census, combined.copy()


def acquire_receipt(path: Path, meta_path: Path | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {"path": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}
    if meta_path is not None and meta_path.is_file():
        body["curl"] = json.loads(meta_path.read_text(encoding="utf-8"))
    return body


def load_flares(csv_path: Path, metadata_path: Path, protocol: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    variables = metadata.get("variable_attributes", {})
    missing_variables = sorted(set(protocol["label_sources"]["required_metadata_variables"]) - set(variables))
    if missing_variables:
        raise RuntimeError(f"NOAA metadata missing required variables: {missing_variables}")
    algorithm = metadata.get("global_attributes", {}).get("flrpt_algorithm_version")
    if str(algorithm) != str(protocol["label_sources"]["algorithm_version"]):
        raise RuntimeError(f"NOAA algorithm-version drift: {algorithm!r}")
    frame = pd.read_csv(csv_path, low_memory=False)
    frame.columns = [str(column).strip() for column in frame.columns]
    missing = sorted(set(protocol["label_sources"]["required_csv_columns"]) - set(frame.columns))
    if missing:
        raise RuntimeError(f"NOAA flare CSV missing required columns: {missing}")
    start = parse_flare_start(frame["start_time"])
    flare_class = frame["flare_class"].astype(str).str.strip().str.upper()
    active_region = pd.to_numeric(frame["active_region"], errors="coerce").map(normalized_region)
    admitted = start.notna() & active_region.notna() & flare_class.str.startswith(tuple(protocol["label_rule"]["flare_class_prefixes"]), na=False)
    flares = pd.DataFrame({"start_utc": start[admitted], "flare_class": flare_class[admitted], "normalized_active_region": active_region[admitted].astype(int)})
    flares = flares.sort_values(["normalized_active_region", "start_utc", "flare_class"], kind="stable")
    duplicate_count = int(flares.duplicated(subset=["start_utc", "flare_class", "normalized_active_region"]).sum())
    flares = flares.drop_duplicates(subset=["start_utc", "flare_class", "normalized_active_region"], keep="first").reset_index(drop=True)
    return flares, {
        "csv_row_count": int(len(frame)),
        "admitted_mx_region_row_count": int(len(flares)),
        "duplicate_mx_region_rows_removed": duplicate_count,
        "first_admitted_start_utc": flares["start_utc"].min().isoformat() if len(flares) else None,
        "last_admitted_start_utc": flares["start_utc"].max().isoformat() if len(flares) else None,
        "algorithm_version": str(algorithm),
    }


def label_records(records: pd.DataFrame, flares: pd.DataFrame, hours: float) -> pd.DataFrame:
    region_times: dict[int, list[pd.Timestamp]] = {}
    region_classes: dict[int, list[str]] = {}
    for region, group in flares.groupby("normalized_active_region", sort=True):
        region_times[int(region)] = list(group["start_utc"])
        region_classes[int(region)] = list(group["flare_class"])
    label = np.zeros(len(records), dtype=np.int8)
    next_start = [""] * len(records)
    next_class = [""] * len(records)
    horizon = pd.Timedelta(hours=hours)
    for position, row in enumerate(records.itertuples(index=False)):
        times = region_times.get(int(row.normalized_noaa_region))
        if not times:
            continue
        instant = pd.Timestamp(row.time_utc)
        candidate = bisect.bisect_right(times, instant)
        if candidate < len(times) and times[candidate] <= instant + horizon:
            label[position] = 1
            next_start[position] = times[candidate].isoformat()
            next_class[position] = region_classes[int(row.normalized_noaa_region)][candidate]
    result = records.copy()
    result["mx24h"] = label
    result["next_mx_start_utc"] = next_start
    result["next_mx_class"] = next_class
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--census-dir", required=True, type=Path)
    parser.add_argument("--flare-csv", required=True, type=Path)
    parser.add_argument("--flare-metadata", required=True, type=Path)
    parser.add_argument("--flare-curl-meta", type=Path)
    parser.add_argument("--metadata-curl-meta", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    if protocol.get("protocol_id") != EXPECTED_PROTOCOL_ID or protocol.get("status") != "LOCKED_BEFORE_NOAA_FLARE_LABEL_ENTITY_ACCESS":
        raise RuntimeError("label-join protocol identity or state mismatch")
    census, combined = verify_census(args.census_dir)
    combined["tai_naive"] = combined["T_REC"].map(parse_trec_naive)
    combined["partition"] = combined["tai_naive"].map(lambda value: partition_of_tai(value, protocol["temporal_partitions_tai"]))
    combined = combined[combined["partition"].notna()].copy()
    combined["QUALITY_num"] = pd.to_numeric(combined["QUALITY"], errors="coerce")
    combined["LON_num"] = pd.to_numeric(combined["LON_FWT"], errors="coerce")
    combined["primary_region"] = combined["NOAA_AR"].map(normalized_region)
    combined["region_list"] = combined["NOAA_ARS"].map(parse_region_list)
    combined["region_unambiguous"] = [primary is not None and (not regions or regions == {primary}) for primary, regions in zip(combined["primary_region"], combined["region_list"])]
    combined["record_filter_pass"] = combined["QUALITY_num"].eq(protocol["harp_record_filter"]["quality_equals"]) & combined["LON_num"].abs().le(float(protocol["harp_record_filter"]["maximum_absolute_lon_fwt_deg"])) & combined["primary_region"].notna() & combined["region_unambiguous"]

    partition_count = combined.groupby("HARPNUM")["partition"].nunique()
    cross_partition_harps = sorted(int(value) for value in partition_count[partition_count > 1].index.tolist())
    filtered = combined[combined["record_filter_pass"] & ~combined["HARPNUM"].astype(int).isin(cross_partition_harps)].copy()
    filtered["normalized_noaa_region"] = filtered["primary_region"].astype(int)
    filtered["time_utc"] = filtered["T_REC"].map(tai_to_utc)
    filtered = filtered.sort_values(["partition", "HARPNUM", "time_utc", "T_REC"], kind="stable").drop_duplicates(subset=["HARPNUM", "T_REC"], keep="first")

    flares, flare_report = load_flares(args.flare_csv, args.flare_metadata, protocol)
    labeled = label_records(filtered[["partition", "HARPNUM", "T_REC", "time_utc", "normalized_noaa_region"]].copy(), flares, float(protocol["label_rule"]["window_hours"]))

    outputs: dict[str, dict[str, Any]] = {}
    summary: dict[str, dict[str, Any]] = {}
    for partition in protocol["temporal_partitions_tai"]:
        part = labeled[labeled["partition"] == partition].copy()
        path = args.output_dir / f"LABELS_{partition.upper()}.csv"
        part.to_csv(path, index=False)
        harp_label = part.groupby("HARPNUM", sort=True)["mx24h"].max() if len(part) else pd.Series(dtype=int)
        positive_harps = int(harp_label.sum()) if len(harp_label) else 0
        unique_harps = int(len(harp_label))
        summary[partition] = {
            "record_count": int(len(part)),
            "positive_record_count": int(part["mx24h"].sum()) if len(part) else 0,
            "positive_record_fraction": float(part["mx24h"].mean()) if len(part) else 0.0,
            "unique_harp_count": unique_harps,
            "positive_harp_count": positive_harps,
            "negative_harp_count": unique_harps - positive_harps,
        }
        outputs[partition] = {"file": path.name, "bytes": path.stat().st_size, "sha256": sha256(path)}

    thresholds = protocol["identifiability"]
    gate_checks = {
        "train_positive_harps": summary["train"]["positive_harp_count"] >= int(thresholds["minimum_positive_harps_train"]),
        "calibration_positive_harps": summary["calibration"]["positive_harp_count"] >= int(thresholds["minimum_positive_harps_calibration"]),
        "test1_positive_harps": summary["sealed_test_epoch_1"]["positive_harp_count"] >= int(thresholds["minimum_positive_harps_each_sealed_epoch"]),
        "test2_positive_harps": summary["sealed_test_epoch_2"]["positive_harp_count"] >= int(thresholds["minimum_positive_harps_each_sealed_epoch"]),
        "test1_unique_harps": summary["sealed_test_epoch_1"]["unique_harp_count"] >= int(thresholds["minimum_unique_harps_each_sealed_epoch"]),
        "test2_unique_harps": summary["sealed_test_epoch_2"]["unique_harp_count"] >= int(thresholds["minimum_unique_harps_each_sealed_epoch"]),
    }
    for partition, values in summary.items():
        gate_checks[f"{partition}_negative_harps"] = values["negative_harp_count"] >= int(thresholds["minimum_negative_harps_each_partition"])
    outcome = "LABEL_JOIN_POWER_PASS" if all(gate_checks.values()) else "NOT_IDENTIFIABLE_REGION_LABEL_ASSOCIATION" if any(summary[name]["unique_harp_count"] == 0 for name in summary) else "INSUFFICIENT_REGION_LEVEL_POWER"

    cross_path = args.output_dir / "CROSS_PARTITION_HARPS_EXCLUDED.json"
    write_json(cross_path, {"rule": "EXCLUDE_EVERY_HARPNUM_OBSERVED_IN_MORE_THAN_ONE_OF_FOUR_FROZEN_PARTITIONS_BEFORE_LABEL_ACCESS", "count": len(cross_partition_harps), "HARPNUM": cross_partition_harps})
    body = {
        "format": "KCH_MHD001_NOAA_NCEI_BLIND_LABEL_JOIN_RESULT",
        "protocol_id": protocol["protocol_id"],
        "predecessor_prelock_id": protocol["predecessor_prelock_id"],
        "census_id": census["census_id"],
        "source_receipts": {"flare_csv": acquire_receipt(args.flare_csv, args.flare_curl_meta), "flare_metadata": acquire_receipt(args.flare_metadata, args.metadata_curl_meta)},
        "flare_parse_report": flare_report,
        "cross_partition_harp_count_excluded": len(cross_partition_harps),
        "cross_partition_harps_file": {"file": cross_path.name, "sha256": sha256(cross_path)},
        "record_count_before_filters": int(len(combined)),
        "record_count_after_locked_filters": int(len(filtered)),
        "ambiguous_or_missing_region_record_count": int((~combined["region_unambiguous"]).sum()),
        "partition_summary": summary,
        "output_files": outputs,
        "gate_checks": gate_checks,
        "outcome": outcome,
        "helical_keywords_accessed": False,
        "vector_segments_accessed": False,
        "scientific_model_execution_performed": False,
        "physical_helicity": "NOT_EVALUATED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "authority_ceiling": "NONE",
    }
    body["result_id"] = "mhd001labelresult:" + hashlib.sha256(canonical(body)).hexdigest()
    write_json(args.output_dir / "BLIND_LABEL_JOIN_RESULT.json", body)
    print(json.dumps({"result_id": body["result_id"], "outcome": outcome, "partition_summary": summary, "gate_checks": gate_checks, "helical_keywords_accessed": False, "scientific_model_execution_performed": False}, indent=2, sort_keys=True))
    return 0 if outcome == "LABEL_JOIN_POWER_PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
