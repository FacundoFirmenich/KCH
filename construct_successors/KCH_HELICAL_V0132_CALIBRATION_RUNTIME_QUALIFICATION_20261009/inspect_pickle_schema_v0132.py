from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import pickle
import pickletools
import re
from typing import Any, Mapping

import numpy as np

AUTHORITY_CEILING = "EXACT_SOURCE_SCHEMA_INSPECTION_ONLY"
EXPECTED_SOURCE_BYTES = 528_904_117
EXPECTED_SOURCE_SHA256 = "cc13d9e4335bb20579d224c52ea2936d3251719c381c830c23b2abfd0a1eedeb"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_id(prefix: str, body: dict[str, Any]) -> str:
    material = json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return f"{prefix}:{hashlib.sha256(material).hexdigest()}"


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def location_roles(name: str) -> list[str]:
    normalized = normalize_name(name)
    roles: list[str] = []
    horizontal_tokens = (
        "horizontalerror", "horizontaluncert", "horizontalunc", "horizerror", "horizuncert",
        "locationerror", "locationuncert", "locerror", "locuncert", "epicentralerror",
        "epicentraluncert", "herr", "erh", "seh", "laterror", "lonerror", "xyerror",
    )
    vertical_tokens = (
        "deptherror", "depthuncert", "depthunc", "verticalerror", "verticaluncert",
        "verticalunc", "zerror", "zuncert", "derr", "erz", "sez",
    )
    covariance_tokens = ("covariance", "covar", "locationcov", "loccov", "errorellipse", "ellipse")
    if any(token in normalized for token in horizontal_tokens):
        roles.append("HORIZONTAL_LOCATION_UNCERTAINTY_CANDIDATE")
    if any(token in normalized for token in vertical_tokens):
        roles.append("DEPTH_OR_VERTICAL_UNCERTAINTY_CANDIDATE")
    if any(token in normalized for token in covariance_tokens):
        roles.append("LOCATION_COVARIANCE_OR_ELLIPSE_CANDIDATE")
    if ("error" in normalized or "uncert" in normalized or "sigma" in normalized) and any(
        token in normalized for token in ("lat", "lon", "depth", "dep", "loc", "horiz", "vert", "xyz")
    ):
        roles.append("GENERIC_LOCATION_UNCERTAINTY_CANDIDATE")
    return sorted(set(roles))


def type_name(value: Any) -> str:
    cls = type(value)
    return f"{cls.__module__}.{cls.__qualname__}"


def safe_length(value: Any) -> int | None:
    try:
        return int(len(value))
    except Exception:
        return None


def mapping_root(value: Any) -> Mapping[Any, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"pickle root must be Mapping; observed={type_name(value)}")
    return value


def inspect_field(name: str, value: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "name": name,
        "normalized_name": normalize_name(name),
        "python_type": type_name(value),
        "python_length": safe_length(value),
        "location_uncertainty_roles": location_roles(name),
    }
    try:
        array = np.asarray(value)
        entry.update(
            {
                "numpy_convertible": True,
                "numpy_shape": [int(item) for item in array.shape],
                "numpy_ndim": int(array.ndim),
                "numpy_size": int(array.size),
                "numpy_dtype": str(array.dtype),
                "numpy_dtype_kind": str(array.dtype.kind),
                "numpy_itemsize": int(array.dtype.itemsize),
                "numpy_object_dtype": bool(array.dtype.hasobject or array.dtype.kind == "O"),
                "numpy_nbytes": int(array.nbytes),
            }
        )
    except Exception as exc:
        entry.update(
            {
                "numpy_convertible": False,
                "numpy_conversion_error_type": type(exc).__name__,
            }
        )
    return entry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pickle", required=True, type=Path)
    parser.add_argument("--expected-pickle-sha256", required=True)
    parser.add_argument("--authority", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    authority = json.loads(args.authority.read_text(encoding="utf-8"))
    if authority.get("authority_ceiling") != AUTHORITY_CEILING:
        raise SystemExit("authority ceiling mismatch")
    if authority.get("single_use") is not True:
        raise SystemExit("authority is not single-use")
    if "EXPORT_ANY_ROW_VALUE" not in authority.get("prohibitions", []):
        raise SystemExit("authority lacks row-value export prohibition")

    observed_sha = sha256_file(args.pickle)
    observed_bytes = args.pickle.stat().st_size
    if args.expected_pickle_sha256 != EXPECTED_SOURCE_SHA256:
        raise SystemExit("workflow propagated noncanonical expected source SHA-256")
    if observed_sha != EXPECTED_SOURCE_SHA256:
        raise SystemExit(f"source SHA-256 mismatch: {observed_sha}")
    if observed_bytes != EXPECTED_SOURCE_BYTES:
        raise SystemExit(f"source byte-count mismatch: {observed_bytes}")

    opcode_count = 0
    protocol_versions: set[int] = set()
    with args.pickle.open("rb") as handle:
        for opcode, argument, _ in pickletools.genops(handle):
            opcode_count += 1
            if opcode.name == "PROTO" and isinstance(argument, int):
                protocol_versions.add(argument)

    with args.pickle.open("rb") as handle:
        root = mapping_root(pickle.load(handle))

    key_type_counts = Counter(type_name(key) for key in root.keys())
    non_string_keys = [type_name(key) for key in root.keys() if not isinstance(key, str)]
    if non_string_keys:
        raise SystemExit(f"non-string schema keys forbidden: {Counter(non_string_keys)}")

    fields = [inspect_field(str(name), root[name]) for name in sorted(root)]
    location_candidates = [
        {
            "name": field["name"],
            "roles": field["location_uncertainty_roles"],
            "numpy_shape": field.get("numpy_shape"),
            "numpy_dtype": field.get("numpy_dtype"),
            "python_length": field.get("python_length"),
        }
        for field in fields
        if field["location_uncertainty_roles"]
    ]

    horizontal = [item["name"] for item in location_candidates if "HORIZONTAL_LOCATION_UNCERTAINTY_CANDIDATE" in item["roles"]]
    vertical = [item["name"] for item in location_candidates if "DEPTH_OR_VERTICAL_UNCERTAINTY_CANDIDATE" in item["roles"]]
    covariance = [item["name"] for item in location_candidates if "LOCATION_COVARIANCE_OR_ELLIPSE_CANDIDATE" in item["roles"]]

    one_dimensional_lengths = Counter(
        int(field["numpy_shape"][0])
        for field in fields
        if field.get("numpy_convertible") is True and field.get("numpy_ndim") == 1 and field.get("numpy_shape")
    )
    dominant_lengths = [
        {"length": int(length), "field_count": int(count)}
        for length, count in sorted(one_dimensional_lengths.items(), key=lambda item: (-item[1], item[0]))
    ]

    if horizontal and vertical:
        location_status = "HORIZONTAL_AND_VERTICAL_SCHEMA_CANDIDATES_PRESENT"
    elif horizontal or vertical or covariance or location_candidates:
        location_status = "PARTIAL_OR_AMBIGUOUS_LOCATION_UNCERTAINTY_SCHEMA"
    else:
        location_status = "NO_LOCATION_UNCERTAINTY_SCHEMA_CANDIDATES"

    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_13_2_EXACT_SOURCE_SCHEMA_INSPECTION_RESULT",
        "authority_lease_id": authority.get("lease_id"),
        "authority_ceiling": AUTHORITY_CEILING,
        "source_pickle_sha256": observed_sha,
        "source_pickle_bytes": observed_bytes,
        "pickle_opcode_count": opcode_count,
        "pickle_protocol_versions": sorted(protocol_versions),
        "root_python_type": type_name(root),
        "root_field_count": len(root),
        "root_key_type_counts": dict(sorted(key_type_counts.items())),
        "fields": fields,
        "dominant_one_dimensional_field_lengths": dominant_lengths,
        "location_uncertainty_candidates": location_candidates,
        "horizontal_location_uncertainty_candidates": horizontal,
        "depth_or_vertical_uncertainty_candidates": vertical,
        "location_covariance_or_ellipse_candidates": covariance,
        "location_uncertainty_schema_status": location_status,
        "row_values_exported": False,
        "event_identifiers_exported": False,
        "cohort_partition_constructed": False,
        "train_calibration_test_partition_constructed": False,
        "sealed_test_scored": False,
        "model_fit_performed": False,
        "null_or_perturbation_execution_performed": False,
        "scientific_result": None,
        "network_mode": "NONE",
        "root_filesystem": "READ_ONLY",
        "capabilities": "ALL_DROPPED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    body["result_id"] = canonical_id("h132schema", body)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    temporary.write_text(json.dumps(body, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(temporary, args.output)
    print(json.dumps({"result_id": body["result_id"], "location_uncertainty_schema_status": location_status}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
