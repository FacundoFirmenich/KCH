#!/usr/bin/env python3
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
FORENSIC_TARGETS = {
    "runtime": "src/kch_helical_dynamic_v08/null_runtime.py",
    "tests": "tests_v0_8_4/test_null_runtime.py",
}
COMPILER_SUFFIX = "tools/freeze_null_perturbation_runtime.py"


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


def candidate_records(
    forensic_receipt: dict[str, Any], suffix: str
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    diagnostics = forensic_receipt.get("candidate_diagnostics")
    if not isinstance(diagnostics, list) or not diagnostics:
        raise RuntimeError("forensic receipt contains no candidate diagnostics")
    for diagnostic in diagnostics:
        if not isinstance(diagnostic, dict):
            continue
        label = diagnostic.get("label")
        scan = diagnostic.get("tar_scan")
        if not isinstance(label, str) or not isinstance(scan, dict):
            continue
        members = scan.get("members")
        recovered = scan.get("targets_recovered")
        if not isinstance(members, list) or not isinstance(recovered, list):
            continue
        member_by_name = {
            item.get("name"): item
            for item in members
            if isinstance(item, dict) and isinstance(item.get("name"), str)
        }
        for target in recovered:
            if not isinstance(target, dict):
                continue
            name = target.get("name")
            if not isinstance(name, str) or not name.endswith(suffix):
                continue
            member = member_by_name.get(name)
            if not isinstance(member, dict):
                raise RuntimeError(f"forensic target has no TAR member record: {name}")
            if member.get("complete") is not True:
                raise RuntimeError(f"forensic target is incomplete: {name}")
            if member.get("checksum_pass") is not True:
                raise RuntimeError(f"forensic target header checksum failed: {name}")
            if member.get("safe_name") is not True:
                raise RuntimeError(f"forensic target path is unsafe: {name}")
            if member.get("typeflag") not in {"0", "\x00", "7"}:
                raise RuntimeError(f"forensic target is not a regular member: {name}")
            entry = dict(target)
            entry["candidate_label"] = label
            entry["member_offset"] = member.get("offset")
            entry["member_typeflag"] = member.get("typeflag")
            output.append(entry)
    return output


def locate_candidate_files(forensic_output: Path, suffix: str) -> list[Path]:
    basename = Path(suffix).name
    return sorted(
        path
        for path in forensic_output.rglob(basename)
        if path.is_file() and not path.is_symlink() and path.as_posix().endswith(suffix)
    )


def materialize_exact(
    *,
    forensic_output: Path,
    recovered_root: Path,
    label: str,
    suffix: str,
    records: list[dict[str, Any]],
    compile_output: Path,
) -> dict[str, Any]:
    if not records:
        raise RuntimeError(f"NOT_RECOVERABLE_FROM_VALID_PREFIX: {suffix}")
    receipt_hashes = {record.get("sha256") for record in records}
    if None in receipt_hashes or len(receipt_hashes) != 1:
        raise RuntimeError(f"cross-candidate forensic receipt disagreement: {suffix}")

    hits = locate_candidate_files(forensic_output, suffix)
    if not hits:
        raise RuntimeError(f"forensic receipt/file mismatch: {suffix}")
    file_hashes = {sha256_bytes(path.read_bytes()) for path in hits}
    if len(file_hashes) != 1:
        raise RuntimeError(f"cross-candidate file disagreement: {suffix}")
    target_sha256 = next(iter(file_hashes))
    if target_sha256 != next(iter(receipt_hashes)):
        raise RuntimeError(f"receipt/file SHA disagreement: {suffix}")

    data = hits[0].read_bytes()
    destination = recovered_root / suffix
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    if destination.read_bytes() != data:
        raise RuntimeError(f"post-write byte identity failure: {suffix}")

    surface = parse_surface(destination)
    bytecode = compile_output / f"{label}.pyc"
    py_compile.compile(str(destination), doraise=True, cfile=str(bytecode))
    return {
        "recovery_channel": "VALID_COMPLETE_TAR_PREFIX_MEMBER",
        "historical_suffix": suffix,
        "bytes": len(data),
        "sha256": target_sha256,
        "candidate_labels": sorted({str(record["candidate_label"]) for record in records}),
        "candidate_count": len({str(record["candidate_label"]) for record in records}),
        "candidate_materializations": [
            path.relative_to(forensic_output).as_posix() for path in hits
        ],
        "all_candidate_representations_agree": True,
        "tar_member_complete": True,
        "tar_header_checksum_pass": True,
        "safe_relative_path": True,
        "ast_surface": surface,
        "ephemeral_bytecode_sha256": sha256_bytes(bytecode.read_bytes()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    root = args.root.resolve()
    scratch = args.scratch.resolve()
    recovered_root = root / "recovered_separate_channels_exact"
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

    predecessor_receipt_path = repo / PREDECESSOR_RECEIPT_REL
    predecessor_validation_path = repo / PREDECESSOR_VALIDATION_REL
    predecessor_compiler_path = repo / PREDECESSOR_COMPILER_REL
    predecessor_receipt = load_json(predecessor_receipt_path)
    predecessor_validation = load_json(predecessor_validation_path)
    if predecessor_receipt.get("status") != "PASS" or predecessor_validation.get("status") != "PASS":
        raise RuntimeError("independent compiler predecessor is not PASS")
    if predecessor_validation.get("receipt_id") != predecessor_receipt.get("receipt_id"):
        raise RuntimeError("independent compiler receipt-validation linkage mismatch")
    compiler_sha256 = predecessor_receipt.get("decoded_compiler_sha256")
    if not isinstance(compiler_sha256, str) or len(compiler_sha256) != 64:
        raise RuntimeError("invalid receipt-derived compiler SHA-256")
    compiler_bytes = predecessor_compiler_path.read_bytes()
    if sha256_bytes(compiler_bytes) != compiler_sha256:
        raise RuntimeError("independent compiler bytes disagree with predecessor receipt")

    compiler_destination = recovered_root / COMPILER_SUFFIX
    compiler_destination.parent.mkdir(parents=True, exist_ok=True)
    compiler_destination.write_bytes(compiler_bytes)
    compiler_surface = parse_surface(compiler_destination)
    compiler_bytecode = compile_output / "compiler.pyc"
    py_compile.compile(str(compiler_destination), doraise=True, cfile=str(compiler_bytecode))
    compiler_record = {
        "recovery_channel": "INDEPENDENT_GIT_BLOB_TRANSPORT",
        "historical_suffix": COMPILER_SUFFIX,
        "bytes": len(compiler_bytes),
        "sha256": compiler_sha256,
        "predecessor_receipt_id": predecessor_receipt["receipt_id"],
        "predecessor_validation_id": predecessor_validation["validation_id"],
        "ast_surface": compiler_surface,
        "ephemeral_bytecode_sha256": sha256_bytes(compiler_bytecode.read_bytes()),
    }

    forensic_v2 = repo / FORENSIC_V2_REL
    forensic_base = repo / FORENSIC_BASE_REL
    if git_blob(repo, FORENSIC_V2_REL) != EXPECTED_FORENSIC_V2_BLOB:
        raise RuntimeError("frozen forensic v2 blob mismatch")
    if git_blob(repo, FORENSIC_BASE_REL) != EXPECTED_FORENSIC_BASE_BLOB:
        raise RuntimeError("frozen forensic base blob mismatch")

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
    (receipts / "FORENSIC_V2_STDOUT_V0_16_4_3_2.txt").write_text(run.stdout, encoding="utf-8")
    (receipts / "FORENSIC_V2_STDERR_V0_16_4_3_2.txt").write_text(run.stderr, encoding="utf-8")
    if run.returncode != 0:
        raise RuntimeError(f"frozen forensic recovery failed: {run.returncode}")

    forensic_receipt_path = forensic_output / "V084_SOURCE_TRANSPORT_FORENSIC_RECEIPT_V2.json"
    forensic_receipt = load_json(forensic_receipt_path)
    if forensic_receipt.get("source_commit") != SOURCE_COMMIT:
        raise RuntimeError("forensic source commit mismatch")
    if forensic_receipt.get("scientific_execution_performed") is not False:
        raise RuntimeError("forensic scanner crossed scientific-execution boundary")
    if forensic_receipt.get("calibration_data_accessed") is not False:
        raise RuntimeError("forensic scanner crossed calibration-data boundary")
    if forensic_receipt.get("sealed_test_accessed") is not False:
        raise RuntimeError("forensic scanner crossed sealed-test boundary")

    targets: dict[str, Any] = {"compiler": compiler_record}
    for label, suffix in FORENSIC_TARGETS.items():
        targets[label] = materialize_exact(
            forensic_output=forensic_output,
            recovered_root=recovered_root,
            label=label,
            suffix=suffix,
            records=candidate_records(forensic_receipt, suffix),
            compile_output=compile_output,
        )

    (receipts / "V084_SOURCE_TRANSPORT_FORENSIC_RECEIPT_V2.json").write_bytes(
        forensic_receipt_path.read_bytes()
    )

    forbidden = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower()
        in {
            ".bin", ".gz", ".b64", ".pickle", ".pkl", ".npz", ".npy",
            ".csv", ".parquet", ".geojson", ".fits", ".sqlite", ".db", ".pyc",
        }
    ]
    if forbidden:
        raise RuntimeError(f"forbidden payload persisted: {forbidden}")

    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_16_4_3_2_SEPARATE_CHANNEL_RUNTIME_RECOVERY_RECEIPT",
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_sha": os.environ.get("GITHUB_SHA"),
        "source_commit": SOURCE_COMMIT,
        "compiler_channel": "INDEPENDENT_GIT_BLOB_TRANSPORT",
        "runtime_channel": "VALID_COMPLETE_TAR_PREFIX_MEMBER",
        "tests_channel": "VALID_COMPLETE_TAR_PREFIX_MEMBER",
        "forensic_source_receipt_id": forensic_receipt.get("receipt_id"),
        "forensic_source_receipt_sha256": sha256_bytes(forensic_receipt_path.read_bytes()),
        "targets": targets,
        "target_count": len(targets),
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
        "authority_ceiling": "SEPARATE_CHANNEL_EXACT_RUNTIME_RECOVERY_ONLY",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "status": "PASS",
        "next_gate": "EXACT_6376_ROW_LEDGER_REGENERATION_AND_IDENTITY_GATE",
    }
    body["receipt_id"] = "h16432runtime:" + sha256_bytes(canonical_bytes(body))
    receipt_path = receipts / "SEPARATE_CHANNEL_RUNTIME_RECOVERY_RECEIPT_V0_16_4_3_2.json"
    receipt_path.write_text(json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    validation: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_16_4_3_2_SEPARATE_CHANNEL_RUNTIME_RECOVERY_VALIDATION",
        "status": "PASS",
        "receipt_id": body["receipt_id"],
        "checks": {
            "compiler_independent_channel_pass": True,
            "runtime_complete_tar_member_pass": True,
            "tests_complete_tar_member_pass": True,
            "all_three_targets_ast_parse": True,
            "all_three_targets_compile_without_import": True,
            "source_bytes_unmodified": True,
            "incomplete_members_rejected": True,
            "forbidden_payloads_not_persisted": True,
            "ledger_not_regenerated": True,
            "scientific_data_not_accessed": True,
            "sealed_test_not_accessed": True,
        },
    }
    validation["validation_id"] = "h16432validation:" + sha256_bytes(canonical_bytes(validation))
    (receipts / "SEPARATE_CHANNEL_RUNTIME_RECOVERY_VALIDATION_V0_16_4_3_2.json").write_text(
        json.dumps(validation, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )

    print(
        json.dumps(
            {
                "receipt_id": body["receipt_id"],
                "validation_id": validation["validation_id"],
                "compiler_sha256": targets["compiler"]["sha256"],
                "runtime_sha256": targets["runtime"]["sha256"],
                "tests_sha256": targets["tests"]["sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
