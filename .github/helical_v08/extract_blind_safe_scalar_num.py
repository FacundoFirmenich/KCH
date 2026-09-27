from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import pickletools
from pathlib import Path
from typing import Any, Mapping

import numpy as np

ALLOWED = (
    "num", "nc_sc", "ev_bl", "year", "month", "day", "hour", "minute", "second",
    "time_utc", "evid", "lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "npol", "prob",
)
EVENT_FIELDS = tuple(name for name in ALLOWED if name != "num")
SEALED = (
    "strike", "dip", "rake", "strike_orig", "dip_orig", "rake_orig",
    "ftype", "p_azi", "p_dip", "t_azi", "t_dip",
)
STRING_FIELDS = {"nc_sc", "ev_bl", "time_utc", "evid"}
INTEGER_FIELDS = {"num", "year", "month", "day", "hour", "minute", "npol"}
FLOAT_FIELDS = {"second", "lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "prob"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if hasattr(value, "to_dict"):
        candidate = value.to_dict()
        if isinstance(candidate, Mapping):
            return candidate
    raise TypeError(type(value).__name__)


def safe_array(name: str, value: Any) -> np.ndarray:
    raw = np.asarray(value)
    if raw.ndim == 0:
        raw = raw.reshape(1)
    if raw.ndim != 1:
        raw = raw.reshape(-1)
    if name in STRING_FIELDS:
        return np.asarray([str(item) for item in raw], dtype=np.str_)
    if name in INTEGER_FIELDS:
        return np.asarray(raw, dtype=np.int64)
    if name in FLOAT_FIELDS:
        return np.asarray(raw, dtype=np.float64)
    raise KeyError(name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    observed = sha256(args.input)
    if observed != args.expected_sha256:
        raise SystemExit(f"SHA-256 mismatch: {observed}")
    payload = args.input.read_bytes()
    opcode_counts: dict[str, int] = {}
    globals_seen: list[str] = []
    for opcode, arg, _pos in pickletools.genops(payload):
        opcode_counts[opcode.name] = opcode_counts.get(opcode.name, 0) + 1
        if opcode.name in {"GLOBAL", "STACK_GLOBAL"}:
            globals_seen.append(str(arg))
    with args.input.open("rb") as f:
        root = mapping(pickle.load(f))
    missing = [name for name in ALLOWED if name not in root]
    if missing:
        raise SystemExit(f"missing allow-list fields: {missing}")
    arrays = {name: safe_array(name, root[name]) for name in ALLOWED}
    event_lengths = {name: int(len(arrays[name])) for name in EVENT_FIELDS}
    if len(set(event_lengths.values())) != 1:
        raise SystemExit(f"event-field length mismatch: {event_lengths}")
    event_count = next(iter(event_lengths.values()))
    num = arrays["num"]
    if len(num) == 1:
        declared_event_count = int(num[0])
        if declared_event_count != event_count:
            raise SystemExit(
                f"declared event count mismatch: num={declared_event_count}, event_fields={event_count}"
            )
        num_semantics = "DECLARED_EVENT_COUNT_SCALAR"
    elif len(num) == event_count:
        declared_event_count = event_count
        num_semantics = "EVENT_VECTOR"
    else:
        raise SystemExit(
            f"unsupported num cardinality: num_length={len(num)}, event_count={event_count}"
        )
    object_fields = [name for name, value in arrays.items() if value.dtype.hasobject]
    if object_fields:
        raise SystemExit(f"object dtype forbidden: {object_fields}")
    output = args.output_dir / "blind_columns.npz"
    np.savez_compressed(output, **arrays)
    with np.load(output, allow_pickle=False) as check:
        if sorted(check.files) != sorted(ALLOWED):
            raise SystemExit(f"NPZ field mismatch: {check.files}")
        if any(check[name].dtype.hasobject for name in check.files):
            raise SystemExit("object dtype survived serialization")
        check_event_lengths = {name: int(len(check[name])) for name in EVENT_FIELDS}
        if len(set(check_event_lengths.values())) != 1:
            raise SystemExit(f"serialized event-field mismatch: {check_event_lengths}")
        if int(len(check["evid"])) != event_count:
            raise SystemExit("serialized event count changed")
    receipt = {
        "format": "KCH_HELICAL_V0_8_ISOLATED_PICKLE_EXTRACTION_RECEIPT_SAFE_SUCCESSOR_V2",
        "source_bytes": len(payload),
        "source_sha256": observed,
        "output_bytes": output.stat().st_size,
        "output_sha256": sha256(output),
        "event_count": event_count,
        "declared_event_count": declared_event_count,
        "num_semantics": num_semantics,
        "field_lengths": {name: int(len(value)) for name, value in arrays.items()},
        "fields_emitted": list(ALLOWED),
        "field_dtypes": {name: str(value.dtype) for name, value in arrays.items()},
        "sealed_fields_emitted": [],
        "sealed_fields": list(SEALED),
        "angle_fields_accessed_for_selection": False,
        "object_dtype_emitted": False,
        "pickle_opcode_counts": dict(sorted(opcode_counts.items())),
        "pickle_globals_seen": sorted(set(globals_seen)),
        "schema_successor_scope": "NUM_DECLARED_COUNT_SCALAR_CARDINALITY_ONLY",
        "scientific_values_changed": False,
        "authority_ceiling": "NONE",
    }
    receipt_bytes = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    receipt["receipt_id"] = "h8extract:" + hashlib.sha256(receipt_bytes).hexdigest()
    (args.output_dir / "EXTRACTION_RECEIPT_V0_8.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
