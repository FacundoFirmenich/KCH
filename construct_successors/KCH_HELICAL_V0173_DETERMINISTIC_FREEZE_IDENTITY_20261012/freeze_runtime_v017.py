#!/usr/bin/env python3
"""Freeze and validate the specification-derived nonidentical runtime v0.17."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def git_blob(repo: Path, relative: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", f"HEAD:{relative}"],
        text=True,
    ).strip()


def assertion(checks: list[dict[str, Any]], name: str, condition: bool, detail: Any = None) -> None:
    checks.append({"name": name, "pass": bool(condition), "detail": detail})
    if not condition:
        raise RuntimeError(f"freeze assertion failed: {name}: {detail!r}")


def ast_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    output: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            output.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            output.add((node.module or "").split(".", 1)[0])
    return output


def structural_pass_records(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for job in jobs:
        output.append(
            {
                "job_id": job["job_id"],
                "seed": job["seed"],
                "runtime_contract_id": job["runtime_contract_id"],
                "protocol_id": job["protocol_id"],
                "stage": job["stage"],
                "cohort": job["cohort"],
                "family": job["family"],
                "replicate": job["replicate"],
                "status": "PASS",
                "input_hashes": {
                    "structural_fixture": hashlib.sha256(
                        ("input:" + job["job_id"]).encode("utf-8")
                    ).hexdigest()
                },
                "output_sha256": hashlib.sha256(
                    ("output:" + job["job_id"]).encode("utf-8")
                ).hexdigest(),
                "operator_diagnostics": {
                    "structural_fixture_only": True,
                    "scientific_execution": False,
                },
                "sealed_test_accessed": False,
                "scientific_result": None,
            }
        )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--unittest-log", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--development-skip-git-blob-check", action="store_true")
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    root = args.root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    unittest_log = args.unittest_log.resolve()

    sys.path.insert(0, str(root / "src"))
    from kch_helical_null_v017.runtime import (  # noqa: PLC0415
        COHORTS,
        EXPECTED_JOB_COUNT,
        HISTORICAL_FREEZE_ID,
        HISTORICAL_LEDGER_ID,
        HISTORICAL_LEDGER_SHA256,
        HISTORICAL_RUNTIME_CONTRACT_ID,
        NULL_FAMILIES,
        PROTOCOL_ID,
        QUALIFICATION_FAIL_CLOSED,
        QUALIFICATION_NOT_EXECUTED,
        QUALIFICATION_PASS,
        STAGE_COUNTS,
        build_job_ledger,
        not_run_records,
        qualification_status,
        runtime_contract,
        validate_job_ledger,
    )

    checks: list[dict[str, Any]] = []
    derivation_path = root / "contracts/SPEC_DERIVATION_CONTRACT_V0_17.json"
    artifact_audit_path = root / "contracts/CONNECTOR_ARTIFACT_SURFACE_ADJUDICATION_V0_16_6.json"
    runtime_path = root / "src/kch_helical_null_v017/runtime.py"
    init_path = root / "src/kch_helical_null_v017/__init__.py"
    tests_path = root / "tests/test_runtime_v017.py"
    freeze_path = root / "freeze_runtime_v017.py"

    derivation = load_json(derivation_path)
    artifact_audit = load_json(artifact_audit_path)
    assertion(checks, "derivation_format", derivation.get("format") == "KCH_HELICAL_V0_17_SPEC_DERIVATION_CONTRACT")
    assertion(checks, "derivation_protocol_exact", derivation["inputs"]["protocol_id"] == PROTOCOL_ID)
    assertion(checks, "historical_contract_reference_exact", derivation["inputs"]["historical_runtime_contract_id"] == HISTORICAL_RUNTIME_CONTRACT_ID)
    assertion(checks, "historical_ledger_reference_exact", derivation["inputs"]["historical_ledger_id"] == HISTORICAL_LEDGER_ID)
    assertion(checks, "historical_ledger_sha_reference_exact", derivation["inputs"]["historical_ledger_sha256"] == HISTORICAL_LEDGER_SHA256)
    assertion(checks, "historical_freeze_reference_exact", derivation["inputs"]["historical_freeze_id"] == HISTORICAL_FREEZE_ID)
    assertion(checks, "artifact_audit_id_exact", artifact_audit["adjudication_id"] == derivation["inputs"]["connector_artifact_adjudication_id"])
    assertion(checks, "artifact_search_negative", artifact_audit["conclusion"] == "RUNTIME_SOURCE_NOT_RECOVERABLE_FROM_AVAILABLE_INDEPENDENT_TRANSPORTS")
    assertion(checks, "artifact_target_hits_zero", artifact_audit["downloaded_artifact_target_hit_count"] == 0)

    if args.development_skip_git_blob_check and os.environ.get("GITHUB_ACTIONS", "").lower() == "true":
        raise RuntimeError("development Git-blob bypass is forbidden in GitHub Actions")

    operator_paths = {
        "operator_contract_git_blob_sha1": "construct_successors/KCH_HELICAL_V016_EXPLICIT_NULL_OPERATOR_QUALIFICATION_20261011/OPERATOR_CONTRACT_V0_16.json",
        "operator_source_git_blob_sha1": "construct_successors/KCH_HELICAL_V016_EXPLICIT_NULL_OPERATOR_QUALIFICATION_20261011/null_perturbation_operators_v016.py",
        "operator_test_git_blob_sha1": "construct_successors/KCH_HELICAL_V016_EXPLICIT_NULL_OPERATOR_QUALIFICATION_20261011/test_null_perturbation_operators_v016.py",
        "operator_runner_git_blob_sha1": "construct_successors/KCH_HELICAL_V016_EXPLICIT_NULL_OPERATOR_QUALIFICATION_20261011/run_operator_qualification_v016.py",
    }
    if args.development_skip_git_blob_check:
        checks.append({
            "name": "git_blob_checks_development_bypass",
            "pass": True,
            "detail": "LOCAL_DEVELOPMENT_ONLY_NOT_ACCEPTABLE_FOR_RELEASE",
        })
    else:
        for field, relative in operator_paths.items():
            observed = git_blob(repo, relative)
            assertion(checks, f"git_blob::{field}", observed == derivation["inputs"][field], observed)

    imports = ast_imports(runtime_path)
    allowed_imports = {"__future__", "collections", "hashlib", "json", "typing"}
    assertion(checks, "runtime_import_allowlist", imports <= allowed_imports, sorted(imports))
    assertion(checks, "runtime_no_os_import", "os" not in imports)
    assertion(checks, "runtime_no_pathlib_import", "pathlib" not in imports)
    assertion(checks, "runtime_no_subprocess_import", "subprocess" not in imports)
    assertion(checks, "runtime_no_socket_import", "socket" not in imports)

    test_text = unittest_log.read_text(encoding="utf-8")
    match = re.search(r"Ran\s+(\d+)\s+tests", test_text)
    assertion(
        checks,
        "unittest_count_parse",
        match is not None,
        {"matched": match is not None},
    )
    test_count = int(match.group(1)) if match else 0
    assertion(checks, "unittest_minimum_44", test_count >= 44, test_count)
    unittest_ok = re.search(r"\nOK\s*$", test_text) is not None
    assertion(
        checks,
        "unittest_ok",
        unittest_ok,
        {"matched": unittest_ok},
    )

    parent_graph_lock_id = derivation["semantic_invariants"].get(
        "parent_graph_lock_id",
        "h8parent:f61e9b60c455e75e53f16b9579cd085b68de20d810f05165504f91ab09d400cb",
    )
    location_operator_id = derivation["semantic_invariants"].get(
        "location_operator_id",
        "h12locop:6b3fcf56d1f427d107e5e5dbb264aba02f871c93708a5796074fd0916d89b1b5",
    )
    contract = runtime_contract(
        protocol_id=PROTOCOL_ID,
        parent_graph_lock_id=parent_graph_lock_id,
        location_operator_id=location_operator_id,
        cohorts=COHORTS,
    )
    jobs_a = build_job_ledger(
        protocol_id=PROTOCOL_ID,
        parent_graph_lock_id=parent_graph_lock_id,
        location_operator_id=location_operator_id,
        cohorts=COHORTS,
    )
    jobs_b = build_job_ledger(
        protocol_id=PROTOCOL_ID,
        parent_graph_lock_id=parent_graph_lock_id,
        location_operator_id=location_operator_id,
        cohorts=COHORTS,
    )
    assertion(checks, "ledger_repeatability", jobs_a == jobs_b)
    ledger_report = validate_job_ledger(jobs_a, expected_contract_id=contract["contract_id"])
    assertion(checks, "job_count_exact", ledger_report["job_count"] == EXPECTED_JOB_COUNT, ledger_report)
    assertion(checks, "job_ids_unique", ledger_report["job_id_unique_count"] == EXPECTED_JOB_COUNT)
    assertion(checks, "seeds_unique", ledger_report["seed_unique_count"] == EXPECTED_JOB_COUNT)
    assertion(checks, "stage_counts_exact", ledger_report["stage_counts"] == dict(STAGE_COUNTS), ledger_report["stage_counts"])
    assertion(checks, "null_family_set_exact", set(ledger_report["null_family_counts"]) == set(NULL_FAMILIES))
    assertion(checks, "null_family_counts_exact", all(value == 398 for value in ledger_report["null_family_counts"].values()))
    assertion(checks, "contract_identity_new", contract["contract_id"] != HISTORICAL_RUNTIME_CONTRACT_ID, contract["contract_id"])
    assertion(checks, "contract_prefix_new", contract["contract_id"].startswith("h17nullspec:"))

    ledger_path = output / "NULL_PERTURBATION_JOB_LEDGER_V0_17.jsonl"
    with ledger_path.open("w", encoding="utf-8", newline="\n") as handle:
        for job in jobs_a:
            handle.write(json.dumps(job, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
    ledger_sha256 = sha256_file(ledger_path)
    assertion(checks, "ledger_sha_new", ledger_sha256 != HISTORICAL_LEDGER_SHA256, ledger_sha256)

    not_run_outcome = qualification_status(jobs_a, not_run_records(jobs_a))
    assertion(checks, "not_run_adjudicates_not_executed", not_run_outcome["outcome"] == QUALIFICATION_NOT_EXECUTED, not_run_outcome)
    structural_pass = structural_pass_records(jobs_a)
    structural_pass_outcome = qualification_status(jobs_a, structural_pass)
    assertion(checks, "structural_pass_adjudicates_pass", structural_pass_outcome["outcome"] == QUALIFICATION_PASS, structural_pass_outcome)
    missing_outcome = qualification_status(jobs_a, structural_pass[:-1])
    assertion(checks, "missing_record_fails_closed", missing_outcome["outcome"] == QUALIFICATION_FAIL_CLOSED, missing_outcome)
    tampered = [dict(record) for record in not_run_records(jobs_a)]
    tampered[0]["seed"] += 1
    tampered_outcome = qualification_status(jobs_a, tampered)
    assertion(checks, "tampered_identity_fails_closed", tampered_outcome["outcome"] == QUALIFICATION_FAIL_CLOSED, tampered_outcome)
    test_violation = [dict(record) for record in not_run_records(jobs_a)]
    test_violation[0]["sealed_test_accessed"] = True
    test_outcome = qualification_status(jobs_a, test_violation)
    assertion(checks, "sealed_test_violation_fails_closed", test_outcome["outcome"] == QUALIFICATION_FAIL_CLOSED, test_outcome)

    source_manifest = []
    for path, role in (
        (runtime_path, "V0_17_SPEC_DERIVED_RUNTIME"),
        (init_path, "V0_17_PACKAGE_INIT"),
        (tests_path, "V0_17_STRUCTURAL_AND_ADVERSARIAL_TESTS"),
        (freeze_path, "V0_17_FREEZE_COMPILER"),
        (derivation_path, "V0_17_DERIVATION_CONTRACT"),
        (artifact_audit_path, "V0_16_6_ARTIFACT_SURFACE_ADJUDICATION"),
    ):
        source_manifest.append(
            {
                "path": path.relative_to(repo).as_posix(),
                "role": role,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    write_json(output / "FULL_NULL_AND_PERTURBATION_RUNTIME_CONTRACT_V0_17.json", contract)
    write_json(output / "RUNTIME_SOURCE_MANIFEST_V0_17.json", {"format": "KCH_HELICAL_V0_17_SOURCE_MANIFEST", "files": source_manifest})

    summary_body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_17_NULL_PERTURBATION_JOB_LEDGER_SUMMARY",
        "protocol_id": PROTOCOL_ID,
        "runtime_contract_id": contract["contract_id"],
        "derivation_contract_id": derivation["derivation_contract_id"],
        "job_count": EXPECTED_JOB_COUNT,
        "job_id_unique_count": ledger_report["job_id_unique_count"],
        "seed_unique_count": ledger_report["seed_unique_count"],
        "stage_counts": ledger_report["stage_counts"],
        "null_family_counts": ledger_report["null_family_counts"],
        "ledger_sha256": ledger_sha256,
        "historical_ledger_id_reference": HISTORICAL_LEDGER_ID,
        "historical_ledger_sha256_reference": HISTORICAL_LEDGER_SHA256,
        "historical_identity_transferred": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "authority_ceiling": "SOFTWARE_CANDIDATE_LOCAL_SHADOW",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    summary = dict(summary_body)
    summary["ledger_id"] = "h17nullledger:" + sha256_bytes(canonical(summary_body))
    assertion(checks, "ledger_id_new", summary["ledger_id"] != HISTORICAL_LEDGER_ID, summary["ledger_id"])
    write_json(output / "NULL_PERTURBATION_JOB_LEDGER_SUMMARY_V0_17.json", summary)

    nonidentity_body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_17_NONIDENTITY_PROOF",
        "historical_runtime_contract_id": HISTORICAL_RUNTIME_CONTRACT_ID,
        "successor_runtime_contract_id": contract["contract_id"],
        "historical_ledger_id": HISTORICAL_LEDGER_ID,
        "successor_ledger_id": summary["ledger_id"],
        "historical_ledger_sha256": HISTORICAL_LEDGER_SHA256,
        "successor_ledger_sha256": ledger_sha256,
        "contract_ids_distinct": contract["contract_id"] != HISTORICAL_RUNTIME_CONTRACT_ID,
        "ledger_ids_distinct": summary["ledger_id"] != HISTORICAL_LEDGER_ID,
        "ledger_bytes_distinct": ledger_sha256 != HISTORICAL_LEDGER_SHA256,
        "byte_identity_claim": "FORBIDDEN",
        "semantic_derivation_claim": "EXPLICIT",
        "historical_hash_reuse": False,
        "scientific_result": None,
    }
    nonidentity = dict(nonidentity_body)
    nonidentity["proof_id"] = "h17nonidentity:" + sha256_bytes(canonical(nonidentity_body))
    write_json(output / "NONIDENTITY_PROOF_V0_17.json", nonidentity)

    validation_body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_17_RUNTIME_VALIDATION_REPORT",
        "checks": checks,
        "check_count": len(checks),
        "pass_count": sum(1 for check in checks if check["pass"]),
        "all_pass": all(check["pass"] for check in checks),
        "unittest_count": test_count,
        "not_run_qualification_outcome": not_run_outcome,
        "structural_fixture_qualification_outcome": structural_pass_outcome,
        "structural_fixture_is_scientific_execution": False,
        "scientific_data_accessed": False,
        "calibration_executed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    validation = dict(validation_body)
    validation["validation_id"] = "h17validation:" + sha256_bytes(canonical(validation_body))
    write_json(output / "RUNTIME_VALIDATION_REPORT_V0_17.json", validation)

    freeze_body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_17_SPEC_DERIVED_NONIDENTICAL_RUNTIME_FREEZE",
        "state": "SPECIFICATION_DERIVED_NONIDENTICAL_RUNTIME_FROZEN",
        "protocol_id": PROTOCOL_ID,
        "derivation_contract_id": derivation["derivation_contract_id"],
        "runtime_contract_id": contract["contract_id"],
        "ledger_id": summary["ledger_id"],
        "ledger_sha256": ledger_sha256,
        "nonidentity_proof_id": nonidentity["proof_id"],
        "validation_id": validation["validation_id"],
        "job_count": EXPECTED_JOB_COUNT,
        "runtime_source_recovered_historically": False,
        "runtime_source_reimplemented": True,
        "historical_identity_transferred": False,
        "historical_ledger_hash_reused": False,
        "calibration_runtime_qualification_executed": False,
        "scientific_data_accessed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "authority": "SOFTWARE_CANDIDATE_LOCAL_SHADOW",
        "publication": "BLOCKED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "next_gate": "CALIBRATION_ONLY_FULL_RUNTIME_QUALIFICATION_6376_JOBS_NO_TEST_ACCESS",
    }
    freeze = dict(freeze_body)
    freeze["freeze_id"] = "h17freeze:" + sha256_bytes(canonical(freeze_body))
    write_json(output / "RUNTIME_FREEZE_RECEIPT_V0_17.json", freeze)

    status = {
        "format": "KCH_HELICAL_V0_17_STATUS",
        "state": freeze["state"],
        "freeze_id": freeze["freeze_id"],
        "runtime_contract_id": contract["contract_id"],
        "ledger_id": summary["ledger_id"],
        "ledger_sha256": ledger_sha256,
        "scheduled_job_count": EXPECTED_JOB_COUNT,
        "historical_identity_transferred": False,
        "calibration_runtime_qualification_executed": False,
        "scientific_data_accessed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "authority": "SOFTWARE_CANDIDATE_LOCAL_SHADOW",
        "publication": "BLOCKED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "next_gate": freeze["next_gate"],
    }
    write_json(output / "STATUS_V0_17.json", status)

    execution_body = {
        "format": "KCH_HELICAL_V0_17_FREEZE_EXECUTION_RECEIPT",
        "github_run_id": os.environ.get("GITHUB_RUN_ID", "LOCAL"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "LOCAL"),
        "github_sha": os.environ.get("GITHUB_SHA", "LOCAL"),
        "freeze_id": freeze["freeze_id"],
        "validation_id": validation["validation_id"],
        "runtime_contract_id": contract["contract_id"],
        "ledger_id": summary["ledger_id"],
        "status": "PASS",
        "scientific_data_accessed": False,
        "calibration_executed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    execution = dict(execution_body)
    execution["execution_receipt_id"] = "h17execution:" + sha256_bytes(canonical(execution_body))
    write_json(output / "FREEZE_EXECUTION_RECEIPT_V0_17.json", execution)

    print(
        json.dumps(
            {
                "freeze_id": freeze["freeze_id"],
                "validation_id": validation["validation_id"],
                "runtime_contract_id": contract["contract_id"],
                "ledger_id": summary["ledger_id"],
                "ledger_sha256": ledger_sha256,
                "job_count": EXPECTED_JOB_COUNT,
                "check_count": len(checks),
                "unittest_count": test_count,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
