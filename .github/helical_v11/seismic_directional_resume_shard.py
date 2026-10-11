from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("kch_directional_resume_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-script", type=Path, required=True)
    parser.add_argument("--initial-root", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not 0 <= args.shard_index < args.shard_count:
        raise RuntimeError("invalid shard index")
    args.out.mkdir(parents=True, exist_ok=True)
    module = load_module(args.base_script)
    module.CONCURRENCY = 4
    receipts = pd.read_csv(args.initial_root / "COMCAT_DETAIL_RECEIPTS.csv.gz", low_memory=False)
    failed = sorted(receipts.loc[receipts["parse_status"].eq("FETCH_FAILED"), "event_id"].astype(str).tolist())
    shard_ids = [event_id for index, event_id in enumerate(failed) if index % args.shard_count == args.shard_index]
    if len(shard_ids) > 450:
        raise RuntimeError(f"shard exceeds source limit safety ceiling: {len(shard_ids)}")
    raw_root = args.out / "raw_details"
    new_receipts = asyncio.run(module.acquire(shard_ids, raw_root))
    frame = pd.DataFrame(new_receipts).sort_values("event_id", kind="stable")
    if len(frame) != len(shard_ids) or set(frame["event_id"].astype(str)) != set(shard_ids):
        raise RuntimeError("resume receipt/event mismatch")
    receipt_path = args.out / f"RESUME_SHARD_{args.shard_index:02d}_RECEIPTS.csv.gz"
    frame.to_csv(receipt_path, index=False, compression="gzip")
    archive = args.out / f"RESUME_SHARD_{args.shard_index:02d}_BODIES.tar.gz"
    module.deterministic_tar_gz(raw_root, archive)
    manifest = {
        "format": "KCH_SEISMIC_DIRECTIONAL_RATE_LIMIT_RESUME_SHARD_V1_1",
        "initial_directional_acquisition_id": "s11dir:e4da252002474d9bd5c136ba08b0848953b4b76d4f431b0bf1d67d8768422ae9",
        "initial_failed_event_count": len(failed),
        "failure_class": "HTTP_429_500_REQUESTS_PER_5_MINUTES",
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "event_count": len(shard_ids),
        "source_request_safety_ceiling": 450,
        "event_ids_sha256": hashlib.sha256(("\n".join(shard_ids) + "\n").encode("utf-8")).hexdigest(),
        "receipts_sha256": sha256_file(receipt_path),
        "body_archive_sha256": sha256_file(archive),
        "fetch_failures": int(frame["parse_status"].eq("FETCH_FAILED").sum()),
        "no_valid_product": int(frame["parse_status"].eq("NO_VALID_DIRECTIONAL_PRODUCT").sum()),
        "valid_directional_products": int(frame["parse_status"].eq("PASS").sum()),
        "source_substitution": False,
        "authority_ceiling": "NONE",
    }
    manifest_path = args.out / f"RESUME_SHARD_{args.shard_index:02d}_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for path in sorted(raw_root.rglob("*.geojson")):
        path.unlink()
    for directory in sorted((path for path in raw_root.rglob("*") if path.is_dir()), reverse=True):
        directory.rmdir()
    raw_root.rmdir()
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["fetch_failures"] == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
