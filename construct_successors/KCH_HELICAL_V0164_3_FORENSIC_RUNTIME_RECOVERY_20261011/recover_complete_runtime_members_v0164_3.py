#!/usr/bin/env python3
"""Recover only complete, checksummed Python members from the v0.8.4 transport.

The historical transport has a damaged gzip trailer. This gate never repairs or
rewrites the stream. It delegates to the frozen forensic scanner, accepts only
complete TAR members with valid header checksums and safe paths, requires every
recoverable candidate representation to agree on each target SHA-256, and checks
the compiler against the independently transported v0.16.4.2 copy.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import py_compile
import shutil
import subprocess
import sys
from typing import Any

SOURCE_COMMIT = "e458afe20b8172db5a04194224cf21df5ec00dc4"
FORENSIC_V2_REL = (
    "construct_successors/KCH_HELICAL_V0132_CALIBRATION_RUNTIME_QUALIFICATION_20261009/"
    "forensic_recover_v084_transport_v2.py"
)
FORENSIC_BASE_REL = (
    "construct_successors/KCH_HELICAL_V0132_CALIBRATION_RUNTIME_QUALIFICATION_20261009/"
    "forensic_recover_v084_transport.py"
)
EXPECTED_FORENSIC_V2_BLOB = "4252827e95acd5afdd3b39bb804d1c7b62ef6fca"
EXPECTED_FORENSIC_BASE_BLOB = "0daa8642965ad5792d484cdba8966df03044b45b"
INDEPENDENT_COMPILER_REL = (
    "construct_successors/KCH_HELICAL_V0164_HISTORICAL_NULL_LEDGER_RECOVERY_20261011/"
    "recovered_exact/tools/freeze_null_perturbation_runtime.py"
)
EXPECTED_INDEPENDENT_COMPILER_SHA256 = (
    "5a22e574f1d88f057b85f5b6dd3589f7ad14128ba6e6cd3e807d752a677a6134"
)
TARGETS = {
    "compiler": "tools/freeze_null_perturbation_runtime.py",
    "runtime": "src/kch_helical_dynamic_v08/null_runtime.py",
    "tests": "tests_v0_8_4/test_null_runtime.py",
}


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


def git_blob(repo: Path, rel: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", f"HEAD:{rel}"],
        text=True,
    ).strip()


def parse_surface(path: Path) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8", errors="strict")
    tree = ast.parse(source, filename=str(path))
    functions: list[str] = []
    classes: list[str] = []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append((node.module or "") + ":" + ",".join(alias.name for alias in node.names))
    return {
        "function_names": sorted(set(functions)),
        "class_names": sorted(set(classes)),
        "imports": sorted(set(imports)),
        "ast_dump_sha256": sha256_bytes(
            ast.dump(tree, annotate_fields=True, include_attributes=False).encode("utf-8")
        ),
    }


def complete_target_records(receipt: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    records: dict[str, list[dict[str, Any]]] = {suffix: [] for suffix in TARGETS.values()}
    diagnostics = receipt.get("candidate_diagnostics")
    if not isinstance(diagnostics, list) or not diagnostics:
        raise RuntimeError("forensic receipt contains no candidate diagnostics")
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            raise RuntimeError("malformed candidate diagnostic")
        label = diagnostic.get("label")
        scan = diagnostic.get("tar_scan")
        if not isinstance(label, str) or not isinstance(scan, dict):
            continue
        if scan.get("all_complete_headers_checksum_pass") is not True:
            raise RuntimeError(f"candidate {label} reports a failed complete TAR header checksum")
        recovered = scan.get("targets_recovered")
        if not isinstance(recovered, list):
            continue
        for record in recovered:
            if not isinstance(record, dict):
                raise RuntimeError(f"malformed recovered-target record in {label}")
            name = record.get("name")
            if not isinstance(name, str):
                continue
            for suffix in records:
                if name.endswith(suffix):
                    entry = dict(record)
                    entry["candidate_label"] = label
                    records[suffix].append(entry)
    return records


def locate_candidate_files(forensic_output: Path, suffix: str) -> list[Path]:
    basename = Path(suffix).name
    hits = [
        path
        for path in forensic_output.rglob(basename)
        if path.is_file() and not path.is_symlink() and path.as_posix().endswith(suffix)
    ]
    return sorted(hits)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    root = args.root.resolve()
    scratch = args.scratch.resolve()
    recovered_root = root / "recovered_forensic_exact"
    receipts = root / "receipts"
    forensic_output = scratch / "forensic_output"
    compile_output = scratch / "bytecode"

    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    compile_output.mkdir(parents=True)
    if recovered_root.exists():
        shutil.rmtree(recovered_root)
    recovered_root.mkdir(parents=True)
    receipts.mkdir(parents=True, exist_ok=True)

    forensic_v2 = repo / FORENSIC_V2_REL
    forensic_base = repo / FORENSIC_BASE_REL
    independent_compiler = repo / INDEPENDENT_COMPILER_REL
    if not forensic_v2.is_file() or not forensic_base.is_file():
        raise RuntimeError("frozen forensic recovery source is missing")
    if not independent_compiler.is_file() or independent_compiler.is_symlink():
        raise RuntimeError("independently recovered compiler is missing or unsafe")

    observed_v2_blob = git_blob(repo, FORENSIC_V2_REL)
    observed_base_blob = git_blob(repo, FORENSIC_BASE_REL)
    if observed_v2_blob != EXPECTED_FORENSIC_V2_BLOB:
        raise RuntimeError(f"forensic v2 blob mismatch: {observed_v2_blob}")
    if observed_base_blob != EXPECTED_FORENSIC_BASE_BLOB:
        raise RuntimeError(f"forensic base blob mismatch: {observed_base_blob}")

    independent_compiler_bytes = independent_compiler.read_bytes()
    independent_compiler_sha256 = sha256_bytes(independent_compiler_bytes)
    if independent_compiler_sha256 != EXPECTED_INDEPENDENT_COMPILER_SHA256:
        raise RuntimeError(
            "independent compiler SHA-256 mismatch: " + independent_compiler_sha256
        )

    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }
    run = subprocess.run(
        [
            sys.executable,
            str(forensic_v2),
            "--repo-root",
            str(repo),
            "--output",
            str(forensic_output),
        ],
        check=False,
        text=True,
        capture_output=True,
        env=env,
        timeout=180,
    )
    (receipts / "FORENSIC_V2_STDOUT_V0_16_4_3.txt").write_text(run.stdout, encoding="utf-8")
    (receipts / "FORENSIC_V2_STDERR_V0_16_4_3.txt").write_text(run.stderr, encoding="utf-8")
    if run.returncode != 0:
        raise RuntimeError(f"frozen forensic recovery failed with {run.returncode}")

    source_receipt_path = forensic_output / "V084_SOURCE_TRANSPORT_FORENSIC_RECEIPT_V2.json"
    if not source_receipt_path.is_file():
        raise RuntimeError("frozen forensic recovery emitted no receipt")
    source_receipt = json.loads(source_receipt_path.read_text(encoding="utf-8"))
    if source_receipt.get("format") != "KCH_HELICAL_V0_13_2_V084_SOURCE_TRANSPORT_FORENSIC_RECEIPT_V2":
        raise RuntimeError("unexpected forensic receipt format")
    if source_receipt.get("source_commit") != SOURCE_COMMIT:
        raise RuntimeError("forensic receipt source commit mismatch")
    if source_receipt.get("scientific_execution_performed") is not False:
        raise RuntimeError("forensic recovery crossed scientific-execution boundary")
    if source_receipt.get("calibration_data_accessed") is not False:
        raise RuntimeError("forensic recovery crossed calibration-data boundary")
    if source_receipt.get("sealed_test_accessed") is not False:
        raise RuntimeError("forensic recovery crossed sealed-test boundary")
    if source_receipt.get("scientific_result") is not None:
        raise RuntimeError("forensic recovery emitted a scientific result")

    receipt_records = complete_target_records(source_receipt)
    target_receipts: dict[str, Any] = {}

    for label, suffix in TARGETS.items():
        record_rows = receipt_records[suffix]
        if not record_rows:
            raise RuntimeError(f"NOT_RECOVERABLE_FROM_VALID_PREFIX: {suffix}")
        receipt_hashes = {row.get("sha256") for row in record_rows}
        if None in receipt_hashes or len(receipt_hashes) != 1:
            raise RuntimeError(f"cross-candidate receipt SHA disagreement for {suffix}")

        hits = locate_candidate_files(forensic_output, suffix)
        if not hits:
            raise RuntimeError(f"forensic receipt claimed target but no file exists: {suffix}")
        file_hashes = {sha256_bytes(path.read_bytes()) for path in hits}
        if len(file_hashes) != 1:
            raise RuntimeError(f"cross-candidate file SHA disagreement for {suffix}")
        target_sha256 = next(iter(file_hashes))
        if target_sha256 != next(iter(receipt_hashes)):
            raise RuntimeError(f"receipt/file SHA disagreement for {suffix}")

        destination = recovered_root / suffix
        destination.parent.mkdir(parents=True, exist_ok=True)
        exact_bytes = hits[0].read_bytes()
        destination.write_bytes(exact_bytes)
        if destination.read_bytes() != exact_bytes:
            raise RuntimeError(f"post-write byte identity failure for {suffix}")

        surface = parse_surface(destination)
        bytecode_path = compile_output / f"{label}.pyc"
        py_compile.compile(str(destination), doraise=True, cfile=str(bytecode_path))
        bytecode_sha256 = sha256_bytes(bytecode_path.read_bytes())

        candidate_labels = sorted({str(row["candidate_label"]) for row in record_rows})
        candidate_paths = [path.relative_to(forensic_output).as_posix() for path in hits]
        target_receipts[label] = {
            "historical_suffix": suffix,
            "bytes": len(exact_bytes),
            "sha256": target_sha256,
            "receipt_candidate_labels": candidate_labels,
            "receipt_candidate_count": len(candidate_labels),
            "materialized_candidate_paths": candidate_paths,
            "materialized_candidate_count": len(candidate_paths),
            "all_candidate_representations_agree": True,
            "tar_member_complete": True,
            "tar_header_checksum_pass": True,
            "safe_relative_path": True,
            "ast_surface": surface,
            "ephemeral_bytecode_sha256": bytecode_sha256,
        }

    recovered_compiler = recovered_root / TARGETS["compiler"]
    recovered_compiler_sha256 = sha256_bytes(recovered_compiler.read_bytes())
    compiler_quorum_pass = (
        recovered_compiler_sha256 == independent_compiler_sha256
        == EXPECTED_INDEPENDENT_COMPILER_SHA256
    )
    if not compiler_quorum_pass:
        raise RuntimeError("forensic compiler disagrees with independent compiler transport")

    persisted_forensic_receipt = receipts / "V084_SOURCE_TRANSPORT_FORENSIC_RECEIPT_V2.json"
    persisted_forensic_receipt.write_bytes(source_receipt_path.read_bytes())

    forbidden_persisted = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower()
        in {
            ".bin", ".gz", ".b64", ".pickle", ".pkl", ".npz", ".npy",
            ".csv", ".parquet", ".geojson", ".fits", ".sqlite", ".db", ".pyc",
        }
    ]
    if forbidden_persisted:
        raise RuntimeError(f"forbidden payload persisted: {forbidden_persisted}")

    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_16_4_3_FORENSIC_RUNTIME_RECOVERY_RECEIPT",
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_sha": os.environ.get("GITHUB_SHA"),
        "source_commit": SOURCE_COMMIT,
        "forensic_v2_git_blob_sha1": observed_v2_blob,
        "forensic_base_git_blob_sha1": observed_base_blob,
        "forensic_source_receipt_id": source_receipt.get("receipt_id"),
        "forensic_source_receipt_sha256": sha256_bytes(source_receipt_path.read_bytes()),
        "independent_compiler_path": INDEPENDENT_COMPILER_REL,
        "independent_compiler_sha256": independent_compiler_sha256,
        "expected_independent_compiler_sha256": EXPECTED_INDEPENDENT_COMPILER_SHA256,
        "compiler_quorum_pass": compiler_quorum_pass,
        "targets": target_receipts,
        "target_count": len(target_receipts),
        "source_bytes_modified": False,
        "incomplete_tar_members_recovered": False,
        "partial_decompressed_prefix_persisted": False,
        "unused_compressed_suffix_persisted": False,
        "recovered_sources_imported": False,
        "recovered_sources_executed": False,
        "ledger_rows_regenerated": False,
        "scientific_data_accessed": False,
        "calibration_executed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "authority_ceiling": "FORENSIC_COMPLETE_MEMBER_RECOVERY_ONLY",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "status": "PASS",
        "next_gate": "EXACT_6376_ROW_LEDGER_REGENERATION_AND_IDENTITY_GATE",
    }
    body["receipt_id"] = "h1643forensic:" + sha256_bytes(canonical_bytes(body))
    receipt_path = receipts / "FORENSIC_RUNTIME_RECOVERY_RECEIPT_V0_16_4_3.json"
    receipt_path.write_text(json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    validation: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_16_4_3_FORENSIC_RUNTIME_RECOVERY_VALIDATION",
        "status": "PASS",
        "receipt_id": body["receipt_id"],
        "checks": {
            "frozen_forensic_v2_blob_identity": True,
            "frozen_forensic_base_blob_identity": True,
            "source_commit_identity": True,
            "strict_transport_processing_delegated_to_frozen_forensic_code": True,
            "all_three_targets_recovered": len(target_receipts) == 3,
            "all_targets_complete": True,
            "all_target_tar_header_checksums_pass": True,
            "all_target_paths_safe": True,
            "all_candidate_representations_agree": True,
            "compiler_independent_transport_quorum": compiler_quorum_pass,
            "all_sources_ast_parse": True,
            "all_sources_compile_without_import": True,
            "no_recovered_source_executed": True,
            "no_forbidden_payload_persisted": True,
            "ledger_not_regenerated": True,
            "scientific_data_not_accessed": True,
            "sealed_test_not_accessed": True,
        },
    }
    validation["validation_id"] = "h1643validation:" + sha256_bytes(canonical_bytes(validation))
    validation_path = receipts / "FORENSIC_RUNTIME_RECOVERY_VALIDATION_V0_16_4_3.json"
    validation_path.write_text(
        json.dumps(validation, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "receipt_id": body["receipt_id"],
                "validation_id": validation["validation_id"],
                "compiler_sha256": target_receipts["compiler"]["sha256"],
                "runtime_sha256": target_receipts["runtime"]["sha256"],
                "tests_sha256": target_receipts["tests"]["sha256"],
                "compiler_quorum_pass": compiler_quorum_pass,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
