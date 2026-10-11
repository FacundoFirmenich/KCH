from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import importlib.util
import json
import sys
import tarfile
from pathlib import Path

import pandas as pd


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("kch_directional_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-script", type=Path, required=True)
    parser.add_argument("--network-root", type=Path, required=True)
    parser.add_argument("--shard-index", type=int, required=True)
    parser.add_argument("--shard-count", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not 0 <= args.shard_index < args.shard_count:
        raise RuntimeError("invalid shard index")
    args.out.mkdir(parents=True, exist_ok=True)
    module = load_module(args.base_script)
    module.CONCURRENCY = 4
    selected = pd.read_csv(args.network_root / "SELECTED_EVENT_IDS_AND_SPLITS.csv", low_memory=False)
    selected["event_id"] = selected["event_id"].astype(str)
    event_ids = sorted(selected["event_id"].tolist())
    if len(event_ids) != len(set(event_ids)):
        raise RuntimeError("sealed event list is not disjoint")
    shard_ids = [event_id for index, event_id in enumerate(event_ids) if index % args.shard_count == args.shard_index]
    raw_root = args.out / "raw_details"
    receipts = asyncio.run(module.acquire(shard_ids, raw_root))
    frame = pd.DataFrame(receipts).sort_values("event_id", kind="stable")
    if len(frame) != len(shard_ids) or set(frame["event_id"].astype(str)) != set(shard_ids):
        raise RuntimeError("shard receipt/event mismatch")
    frame.to_csv(args.out / f"SHARD_{args.shard_index}_RECEIPTS.csv.gz", index=False, compression="gzip")
    archive = args.out / f"SHARD_{args.shard_index}_BODIES.tar.gz"
    module.deterministic_tar_gz(raw_root, archive)
    manifest = {
        "format": "KCH_SEISMIC_DIRECTIONAL_ACQUISITION_SHARD_V1_1",
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "event_count": len(shard_ids),
        "event_ids_sha256": hashlib.sha256(("\n".join(shard_ids) + "\n").encode()).hexdigest(),
        "receipts_sha256": sha256_file(args.out / f"SHARD_{args.shard_index}_RECEIPTS.csv.gz"),
        "body_archive_sha256": sha256_file(archive),
        "fetch_failures": int(frame["parse_status"].eq("FETCH_FAILED").sum()),
        "no_valid_product": int(frame["parse_status"].eq("NO_VALID_DIRECTIONAL_PRODUCT").sum()),
        "valid_directional_products": int(frame["parse_status"].eq("PASS").sum()),
        "source_substitution": False,
        "authority_ceiling": "NONE",
    }
    (args.out / f"SHARD_{args.shard_index}_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    for path in sorted(raw_root.rglob("*.geojson")):
        path.unlink()
    for directory in sorted((path for path in raw_root.rglob("*") if path.is_dir()), reverse=True):
        directory.rmdir()
    raw_root.rmdir()
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0 if manifest["fetch_failures"] == 0 else 3


if __name__ == "__main__":
    raise SystemExit(main())
