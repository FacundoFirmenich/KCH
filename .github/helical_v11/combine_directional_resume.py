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
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def extract_archive(path: Path, destination: Path) -> None:
    with tarfile.open(path, "r:gz") as archive:
        for member in archive.getmembers():
            if not member.isfile():
                continue
            extracted = archive.extractfile(member)
            if extracted is None:
                raise RuntimeError(f"cannot extract {member.name}")
            payload = extracted.read()
            target = destination / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.exists() and target.read_bytes() != payload:
                raise RuntimeError(f"conflicting exact body for {member.name}")
            target.write_bytes(payload)


def deterministic_tar_gz(root: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("wb") as raw_handle:
        with gzip.GzipFile(fileobj=raw_handle, mode="wb", mtime=0, compresslevel=6) as gzip_handle:
            with tarfile.open(fileobj=gzip_handle, mode="w") as archive:
                for path in sorted(root.rglob("*.geojson")):
                    relative = path.relative_to(root).as_posix()
                    payload = path.read_bytes()
                    info = tarfile.TarInfo(relative)
                    info.size = len(payload); info.mtime = 0; info.uid = info.gid = 0
                    info.uname = info.gname = ""; info.mode = 0o644
                    archive.addfile(info, io.BytesIO(payload))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial-root", type=Path, required=True)
    parser.add_argument("--resume-root", type=Path, required=True)
    parser.add_argument("--network-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source-run-id", type=int, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    initial_result = json.loads((args.initial_root / "SEISMIC_DIRECTIONAL_ACQUISITION_V1_1.json").read_text(encoding="utf-8"))
    if initial_result["directional_acquisition_id"] != "s11dir:e4da252002474d9bd5c136ba08b0848953b4b76d4f431b0bf1d67d8768422ae9":
        raise RuntimeError("initial acquisition identity mismatch")
    initial = pd.read_csv(args.initial_root / "COMCAT_DETAIL_RECEIPTS.csv.gz", low_memory=False)
    pass_initial = initial[initial["parse_status"].eq("PASS")].copy()
    failed_initial = initial[initial["parse_status"].eq("FETCH_FAILED")].copy()
    if len(failed_initial) != 3200:
        raise RuntimeError(f"unexpected initial failure count: {len(failed_initial)}")
    manifests = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(args.resume_root.rglob("RESUME_SHARD_*_MANIFEST.json"))]
    receipt_paths = sorted(args.resume_root.rglob("RESUME_SHARD_*_RECEIPTS.csv.gz"))
    if len(manifests) != 16 or len(receipt_paths) != 16:
        raise RuntimeError(f"expected 16 resume manifests/receipts, got {len(manifests)}/{len(receipt_paths)}")
    if sorted(row["shard_index"] for row in manifests) != list(range(16)):
        raise RuntimeError("incomplete resume shard index set")
    if any(row["fetch_failures"] != 0 for row in manifests):
        raise RuntimeError("one or more resume shards still contain fetch failures")
    resumed = pd.concat([pd.read_csv(path, compression="gzip", low_memory=False) for path in receipt_paths], ignore_index=True)
    resumed["event_id"] = resumed["event_id"].astype(str)
    failed_ids = set(failed_initial["event_id"].astype(str))
    if set(resumed["event_id"]) != failed_ids or resumed["event_id"].duplicated().any():
        raise RuntimeError("resume union does not equal initial failed event set")
    combined = pd.concat([pass_initial, resumed], ignore_index=True, sort=False).sort_values("event_id", kind="stable")
    if combined["event_id"].astype(str).duplicated().any() or len(combined) != len(initial):
        raise RuntimeError("combined receipt cardinality mismatch")
    if not combined["parse_status"].isin(["PASS", "NO_VALID_DIRECTIONAL_PRODUCT"]).all():
        raise RuntimeError("combined receipts contain unresolved failures")

    selected = pd.read_csv(args.network_root / "SELECTED_EVENT_IDS_AND_SPLITS.csv", low_memory=False)
    selected["event_id"] = selected["event_id"].astype(str)
    combined["event_id"] = combined["event_id"].astype(str)
    if set(combined["event_id"]) != set(selected["event_id"]):
        raise RuntimeError("combined event IDs differ from prelocked selection")
    joined = selected.merge(combined, on="event_id", how="left", validate="one_to_one")

    raw_root = args.out / "raw_details"
    raw_root.mkdir(parents=True, exist_ok=True)
    extract_archive(args.initial_root / "COMCAT_DETAIL_BODIES.tar.gz", raw_root)
    for archive in sorted(args.resume_root.rglob("RESUME_SHARD_*_BODIES.tar.gz")):
        extract_archive(archive, raw_root)
    expected_body_ids = set(combined.loc[combined["parse_status"].eq("PASS"), "event_id"])
    body_ids = {path.stem for path in raw_root.rglob("*.geojson")}
    if body_ids != expected_body_ids:
        raise RuntimeError(f"exact body set mismatch: missing={len(expected_body_ids-body_ids)} extra={len(body_ids-expected_body_ids)}")

    receipt_path = args.out / "COMCAT_DETAIL_RECEIPTS.csv.gz"
    combined.to_csv(receipt_path, index=False, compression="gzip")
    mechanism_path = args.out / "SELECTED_DIRECTIONAL_MECHANISMS.csv.gz"
    joined.to_csv(mechanism_path, index=False, compression="gzip")
    archive_path = args.out / "COMCAT_DETAIL_BODIES.tar.gz"
    deterministic_tar_gz(raw_root, archive_path)
    cohort_rows = []
    for region, group in joined.groupby("region", sort=True):
        test = group[group["split"].eq("TEST")]
        cohort_rows.append({
            "region": region,
            "selected_events": int(len(group)),
            "parsed_directional_events": int(group["parse_status"].eq("PASS").sum()),
            "directional_coverage": float(group["parse_status"].eq("PASS").mean()),
            "sealed_test_events": int(len(test)),
            "sealed_test_parsed_directional_events": int(test["parse_status"].eq("PASS").sum()),
            "sealed_test_directional_coverage": float(test["parse_status"].eq("PASS").mean()) if len(test) else 0.0,
        })
    coverage_gate = all(row["directional_coverage"] >= 0.75 and row["sealed_test_parsed_directional_events"] >= 200 for row in cohort_rows)
    body = {
        "format": "KCH_SEISMIC_DIRECTIONAL_ACQUISITION_V1_1",
        "transport": "INITIAL_SUCCESS_PLUS_16_RATE_LIMIT_RESUME_SHARDS",
        "source_run_id": args.source_run_id,
        "initial_directional_acquisition_id": initial_result["directional_acquisition_id"],
        "initial_http_429_failures": 3200,
        "source_limit": "500_REQUESTS_PER_5_MINUTE_WINDOW",
        "network_lock_id": initial_result["network_lock_id"],
        "network_lock_sha256": initial_result["network_lock_sha256"],
        "selected_event_file_sha256": initial_result["selected_event_file_sha256"],
        "acquired_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "selected_event_count": int(len(combined)),
        "successful_directional_parse_count": int(combined["parse_status"].eq("PASS").sum()),
        "fetch_failures": 0,
        "no_valid_product": int(combined["parse_status"].eq("NO_VALID_DIRECTIONAL_PRODUCT").sum()),
        "cohorts": cohort_rows,
        "resume_shard_manifests": manifests,
        "all_http_acquisitions_complete": True,
        "directional_coverage_gate_pass": coverage_gate,
        "scientific_model_execution_performed": False,
        "raw_body_archive": {"path": archive_path.name, "bytes": archive_path.stat().st_size, "sha256": sha256_file(archive_path)},
        "receipt_file": {"path": receipt_path.name, "sha256": sha256_file(receipt_path)},
        "mechanism_file": {"path": mechanism_path.name, "sha256": sha256_file(mechanism_path)},
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
    return 0 if coverage_gate else 3


if __name__ == "__main__":
    raise SystemExit(main())
