#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

ORIGINAL_SHA256 = "f55856ef2b062eb4fb9f8cd079d302ed973cd6090f8eefb773fef6b3c0f83265"
PATCHED_SHA256 = "f1425bc8d3d9df2d0cc6343dc4bd09785b0eaa81b6ac7770ad59a1e49c14f68a"

OLD = '''    match = re.search(r"Ran\\s+(\\d+)\\s+tests", test_text)\n    assertion(checks, "unittest_count_parse", match is not None, test_text[-1000:])\n    test_count = int(match.group(1)) if match else 0\n    assertion(checks, "unittest_minimum_44", test_count >= 44, test_count)\n    assertion(checks, "unittest_ok", re.search(r"\\nOK\\s*$", test_text) is not None, test_text[-300:])\n'''

NEW = '''    match = re.search(r"Ran\\s+(\\d+)\\s+tests", test_text)\n    assertion(\n        checks,\n        "unittest_count_parse",\n        match is not None,\n        {"matched": match is not None},\n    )\n    test_count = int(match.group(1)) if match else 0\n    assertion(checks, "unittest_minimum_44", test_count >= 44, test_count)\n    unittest_ok = re.search(r"\\nOK\\s*$", test_text) is not None\n    assertion(\n        checks,\n        "unittest_ok",\n        unittest_ok,\n        {"matched": unittest_ok},\n    )\n'''


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    target = args.target.resolve()
    receipt_path = args.receipt.resolve()
    original = target.read_bytes()
    observed_original = sha256(original)
    if observed_original != ORIGINAL_SHA256:
        raise RuntimeError(
            f"original freeze compiler SHA-256 mismatch: {observed_original}"
        )

    text = original.decode("utf-8", errors="strict")
    count = text.count(OLD)
    if count != 1:
        raise RuntimeError(f"authorized source block occurs {count} times")

    patched_text = text.replace(OLD, NEW, 1)
    patched = patched_text.encode("utf-8")
    observed_patched = sha256(patched)
    if observed_patched != PATCHED_SHA256:
        raise RuntimeError(
            f"patched freeze compiler SHA-256 mismatch: {observed_patched}"
        )

    temporary = target.with_name(target.name + ".v0173.tmp")
    temporary.write_bytes(patched)
    os.replace(temporary, target)
    if target.read_bytes() != patched:
        raise RuntimeError("post-patch byte identity failure")

    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_17_3_DETERMINISTIC_FREEZE_PATCH_RECEIPT",
        "target": target.name,
        "original_bytes": len(original),
        "original_sha256": observed_original,
        "patched_bytes": len(patched),
        "patched_sha256": observed_patched,
        "replacement_count": count,
        "runtime_module_changed": False,
        "job_schedule_changed": False,
        "seed_derivation_changed": False,
        "null_operator_semantics_changed": False,
        "scientific_thresholds_changed": False,
        "scientific_data_accessed": False,
        "calibration_executed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "status": "PASS",
    }
    body["receipt_id"] = "h173patch:" + sha256(canonical(body))
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(body, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"receipt_id": body["receipt_id"], "patched_sha256": observed_patched}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
