from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np

from common_v09 import content_id, sha256_file, write_json_atomic

ALLOWED = {
    "num", "nc_sc", "ev_bl", "year", "month", "day", "hour", "minute", "second",
    "time_utc", "evid", "lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "npol", "prob",
}
REQUIRED = ALLOWED - {"num"}
SEALED = {
    "strike", "dip", "rake", "strike_orig", "dip_orig", "rake_orig",
    "ftype", "p_azi", "p_dip", "t_azi", "t_dip",
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--npz", required=True, type=Path)
    parser.add_argument("--extraction-receipt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    receipt = json.loads(args.extraction_receipt.read_text(encoding="utf-8"))
    if receipt.get("format") != "KCH_HELICAL_V0_9_STREAMING_HARDENED_PICKLE_EXTRACTION":
        raise SystemExit("unexpected extraction receipt format")
    observed_sha = sha256_file(args.npz)
    if receipt.get("output_sha256") != observed_sha:
        raise SystemExit("NPZ/extraction receipt SHA-256 mismatch")
    if receipt.get("sealed_fields_emitted") != [] or receipt.get("angle_fields_accessed_for_selection") is not False:
        raise SystemExit("blind barrier violation in extraction receipt")

    arrays: dict[str, Any] = {}
    with np.load(args.npz, allow_pickle=False) as loaded:
        fields = set(loaded.files)
        if not REQUIRED.issubset(fields) or not fields.issubset(ALLOWED):
            raise SystemExit(f"safe NPZ field contract violation: {sorted(fields)}")
        if fields & SEALED:
            raise SystemExit("sealed field present")
        for name in sorted(fields):
            value = loaded[name]
            if value.dtype.kind == "O" or value.dtype.hasobject or value.ndim != 1:
                raise SystemExit(f"unsafe array: {name} {value.dtype} {value.shape}")
            arrays[name] = {
                "dtype": value.dtype.str,
                "shape": list(value.shape),
                "nbytes": int(value.nbytes),
            }
    lengths = {name: meta["shape"][0] for name, meta in arrays.items()}
    if len(set(lengths.values())) != 1:
        raise SystemExit(f"event-vector length mismatch: {lengths}")
    event_count = next(iter(lengths.values()))
    if event_count != receipt.get("event_count"):
        raise SystemExit("event count differs from extraction receipt")

    body = {
        "format": "KCH_HELICAL_V0_9_SAFE_NPZ_VERIFICATION",
        "status": "PASS",
        "npz_sha256": observed_sha,
        "npz_bytes": args.npz.stat().st_size,
        "event_count": event_count,
        "fields": sorted(arrays),
        "arrays": arrays,
        "allow_pickle_false": True,
        "sealed_fields_present": [],
        "authority_ceiling": "NONE",
    }
    body["receipt_id"] = content_id("h9npz", body)
    write_json_atomic(args.output, body)
    print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
