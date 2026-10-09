from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickle
import pickletools
from pathlib import Path
from typing import Any, Mapping

import numpy as np

FIELDS = (
    "nc_sc", "ev_bl", "year", "month", "day", "hour", "minute", "second",
    "time_utc", "evid", "lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "npol", "prob",
)
STRING_FIELDS = {"nc_sc", "ev_bl", "time_utc", "evid"}
INTEGER_FIELDS = {"year", "month", "day", "hour", "minute", "npol"}
FLOAT_FIELDS = {"second", "lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "prob"}
SEALED_FIELDS = {
    "strike", "dip", "rake", "strike_orig", "dip_orig", "rake_orig",
    "ftype", "p_azi", "p_dip", "t_azi", "t_dip",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "to_dict"):
        candidate = value.to_dict()
        if isinstance(candidate, Mapping):
            return candidate
    raise TypeError(f"unsupported pickle root: {type(value).__name__}")


def vector(name: str, value: Any) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim == 0:
        array = array.reshape(1)
    if array.ndim != 1:
        array = array.reshape(-1)
    if name in STRING_FIELDS:
        return np.asarray([str(item) for item in array], dtype=np.str_)
    if name in INTEGER_FIELDS:
        result = np.asarray(array, dtype=np.int64)
    elif name in FLOAT_FIELDS:
        result = np.asarray(array, dtype=np.float64)
    else:
        raise KeyError(name)
    if not np.all(np.isfinite(result)):
        raise ValueError(f"{name}: non-finite values")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pickle", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    observed = sha256(args.pickle)
    if observed != args.expected_sha256:
        raise SystemExit(f"source hash mismatch: {observed}")

    opcode_count = 0
    with args.pickle.open("rb") as handle:
        for _ in pickletools.genops(handle):
            opcode_count += 1
    with args.pickle.open("rb") as handle:
        root = mapping(pickle.load(handle))

    missing = sorted(set(FIELDS) - set(root))
    if missing:
        raise SystemExit(f"missing blind fields: {missing}")
    arrays = {name: vector(name, root[name]) for name in FIELDS}
    lengths = {name: len(value) for name, value in arrays.items()}
    if len(set(lengths.values())) != 1:
        raise SystemExit(f"blind field-length mismatch: {lengths}")
    if set(root) & SEALED_FIELDS and set(arrays) & SEALED_FIELDS:
        raise SystemExit("sealed field crossed blind output firewall")
    if any(value.dtype.hasobject or value.dtype.kind == "O" for value in arrays.values()):
        raise SystemExit("object dtype forbidden")

    output = args.output_dir / "blind_columns.npz"
    temporary = args.output_dir / "blind_columns.tmp.npz"
    np.savez_compressed(temporary, **arrays)
    os.replace(temporary, output)
    with np.load(output, allow_pickle=False) as check:
        if set(check.files) != set(FIELDS):
            raise SystemExit("blind NPZ schema drift")
        if any(check[name].dtype.hasobject or check[name].dtype.kind == "O" for name in check.files):
            raise SystemExit("unsafe blind NPZ")

    body = {
        "format": "KCH_HELICAL_V0_11_BLIND_EXTRACTION_RECEIPT",
        "source_sha256": observed,
        "source_bytes": args.pickle.stat().st_size,
        "output_sha256": sha256(output),
        "output_bytes": output.stat().st_size,
        "event_count": next(iter(set(lengths.values()))),
        "fields_emitted": sorted(arrays),
        "sealed_fields_emitted": [],
        "directional_fields_accessed": False,
        "pickle_opcode_count": opcode_count,
        "network_mode": "NONE",
        "authority_ceiling": "FINITE_DIRECTIONAL_PRETEST_ONLY",
        "promotion": "BLOCKED",
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    body["receipt_id"] = "h11blind:" + hashlib.sha256(canonical).hexdigest()
    (args.output_dir / "BLIND_EXTRACTION_RECEIPT_V0_11.json").write_text(
        json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(body, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
