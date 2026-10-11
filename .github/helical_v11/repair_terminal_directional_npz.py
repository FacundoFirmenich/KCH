from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--npz", type=Path, required=True)
    parser.add_argument("--materialization-report", type=Path, required=True)
    parser.add_argument("--out-receipt", type=Path, required=True)
    args = parser.parse_args()
    before_sha = sha256_file(args.npz)
    with np.load(args.npz, allow_pickle=True) as archive:
        arrays = {key: archive[key] for key in archive.files}
    object_keys = sorted(key for key, value in arrays.items() if value.dtype == object)
    if object_keys != ["evid"]:
        raise RuntimeError(f"refusing unexpected object-array repair: {object_keys}")
    evid_values = arrays["evid"].tolist()
    if not all(isinstance(value, str) for value in evid_values):
        raise RuntimeError("event identifier object array contains non-string values")
    max_length = max((len(value) for value in evid_values), default=1)
    arrays["evid"] = np.asarray(evid_values, dtype=f"U{max_length}")
    temporary = args.npz.with_suffix(".repacked.npz")
    np.savez_compressed(temporary, **arrays)
    temporary.replace(args.npz)
    with np.load(args.npz, allow_pickle=False) as check:
        if check["evid"].dtype.kind != "U":
            raise RuntimeError("post-repair event identifier dtype is not Unicode")
        if check["evid"].tolist() != evid_values:
            raise RuntimeError("post-repair event identifiers changed")
    after_sha = sha256_file(args.npz)
    receipt = {
        "format": "KCH_TERMINAL_EVENT_ID_DTYPE_REPAIR_V1_1",
        "before_sha256": before_sha,
        "after_sha256": after_sha,
        "object_keys_before": object_keys,
        "event_count": len(evid_values),
        "event_identifier_dtype_after": f"U{max_length}",
        "event_identifiers_changed": False,
        "scientific_values_changed": False,
        "model_changed": False,
        "thresholds_changed": False,
        "authority_ceiling": "NONE",
    }
    receipt["receipt_id"] = "s11dtype:" + hashlib.sha256(canonical(receipt)).hexdigest()
    args.out_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = json.loads(args.materialization_report.read_text(encoding="utf-8"))
    report["event_id_dtype_repair_receipt_id"] = receipt["receipt_id"]
    report["directional_npz"]["sha256"] = after_sha
    report["materialization_id_before_dtype_repair"] = report.get("materialization_id")
    report.pop("materialization_id", None)
    report["materialization_id"] = "s11mat:" + hashlib.sha256(canonical(report)).hexdigest()
    args.materialization_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
