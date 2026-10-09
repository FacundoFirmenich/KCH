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

EVENT_FIELDS = (
    "nc_sc", "ev_bl", "year", "month", "day", "hour", "minute", "second",
    "time_utc", "evid", "lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "npol", "prob",
)
DIRECTIONAL_FIELDS = ("strike", "dip", "rake")
OUTPUT_FIELDS = EVENT_FIELDS + DIRECTIONAL_FIELDS
STRING_FIELDS = {"nc_sc", "ev_bl", "time_utc", "evid"}
INTEGER_FIELDS = {"year", "month", "day", "hour", "minute", "npol"}
FLOAT_FIELDS = {
    "second", "lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "prob",
    "strike", "dip", "rake",
}
REMAINING_SEALED_FIELDS = (
    "strike_orig", "dip_orig", "rake_orig", "ftype", "p_azi", "p_dip", "t_azi", "t_dip",
)
INDEX_FIELDS = {
    "global_index", "cohort_code", "fault_assignment", "nearest_km", "second_km",
    "event_time_epoch", "event_id",
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


def typed(name: str, value: Any) -> np.ndarray:
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
    parser.add_argument("--expected-pickle-sha256", required=True)
    parser.add_argument("--selected-indices", required=True, type=Path)
    parser.add_argument("--expected-indices-sha256", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    observed_pickle = sha256(args.pickle)
    observed_indices = sha256(args.selected_indices)
    if observed_pickle != args.expected_pickle_sha256:
        raise SystemExit(f"pickle SHA-256 mismatch: {observed_pickle}")
    if observed_indices != args.expected_indices_sha256:
        raise SystemExit(f"selected-indices SHA-256 mismatch: {observed_indices}")

    with np.load(args.selected_indices, allow_pickle=False) as index_npz:
        selected = {name: index_npz[name] for name in index_npz.files}
    if set(selected) != INDEX_FIELDS:
        raise SystemExit(f"selected-index schema mismatch: {sorted(selected)}")
    global_index = np.asarray(selected["global_index"], dtype=np.int64)
    if len(global_index) == 0 or np.any(global_index < 0) or len(np.unique(global_index)) != len(global_index):
        raise SystemExit("invalid selected global indices")

    opcode_count = 0
    with args.pickle.open("rb") as handle:
        for _ in pickletools.genops(handle):
            opcode_count += 1
    with args.pickle.open("rb") as handle:
        root = mapping(pickle.load(handle))
    missing = sorted(set(OUTPUT_FIELDS) - set(root))
    if missing:
        raise SystemExit(f"missing selected directional fields: {missing}")
    event_count = len(np.asarray(root["evid"]).reshape(-1))
    if int(np.max(global_index)) >= event_count:
        raise SystemExit("selected global index outside catalog")

    arrays: dict[str, np.ndarray] = {}
    for name in OUTPUT_FIELDS:
        source = typed(name, root[name])
        if len(source) != event_count:
            raise SystemExit(f"catalog field-length mismatch for {name}: {len(source)} != {event_count}")
        arrays[name] = source[global_index]
    if not np.array_equal(arrays["evid"].astype(str), np.asarray(selected["event_id"]).astype(str)):
        raise SystemExit("selected event identities do not match catalog indices")

    arrays.update(
        global_index=global_index,
        cohort_code=np.asarray(selected["cohort_code"], dtype=np.int16),
        fault_assignment=np.asarray(selected["fault_assignment"], dtype=np.int64),
        nearest_km=np.asarray(selected["nearest_km"], dtype=np.float64),
        second_km=np.asarray(selected["second_km"], dtype=np.float64),
        event_time_epoch=np.asarray(selected["event_time_epoch"], dtype=np.float64),
    )
    if len({len(value) for value in arrays.values()}) != 1:
        raise SystemExit("selected directional length mismatch")
    if any(value.dtype.hasobject or value.dtype.kind == "O" for value in arrays.values()):
        raise SystemExit("object dtype forbidden")

    strike = arrays["strike"]
    dip = arrays["dip"]
    rake = arrays["rake"]
    finite = np.isfinite(strike) & np.isfinite(dip) & np.isfinite(rake)
    bounded = finite & (strike >= 0.0) & (strike < 360.0) & (dip >= 0.0) & (dip <= 90.0) & (rake >= -180.0) & (rake <= 180.0)

    output = args.output_dir / "selected_directional_columns.npz"
    temporary = args.output_dir / "selected_directional_columns.tmp.npz"
    np.savez_compressed(temporary, **arrays)
    os.replace(temporary, output)
    with np.load(output, allow_pickle=False) as check:
        if set(check.files) != set(arrays):
            raise SystemExit("selected directional serialization drift")
        if any(check[name].dtype.hasobject or check[name].dtype.kind == "O" for name in check.files):
            raise SystemExit("unsafe selected directional artifact")

    counts = {
        str(code): int(np.sum(arrays["cohort_code"] == code))
        for code in sorted(set(int(value) for value in arrays["cohort_code"].tolist()))
    }
    body = {
        "format": "KCH_HELICAL_V0_11_SELECTED_DIRECTIONAL_EXTRACTION_RECEIPT",
        "source_pickle_sha256": observed_pickle,
        "source_pickle_bytes": args.pickle.stat().st_size,
        "selected_indices_sha256": observed_indices,
        "output_sha256": sha256(output),
        "output_bytes": output.stat().st_size,
        "catalog_event_count": event_count,
        "selected_event_count": len(global_index),
        "cohort_counts_by_code": counts,
        "fields_emitted": sorted(arrays),
        "directional_fields_opened": list(DIRECTIONAL_FIELDS),
        "remaining_sealed_fields_not_emitted": list(REMAINING_SEALED_FIELDS),
        "finite_sdr_count": int(np.sum(finite)),
        "physically_bounded_sdr_count": int(np.sum(bounded)),
        "pickle_opcode_count": opcode_count,
        "source_values_changed": False,
        "selection_changed": False,
        "network_mode": "NONE",
        "authority_ceiling": "FINITE_DIRECTIONAL_PRETEST_ONLY",
        "sealed_test_scored": False,
        "scientific_model_fit_performed": False,
        "promotion": "BLOCKED",
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    body["receipt_id"] = "h11unseal:" + hashlib.sha256(canonical).hexdigest()
    (args.output_dir / "SELECTED_DIRECTIONAL_EXTRACTION_RECEIPT_V0_11.json").write_text(
        json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(body, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
