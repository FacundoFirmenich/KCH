from __future__ import annotations

import argparse
from datetime import date, datetime
import hashlib
import json
import pickle
import pickletools
from pathlib import Path
from typing import Any, Mapping

import numpy as np

FORMAT = "KCH_HELICAL_V0_9_BLIND_BOUNDARY_EXTRACTION"
EVENT_FIELDS = (
    "nc_sc", "ev_bl", "year", "month", "day", "hour", "minute", "second",
    "time_utc", "evid", "lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "npol", "prob",
)
METADATA_FIELDS = ("num",)
ALLOWED = METADATA_FIELDS + EVENT_FIELDS
TEXT_FIELDS = {"nc_sc", "ev_bl", "time_utc", "evid"}
SEALED = (
    "strike", "dip", "rake", "strike_orig", "dip_orig", "rake_orig",
    "ftype", "p_azi", "p_dip", "t_azi", "t_dip",
)
CHUNK = 8 * 1024 * 1024


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "to_dict"):
        candidate = value.to_dict()
        if isinstance(candidate, Mapping):
            return candidate
    raise TypeError(f"root object is not a mapping: {type(value).__name__}")


def one_dimensional(value: Any, name: str) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim == 0:
        array = array.reshape(1)
    if array.ndim != 1:
        raise ValueError(f"{name}: expected one dimension, observed {array.ndim}")
    return array


def safe_text(value: Any, name: str) -> np.ndarray:
    array = one_dimensional(value, name)
    converted: list[str] = []
    for index, item in enumerate(array.tolist()):
        if isinstance(item, (str, np.str_)):
            text = str(item)
        elif isinstance(item, (bytes, np.bytes_)):
            text = bytes(item).decode("utf-8", errors="strict")
        elif isinstance(item, (datetime, date, np.datetime64)):
            text = str(item)
        elif item is None:
            text = ""
        elif isinstance(item, (int, float, np.integer, np.floating)):
            text = str(item)
        else:
            raise TypeError(f"{name}[{index}]: inadmissible text scalar {type(item).__name__}")
        if "\x00" in text:
            raise ValueError(f"{name}[{index}]: NUL byte is forbidden")
        converted.append(text)
    width = max(1, max((len(item) for item in converted), default=1))
    return np.asarray(converted, dtype=f"<U{width}")


def safe_numeric(value: Any, name: str) -> np.ndarray:
    array = one_dimensional(value, name)
    try:
        numeric = np.asarray(array, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name}: cannot be represented as float64") from exc
    return numeric.astype("<f8", copy=False)


def normalize(root: Mapping[str, Any]) -> tuple[dict[str, np.ndarray], int]:
    missing = [name for name in ALLOWED if name not in root]
    if missing:
        raise KeyError(f"missing allow-list fields: {missing}")
    arrays: dict[str, np.ndarray] = {}
    for name in ALLOWED:
        arrays[name] = safe_text(root[name], name) if name in TEXT_FIELDS else safe_numeric(root[name], name)
    event_lengths = {name: int(arrays[name].shape[0]) for name in EVENT_FIELDS}
    if len(set(event_lengths.values())) != 1:
        raise ValueError(f"event-field length mismatch: {event_lengths}")
    event_count = next(iter(event_lengths.values()))
    if arrays["num"].shape[0] not in {1, event_count}:
        raise ValueError(f"num must be scalar metadata or event-length vector; observed {arrays['num'].shape[0]}")
    for name, value in arrays.items():
        if value.dtype.kind == "O" or value.dtype.hasobject or value.ndim != 1:
            raise TypeError(f"{name}: unsafe array survived normalization: {value.dtype} {value.shape}")
    return arrays, event_count


def array_receipt(array: np.ndarray) -> dict[str, Any]:
    contiguous = np.ascontiguousarray(array)
    receipt = {
        "dtype": contiguous.dtype.str,
        "shape": list(contiguous.shape),
        "nbytes": int(contiguous.nbytes),
        "data_sha256": hashlib.sha256(contiguous.tobytes(order="C")).hexdigest(),
    }
    if contiguous.dtype.kind in "fc":
        receipt["nonfinite_count"] = int(np.sum(~np.isfinite(contiguous)))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    expected = args.expected_sha256.lower()
    observed = sha256_file(args.input)
    if observed != expected:
        raise SystemExit(f"source SHA-256 mismatch: {observed}")

    opcode_counts: dict[str, int] = {}
    with args.input.open("rb") as opcode_stream:
        for opcode, _arg, _pos in pickletools.genops(opcode_stream):
            opcode_counts[opcode.name] = opcode_counts.get(opcode.name, 0) + 1

    # The monolithic pickle necessarily materializes all serialized fields inside this destroyed,
    # networkless boundary. Extractor logic indexes only ALLOWED and emits no sealed field.
    with args.input.open("rb") as handle:
        root = mapping(pickle.load(handle))
    arrays, event_count = normalize(root)

    output = args.output_dir / "blind_columns.npz"
    np.savez_compressed(output, **arrays)
    with np.load(output, allow_pickle=False) as checked:
        if set(checked.files) != set(ALLOWED) or len(checked.files) != len(ALLOWED):
            raise RuntimeError(f"safe NPZ field mismatch: {checked.files}")
        for name in ALLOWED:
            value = checked[name]
            if value.dtype.kind == "O" or value.dtype.hasobject or value.ndim != 1:
                raise RuntimeError(f"unsafe output array: {name} {value.dtype} {value.shape}")

    body = {
        "format": FORMAT,
        "source_bytes": args.input.stat().st_size,
        "source_sha256": observed,
        "output_bytes": output.stat().st_size,
        "output_sha256": sha256_file(output),
        "event_count": event_count,
        "fields_emitted": list(ALLOWED),
        "field_receipts": {name: array_receipt(arrays[name]) for name in ALLOWED},
        "sealed_fields_emitted": [],
        "sealed_field_values_read_by_extractor_logic": False,
        "sealed_values_necessarily_materialized_by_monolithic_unpickler_inside_destroyed_boundary": True,
        "angle_fields_accessed_by_outer_selection": False,
        "pickle_opcode_counts": dict(sorted(opcode_counts.items())),
        "safe_npz_allow_pickle_false_verified": True,
        "object_dtype_emitted": False,
        "num_scalar_transport_supported": True,
        "nonfinite_values_imputed": False,
        "authority_ceiling": "NONE",
        "scientific_execution_performed": False,
    }
    body["receipt_id"] = "h9extract:" + hashlib.sha256(canonical(body)).hexdigest()
    receipt = args.output_dir / "EXTRACTION_RECEIPT_V0_9.json"
    receipt.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
