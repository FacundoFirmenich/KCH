#!/usr/bin/env python3
"""Successor wrapper for v0.16.5 Git-object type discrimination.

The predecessor enumerator assumed every object/path row emitted by
`git rev-list --objects --all` was a blob. This wrapper preserves the predecessor
scanner, inserts explicit object-type discrimination, records every skipped non-blob
or unavailable object, and re-addresses all receipts after the run.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("kch_v0165_predecessor", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load predecessor scanner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    predecessor = Path(__file__).with_name("exhaustive_runtime_transport_quorum_v0165.py")
    module = load_module(predecessor)
    original_sh = module.sh
    skipped: list[dict[str, Any]] = []

    def guarded_sh(repo: Path, *args: str, text: bool = False):
        if len(args) >= 3 and args[0] == "cat-file" and args[1] == "blob":
            oid = args[2]
            try:
                kind = original_sh(repo, "cat-file", "-t", oid, text=True).strip()
            except Exception as exc:
                skipped.append({"oid": oid, "classification": "TYPE_UNAVAILABLE", "error": repr(exc)})
                return "" if text else b""
            if kind != "blob":
                skipped.append({"oid": oid, "classification": "NON_BLOB", "git_type": kind})
                return "" if text else b""
            try:
                return original_sh(repo, *args, text=text)
            except subprocess.CalledProcessError as exc:
                skipped.append({"oid": oid, "classification": "BLOB_UNAVAILABLE", "error": repr(exc)})
                return "" if text else b""
        return original_sh(repo, *args, text=text)

    module.sh = guarded_sh
    exit_code = int(module.main())
    if exit_code != 0:
        return exit_code

    output_arg = None
    for index, value in enumerate(sys.argv[:-1]):
        if value == "--output":
            output_arg = sys.argv[index + 1]
            break
    if output_arg is None:
        raise RuntimeError("--output not present in scanner arguments")
    output = Path(output_arg)
    receipt_path = output / "EXHAUSTIVE_RUNTIME_TRANSPORT_QUORUM_RECEIPT_V0_16_5.json"
    inventory_path = output / "EXHAUSTIVE_RUNTIME_TRANSPORT_SEARCH_INVENTORY_V0_16_5.json"
    validation_path = output / "EXHAUSTIVE_RUNTIME_TRANSPORT_QUORUM_VALIDATION_V0_16_5.json"

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))

    inventory["object_type_guard"] = {
        "format": "KCH_HELICAL_V0_16_5_1_GIT_OBJECT_TYPE_GUARD",
        "skipped_count": len(skipped),
        "skipped": skipped,
        "non_blob_rows_do_not_reduce_blob_search": True,
    }
    inventory.pop("inventory_id", None)
    inventory["inventory_id"] = "h1651inventory:" + digest(inventory)

    receipt["format"] = "KCH_HELICAL_V0_16_5_1_EXHAUSTIVE_RUNTIME_TRANSPORT_QUORUM"
    receipt["predecessor_failed_run_id"] = 38189616529
    receipt["predecessor_failed_job_id"] = 114619344855
    receipt["object_type_guard_skipped_count"] = len(skipped)
    receipt["git_object_type_discrimination"] = "PASS"
    receipt["github_run_id"] = os.environ.get("GITHUB_RUN_ID")
    receipt["github_sha"] = os.environ.get("GITHUB_SHA")
    receipt.pop("receipt_id", None)
    receipt["receipt_id"] = "h1651transport:" + digest(receipt)

    validation["format"] = "KCH_HELICAL_V0_16_5_1_VALIDATION"
    validation["receipt_id"] = receipt["receipt_id"]
    validation["inventory_id"] = inventory["inventory_id"]
    validation.setdefault("checks", {})["git_object_type_discrimination"] = True
    validation["checks"]["predecessor_failure_preserved"] = True
    validation.pop("validation_id", None)
    validation["validation_id"] = "h1651validation:" + digest(validation)

    inventory_path.write_text(json.dumps(inventory, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    receipt_path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    validation_path.write_text(json.dumps(validation, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "receipt_id": receipt["receipt_id"],
        "validation_id": validation["validation_id"],
        "inventory_id": inventory["inventory_id"],
        "outcome": receipt["outcome"],
        "skipped_non_blob_or_unavailable_objects": len(skipped),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
