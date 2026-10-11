#!/usr/bin/env python3
"""Build and independently verify the v0.16.3.1 code-only source custody.

This is an implementation successor to failed GitHub Actions run 38164023152.
It performs no scientific acquisition, deserialization, calibration, test access,
scoring, interpretation, promotion, or canonization.
"""
from __future__ import annotations

from pathlib import Path
import ast
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import zipfile
from typing import Any


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


def git_blob_sha(path: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", f"HEAD:{path}"],
        check=True,
        text=True,
        capture_output=True,
    )
    return result.stdout.strip()


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        raise SystemExit("usage: build_source_custody_v0163_1.py STAGE_DIR ROOT_DIR")

    stage = Path(argv[1]).resolve()
    root = Path(argv[2]).resolve()
    receipts = root / "receipts"
    repo = Path.cwd().resolve()
    contract_path = root / "SOURCE_CUSTODY_CONTRACT_V0_16_3.json"
    lease_path = root / "AUTHORITY_LEASE_V0_16_3_1.json"
    readme_path = root / "README.md"
    builder_path = root / "build_source_custody_v0163_1.py"

    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    lease = json.loads(lease_path.read_text(encoding="utf-8"))
    if contract.get("format") != "KCH_HELICAL_V0_16_3_SOURCE_CUSTODY_CONTRACT":
        raise SystemExit("invalid source-custody contract format")
    if lease.get("format") != "KCH_HELICAL_V0_16_3_1_AUTHORITY_LEASE":
        raise SystemExit("invalid implementation-repair lease format")
    if lease.get("authority_ceiling") != "CODE_ONLY_SOURCE_CUSTODY_REPAIR":
        raise SystemExit("invalid authority ceiling")

    roots = [Path(value) for value in contract["source_roots"]]
    required_blobs = dict(contract["required_blobs"])
    admitted_suffixes = set(contract["admitted_suffixes"])
    forbidden_suffixes = set(contract["forbidden_suffixes"])
    excluded_components = set(contract["excluded_path_components"])
    minimum_per_root = int(contract["minimum_admitted_files_per_root"])

    if not roots or not required_blobs:
        raise SystemExit("contract contains no source roots or required blobs")
    if admitted_suffixes & forbidden_suffixes:
        raise SystemExit("admitted and forbidden suffix sets overlap")

    required_verification: list[dict[str, Any]] = []
    for rel, expected_blob in sorted(required_blobs.items()):
        path = repo / rel
        if not path.is_file() or path.is_symlink():
            raise SystemExit(f"missing or unsafe required file: {rel}")
        actual_blob = git_blob_sha(rel)
        if actual_blob != expected_blob:
            raise SystemExit(
                f"required blob mismatch for {rel}: expected {expected_blob}, got {actual_blob}"
            )
        required_verification.append(
            {"path": rel, "expected_git_blob": expected_blob, "actual_git_blob": actual_blob}
        )

    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=False)
    receipts.mkdir(parents=True, exist_ok=True)

    files: list[dict[str, Any]] = []
    root_inventory: list[dict[str, Any]] = []
    skipped_forbidden: list[str] = []
    skipped_unsupported: list[str] = []
    skipped_excluded: list[str] = []
    python_files_parsed = 0

    def admit_file(path: Path, rel: Path, root_label: str) -> None:
        nonlocal python_files_parsed
        if path.is_symlink():
            raise SystemExit(f"symlink forbidden in custody source: {rel.as_posix()}")
        data = path.read_bytes()
        if path.suffix.lower() == ".py":
            try:
                ast.parse(data.decode("utf-8"), filename=rel.as_posix())
            except Exception as exc:
                raise SystemExit(f"Python syntax/encoding failure in {rel}: {exc}") from exc
            python_files_parsed += 1
        target = stage / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        files.append(
            {
                "path": rel.as_posix(),
                "bytes": len(data),
                "sha256": sha256_bytes(data),
                "root": root_label,
            }
        )

    for relroot in roots:
        source = repo / relroot
        if not source.is_dir() or source.is_symlink():
            raise SystemExit(f"missing or unsafe required source root: {relroot.as_posix()}")
        admitted_count = 0
        forbidden_count = 0
        unsupported_count = 0
        excluded_count = 0
        candidates = sorted(item for item in source.rglob("*") if item.is_file() or item.is_symlink())
        for path in candidates:
            rel = path.relative_to(repo)
            relative_inside_root = path.relative_to(source)
            if any(part in excluded_components for part in relative_inside_root.parts):
                skipped_excluded.append(rel.as_posix())
                excluded_count += 1
                continue
            suffix = path.suffix.lower()
            if suffix in forbidden_suffixes:
                skipped_forbidden.append(rel.as_posix())
                forbidden_count += 1
                continue
            if suffix not in admitted_suffixes:
                skipped_unsupported.append(rel.as_posix())
                unsupported_count += 1
                continue
            admit_file(path, rel, relroot.as_posix())
            admitted_count += 1
        if admitted_count < minimum_per_root:
            raise SystemExit(
                f"source root below admitted-file floor: {relroot.as_posix()} -> {admitted_count}"
            )
        root_inventory.append(
            {
                "root": relroot.as_posix(),
                "admitted_files": admitted_count,
                "forbidden_payloads_skipped": forbidden_count,
                "unsupported_paths_skipped": unsupported_count,
                "excluded_historical_outcomes_skipped": excluded_count,
            }
        )

    control_files = [contract_path, lease_path, readme_path, builder_path]
    for path in control_files:
        rel = path.relative_to(repo)
        admit_file(path, rel, "v0.16.3.1-control-plane")

    paths = [row["path"] for row in files]
    if len(paths) != len(set(paths)):
        raise SystemExit("duplicate archive member path")
    files.sort(key=lambda row: row["path"])
    if not files:
        raise SystemExit("empty source custody bundle")

    archive = receipts / "RUNTIME_INTEGRATION_SOURCE_CUSTODY_V0_16_3_1.zip"
    with zipfile.ZipFile(
        archive,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as zf:
        for row in files:
            path = stage / row["path"]
            info = zipfile.ZipInfo(row["path"], date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            zf.writestr(info, path.read_bytes())

    archive_bytes = archive.read_bytes()
    observed_members: list[dict[str, Any]] = []
    with zipfile.ZipFile(archive, "r") as zf:
        bad_member = zf.testzip()
        if bad_member is not None:
            raise SystemExit(f"ZIP CRC verification failed at {bad_member}")
        names = zf.namelist()
        expected_names = [row["path"] for row in files]
        if names != expected_names:
            raise SystemExit("ZIP member order or membership mismatch")
        for row in files:
            data = zf.read(row["path"])
            actual = sha256_bytes(data)
            if actual != row["sha256"]:
                raise SystemExit(f"ZIP member hash mismatch: {row['path']}")
            observed_members.append(
                {"path": row["path"], "bytes": len(data), "sha256": actual}
            )

    member_tree_sha256 = sha256_bytes(canonical_bytes(observed_members))
    manifest = {
        "format": "KCH_HELICAL_V0_16_3_1_SOURCE_CUSTODY_MEMBER_MANIFEST",
        "members": observed_members,
        "member_count": len(observed_members),
        "member_tree_sha256": member_tree_sha256,
    }
    manifest["manifest_id"] = "h1631manifest:" + sha256_bytes(canonical_bytes(manifest))
    manifest_path = receipts / "SOURCE_CUSTODY_MEMBER_MANIFEST_V0_16_3_1.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    body = {
        "format": "KCH_HELICAL_V0_16_3_1_RUNTIME_INTEGRATION_SOURCE_CUSTODY_RECEIPT",
        "implementation_revision": "0.16.3.1",
        "github_run_id": os.environ["GITHUB_RUN_ID"],
        "github_run_attempt": os.environ["GITHUB_RUN_ATTEMPT"],
        "github_sha": os.environ["GITHUB_SHA"],
        "predecessor_v0_16_2_failure": contract["predecessor_failure"],
        "predecessor_v0_16_3_failure": {
            "run_id": 38164023152,
            "job_id": 114542710164,
            "failure_class": "GATE_IMPLEMENTATION_ERROR",
            "terminal_error": "SyntaxError: no binding for nonlocal 'python_files_parsed' found",
        },
        "contract_sha256": sha256_bytes(contract_path.read_bytes()),
        "lease_sha256": sha256_bytes(lease_path.read_bytes()),
        "builder_sha256": sha256_bytes(builder_path.read_bytes()),
        "source_roots": [value.as_posix() for value in roots],
        "root_inventory": root_inventory,
        "required_blob_count": len(required_verification),
        "required_blob_verification": required_verification,
        "required_blob_identity": "PASS",
        "admitted_file_count": len(files),
        "python_files_parsed": python_files_parsed,
        "skipped_forbidden_paths": sorted(skipped_forbidden),
        "skipped_unsupported_paths": sorted(skipped_unsupported),
        "skipped_excluded_historical_outcomes": sorted(skipped_excluded),
        "archive_bytes": len(archive_bytes),
        "archive_sha256": sha256_bytes(archive_bytes),
        "archive_member_count": len(observed_members),
        "archive_member_tree_sha256": member_tree_sha256,
        "manifest_id": manifest["manifest_id"],
        "zip_crc_test": "PASS",
        "zip_member_hash_identity": "PASS",
        "independent_archive_reopen": "PASS",
        "scientific_data_included": False,
        "calibration_executed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "authority_ceiling": "CODE_ONLY_SOURCE_CUSTODY_REPAIR",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "next_gate": "CALIBRATION_ONLY_FULL_RUNTIME_QUALIFICATION_6376_JOBS_NO_TEST_ACCESS",
        "status": "PASS",
    }
    body["receipt_id"] = "h1631custody:" + sha256_bytes(canonical_bytes(body))
    receipt_path = receipts / "RUNTIME_INTEGRATION_SOURCE_CUSTODY_RECEIPT_V0_16_3_1.json"
    receipt_path.write_text(json.dumps(body, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    validation = {
        "format": "KCH_HELICAL_V0_16_3_1_SOURCE_CUSTODY_VALIDATION",
        "status": "PASS",
        "receipt_id": body["receipt_id"],
        "manifest_id": manifest["manifest_id"],
        "required_checks": {
            "v0_16_2_failure_preserved": True,
            "v0_16_3_failure_preserved": True,
            "all_source_roots_exist": True,
            "all_required_git_blobs_match": True,
            "each_root_has_admitted_source": True,
            "historical_outcomes_excluded": True,
            "forbidden_payloads_not_archived": True,
            "all_python_sources_parse": True,
            "deterministic_member_order": True,
            "zip_crc_pass": True,
            "member_hash_identity_pass": True,
            "sealed_test_not_accessed": True,
            "scientific_execution_not_performed": True,
        },
    }
    validation["validation_id"] = "h1631validation:" + sha256_bytes(canonical_bytes(validation))
    validation_path = receipts / "SOURCE_CUSTODY_VALIDATION_V0_16_3_1.json"
    validation_path.write_text(
        json.dumps(validation, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "receipt_id": body["receipt_id"],
                "manifest_id": manifest["manifest_id"],
                "validation_id": validation["validation_id"],
                "archive_sha256": body["archive_sha256"],
                "archive_member_count": body["archive_member_count"],
                "python_files_parsed": python_files_parsed,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
