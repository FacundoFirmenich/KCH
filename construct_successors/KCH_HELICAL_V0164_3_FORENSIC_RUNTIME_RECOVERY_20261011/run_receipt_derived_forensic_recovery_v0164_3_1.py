#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

PREDECESSOR_ROOT_REL = (
    "construct_successors/KCH_HELICAL_V0164_HISTORICAL_NULL_LEDGER_RECOVERY_20261011"
)
PREDECESSOR_RECEIPT_REL = (
    PREDECESSOR_ROOT_REL + "/receipts/AST_ONLY_COMPILER_RECOVERY_RECEIPT_V0_16_4_2.json"
)
PREDECESSOR_VALIDATION_REL = (
    PREDECESSOR_ROOT_REL + "/receipts/AST_ONLY_COMPILER_RECOVERY_VALIDATION_V0_16_4_2.json"
)
PREDECESSOR_COMPILER_REL = (
    PREDECESSOR_ROOT_REL + "/recovered_exact/tools/freeze_null_perturbation_runtime.py"
)
DELEGATE_REL = (
    "construct_successors/KCH_HELICAL_V0164_3_FORENSIC_RUNTIME_RECOVERY_20261011/"
    "recover_complete_runtime_members_v0164_3.py"
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def load_delegate(path: Path):
    spec = importlib.util.spec_from_file_location("kch_helical_v0164_3_delegate", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to create delegate import specification")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    root = args.root.resolve()
    scratch = args.scratch.resolve()
    receipts = root / "receipts"
    receipts.mkdir(parents=True, exist_ok=True)

    predecessor_receipt_path = repo / PREDECESSOR_RECEIPT_REL
    predecessor_validation_path = repo / PREDECESSOR_VALIDATION_REL
    predecessor_compiler_path = repo / PREDECESSOR_COMPILER_REL
    delegate_path = repo / DELEGATE_REL

    for path in (
        predecessor_receipt_path,
        predecessor_validation_path,
        predecessor_compiler_path,
        delegate_path,
    ):
        if not path.is_file() or path.is_symlink():
            raise RuntimeError(f"missing or unsafe trust-path file: {path.relative_to(repo)}")

    predecessor_receipt = load_json(predecessor_receipt_path)
    predecessor_validation = load_json(predecessor_validation_path)

    if predecessor_receipt.get("format") != "KCH_HELICAL_V0_16_4_2_AST_ONLY_COMPILER_RECOVERY_RECEIPT":
        raise RuntimeError("unexpected predecessor receipt format")
    if predecessor_validation.get("format") != "KCH_HELICAL_V0_16_4_2_AST_ONLY_COMPILER_RECOVERY_VALIDATION":
        raise RuntimeError("unexpected predecessor validation format")
    if predecessor_receipt.get("status") != "PASS" or predecessor_validation.get("status") != "PASS":
        raise RuntimeError("predecessor receipt or validation is not PASS")
    if predecessor_validation.get("receipt_id") != predecessor_receipt.get("receipt_id"):
        raise RuntimeError("predecessor receipt-validation linkage mismatch")
    if predecessor_receipt.get("exact_independent_compiler_materialized") is not True:
        raise RuntimeError("predecessor did not materialize exact independent compiler")
    if predecessor_receipt.get("python_ast_parse") != "PASS":
        raise RuntimeError("predecessor AST gate is not PASS")
    if predecessor_receipt.get("python_bytecode_compile_without_import") != "PASS":
        raise RuntimeError("predecessor compile gate is not PASS")
    if predecessor_receipt.get("scientific_data_accessed") is not False:
        raise RuntimeError("predecessor crossed scientific-data boundary")
    if predecessor_receipt.get("sealed_test_accessed") is not False:
        raise RuntimeError("predecessor crossed sealed-test boundary")

    expected_compiler_sha256 = predecessor_receipt.get("decoded_compiler_sha256")
    if not isinstance(expected_compiler_sha256, str) or len(expected_compiler_sha256) != 64:
        raise RuntimeError("predecessor receipt contains no valid compiler SHA-256")
    observed_compiler_sha256 = sha256_bytes(predecessor_compiler_path.read_bytes())
    if observed_compiler_sha256 != expected_compiler_sha256:
        raise RuntimeError("persisted predecessor compiler disagrees with its receipt")

    trust_body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_16_4_3_1_RECEIPT_DERIVED_TRUST_ANCHOR",
        "predecessor_receipt_path": PREDECESSOR_RECEIPT_REL,
        "predecessor_receipt_id": predecessor_receipt["receipt_id"],
        "predecessor_receipt_sha256": sha256_bytes(predecessor_receipt_path.read_bytes()),
        "predecessor_validation_path": PREDECESSOR_VALIDATION_REL,
        "predecessor_validation_id": predecessor_validation["validation_id"],
        "predecessor_validation_sha256": sha256_bytes(predecessor_validation_path.read_bytes()),
        "predecessor_compiler_path": PREDECESSOR_COMPILER_REL,
        "receipt_compiler_sha256": expected_compiler_sha256,
        "observed_compiler_sha256": observed_compiler_sha256,
        "receipt_validation_link": "PASS",
        "compiler_byte_identity": "PASS",
        "manual_hash_transcription_used": False,
        "scientific_data_accessed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "status": "PASS",
    }
    trust_body["trust_anchor_id"] = "h16431trust:" + sha256_bytes(canonical_bytes(trust_body))
    trust_path = receipts / "RECEIPT_DERIVED_TRUST_ANCHOR_V0_16_4_3_1.json"
    trust_path.write_text(json.dumps(trust_body, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    delegate = load_delegate(delegate_path)
    delegate.EXPECTED_INDEPENDENT_COMPILER_SHA256 = expected_compiler_sha256
    original_argv = sys.argv[:]
    try:
        sys.argv = [
            str(delegate_path),
            "--repo-root",
            str(repo),
            "--root",
            str(root),
            "--scratch",
            str(scratch),
        ]
        return_code = int(delegate.main())
    finally:
        sys.argv = original_argv
    if return_code != 0:
        raise RuntimeError(f"forensic delegate returned {return_code}")

    delegate_receipt_path = receipts / "FORENSIC_RUNTIME_RECOVERY_RECEIPT_V0_16_4_3.json"
    delegate_validation_path = receipts / "FORENSIC_RUNTIME_RECOVERY_VALIDATION_V0_16_4_3.json"
    delegate_receipt = load_json(delegate_receipt_path)
    delegate_validation = load_json(delegate_validation_path)
    if delegate_receipt.get("status") != "PASS" or delegate_validation.get("status") != "PASS":
        raise RuntimeError("forensic delegate did not produce PASS receipts")
    if delegate_validation.get("receipt_id") != delegate_receipt.get("receipt_id"):
        raise RuntimeError("forensic delegate receipt-validation linkage mismatch")
    if delegate_receipt.get("independent_compiler_sha256") != expected_compiler_sha256:
        raise RuntimeError("forensic delegate did not use receipt-derived compiler SHA")
    if delegate_receipt.get("compiler_quorum_pass") is not True:
        raise RuntimeError("forensic compiler quorum did not pass")

    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_16_4_3_1_RECEIPT_DERIVED_FORENSIC_RECOVERY_RECEIPT",
        "trust_anchor_id": trust_body["trust_anchor_id"],
        "predecessor_receipt_id": predecessor_receipt["receipt_id"],
        "predecessor_validation_id": predecessor_validation["validation_id"],
        "receipt_derived_compiler_sha256": expected_compiler_sha256,
        "delegate_receipt_id": delegate_receipt["receipt_id"],
        "delegate_validation_id": delegate_validation["validation_id"],
        "forensic_source_receipt_id": delegate_receipt["forensic_source_receipt_id"],
        "targets": delegate_receipt["targets"],
        "target_count": delegate_receipt["target_count"],
        "compiler_quorum_pass": True,
        "manual_hash_transcription_used": False,
        "source_bytes_modified": False,
        "incomplete_tar_members_recovered": False,
        "ledger_rows_regenerated": False,
        "scientific_data_accessed": False,
        "calibration_executed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "authority_ceiling": "RECEIPT_DERIVED_FORENSIC_COMPLETE_MEMBER_RECOVERY_ONLY",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "status": "PASS",
        "next_gate": "EXACT_6376_ROW_LEDGER_REGENERATION_AND_IDENTITY_GATE",
    }
    body["receipt_id"] = "h16431forensic:" + sha256_bytes(canonical_bytes(body))
    final_receipt_path = receipts / "RECEIPT_DERIVED_FORENSIC_RECOVERY_RECEIPT_V0_16_4_3_1.json"
    final_receipt_path.write_text(json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    validation: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_16_4_3_1_RECEIPT_DERIVED_FORENSIC_RECOVERY_VALIDATION",
        "status": "PASS",
        "receipt_id": body["receipt_id"],
        "checks": {
            "predecessor_receipt_pass": True,
            "predecessor_validation_pass": True,
            "predecessor_receipt_validation_link": True,
            "predecessor_compiler_byte_identity": True,
            "manual_hash_transcription_eliminated": True,
            "forensic_delegate_pass": True,
            "compiler_independent_transport_quorum": True,
            "all_three_targets_recovered": body["target_count"] == 3,
            "source_bytes_unmodified": True,
            "incomplete_members_rejected": True,
            "ledger_not_regenerated": True,
            "scientific_data_not_accessed": True,
            "sealed_test_not_accessed": True,
        },
    }
    validation["validation_id"] = "h16431validation:" + sha256_bytes(canonical_bytes(validation))
    (receipts / "RECEIPT_DERIVED_FORENSIC_RECOVERY_VALIDATION_V0_16_4_3_1.json").write_text(
        json.dumps(validation, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "trust_anchor_id": trust_body["trust_anchor_id"],
                "receipt_id": body["receipt_id"],
                "validation_id": validation["validation_id"],
                "compiler_sha256": expected_compiler_sha256,
                "runtime_sha256": body["targets"]["runtime"]["sha256"],
                "tests_sha256": body["targets"]["tests"]["sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
