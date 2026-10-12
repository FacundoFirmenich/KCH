#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import py_compile
import shutil
import stat
import subprocess
import sys
import zipfile
from typing import Any

EXPECTED_OUTPUTS = [
    "FREEZE_EXECUTION_RECEIPT_V0_17.json",
    "FULL_NULL_AND_PERTURBATION_RUNTIME_CONTRACT_V0_17.json",
    "NONIDENTITY_PROOF_V0_17.json",
    "NULL_PERTURBATION_JOB_LEDGER_SUMMARY_V0_17.json",
    "NULL_PERTURBATION_JOB_LEDGER_V0_17.jsonl",
    "RUNTIME_FREEZE_RECEIPT_V0_17.json",
    "RUNTIME_SOURCE_MANIFEST_V0_17.json",
    "RUNTIME_VALIDATION_REPORT_V0_17.json",
    "STATUS_V0_17.json",
]
HISTORICAL_H13_LEDGER = "h13nullledger:6abcf3c64273d25a52d75fd423b6b825ee0b1a1b800aaf5d38acf98795179c2a"

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())

def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode("utf-8")

def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"JSON object required: {path}")
    return value

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")

def run(argv: list[str], *, cwd: Path, env: dict[str, str], log: Path) -> None:
    result = subprocess.run(argv, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(result.stdout, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {argv}; log={log}")

def tree(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rows.append({"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    return rows

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, required=True)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    args = ap.parse_args()

    repo = args.repo_root.resolve()
    root = args.root.resolve()
    work = args.work.resolve()
    manifest = args.manifest.resolve()
    receipts = root / "receipts"
    generated = root / "generated"
    replay = work / "generated-replay"
    release = root / "release"
    pycache = work / "pycache"
    home = work / "home"
    tmpdir = work / "tmp"

    for path in (generated, replay, release, work):
        if path.exists():
            shutil.rmtree(path)
    for path in (receipts, generated, replay, release, pycache, home, tmpdir):
        path.mkdir(parents=True, exist_ok=True)

    lease = load_json(root / "AUTHORITY_LEASE_V0_17_3.json")
    contract = load_json(root / "DOUBLE_FREEZE_CANONICAL_IDENTITY_CONTRACT_V0_17_3.json")
    if lease.get("authority_ceiling") != "DETERMINISTIC_FREEZE_DIAGNOSTIC_NORMALIZATION_ONLY":
        raise RuntimeError("invalid v0.17.3 authority ceiling")
    if contract.get("format") != "KCH_HELICAL_V0_17_3_DOUBLE_FREEZE_CANONICAL_IDENTITY_CONTRACT":
        raise RuntimeError("invalid v0.17.3 identity contract")

    materializer = root / "materialize_text_capsule_v0173.py"
    patcher = root / "patch_deterministic_freeze_v0173.py"
    transport_receipt = receipts / "TEXT_CAPSULE_MATERIALIZATION_RECEIPT_V0_17_3.json"
    patch_receipt = receipts / "DETERMINISTIC_FREEZE_PATCH_RECEIPT_V0_17_3.json"

    base_env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(home),
        "TMPDIR": str(tmpdir),
        "PYTHONPATH": str(root / "src"),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
    }

    run([
        sys.executable, str(materializer),
        "--repo-root", str(repo),
        "--manifest", str(manifest),
        "--output", str(root),
        "--receipt", str(transport_receipt),
    ], cwd=repo, env=base_env, log=work / "materialize.log")

    run([
        sys.executable, str(patcher),
        "--target", str(root / "freeze_runtime_v017.py"),
        "--receipt", str(patch_receipt),
    ], cwd=repo, env=base_env, log=work / "patch.log")

    patch = load_json(patch_receipt)
    expected_patch = contract["authorized_source_patch"]
    if patch["original_sha256"] != expected_patch["expected_original_sha256"]:
        raise RuntimeError("original freeze compiler identity mismatch")
    if patch["patched_sha256"] != expected_patch["expected_patched_sha256"]:
        raise RuntimeError("patched freeze compiler identity mismatch")
    if patch["replacement_count"] != expected_patch["replacement_count"]:
        raise RuntimeError("unexpected patch replacement count")

    sources = [
        root / "src/kch_helical_null_v017/__init__.py",
        root / "src/kch_helical_null_v017/runtime.py",
        root / "tests/test_runtime_v017.py",
        root / "freeze_runtime_v017.py",
        materializer,
        patcher,
    ]
    for i, path in enumerate(sources):
        py_compile.compile(str(path), doraise=True, cfile=str(pycache / f"{i}.pyc"))

    test_logs: list[Path] = []
    for tag in ("a", "b"):
        log = work / f"unittest-{tag}.log"
        run([
            sys.executable, "-m", "unittest", "discover",
            "-s", str(root / "tests"), "-v"
        ], cwd=repo, env=base_env, log=log)
        text = log.read_text(encoding="utf-8")
        if "Ran 44 tests" not in text or not text.rstrip().endswith("OK"):
            raise RuntimeError(f"unit-test census/terminal status failed for run {tag}")
        test_logs.append(log)

    freeze = root / "freeze_runtime_v017.py"
    for output, log, tag in (
        (generated, test_logs[0], "a"),
        (replay, test_logs[1], "b"),
    ):
        run([
            sys.executable, str(freeze),
            "--repo-root", str(repo),
            "--root", str(root),
            "--unittest-log", str(log),
            "--output", str(output),
        ], cwd=repo, env=base_env, log=work / f"freeze-{tag}.log")

    tree_a = tree(generated)
    tree_b = tree(replay)
    if tree_a != tree_b:
        a = {row["path"]: row for row in tree_a}
        b = {row["path"]: row for row in tree_b}
        diff = []
        for key in sorted(set(a) | set(b)):
            if a.get(key) != b.get(key):
                diff.append({"path": key, "generated": a.get(key), "replay": b.get(key)})
        write_json(receipts / "DOUBLE_FREEZE_DIVERGENCE_V0_17_3.json", {"divergences": diff})
        raise RuntimeError(f"double-freeze byte identity failed for {len(diff)} members")

    names = [row["path"] for row in tree_a]
    if names != sorted(EXPECTED_OUTPUTS):
        raise RuntimeError(f"unexpected freeze membership: {names}")

    status = load_json(generated / "STATUS_V0_17.json")
    proof = load_json(generated / "NONIDENTITY_PROOF_V0_17.json")
    validation = load_json(generated / "RUNTIME_VALIDATION_REPORT_V0_17.json")
    summary = load_json(generated / "NULL_PERTURBATION_JOB_LEDGER_SUMMARY_V0_17.json")
    freeze_receipt = load_json(generated / "RUNTIME_FREEZE_RECEIPT_V0_17.json")
    ledger_text = (generated / "NULL_PERTURBATION_JOB_LEDGER_V0_17.jsonl").read_text(encoding="utf-8")

    required = contract["required_semantic_identities_preserved"]
    checks = {
        "state": status.get("state") == "SPECIFICATION_DERIVED_NONIDENTICAL_RUNTIME_FROZEN",
        "scheduled_job_count": status.get("scheduled_job_count") == 6376 == summary.get("job_count"),
        "runtime_contract_id": summary.get("runtime_contract_id") == required["runtime_contract_id"],
        "job_ledger_id": summary.get("ledger_id") == required["job_ledger_id"],
        "job_ledger_sha256": sha256_file(generated / "NULL_PERTURBATION_JOB_LEDGER_V0_17.jsonl") == required["job_ledger_sha256"],
        "unique_job_ids": summary.get("job_id_unique_count") == 6376,
        "unique_seeds": summary.get("seed_unique_count") == 6376,
        "validation_all_pass": validation.get("all_pass") is True,
        "validation_unittest_count": int(validation.get("unittest_count", 0)) >= 44,
        "contract_ids_distinct": proof.get("contract_ids_distinct") is True,
        "ledger_ids_distinct": proof.get("ledger_ids_distinct") is True,
        "ledger_bytes_distinct": proof.get("ledger_bytes_distinct") is True,
        "historical_identity_transfer_forbidden": proof.get("historical_hash_reuse") is False,
        "historical_h13_not_in_ledger": HISTORICAL_H13_LEDGER not in ledger_text,
        "test_partition_not_scheduled": '"TEST"' not in ledger_text,
        "calibration_not_executed": status.get("calibration_runtime_qualification_executed") is False,
        "scientific_data_not_accessed": status.get("scientific_data_accessed") is False,
        "sealed_test_not_accessed": status.get("sealed_test_accessed") is False,
        "scientific_result_null": status.get("scientific_result") is None,
        "freeze_promotion_blocked": freeze_receipt.get("promotion") == "BLOCKED",
        "freeze_canonicalization_blocked": freeze_receipt.get("canonicalization") == "BLOCKED",
        "freeze_scientific_result_null": freeze_receipt.get("scientific_result") is None,
    }
    if not all(checks.values()):
        raise RuntimeError("semantic firewall failed: " + repr([key for key, value in checks.items() if not value]))

    tree_hash = sha256_bytes(canonical(tree_a))

    source_manifest = load_json(generated / "RUNTIME_SOURCE_MANIFEST_V0_17.json")
    source_paths = source_manifest.get("source_files") or source_manifest.get("files") or []
    if not source_paths:
        # The generated manifest shape is runtime-owned. Presence and hash are sufficient
        # here because its identity is itself part of the byte-identical freeze.
        source_paths = [{"manifest_sha256": sha256_file(generated / "RUNTIME_SOURCE_MANIFEST_V0_17.json")}]

    boundary_forbidden_suffixes = {
        ".pickle", ".pkl", ".npz", ".npy", ".csv", ".parquet", ".geojson",
        ".fits", ".sqlite", ".db", ".h5", ".hdf5"
    }
    forbidden = [
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in boundary_forbidden_suffixes
    ]
    if forbidden:
        raise RuntimeError(f"scientific/raw payload crossed v0.17.3 boundary: {forbidden}")

    release_files = [
        path for path in root.rglob("*")
        if path.is_file()
        and "release" not in path.relative_to(root).parts
        and "__pycache__" not in path.parts
    ]
    release_rows = [
        {"path": path.relative_to(root).as_posix(), "bytes": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted(release_files)
    ]
    archive = release / "KCH_HELICAL_V0173_DETERMINISTIC_SPEC_DERIVED_RUNTIME.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for row in release_rows:
            info = zipfile.ZipInfo(row["path"], (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            zf.writestr(info, (root / row["path"]).read_bytes())

    with zipfile.ZipFile(archive) as zf:
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f"release CRC failed at {bad}")
        if zf.namelist() != [row["path"] for row in release_rows]:
            raise RuntimeError("release membership/order mismatch")
        for row in release_rows:
            if sha256_bytes(zf.read(row["path"])) != row["sha256"]:
                raise RuntimeError(f"release member hash mismatch: {row['path']}")

    manifest_body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_17_3_RELEASE_MANIFEST",
        "members": release_rows,
        "member_count": len(release_rows),
        "member_tree_sha256": sha256_bytes(canonical(release_rows)),
    }
    manifest_body["manifest_id"] = "h173manifest:" + sha256_bytes(canonical(manifest_body))
    write_json(release / "RELEASE_MANIFEST_V0_17_3.json", manifest_body)

    release_body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_17_3_RELEASE_RECEIPT",
        "archive_name": archive.name,
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": sha256_file(archive),
        "manifest_id": manifest_body["manifest_id"],
        "member_count": len(release_rows),
        "zip_crc": "PASS",
        "member_hash_identity": "PASS",
        "double_freeze_identity": "PASS",
        "freeze_tree_sha256": tree_hash,
        "runtime_contract_id": summary["runtime_contract_id"],
        "job_ledger_id": summary["ledger_id"],
        "job_ledger_sha256": sha256_file(generated / "NULL_PERTURBATION_JOB_LEDGER_V0_17.jsonl"),
        "scheduled_job_count": summary["job_count"],
        "historical_v0_13_identity_transfer": False,
        "scientific_data_included": False,
        "calibration_executed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "status": "PASS",
    }
    release_body["receipt_id"] = "h173release:" + sha256_bytes(canonical(release_body))
    write_json(release / "RELEASE_RECEIPT_V0_17_3.json", release_body)
    (release / (archive.name + ".sha256")).write_text(
        f"{release_body['archive_sha256']}  {archive.name}\n", encoding="utf-8"
    )

    receipt: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_17_3_DETERMINISTIC_FREEZE_RECEIPT",
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_sha": os.environ.get("GITHUB_SHA"),
        "predecessor_diagnostic_report_id": contract["predecessor_diagnostic_report_id"],
        "transport_receipt_id": load_json(transport_receipt)["receipt_id"],
        "patch_receipt_id": patch["receipt_id"],
        "patched_freeze_compiler_sha256": patch["patched_sha256"],
        "unit_test_count_each": 44,
        "unit_test_total_executions": 88,
        "double_freeze_identity": "PASS",
        "freeze_tree_sha256": tree_hash,
        "byte_identical_output_count": len(tree_a),
        "runtime_contract_id": summary["runtime_contract_id"],
        "job_ledger_id": summary["ledger_id"],
        "job_ledger_sha256": sha256_file(generated / "NULL_PERTURBATION_JOB_LEDGER_V0_17.jsonl"),
        "scheduled_job_count": summary["job_count"],
        "historical_v0_13_identity_transfer": False,
        "scientific_data_accessed": False,
        "calibration_runtime_qualification_executed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "release_manifest_id": manifest_body["manifest_id"],
        "release_receipt_id": release_body["receipt_id"],
        "release_archive_sha256": release_body["archive_sha256"],
        "status": "PASS",
        "next_gate": "CALIBRATION_ONLY_FULL_RUNTIME_QUALIFICATION_6376_JOBS_NO_TEST_ACCESS",
    }
    receipt["receipt_id"] = "h173freeze:" + sha256_bytes(canonical(receipt))
    write_json(receipts / "DETERMINISTIC_FREEZE_RECEIPT_V0_17_3.json", receipt)

    validation_body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_17_3_DETERMINISTIC_FREEZE_VALIDATION",
        "status": "PASS",
        "receipt_id": receipt["receipt_id"],
        "checks": checks | {
            "transport_materialization_pass": True,
            "authorized_patch_pass": True,
            "test_run_a_pass": True,
            "test_run_b_pass": True,
            "double_freeze_byte_identity": True,
            "required_nine_outputs_present": True,
            "release_crc_pass": True,
            "release_member_hash_identity": True,
            "scientific_payload_boundary_pass": True,
        },
    }
    validation_body["validation_id"] = "h173validation:" + sha256_bytes(canonical(validation_body))
    write_json(receipts / "DETERMINISTIC_FREEZE_VALIDATION_V0_17_3.json", validation_body)

    print(json.dumps({
        "receipt_id": receipt["receipt_id"],
        "validation_id": validation_body["validation_id"],
        "double_freeze_identity": receipt["double_freeze_identity"],
        "freeze_tree_sha256": tree_hash,
        "runtime_contract_id": receipt["runtime_contract_id"],
        "job_ledger_id": receipt["job_ledger_id"],
        "job_ledger_sha256": receipt["job_ledger_sha256"],
        "scheduled_job_count": receipt["scheduled_job_count"],
        "release_archive_sha256": receipt["release_archive_sha256"],
    }, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
