from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import drms
import pandas as pd

SERIES = "hmi.sharp_cea_720s"
START = datetime(2010, 5, 1, tzinfo=timezone.utc)
END = datetime(2026, 1, 1, tzinfo=timezone.utc)
CHUNK_DAYS = 31
CADENCE = "6h"
KEYS = [
    "HARPNUM","T_REC","NOAA_AR","NOAA_ARS","QUALITY","LAT_FWT","LON_FWT",
    "USFLUX","MEANGBT","MEANGBZ","MEANGBH","MEANJZD","TOTUSJZ","MEANALP",
    "MEANJZH","TOTUSJH","ABSNJZH","SAVNCPP","MEANPOT","TOTPOT","MEANSHR",
    "SHRGT45","R_VALUE","AREA_ACR",
]
EXPECTED_MODEL_PROTOCOL_ID = "mhd001model:5d14dfdbf3c25a2bc9b8ed111a39cec1fb1cbedd8a8cde6272a80af439a105fd"


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def query_interval(client: drms.Client, start: datetime, stop: datetime, depth: int = 0):
    duration_days = max(1, int(math.ceil((stop - start).total_seconds() / 86400.0)))
    start_text = start.strftime("%Y.%m.%d_%H:%M:%S_TAI")
    query = f"{SERIES}[][{start_text}/{duration_days}d@{CADENCE}]"
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-protocol", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    protocol = json.loads(args.model_protocol.read_text(encoding="utf-8"))
    if protocol.get("protocol_id") != EXPECTED_MODEL_PROTOCOL_ID:
        raise RuntimeError("model protocol identity mismatch")
    if protocol["source"]["series"] != SERIES or protocol["source"]["cadence"] != CADENCE:
        raise RuntimeError("source series/cadence drift")
    if protocol["source"]["keywords"] != KEYS:
        raise RuntimeError("source keyword order drift")

    client = drms.Client()
    chunk_receipts: list[dict[str, Any]] = []
    all_keys: list[pd.DataFrame] = []
    cursor = START
    sequence = 0
    while cursor < END:
        stop = min(cursor + timedelta(days=CHUNK_DAYS), END)
        for sub_start, sub_stop, query, frame, attempts, depth in query_interval(client, cursor, stop):
            sequence += 1
            missing = sorted(set(KEYS) - set(frame.columns))
            if missing:
                raise RuntimeError(f"{query}: missing keywords {missing}")
            frame = frame[KEYS]
            path = out / f"chunk_{sequence:04d}_{sub_start:%Y%m%dT%H%M%S}_{sub_stop:%Y%m%dT%H%M%S}.csv"
            frame.to_csv(path, index=False)
            chunk_receipts.append({
                "query": query,
                "start_tai_label": sub_start.isoformat(),
                "stop_exclusive_tai_label": sub_stop.isoformat(),
                "records": int(len(frame)),
                "file": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "attempts": attempts,
                "split_depth": depth,
            })
            if len(frame):
                all_keys.append(frame[["HARPNUM","T_REC"]])
        cursor = stop

    keys = pd.concat(all_keys, ignore_index=True) if all_keys else pd.DataFrame(columns=["HARPNUM","T_REC"])
    duplicate_rows = int(keys.duplicated(subset=["HARPNUM","T_REC"]).sum())
    unique_records = int(len(keys.drop_duplicates(subset=["HARPNUM","T_REC"])))
    body = {
        "format": "KCH_MHD001_SHARP_FEATURE_CENSUS",
        "model_protocol_id": protocol["protocol_id"],
        "series": SERIES,
        "cadence": CADENCE,
        "start_tai_label": START.isoformat(),
        "end_exclusive_tai_label": END.isoformat(),
        "keywords": KEYS,
        "helicity_keywords_accessed": True,
        "vector_segments_accessed": False,
        "flare_labels_accessed_by_this_process": False,
        "query_count": len(chunk_receipts),
        "maximum_split_depth": max((row["split_depth"] for row in chunk_receipts), default=0),
        "record_rows": int(len(keys)),
        "duplicate_harp_trec_rows": duplicate_rows,
        "unique_harp_trec_records": unique_records,
        "chunks": chunk_receipts,
        "scientific_model_execution_performed": False,
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "authority_ceiling": "NONE",
    }
    body["feature_census_id"] = "mhd001features:" + hashlib.sha256(canonical(body)).hexdigest()
    (out / "SHARP_FEATURE_CENSUS.json").write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: body[key] for key in ["feature_census_id","query_count","record_rows","duplicate_harp_trec_rows","unique_harp_trec_records","helicity_keywords_accessed"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
