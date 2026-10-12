#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import Counter
import dataclasses
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
from typing import Any, Mapping, Sequence

import numpy as np

EXPECTED_NUMPY_VERSION = "2.1.3"
EXPECTED_RUNTIME_SHA256 = "23bb0b2431ae3ea1d9912858350b27ad9efe6163b0634fc2c2b92889de630e11"
EXPECTED_OPERATOR_SHA256 = "6a41cdbfc3131c3e42d7bcd41770dd615712e75824cc016e0fa8a1a70d389acb"
EXPECTED_RUNTIME_CONTRACT_ID = "h17nullspec:20fbec42c3b9e1c6ec1ed8ef1a1f418907dee6a41fbba73259911f3a359e315d"
EXPECTED_LEDGER_ID = "h17nullledger:d524bca6e35f07bbfaabaa947c43a11d2d2317e04ac640d0d3d9243baade2e29"
EXPECTED_LEDGER_SHA256 = "2d4e219af4d6099b1cf207c46d04b137a1710cc624c07eee260a6436b09ccb3e"
EXPECTED_JOB_COUNT = 6376

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())

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
        raise RuntimeError(f"JSON object required: {path}")
    return value

def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")

def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

def normalize(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return normalize(dataclasses.asdict(value))
    if isinstance(value, np.ndarray):
        arr = np.ascontiguousarray(value)
        return {
            "__ndarray__": True,
            "dtype": str(arr.dtype),
            "shape": list(arr.shape),
            "sha256": sha256_bytes(arr.tobytes(order="C")),
        }
    if isinstance(value, np.generic):
        return normalize(value.item())
    if isinstance(value, Mapping):
        return {str(k): normalize(v) for k, v in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    if isinstance(value, set):
        return sorted(normalize(v) for v in value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RuntimeError("non-finite float in operator output")
        return value
    if value is None or isinstance(value, (str, int, bool)):
        return value
    return repr(value)

def holm_adjust(p_values: Sequence[float]) -> list[float]:
    values = [float(v) for v in p_values]
    if not values or any((not math.isfinite(v) or v < 0.0 or v > 1.0) for v in values):
        raise RuntimeError("invalid Holm p-values")
    order = sorted(range(len(values)), key=lambda i: (values[i], i))
    adjusted = [0.0] * len(values)
    running = 0.0
    m = len(values)
    for rank, index in enumerate(order):
        candidate = min(1.0, (m - rank) * values[index])
        running = max(running, candidate)
        adjusted[index] = running
    return adjusted

def fixture_contract() -> dict[str, Any]:
    return {
        "format": "KCH_HELICAL_V0_17_4_STRUCTURAL_FIXTURE_CONTRACT",
        "purpose": "SOFTWARE_RUNTIME_QUALIFICATION_ONLY",
        "scientific_observation": False,
        "scientific_calibration_data": False,
        "sealed_test_data": False,
        "event_fixture_size": 12,
        "mark_fixture_columns": 2,
        "time_support_days": [0.0, 11.0],
        "magnitude_values": [2.0, 2.1, 2.5],
        "quality_labels": ["Q"],
        "operator_parameter_fixture": {
            "productivity": 0.44,
            "magnitude_scaling": 0.3,
            "c_days": 0.1,
            "p": 1.1,
            "network_scale_km": 1.5,
            "magnitude_reference": 2.0,
            "background_rate_per_day": 0.2,
            "branching_ratio": 0.2,
        },
        "location_fixture": "TWO_REFERENCE_LINES_DETERMINISTIC_NEAREST_ASSIGNMENT",
        "holm_fixture_p_values": [0.001, 0.01, 0.02, 0.2, 0.8],
    }

def base_fixture(cohort: str) -> dict[str, Any]:
    times = np.arange(12, dtype=np.float64)
    parent = np.asarray([0,1,2,3,4,5,0,1,2,3,4,5], dtype=np.int64)
    child = np.asarray([6,7,8,9,10,11,7,8,9,10,11,6], dtype=np.int64)
    weights = np.ones(12, dtype=np.float64)
    allowed = {(p, c) for p in range(6) for c in range(6, 12)}
    marks = np.arange(24, dtype=np.float64).reshape(12, 2)
    return {
        "cohort": cohort,
        "times": times,
        "magnitude": np.asarray([2.0,2.1,2.0,2.1,2.0,2.1,2.5,2.5,2.5,2.5,2.5,2.5], dtype=np.float64),
        "parent": parent,
        "child": child,
        "weights": weights,
        "allowed": allowed,
        "edge_cohort": [cohort] * 12,
        "marks": marks,
        "component": ["x"] * 6 + ["y"] * 6,
        "quality": ["Q"] * 12,
        "node": [f"n{i%3}" for i in range(12)],
        "parameters": {
            "productivity": 0.44,
            "magnitude_scaling": 0.3,
            "c_days": 0.1,
            "p": 1.1,
            "network_scale_km": 1.5,
            "magnitude_reference": 2.0,
            "background_rate_per_day": 0.2,
            "branching_ratio": 0.2,
        },
    }

def dependencies_satisfied(job: Mapping[str, Any], completed: Sequence[Mapping[str, Any]]) -> bool:
    selectors = job.get("dependency_selector", [])
    if not selectors:
        return True
    for selector in selectors:
        stage = selector["stage"]
        cohort = selector["cohort"]
        matches = [
            record for record in completed
            if record["stage"] == stage and (cohort == "*" or record["cohort"] == cohort)
        ]
        if not matches or any(record["status"] != "PASS" for record in matches):
            return False
    return True

def execute_job(job: Mapping[str, Any], op, completed: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    if not dependencies_satisfied(job, completed):
        raise RuntimeError(f"dependency selector unresolved for {job['job_id']}")

    cohort = str(job["cohort"])
    fixture = base_fixture(cohort if cohort != "GLOBAL" else "GLOBAL")
    seed = int(job["seed"])
    stage = str(job["stage"])
    family = str(job["family"])
    rng = op.seeded_rng("v0174:" + job["job_id"], seed)
    binding = list(job.get("operator_binding", []))
    outputs: dict[str, Any] = {}
    called: list[str] = []

    if stage == "OBSERVED_CALIBRATION_SCORE":
        outputs["score"] = op.score_null_metrics(
            [0.0, 10.0, 20.0, 30.0],
            [5.0, 15.0, 25.0, 35.0],
            [5.0, 15.0, 25.0, 35.0],
            [0.0, 10.0, 20.0, 30.0],
            edge_weight=[1.0, 2.0, 1.0, 2.0],
        )
        called.append("score_null_metrics")

    elif stage == "NULL_CALIBRATION_REPLICATE":
        if family == "MARK_PERMUTATION_WITHIN_FAULT_TIME_MAGNITUDE_QUALITY_BLOCKS":
            permuted, diag = op.permute_within_bins(
                fixture["marks"], [cohort]*12, fixture["component"], fixture["times"],
                fixture["magnitude"], fixture["quality"], rng=rng,
            )
            outputs["permuted"] = permuted
            outputs["diagnostics"] = diag
            called.append("permute_within_bins")

        elif family == "PARENT_EDGE_REWIRING_PRESERVING_ETAS_WEIGHT_DISTRIBUTION":
            direct = op.rewire_parent_graph(
                fixture["parent"], fixture["child"], fixture["weights"], fixture["times"],
                fixture["edge_cohort"], rng=rng, candidate_allowed=fixture["allowed"],
            )
            state = op.ParentState(
                fixture["child"], fixture["parent"], fixture["weights"],
                fixture["weights"] / 2.0, np.ones(12, dtype=np.float64),
                np.ones(12, dtype=np.float64),
            )
            wrapped = op.make_rewired_null(
                state, fixture["times"], fixture["edge_cohort"],
                namespace="v0174-rewire:" + job["job_id"], seed=seed,
                candidate_allowed=fixture["allowed"],
            )
            outputs["direct"] = direct
            outputs["wrapped"] = wrapped
            called.extend(["rewire_parent_graph", "make_rewired_null"])

        elif family == "STATIC_ORIENTATION_FIELD_SURROGATES":
            source_marks = np.asarray([[1.,0.],[2.,0.],[3.,0.],[4.,0.]], dtype=np.float64)
            drawn, backoff, diag = op.draw_static_fields(
                source_marks,
                ["n1","n1","n2","n3"], ["c1","c1","c1","c2"], [cohort]*4,
                [2.1,2.1,2.1,3.1], ["Q","Q","Q","Q"],
                ["n1","missing","missing","missing"], ["c1","c1","missing","missing"], [cohort]*4,
                [2.1,2.1,2.1,99.0], ["Q","Q","Q","missing"],
                rng=rng,
            )
            outputs["drawn"] = drawn
            outputs["backoff"] = backoff
            outputs["draw_diagnostics"] = diag
            outputs["logodds"] = op.static_logodds([7.0,3.0], [10.0,10.0])
            called.extend(["draw_static_fields", "static_logodds"])

        elif family == "PROPAGATION_DIRECTION_REVERSAL":
            rake = np.asarray([-170.0,-45.0,10.0,120.0], dtype=np.float64)
            outputs["reflected_rake"] = op.reflected_rake(rake)
            outputs["normals"] = op.head_to_normal([0.0,90.0,180.0,270.0])
            outputs["score"] = op.score_null_metrics(
                [0.0,10.0,20.0,30.0],
                [5.0,20.0,10.0,40.0],
                [5.0,20.0,10.0,40.0],
                [0.0,10.0,20.0,30.0],
            )
            called.extend(["reflected_rake", "head_to_normal", "score_null_metrics"])

        elif family == "NONHELICAL_HAWKES_SIMULATIONS_MATCHED_TO_NETWORK_RATE_MAGNITUDE_UNCERTAINTY":
            state = op.ParentState(
                np.asarray([1], dtype=np.int64),
                np.asarray([0], dtype=np.int64),
                np.asarray([0.2], dtype=np.float64),
                np.asarray([0.5], dtype=np.float64),
                np.asarray([0.4,0.4], dtype=np.float64),
                np.asarray([0.5,0.5], dtype=np.float64),
            )
            outputs["fixed_parent"] = op.simulate_nonhelical_fixed_parent_weights(
                state,
                [[1.,0.],[0.,1.]], ["n1","n2"], ["c","c"], [cohort,cohort], [2.,2.], ["Q","Q"],
                ["n1"], ["c"], [cohort], [2.], ["Q"],
                namespace="v0174-nonhelical:" + job["job_id"], seed=seed,
            )
            outputs["catalog"] = op.simulate_catalog(
                duration_days=5.0,
                parameters=fixture["parameters"],
                empirical_magnitudes=[1.5,2.0,2.5],
                network_nodes=["n1","n2"],
                transition_matrix=[[0.8,0.2],[0.3,0.7]],
                namespace="v0174-catalog:" + job["job_id"],
                seed=seed,
                maximum_events=1000,
            )
            called.extend(["simulate_nonhelical_fixed_parent_weights", "simulate_catalog"])
        else:
            raise RuntimeError(f"unknown null family: {family}")

    elif stage == "MECHANISM_UNCERTAINTY_PROPAGATION":
        args = ([350.,10.,45.,120.], [80.,5.,30.,60.], [170.,-170.,30.,-45.], [20.,20.,5.,10.], [15.,15.,5.,10.], [30.,30.,10.,15.])
        outputs["draws"] = op.propagate_mechanism_uncertainty(
            *args, replicates=4, namespace="v0174-mech:" + job["job_id"], seed=seed,
        )
        outputs["posterior"] = op.posterior_mark_expectations(
            *args, draws=4, namespace="v0174-post:" + job["job_id"], seed=seed,
        )
        called.extend(["propagate_mechanism_uncertainty", "posterior_mark_expectations"])

    elif stage == "PARENT_GRAPH_RESAMPLE":
        outputs["intensity"] = op.eval_intensity(
            [0.,0.,1.], [1.,2.,3.], [2.,2.1,2.5], [1.,2.,1.5], fixture["parameters"],
        )
        outputs["state"] = op.compute_parent_state(
            [0.,1.,2.,3.], [2.,2.1,2.2,2.3],
            [1,2,2,3], [0,0,1,2], [1.,1.,1.,1.], fixture["parameters"],
        )
        called.extend(["eval_intensity", "compute_parent_state"])

    elif stage == "LOCATION_AND_FAULT_ASSIGNMENT_PERTURBATION":
        base = np.asarray([[0.,0.],[1.,0.],[2.,0.],[3.,0.]], dtype=np.float64)
        perturb = rng.normal(0.0, 0.05, size=base.shape).astype(np.float64)
        points = base + perturb
        line_a_y = np.zeros(4, dtype=np.float64)
        line_b_y = np.ones(4, dtype=np.float64)
        distance_a = np.abs(points[:,1] - line_a_y)
        distance_b = np.abs(points[:,1] - line_b_y)
        assignment = (distance_b < distance_a).astype(np.int64)
        outputs["perturbed_points"] = points
        outputs["assignment"] = assignment
        outputs["location_operator_id"] = job["location_operator_id"]
        called.append("seeded_rng")

    elif stage == "MOVING_BLOCK_BOOTSTRAP_TRAIN_PLUS_CALIBRATION":
        outputs["indices"] = op.moving_block_resample(
            np.arange(100, dtype=np.float64), span_days=60.0, rng=rng,
        )
        called.append("moving_block_resample")

    elif stage == "HOLM_MULTIPLICITY_AGGREGATION":
        outputs["adjusted_p"] = holm_adjust([0.001,0.01,0.02,0.2,0.8])
        called.append("holm_adjust")

    elif stage == "RUNTIME_QUALIFICATION_ADJUDICATION":
        counts = Counter(record["status"] for record in completed)
        outputs["upstream_job_count"] = len(completed)
        outputs["upstream_status_counts"] = dict(counts)
        outputs["all_upstream_pass"] = len(completed) == EXPECTED_JOB_COUNT - 1 and counts.get("PASS", 0) == EXPECTED_JOB_COUNT - 1
        if outputs["all_upstream_pass"] is not True:
            raise RuntimeError("adjudication reached before all upstream jobs passed")
        called.append("qualification_precheck")
    else:
        raise RuntimeError(f"unknown job stage: {stage}")

    if binding and not set(binding).issubset(set(called)):
        raise RuntimeError(f"not all bound operators executed for {job['job_id']}: binding={binding}, called={called}")

    normalized = normalize(outputs)
    diagnostics = {
        "structural_fixture_only": True,
        "scientific_execution": False,
        "scientific_data_accessed": False,
        "sealed_test_accessed": False,
        "stage": stage,
        "family": family,
        "declared_operator_binding": binding,
        "called_operators": called,
        "dependency_selector_satisfied": True,
        "output_structure_sha256": sha256_bytes(canonical_bytes(normalized)),
    }
    return normalized, diagnostics

def result_record(job: Mapping[str, Any], *, output: Any, diagnostics: Mapping[str, Any], input_hashes: Mapping[str, str]) -> dict[str, Any]:
    return {
        "job_id": job["job_id"],
        "seed": job["seed"],
        "runtime_contract_id": job["runtime_contract_id"],
        "protocol_id": job["protocol_id"],
        "stage": job["stage"],
        "cohort": job["cohort"],
        "family": job["family"],
        "replicate": job["replicate"],
        "status": "PASS",
        "input_hashes": dict(input_hashes),
        "output_sha256": sha256_bytes(canonical_bytes(output)),
        "operator_diagnostics": dict(diagnostics),
        "sealed_test_accessed": False,
        "scientific_result": None,
    }

def execute_pass(*, jobs, runtime, op, fixture_sha256: str, runtime_sha256: str, operator_sha256: str) -> tuple[list[dict[str, Any]], Counter[str]]:
    records: list[dict[str, Any]] = []
    operator_counts: Counter[str] = Counter()
    for job in jobs:
        output, diagnostics = execute_job(job, op, records)
        for name in diagnostics["called_operators"]:
            operator_counts[name] += 1
        input_hashes = {
            "job_identity": sha256_bytes(canonical_bytes(job)),
            "fixture_contract": fixture_sha256,
            "runtime_source": runtime_sha256,
            "operator_source": operator_sha256,
        }
        records.append(result_record(job, output=output, diagnostics=diagnostics, input_hashes=input_hashes))
    adjudication = runtime.qualification_status(jobs, records)
    if adjudication.get("outcome") != runtime.QUALIFICATION_PASS:
        raise RuntimeError(f"qualification_status did not PASS: {adjudication}")
    return records, operator_counts

def jsonl_bytes(records: Sequence[Mapping[str, Any]]) -> bytes:
    return b"".join(canonical_bytes(record) + b"\n" for record in records)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, required=True)
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()

    repo = args.repo_root.resolve()
    root = args.root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    predecessor_root = repo / "construct_successors/KCH_HELICAL_V0173_DETERMINISTIC_FREEZE_IDENTITY_20261012"
    runtime_path = predecessor_root / "src/kch_helical_null_v017/runtime.py"
    operator_path = repo / "construct_successors/KCH_HELICAL_V016_EXPLICIT_NULL_OPERATOR_QUALIFICATION_20261011/null_perturbation_operators_v016.py"
    operator_receipt_path = repo / "construct_successors/KCH_HELICAL_V016_EXPLICIT_NULL_OPERATOR_QUALIFICATION_20261011/receipts/EXPLICIT_NULL_OPERATOR_QUALIFICATION_RECEIPT_V0_16.json"
    predecessor_receipt_path = predecessor_root / "receipts/DETERMINISTIC_FREEZE_RECEIPT_V0_17_3.json"
    predecessor_validation_path = predecessor_root / "receipts/DETERMINISTIC_FREEZE_VALIDATION_V0_17_3.json"
    summary_path = predecessor_root / "generated/NULL_PERTURBATION_JOB_LEDGER_SUMMARY_V0_17.json"
    ledger_path = predecessor_root / "generated/NULL_PERTURBATION_JOB_LEDGER_V0_17.jsonl"

    if np.__version__ != EXPECTED_NUMPY_VERSION:
        raise RuntimeError(f"NumPy version mismatch: {np.__version__} != {EXPECTED_NUMPY_VERSION}")
    if sha256_file(runtime_path) != EXPECTED_RUNTIME_SHA256:
        raise RuntimeError("v0.17 runtime source SHA-256 mismatch")
    if sha256_file(operator_path) != EXPECTED_OPERATOR_SHA256:
        raise RuntimeError("v0.16 operator source SHA-256 mismatch")

    predecessor = load_json(predecessor_receipt_path)
    predecessor_validation = load_json(predecessor_validation_path)
    summary = load_json(summary_path)
    operator_receipt = load_json(operator_receipt_path)
    if predecessor["status"] != "PASS" or predecessor["double_freeze_identity"] != "PASS":
        raise RuntimeError("v0.17.3 predecessor is not deterministic PASS")
    if predecessor_validation["status"] != "PASS" or predecessor_validation["receipt_id"] != predecessor["receipt_id"]:
        raise RuntimeError("v0.17.3 validation linkage mismatch")
    if predecessor["runtime_contract_id"] != EXPECTED_RUNTIME_CONTRACT_ID:
        raise RuntimeError("runtime contract ID mismatch")
    if predecessor["job_ledger_id"] != EXPECTED_LEDGER_ID or predecessor["job_ledger_sha256"] != EXPECTED_LEDGER_SHA256:
        raise RuntimeError("v0.17 job ledger identity mismatch")
    if sha256_file(ledger_path) != EXPECTED_LEDGER_SHA256:
        raise RuntimeError("v0.17 job ledger bytes mismatch")
    if summary["job_count"] != EXPECTED_JOB_COUNT or summary["seed_unique_count"] != EXPECTED_JOB_COUNT:
        raise RuntimeError("v0.17 ledger census mismatch")
    if operator_receipt["status"] != "EXPLICIT_NULL_OPERATOR_QUALIFICATION_PASS":
        raise RuntimeError("v0.16 operator qualification is not PASS")
    if operator_receipt["module_sha256"] != EXPECTED_OPERATOR_SHA256:
        raise RuntimeError("operator receipt/source mismatch")
    if operator_receipt["numpy_version"] != EXPECTED_NUMPY_VERSION:
        raise RuntimeError("operator qualification NumPy version mismatch")

    runtime = load_module("kch_helical_null_v017_runtime_qualification", runtime_path)
    op = load_module("kch_helical_null_v016_operator_qualification", operator_path)

    jobs = []
    for line_number, line in enumerate(ledger_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise RuntimeError(f"ledger line {line_number} is not an object")
        jobs.append(row)
    if len(jobs) != EXPECTED_JOB_COUNT:
        raise RuntimeError(f"ledger row count mismatch: {len(jobs)}")
    runtime.validate_job_ledger(jobs, expected_contract_id=EXPECTED_RUNTIME_CONTRACT_ID)

    fixture = fixture_contract()
    fixture_sha256 = sha256_bytes(canonical_bytes(fixture))
    write_json(output / "STRUCTURAL_FIXTURE_CONTRACT_V0_17_4.json", fixture)

    records_a, calls_a = execute_pass(
        jobs=jobs,
        runtime=runtime,
        op=op,
        fixture_sha256=fixture_sha256,
        runtime_sha256=EXPECTED_RUNTIME_SHA256,
        operator_sha256=EXPECTED_OPERATOR_SHA256,
    )
    bytes_a = jsonl_bytes(records_a)

    records_b, calls_b = execute_pass(
        jobs=jobs,
        runtime=runtime,
        op=op,
        fixture_sha256=fixture_sha256,
        runtime_sha256=EXPECTED_RUNTIME_SHA256,
        operator_sha256=EXPECTED_OPERATOR_SHA256,
    )
    bytes_b = jsonl_bytes(records_b)

    if bytes_a != bytes_b:
        raise RuntimeError("double qualification result ledger identity failed")
    if calls_a != calls_b:
        raise RuntimeError("double qualification operator-call census mismatch")

    result_path = output / "QUALIFICATION_RESULTS_V0_17_4.jsonl"
    result_path.write_bytes(bytes_a)
    result_sha256 = sha256_bytes(bytes_a)

    adjudication = runtime.qualification_status(jobs, records_a)
    if adjudication.get("outcome") != runtime.QUALIFICATION_PASS:
        raise RuntimeError(f"final qualification adjudication failed: {adjudication}")

    stage_counts = Counter(record["stage"] for record in records_a)
    family_counts = Counter(
        record["family"] for record in records_a
        if record["stage"] == "NULL_CALIBRATION_REPLICATE"
    )
    pass_count = sum(record["status"] == "PASS" for record in records_a)
    sealed_count = sum(bool(record["sealed_test_accessed"]) for record in records_a)
    scientific_result_count = sum(record["scientific_result"] is not None for record in records_a)
    structural_fixture_flags = sum(
        record["operator_diagnostics"].get("structural_fixture_only") is True
        for record in records_a
    )
    scientific_execution_flags = sum(
        record["operator_diagnostics"].get("scientific_execution") is True
        for record in records_a
    )

    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_17_4_FULL_RUNTIME_QUALIFICATION_RECEIPT",
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "github_sha": os.environ.get("GITHUB_SHA"),
        "predecessor_receipt_id": predecessor["receipt_id"],
        "predecessor_validation_id": predecessor_validation["validation_id"],
        "predecessor_double_freeze_identity": predecessor["double_freeze_identity"],
        "runtime_contract_id": EXPECTED_RUNTIME_CONTRACT_ID,
        "job_ledger_id": EXPECTED_LEDGER_ID,
        "job_ledger_sha256": EXPECTED_LEDGER_SHA256,
        "runtime_source_sha256": EXPECTED_RUNTIME_SHA256,
        "operator_source_sha256": EXPECTED_OPERATOR_SHA256,
        "operator_qualification_receipt_id": operator_receipt["receipt_id"],
        "numpy_version": np.__version__,
        "fixture_contract_sha256": fixture_sha256,
        "scheduled_job_count": len(jobs),
        "executed_job_count_each_pass": len(records_a),
        "qualification_pass_count": 2,
        "result_ledger_double_execution_identity": "PASS",
        "result_ledger_bytes": len(bytes_a),
        "result_ledger_sha256": result_sha256,
        "stage_counts": dict(stage_counts),
        "null_family_counts": dict(family_counts),
        "operator_call_counts": dict(sorted(calls_a.items())),
        "status_pass_count": pass_count,
        "status_not_run_count": len(records_a) - pass_count,
        "sealed_test_access_count": sealed_count,
        "scientific_result_count": scientific_result_count,
        "structural_fixture_only_count": structural_fixture_flags,
        "scientific_execution_true_count": scientific_execution_flags,
        "qualification_adjudication": adjudication,
        "historical_v0_13_identity_transfer": False,
        "scientific_data_accessed": False,
        "calibration_scientific_data_accessed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "status": "PASS",
        "next_gate": "FINITE_REAL_CALIBRATION_INPUT_BINDING_GATE_NO_TEST_ACCESS",
    }
    body["receipt_id"] = "h174qual:" + sha256_bytes(canonical_bytes(body))
    write_json(output / "FULL_RUNTIME_QUALIFICATION_RECEIPT_V0_17_4.json", body)

    validation = {
        "format": "KCH_HELICAL_V0_17_4_FULL_RUNTIME_QUALIFICATION_VALIDATION",
        "status": "PASS",
        "receipt_id": body["receipt_id"],
        "checks": {
            "predecessor_double_freeze_pass": True,
            "runtime_source_identity": True,
            "operator_source_identity": True,
            "operator_qualification_pass": True,
            "numpy_version_frozen": True,
            "job_ledger_identity": True,
            "job_census_6376": len(jobs) == EXPECTED_JOB_COUNT,
            "first_pass_all_jobs_executed": len(records_a) == EXPECTED_JOB_COUNT,
            "second_pass_all_jobs_executed": len(records_b) == EXPECTED_JOB_COUNT,
            "all_records_pass": pass_count == EXPECTED_JOB_COUNT,
            "all_records_have_hashes": all(bool(r["input_hashes"]) and len(r["output_sha256"]) == 64 for r in records_a),
            "all_records_have_operator_diagnostics": all(bool(r["operator_diagnostics"]) for r in records_a),
            "double_execution_result_identity": bytes_a == bytes_b,
            "operator_call_census_replay_identity": calls_a == calls_b,
            "runtime_qualification_pass": adjudication.get("outcome") == runtime.QUALIFICATION_PASS,
            "all_records_structural_fixture_only": structural_fixture_flags == EXPECTED_JOB_COUNT,
            "no_scientific_execution": scientific_execution_flags == 0,
            "no_scientific_data_access": True,
            "no_sealed_test_access": sealed_count == 0,
            "no_scientific_result": scientific_result_count == 0,
            "historical_identity_not_transferred": True,
        },
    }
    validation["validation_id"] = "h174validation:" + sha256_bytes(canonical_bytes(validation))
    write_json(output / "FULL_RUNTIME_QUALIFICATION_VALIDATION_V0_17_4.json", validation)

    summary_out = {
        "format": "KCH_HELICAL_V0_17_4_QUALIFICATION_SUMMARY",
        "receipt_id": body["receipt_id"],
        "validation_id": validation["validation_id"],
        "runtime_contract_id": EXPECTED_RUNTIME_CONTRACT_ID,
        "job_ledger_id": EXPECTED_LEDGER_ID,
        "scheduled_jobs": EXPECTED_JOB_COUNT,
        "executed_jobs_total_across_two_passes": 2 * EXPECTED_JOB_COUNT,
        "result_ledger_sha256": result_sha256,
        "qualification_outcome": adjudication["outcome"],
        "operator_call_counts": dict(sorted(calls_a.items())),
        "scientific_data_accessed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "next_gate": body["next_gate"],
    }
    write_json(output / "QUALIFICATION_SUMMARY_V0_17_4.json", summary_out)

    print(json.dumps({
        "receipt_id": body["receipt_id"],
        "validation_id": validation["validation_id"],
        "scheduled_jobs": EXPECTED_JOB_COUNT,
        "executed_jobs_total": 2 * EXPECTED_JOB_COUNT,
        "result_ledger_sha256": result_sha256,
        "qualification_outcome": adjudication["outcome"],
        "operator_call_counts": dict(sorted(calls_a.items())),
    }, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
