from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from kch_helical_dynamic_v08.core import canonical_json_bytes
from kch_helical_dynamic_v08.null_runtime import (
    NULL_FAMILIES,
    build_job_ledger,
    runtime_contract,
)

EXPECTED_PROTOCOL_ID = "h8p:99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f"
EXPECTED_PROTOCOL_SHA = "99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f"
EXPECTED_PARENT_LOCK_ID = "h8parent:56fbeb32122c4f706162bae7ff08f143a6722b92c5c2d43e10e09cb77e3b3487"
EXPECTED_LOCATION_OPERATOR_ID = "h8locop:dc2fe8b8e090cfe61049e347a8c12c344db212cd87482a039e5d89917d60b6c9"
EXPECTED_RECOVERY_RECEIPT_ID = "h8recover3:a70242505a93d9e1dcd17cc1586aeb68ed9ad02be6a84a58bf029402e5160a8c"
EXPECTED_DURABLE_RECEIPT_ID = "h8durable3:c1feb7ee7361a235ec2bcc5b918e25cbce84dc1f63ec38028cc22ca32647dad8"
EXPECTED_COHORTS = ("BAY_AREA_HAYWARD_CALAVERAS", "PARKFIELD_CENTRAL_SAF")
EXPECTED_SOURCE_HASHES = {
    "src/kch_helical_dynamic_v08/core.py": "231f2267057906cdc08d0d1299bd9407e431aae3a5eb6e9f3b1cbd951d5ba798",
    "src/kch_helical_dynamic_v08/eligibility.py": "4f882027beea67826fb282f2912c805e087fb320ced23d143e64576555a646a4",
    "src/kch_helical_dynamic_v08/__init__.py": "40335de8a8b8ba096ae70b1a105573ba6d71c0369a89f940dae2dd0e78d9bed8",
    "tests_v0_8_4/test_dynamic_v08_original.py": "993d386e39704237f5be408dcf3daa1e7b7e631c6a0a69f2230fb4b0372e6c7b",
}
EXPECTED_THRESHOLDS = {
    "maximum_helix_minus_baseline_delta_bic": -10.0,
    "maximum_holm_adjusted_null_p": 0.05,
    "minimum_fault_assignment_perturbation_pass_fraction": 0.8,
    "minimum_mechanism_uncertainty_pass_fraction": 0.8,
    "minimum_moving_block_bootstrap_lower_95": 0.0,
    "minimum_parent_graph_resample_pass_fraction": 0.8,
    "minimum_positive_primary_cohorts": 2,
    "minimum_relative_axial_rmse_improvement": 0.05,
    "minimum_test_mean_log_score_gain_per_edge": 0.02,
    "minimum_time_reversal_sign_consistency": 0.8,
    "minimum_weighted_aggregate_log_score_gain": 0.02,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def assertion(checks: list[dict], name: str, condition: bool, detail: object = None) -> None:
    checks.append({"name": name, "pass": bool(condition), "detail": detail})
    if not condition:
        raise RuntimeError(f"freeze assertion failed: {name}: {detail!r}")


def parse_junit(path: Path) -> dict:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
    totals = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0, "time_seconds": 0.0}
    for suite in suites:
        totals["tests"] += int(suite.attrib.get("tests", 0))
        totals["failures"] += int(suite.attrib.get("failures", 0))
        totals["errors"] += int(suite.attrib.get("errors", 0))
        totals["skipped"] += int(suite.attrib.get("skipped", 0))
        totals["time_seconds"] += float(suite.attrib.get("time", 0.0))
    totals["sha256"] = sha256_file(path)
    return totals


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-run-id", default="LOCAL")
    parser.add_argument("--github-sha", default="LOCAL")
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    evidence = args.evidence_root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []

    protocol_path = repo / ".github/helical_v08/protocol.json"
    protocol = load_json(protocol_path)
    assertion(checks, "protocol_id_exact", protocol.get("protocol_id") == EXPECTED_PROTOCOL_ID, protocol.get("protocol_id"))
    assertion(checks, "protocol_sha_field_exact", protocol.get("protocol_sha256") == EXPECTED_PROTOCOL_SHA, protocol.get("protocol_sha256"))
    protocol_body = dict(protocol)
    protocol_body.pop("protocol_id", None)
    protocol_body.pop("protocol_sha256", None)
    observed_protocol_body_sha = hashlib.sha256(canonical_json_bytes(protocol_body)).hexdigest()
    assertion(checks, "protocol_body_sha_exact", observed_protocol_body_sha == EXPECTED_PROTOCOL_SHA, observed_protocol_body_sha)
    assertion(checks, "protocol_id_derived_from_body_sha", protocol.get("protocol_id") == "h8p:" + observed_protocol_body_sha)
    assertion(checks, "null_families_exact", tuple(protocol["null_families"]["families"]) == NULL_FAMILIES, protocol["null_families"]["families"])
    assertion(checks, "null_replicates_exact", protocol["null_families"]["replicates_each"] == 199, protocol["null_families"]["replicates_each"])
    assertion(checks, "multiplicity_exact", protocol["null_families"]["multiplicity"] == "HOLM_BONFERRONI_ACROSS_COHORTS_AND_NULL_FAMILIES")
    assertion(checks, "uncertainty_replicates_exact", protocol["observation_model"]["uncertainty_propagation_replicates"] == 64)
    assertion(checks, "parent_resamples_exact", protocol["parent_graph"]["parent_graph_resamples"] == 64)
    assertion(checks, "thresholds_exact", protocol["thresholds"] == EXPECTED_THRESHOLDS, protocol["thresholds"])
    assertion(checks, "scientific_execution_prelock_false", protocol.get("scientific_execution_performed") is False)
    assertion(checks, "physical_helicity_not_evaluated", protocol.get("physical_helicity") == "NOT_EVALUATED")
    assertion(checks, "authority_none", protocol.get("authority_ceiling") == "NONE")
    assertion(checks, "promotion_blocked", protocol.get("promotion") == "BLOCKED")
    assertion(checks, "canonicalization_blocked", protocol.get("canonicalization") == "BLOCKED")

    recovery = load_json(evidence / "GREEN_ARTIFACT_RECOVERY_RECEIPT_V0_8_3.json")
    durable = load_json(evidence / "DURABLE_PRETEST_FREEZE_RECEIPT_V0_8_3.json")
    parent = load_json(evidence / "stage/parent_graph/ETAS_HAWKES_PARENT_GRAPH_PARAMETER_LOCK_V0_8.json")
    parent_gate = load_json(evidence / "stage/parent_graph/PARENT_GRAPH_CALIBRATION_RESULT_V0_8.json")
    location = load_json(evidence / "stage/topology/LOCATION_PERTURBATION_OPERATOR_LOCK_V0_8.json")
    selected = load_json(evidence / "stage/selection/SELECTED_INDEX_RECEIPT_V0_8.json")

    assertion(checks, "recovery_receipt_exact", recovery.get("recovery_receipt_id") == EXPECTED_RECOVERY_RECEIPT_ID, recovery.get("recovery_receipt_id"))
    assertion(checks, "durable_receipt_exact", durable.get("receipt_id") == EXPECTED_DURABLE_RECEIPT_ID, durable.get("receipt_id"))
    assertion(checks, "durable_test_unscored", durable.get("sealed_test_response_scored") is False)
    assertion(checks, "durable_scientific_model_unexecuted", durable.get("scientific_model_execution_performed") is False)
    assertion(checks, "selected_cohorts_exact", tuple(durable.get("selected_primary_cohorts", [])) == EXPECTED_COHORTS, durable.get("selected_primary_cohorts"))
    assertion(checks, "parent_lock_exact", parent.get("lock_id") == EXPECTED_PARENT_LOCK_ID, parent.get("lock_id"))
    assertion(checks, "parent_fit_train_only", parent.get("fit_scope") == "TRAIN_ONLY")
    assertion(checks, "parent_test_counts_only", parent.get("test_access") == "COUNTS_ONLY_NO_TEST_VALUES_SCORED")
    assertion(checks, "parent_units_pass", parent.get("all_units_pass") is True)
    assertion(checks, "parent_gate_pass", parent_gate.get("outcome") == "PARENT_GRAPH_LOCK_PASS")
    assertion(checks, "parent_gate_next_exact", parent_gate.get("next_material_gate") == "FULL_NULL_AND_PERTURBATION_RUNTIME_FREEZE")
    assertion(checks, "location_operator_exact", location.get("operator_id") == EXPECTED_LOCATION_OPERATOR_ID, location.get("operator_id"))
    assertion(checks, "location_replicates_exact", location.get("scientific_replicates") == 64)
    assertion(checks, "location_missing_no_imputation", location.get("missing_error_policy") == "UNAVAILABLE_NO_IMPUTATION")
    assertion(checks, "location_test_unscored", location.get("sealed_test_scored") is False)
    assertion(checks, "selected_directional_preaccess_false", selected.get("directional_fields_accessed") is False)
    assertion(checks, "selected_total_exact", selected.get("selected_total") == 61555, selected.get("selected_total"))

    source_manifest: list[dict] = []
    for relative, expected in EXPECTED_SOURCE_HASHES.items():
        path = repo / relative
        observed = sha256_file(path)
        assertion(checks, f"canonical_source_hash::{relative}", observed == expected, observed)
        source_manifest.append({"path": relative, "bytes": path.stat().st_size, "sha256": observed, "role": "CANONICAL_V0_8_SOURCE"})
    for relative, role in (
        ("src/kch_helical_dynamic_v08/null_runtime.py", "V0_8_4_NULL_PERTURBATION_RUNTIME"),
        ("tests_v0_8_4/test_null_runtime.py", "V0_8_4_OPERATOR_TESTS"),
        ("tools/freeze_null_perturbation_runtime.py", "V0_8_4_FREEZE_COMPILER"),
    ):
        path = repo / relative
        source_manifest.append({"path": relative, "bytes": path.stat().st_size, "sha256": sha256_file(path), "role": role})

    junit = parse_junit(args.junit)
    assertion(checks, "pytest_no_failures", junit["failures"] == 0, junit)
    assertion(checks, "pytest_no_errors", junit["errors"] == 0, junit)
    assertion(checks, "pytest_minimum_count", junit["tests"] >= 28, junit)

    contract = dict(
        runtime_contract(
            protocol_id=EXPECTED_PROTOCOL_ID,
            parent_graph_lock_id=EXPECTED_PARENT_LOCK_ID,
            location_operator_id=EXPECTED_LOCATION_OPERATOR_ID,
            cohorts=EXPECTED_COHORTS,
        )
    )
    contract["thresholds"] = EXPECTED_THRESHOLDS
    contract["parent_graph_candidate_contract"] = parent["candidate_contract"]
    contract["source_manifest"] = source_manifest
    contract_material = dict(contract)
    contract["contract_id"] = "h8nullspec:" + hashlib.sha256(canonical_json_bytes(contract_material)).hexdigest()

    jobs = build_job_ledger(
        protocol_id=EXPECTED_PROTOCOL_ID,
        parent_graph_lock_id=EXPECTED_PARENT_LOCK_ID,
        location_operator_id=EXPECTED_LOCATION_OPERATOR_ID,
        cohorts=EXPECTED_COHORTS,
    )
    ledger_path = output / "NULL_PERTURBATION_JOB_LEDGER_V0_8_4.jsonl"
    with ledger_path.open("w", encoding="utf-8", newline="\n") as handle:
        for job in jobs:
            handle.write(json.dumps(job, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
    ledger_sha = sha256_file(ledger_path)
    stage_counts: dict[str, int] = {}
    family_counts: dict[str, int] = {}
    for job in jobs:
        stage_counts[job["stage"]] = stage_counts.get(job["stage"], 0) + 1
        family_counts[job["family"]] = family_counts.get(job["family"], 0) + 1
    ledger_summary = {
        "format": "KCH_HELICAL_V0_8_4_NULL_PERTURBATION_JOB_LEDGER_SUMMARY",
        "protocol_id": EXPECTED_PROTOCOL_ID,
        "contract_id": contract["contract_id"],
        "job_count": len(jobs),
        "job_id_unique_count": len({job["job_id"] for job in jobs}),
        "seed_unique_count": len({job["seed"] for job in jobs}),
        "stage_counts": stage_counts,
        "family_counts": family_counts,
        "ledger_sha256": ledger_sha,
        "sealed_test_values_accessed": False,
        "authority_ceiling": "NONE",
    }
    ledger_summary["ledger_id"] = "h8nullledger:" + hashlib.sha256(canonical_json_bytes(ledger_summary)).hexdigest()

    validation = {
        "format": "KCH_HELICAL_V0_8_4_NULL_RUNTIME_VALIDATION_REPORT",
        "checks": checks,
        "pass_count": sum(1 for check in checks if check["pass"]),
        "check_count": len(checks),
        "all_pass": all(check["pass"] for check in checks),
        "pytest": junit,
        "software_scope": "OPERATOR_ALGEBRA_AND_FREEZE_CONTRACT_ONLY",
        "scientific_result": None,
        "sealed_test_values_accessed": False,
        "authority_ceiling": "NONE",
    }
    validation["validation_id"] = "h8nullval:" + hashlib.sha256(canonical_json_bytes(validation)).hexdigest()

    write_json(output / "FULL_NULL_AND_PERTURBATION_RUNTIME_CONTRACT_V0_8_4.json", contract)
    write_json(output / "NULL_PERTURBATION_JOB_LEDGER_SUMMARY_V0_8_4.json", ledger_summary)
    write_json(output / "NULL_RUNTIME_VALIDATION_REPORT_V0_8_4.json", validation)
    write_json(output / "RUNTIME_SOURCE_MANIFEST_V0_8_4.json", {"files": source_manifest})

    freeze = {
        "format": "KCH_HELICAL_V0_8_4_FULL_NULL_AND_PERTURBATION_RUNTIME_FREEZE_RECEIPT",
        "state": "FULL_NULL_AND_PERTURBATION_RUNTIME_FROZEN",
        "protocol_id": EXPECTED_PROTOCOL_ID,
        "predecessor_durable_receipt_id": EXPECTED_DURABLE_RECEIPT_ID,
        "predecessor_recovery_receipt_id": EXPECTED_RECOVERY_RECEIPT_ID,
        "parent_graph_lock_id": EXPECTED_PARENT_LOCK_ID,
        "location_operator_id": EXPECTED_LOCATION_OPERATOR_ID,
        "contract_id": contract["contract_id"],
        "ledger_id": ledger_summary["ledger_id"],
        "ledger_sha256": ledger_sha,
        "validation_id": validation["validation_id"],
        "source_manifest_sha256": hashlib.sha256(canonical_json_bytes({"files": source_manifest})).hexdigest(),
        "cohorts": list(EXPECTED_COHORTS),
        "null_family_count": len(NULL_FAMILIES),
        "null_replicates_each": 199,
        "null_hypothesis_count": len(EXPECTED_COHORTS) * len(NULL_FAMILIES),
        "scheduled_job_count": len(jobs),
        "scheduled_stage_counts": stage_counts,
        "sealed_test_values_accessed": False,
        "sealed_test_scored": False,
        "calibration_scored": False,
        "scientific_model_execution_performed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "next_material_gate": "CALIBRATION_ONLY_FULL_RUNTIME_QUALIFICATION_NO_TEST_ACCESS",
        "retrospective_mutation": "FORBIDDEN",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "publication": "BLOCKED",
        "authority_ceiling": "NONE",
        "github_run_id": str(args.github_run_id),
        "github_sha": str(args.github_sha),
        "frozen_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    freeze_material = {k: v for k, v in freeze.items() if k not in {"frozen_at_utc", "github_run_id", "github_sha"}}
    freeze["freeze_id"] = "h8nullfreeze:" + hashlib.sha256(canonical_json_bytes(freeze_material)).hexdigest()
    write_json(output / "FULL_NULL_AND_PERTURBATION_RUNTIME_FREEZE_RECEIPT_V0_8_4.json", freeze)

    files = sorted(path for path in output.rglob("*") if path.is_file() and path.name != "SHA256SUMS.txt")
    lines = [f"{sha256_file(path)}  {path.relative_to(output).as_posix()}" for path in files]
    (output / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n")
    print(json.dumps(freeze, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FREEZE_FAIL_CLOSED: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
