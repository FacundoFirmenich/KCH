from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def extract_archives(root: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for archive_path in sorted(root.rglob("SHARD_*_BODIES.tar.gz")):
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                target = destination / member.name
                target.parent.mkdir(parents=True, exist_ok=True)
                payload = archive.extractfile(member).read()
                if target.exists() and target.read_bytes() != payload:
                    raise RuntimeError(f"conflicting body for {member.name}")
                target.write_bytes(payload)


def deterministic_tar_gz(raw_root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as raw_handle:
        with gzip.GzipFile(fileobj=raw_handle, mode="wb", mtime=0, compresslevel=6) as gzip_handle:
            with tarfile.open(fileobj=gzip_handle, mode="w") as archive:
                for path in sorted(raw_root.rglob("*.geojson")):
                    relative = path.relative_to(raw_root).as_posix()
                    payload = path.read_bytes()
                    info = tarfile.TarInfo(relative)
                    info.size = len(payload)
                    info.mtime = 0
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mode = 0o644
                    archive.addfile(info, io.BytesIO(payload))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shards-root", type=Path, required=True)
    parser.add_argument("--network-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-run-id", type=int, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    lock = json.loads((args.network_root / "SEISMIC_FULL_NETWORK_LOCK_V1_1.json").read_text(encoding="utf-8"))
    selected = pd.read_csv(args.network_root / "SELECTED_EVENT_IDS_AND_SPLITS.csv", low_memory=False)
    selected["event_id"] = selected["event_id"].astype(str)
    if selected["event_id"].duplicated().any():
        raise RuntimeError("network selected event list contains duplicates")
    receipt_paths = sorted(args.shards_root.rglob("SHARD_*_RECEIPTS.csv.gz"))
    manifest_paths = sorted(args.shards_root.rglob("SHARD_*_MANIFEST.json"))
    if len(receipt_paths) != 4 or len(manifest_paths) != 4:
        raise RuntimeError(f"expected four shard receipts/manifests, got {len(receipt_paths)}/{len(manifest_paths)}")
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in manifest_paths]
    if sorted(row["shard_index"] for row in manifests) != [0, 1, 2, 3]:
        raise RuntimeError("incomplete shard index set")
    frames = [pd.read_csv(path, compression="gzip", low_memory=False) for path in receipt_paths]
    receipts = pd.concat(frames, ignore_index=True).sort_values("event_id", kind="stable")
    if receipts["event_id"].astype(str).duplicated().any():
        raise RuntimeError("duplicate event receipt across shards")
    expected = set(selected["event_id"])
    observed = set(receipts["event_id"].astype(str))
    if observed != expected:
        raise RuntimeError(f"shard union mismatch: missing={len(expected-observed)} extra={len(observed-expected)}")
    raw_root = args.out / "raw_details"
    extract_archives(args.shards_root, raw_root)
    raw_files = list(raw_root.rglob("*.geojson"))
    if len(raw_files) != len(expected):
        raise RuntimeError(f"raw body count mismatch: {len(raw_files)} != {len(expected)}")
    joined = selected.merge(receipts, on="event_id", how="left", validate="one_to_one")
    receipts_path = args.out / "COMCAT_DETAIL_RECEIPTS.csv.gz"
    receipts.to_csv(receipts_path, index=False, compression="gzip")
    mechanisms_path = args.out / "SELECTED_DIRECTIONAL_MECHANISMS.csv.gz"
    joined.to_csv(mechanisms_path, index=False, compression="gzip")
    archive_path = args.out / "COMCAT_DETAIL_BODIES.tar.gz"
    deterministic_tar_gz(raw_root, archive_path)
    cohort_rows = []
    for region, group in joined.groupby("region", sort=True):
        test = group[group["split"] == "TEST"]
        cohort_rows.append({
            "region": region,
            "selected_events": int(len(group)),
            "parsed_directional_events": int(group["parse_status"].eq("PASS").sum()),
            "directional_coverage": float(group["parse_status"].eq("PASS").mean()),
            "sealed_test_events": int(len(test)),
            "sealed_test_parsed_directional_events": int(test["parse_status"].eq("PASS").sum()),
            "sealed_test_directional_coverage": float(test["parse_status"].eq("PASS").mean()) if len(test) else 0.0,
        })
    all_fetch_complete = bool(joined["parse_status"].ne("FETCH_FAILED").all())
    coverage_gate = all(row["directional_coverage"] >= 0.75 and row["sealed_test_parsed_directional_events"] >= 200 for row in cohort_rows)
    body = {
        "format": "KCH_SEISMIC_DIRECTIONAL_ACQUISITION_V1_1",
        "transport": "FOUR_SHARD_CHECKPOINTED_ACQUISITION",
        "source_run_id": args.source_run_id,
        "network_lock_id": lock["network_lock_id"],
        "network_lock_sha256": sha256_file(args.network_root / "SEISMIC_FULL_NETWORK_LOCK_V1_1.json"),
        "selected_event_file_sha256": sha256_file(args.network_root / "SELECTED_EVENT_IDS_AND_SPLITS.csv"),
        "acquired_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "selected_event_count": len(expected),
        "successful_directional_parse_count": int(joined["parse_status"].eq("PASS").sum()),
        "fetch_failures": int(joined["parse_status"].eq("FETCH_FAILED").sum()),
        "no_valid_product": int(joined["parse_status"].eq("NO_VALID_DIRECTIONAL_PRODUCT").sum()),
        "cohorts": cohort_rows,
        "shard_manifests": manifests,
        "all_http_acquisitions_complete": all_fetch_complete,
        "directional_coverage_gate_pass": coverage_gate,
        "scientific_model_execution_performed": False,
        "raw_body_archive": {"path": archive_path.name, "bytes": archive_path.stat().st_size, "sha256": sha256_file(archive_path)},
        "receipt_file": {"path": receipts_path.name, "sha256": sha256_file(receipts_path)},
        "mechanism_file": {"path": mechanisms_path.name, "sha256": sha256_file(mechanisms_path)},
        "source_substitution": False,
        "authority_ceiling": "NONE",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    body["directional_acquisition_id"] = "s11dir:" + hashlib.sha256(canonical(body)).hexdigest()
    write_json(args.out / "SEISMIC_DIRECTIONAL_ACQUISITION_V1_1.json", body)
    for path in sorted(raw_root.rglob("*.geojson")):
        path.unlink()
    for directory in sorted((path for path in raw_root.rglob("*") if path.is_dir()), reverse=True):
        directory.rmdir()
    raw_root.rmdir()
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0 if all_fetch_complete and coverage_gate else 3


if __name__ == "__main__":
    raise SystemExit(main())
