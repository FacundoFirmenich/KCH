from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
import hashlib
import json
import math
import os
import pickle
import pickletools
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from common_v09 import content_id, fsync_directory, sha256_file, write_json_atomic

FORMAT = "KCH_HELICAL_V0_9_STREAMING_HARDENED_PICKLE_EXTRACTION"
ALLOWED = (
    "num", "nc_sc", "ev_bl", "year", "month", "day", "hour", "minute", "second",
    "time_utc", "evid", "lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "npol", "prob",
)
REQUIRED_EVENT_FIELDS = (
    "nc_sc", "ev_bl", "year", "month", "day", "hour", "minute", "second",
    "time_utc", "evid", "lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "npol", "prob",
)
ANCHOR_FIELDS = ("evid", "lat_reloc", "lon_reloc", "dep_reloc")
SEALED = (
    "strike", "dip", "rake", "strike_orig", "dip_orig", "rake_orig",
    "ftype", "p_azi", "p_dip", "t_azi", "t_dip",
)
TEXT_FIELDS = {"time_utc"}
CATEGORY_FIELDS = {"nc_sc", "ev_bl"}
PROFILE_BASENAME = "BLIND_SCHEMA_PROFILE_V0_10.json"
IDENTIFIER_FIELDS = {"evid"}
INT_FIELDS = {"num", "year", "month", "day", "hour", "minute", "npol"}
FLOAT_FIELDS = {"second", "lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "prob"}


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
        else:
            raise TypeError(f"{name}[{index}]: inadmissible text scalar {type(item).__name__}")
        if "\x00" in text:
            raise ValueError(f"{name}[{index}]: NUL byte is forbidden")
        converted.append(text)
    width = max(1, max((len(item) for item in converted), default=1))
    return np.asarray(converted, dtype=f"<U{width}")


def category_atom(item: Any) -> tuple[str, str]:
    if isinstance(item, np.generic):
        item = item.item()
    if item is None:
        return "null", ""
    if isinstance(item, (str, np.str_)):
        return "text", str(item)
    if isinstance(item, (bytes, np.bytes_)):
        return "text", bytes(item).decode("utf-8", errors="strict")
    if isinstance(item, (bool, np.bool_)):
        return "boolean", "true" if bool(item) else "false"
    if isinstance(item, (int, np.integer)):
        return "numeric", str(int(item))
    if isinstance(item, (float, np.floating)):
        number = float(item)
        if not math.isfinite(number):
            return "nonfinite_numeric", repr(number)
        return "numeric", format(number, ".17g")
    return f"unsupported:{type(item).__module__}.{type(item).__name__}", repr(item)[:200]


def safe_category(value: Any, name: str) -> tuple[np.ndarray, str]:
    array = one_dimensional(value, name)
    kinds: set[str] = set()
    for item in array.tolist():
        kind, _ = category_atom(item)
        if kind != "null":
            kinds.add(kind)
    if not kinds or kinds <= {"text"}:
        return safe_text(value, name), "text"
    if kinds <= {"numeric"}:
        if name == "ev_bl":
            raise ValueError(
                "ev_bl numeric encoding requires an explicit provider-backed earthquake/blast mapping; "
                "schema profile emitted and blind selection remains blocked"
            )
        return safe_float(value, name), "numeric"
    raise TypeError(f"{name}: mixed or unsupported categorical encoding {sorted(kinds)}")


def field_profile(name: str, value: Any) -> dict[str, Any]:
    array = np.asarray(value)
    body: dict[str, Any] = {
        "field": name,
        "container_type": f"{type(value).__module__}.{type(value).__name__}",
        "dtype": str(array.dtype),
        "dtype_kind": array.dtype.kind,
        "has_object": bool(array.dtype.hasobject),
        "shape": list(array.shape),
        "ndim": int(array.ndim),
        "size": int(array.size),
    }
    if array.ndim <= 1 and name in CATEGORY_FIELDS:
        counts: Counter[tuple[str, str]] = Counter(category_atom(item) for item in array.reshape(-1).tolist())
        ordered = sorted(counts.items(), key=lambda pair: (pair[0][0], pair[0][1]))
        body["category_cardinality"] = len(ordered)
        body["category_values_complete"] = len(ordered) <= 64
        body["category_values"] = [
            {"kind": key[0], "value": key[1], "count": int(count)}
            for key, count in ordered[:64]
        ]
    if array.ndim <= 1 and array.dtype.kind in "biufc":
        try:
            numeric = np.asarray(array, dtype=np.float64).reshape(-1)
            finite = np.isfinite(numeric)
            body["finite_count"] = int(np.sum(finite))
            body["nonfinite_count"] = int(np.sum(~finite))
            if np.any(finite):
                body["finite_min"] = float(np.min(numeric[finite]))
                body["finite_max"] = float(np.max(numeric[finite]))
        except Exception as exc:
            body["numeric_profile_error"] = f"{type(exc).__name__}: {exc}"[:500]
    return body


def write_schema_profile(output_dir: Path, root: Mapping[str, Any], source_sha256: str) -> dict[str, Any]:
    profiles = {name: field_profile(name, root[name]) for name in ALLOWED if name in root}
    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_10_BLIND_SCHEMA_PROFILE",
        "source_sha256": source_sha256,
        "allowed_fields_only": True,
        "sealed_field_values_accessed": False,
        "fields_present": sorted(profiles),
        "missing_required_fields": sorted(set(REQUIRED_EVENT_FIELDS) - set(root)),
        "profiles": profiles,
        "authority_ceiling": "NONE",
        "promotion": "BLOCKED",
    }
    body["profile_id"] = content_id("h10schema", body)
    write_json_atomic(output_dir / PROFILE_BASENAME, body)
    return body


def safe_identifier(value: Any, name: str) -> np.ndarray:
    array = one_dimensional(value, name)
    converted: list[str] = []
    for index, item in enumerate(array.tolist()):
        if isinstance(item, (str, np.str_)):
            text = str(item)
        elif isinstance(item, (bytes, np.bytes_)):
            text = bytes(item).decode("utf-8", errors="strict")
        elif isinstance(item, (int, np.integer)) and not isinstance(item, (bool, np.bool_)):
            text = str(int(item))
        elif isinstance(item, (float, np.floating)) and math.isfinite(float(item)) and float(item).is_integer():
            text = str(int(item))
        else:
            raise TypeError(f"{name}[{index}]: inadmissible identifier scalar {type(item).__name__}")
        if not text or "\x00" in text:
            raise ValueError(f"{name}[{index}]: empty/NUL identifier is forbidden")
        converted.append(text)
    width = max(1, max((len(item) for item in converted), default=1))
    return np.asarray(converted, dtype=f"<U{width}")


def safe_int(value: Any, name: str) -> np.ndarray:
    array = one_dimensional(value, name)
    if array.dtype.kind == "O":
        values: list[int] = []
        for index, item in enumerate(array.tolist()):
            if isinstance(item, (bool, np.bool_)):
                raise TypeError(f"{name}[{index}]: booleans are not integer observations")
            if isinstance(item, (int, np.integer)):
                values.append(int(item))
            elif isinstance(item, (float, np.floating)) and math.isfinite(float(item)) and float(item).is_integer():
                values.append(int(item))
            else:
                raise TypeError(f"{name}[{index}]: inadmissible integer scalar {type(item).__name__}")
        return np.asarray(values, dtype="<i8")
    numeric = np.asarray(array, dtype=np.float64)
    if not np.all(np.isfinite(numeric)) or not np.all(numeric == np.floor(numeric)):
        raise ValueError(f"{name}: non-finite or non-integral value")
    return numeric.astype("<i8", copy=False)


def safe_float(value: Any, name: str) -> np.ndarray:
    array = one_dimensional(value, name)
    try:
        numeric = np.asarray(array, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name}: cannot be represented as float64") from exc
    if not np.all(np.isfinite(numeric)):
        raise ValueError(f"{name}: non-finite values are forbidden at the transport boundary")
    return numeric.astype("<f8", copy=False)


def normalize(root: Mapping[str, Any]) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    missing = [name for name in REQUIRED_EVENT_FIELDS if name not in root]
    if missing:
        raise KeyError(f"missing required blind fields: {missing}")
    converted: dict[str, np.ndarray] = {}
    category_modes: dict[str, str] = {}
    for name in ALLOWED:
        if name not in root:
            continue
        if name in TEXT_FIELDS:
            converted[name] = safe_text(root[name], name)
        elif name in CATEGORY_FIELDS:
            converted[name], category_modes[name] = safe_category(root[name], name)
        elif name in IDENTIFIER_FIELDS:
            converted[name] = safe_identifier(root[name], name)
        elif name in INT_FIELDS:
            converted[name] = safe_int(root[name], name)
        elif name in FLOAT_FIELDS:
            converted[name] = safe_float(root[name], name)
        else:
            raise AssertionError(name)

    anchor_lengths = {name: int(converted[name].shape[0]) for name in ANCHOR_FIELDS}
    if len(set(anchor_lengths.values())) != 1:
        raise ValueError(f"event-anchor length mismatch: {anchor_lengths}")
    event_count = next(iter(anchor_lengths.values()))
    if event_count <= 0:
        raise ValueError("empty event catalog")

    scalar_metadata: dict[str, Any] = {}
    arrays: dict[str, np.ndarray] = {}
    for name, value in converted.items():
        length = int(value.shape[0])
        if length == event_count:
            arrays[name] = value
        elif name == "num" and length == 1:
            scalar_metadata["num"] = int(value[0])
            if scalar_metadata["num"] != event_count:
                raise ValueError(f"catalog-level num={scalar_metadata['num']} differs from event_count={event_count}")
        else:
            raise ValueError(f"{name}: length {length} differs from event_count {event_count}")

    if not set(REQUIRED_EVENT_FIELDS).issubset(arrays):
        raise ValueError("required event vectors were not all emitted")
    for name, value in arrays.items():
        if value.dtype.kind == "O" or value.dtype.hasobject or value.ndim != 1:
            raise TypeError(f"{name}: unsafe array survived normalization: {value.dtype} {value.shape}")
    return arrays, {
        "event_count": event_count,
        "catalog_scalar_fields": scalar_metadata,
        "category_modes": category_modes,
    }


def array_receipt(array: np.ndarray) -> dict[str, Any]:
    contiguous = np.ascontiguousarray(array)
    return {
        "dtype": contiguous.dtype.str,
        "shape": list(contiguous.shape),
        "nbytes": int(contiguous.nbytes),
        "data_sha256": hashlib.sha256(contiguous.tobytes(order="C")).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Only deserialization point for the exact mechanism pickle; run inside the shipped networkless namespace")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    expected = args.expected_sha256.lower()
    if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
        raise SystemExit("expected SHA-256 must be 64 lowercase hexadecimal characters")
    observed = sha256_file(args.input)
    if observed != expected:
        raise SystemExit(f"SHA-256 mismatch: {observed}")

    opcode_counts: dict[str, int] = {}
    with args.input.open("rb") as handle:
        for opcode, _arg, _pos in pickletools.genops(handle):
            opcode_counts[opcode.name] = opcode_counts.get(opcode.name, 0) + 1

    with args.input.open("rb") as handle:
        root = mapping(pickle.load(handle))
    schema_profile = write_schema_profile(args.output_dir, root, observed)
    arrays, normalization = normalize(root)

    output = args.output_dir / "blind_columns.npz"
    tmp = args.output_dir / ".blind_columns.npz.tmp"
    with tmp.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, output)
    fsync_directory(args.output_dir)

    with np.load(output, allow_pickle=False) as checked:
        observed_fields = tuple(checked.files)
        if set(observed_fields) != set(arrays) or len(observed_fields) != len(arrays):
            raise RuntimeError(f"safe NPZ field mismatch: {observed_fields}")
        for name in observed_fields:
            value = checked[name]
            if value.dtype.kind == "O" or value.dtype.hasobject or value.ndim != 1:
                raise RuntimeError(f"unsafe output array: {name} {value.dtype} {value.shape}")

    field_receipts = {name: array_receipt(arrays[name]) for name in sorted(arrays)}
    body = {
        "format": FORMAT,
        "source_bytes": args.input.stat().st_size,
        "source_sha256": observed,
        "source_materialized_whole_in_python_bytes": False,
        "opcode_scan_streaming": True,
        "output_bytes": output.stat().st_size,
        "output_sha256": sha256_file(output),
        "event_count": normalization["event_count"],
        "catalog_scalar_fields": normalization["catalog_scalar_fields"],
        "category_modes": normalization["category_modes"],
        "schema_profile_id": schema_profile["profile_id"],
        "schema_profile_basename": PROFILE_BASENAME,
        "fields_emitted": sorted(arrays),
        "field_receipts": field_receipts,
        "sealed_fields_emitted": [],
        "sealed_fields": list(SEALED),
        "angle_fields_accessed_for_selection": False,
        "pickle_opcode_counts": dict(sorted(opcode_counts.items())),
        "safe_npz_allow_pickle_false_verified": True,
        "object_dtype_emitted": False,
        "authority_ceiling": "NONE",
        "scientific_execution_performed": False,
    }
    body["receipt_id"] = content_id("h9extract", body)
    write_json_atomic(args.output_dir / "EXTRACTION_RECEIPT_V0_9.json", body)
    print(json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
