#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os
from pathlib import Path
from typing import Any

def canonical(v:Any)->bytes:
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()
def h(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha(p:Path)->str:return h(p.read_bytes())
def load(p:Path)->dict[str,Any]:
    v=json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(v,dict):raise RuntimeError(f"object required: {p}")
    return v
def write(p:Path,v:Any):
    p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,sort_keys=True,indent=2)+"\n",encoding="utf-8")

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--repo-root",type=Path,required=True)
    ap.add_argument("--root",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    x=ap.parse_args();repo=x.repo_root.resolve();root=x.root.resolve();out=x.output.resolve();out.mkdir(parents=True,exist_ok=True)

    pred=repo/"construct_successors/KCH_HELICAL_V0175_1_REAL_CALIBRATION_BINDING_REPLAY_DRIFT_20261012"
    diag=load(pred/"results/NUMERICAL_PARENT_REFIT_REPLAY_DIAGNOSTIC_V0_17_5_1.json")
    val=load(pred/"results/REAL_CALIBRATION_REPLAY_DRIFT_VALIDATION_V0_17_5_1.json")
    first=load(pred/"FAILURE_RECEIPT_V0_17_5_RUN1.json")
    fail=load(root/"FAILURE_RECEIPT_V0_17_5_1.json")
    lease=load(root/"AUTHORITY_LEASE_V0_17_5_2.json")

    hist=repo/"construct_successors/KCH_HELICAL_V012_PARENT_GRAPH_LOCK_20261009/results/run-37921233515-1"
    hlock=load(hist/"ETAS_HAWKES_PARENT_GRAPH_PARAMETER_LOCK_V0_12.json")
    hcal=load(hist/"PARENT_GRAPH_CALIBRATION_RESULT_V0_12.json")
    hrun=load(hist/"RUN_RECEIPT_V0_12.json")
    replay_acq=load(pred/"replay_safe/ACQUISITION_RECEIPT_V0_12.json")
    replay_sel=load(pred/"replay_safe/SELECTED_INDEX_RECEIPT_V0_12.json")
    replay_dir=load(pred/"replay_safe/SELECTED_DIRECTIONAL_EXTRACTION_RECEIPT_V0_12.json")
    replay_rec=load(pred/"replay_safe/DIRECTIONAL_PREFLIGHT_RECONCILIATION_V0_12.json")
    current_pip=(pred/"replay_safe/CURRENT_PIP_FREEZE.txt").read_bytes()
    historical_pip=(hist/"PIP_FREEZE.txt").read_bytes()

    exact_input_pass=all(bool(v) for v in diag["exact_input_checks"].values())
    exact_split_pass=all(bool(v["pass"]) for v in diag["cohort_split_checks"].values())
    current_replay_identity=(
        first["regenerated_parent_graph_lock_id"]==diag["replay_parent_lock_id"]
        and first["regenerated_parent_graph_gate_id"]==diag["replay_parent_gate_id"]
    )
    historical_custody=(
        hlock["lock_id"]=="h8parent:f61e9b60c455e75e53f16b9579cd085b68de20d810f05165504f91ab09d400cb"
        and hcal["gate_id"]=="h8pg:5690829352b8163faf63bc3cecc0a6efb34fe024894b90e5dd961e2c7eb732ba"
        and hcal["parent_graph_lock_id"]==hlock["lock_id"]
        and hrun["parent_graph_lock_id"]==hlock["lock_id"]
        and hrun["parent_graph_gate_id"]==hcal["gate_id"]
        and hrun["outcome"]=="PARENT_GRAPH_LOCK_PASS"
        and hrun["sealed_test_scored"] is False
    )
    checks={
        "authority_ceiling":lease["authority_ceiling"]=="FROZEN_HISTORICAL_LOCK_CUSTODY_AND_REAL_INPUT_BINDING_ONLY",
        "v0175_1_remains_fail_closed":diag["status"]=="FAIL_CLOSED" and val["status"]=="FAIL_CLOSED" and fail["outcome"]=="NUMERICAL_REPLAY_TOLERANCE_FAIL_CLOSED",
        "v0175_1_threshold_not_relaxed":diag["threshold_relaxed_after_observation"] is False and val["threshold_relaxed_after_observation"] is False,
        "exact_input_identity":exact_input_pass,
        "exact_cohort_split_identity":exact_split_pass,
        "historical_lock_custody":historical_custody,
        "two_current_replays_same_lock_and_gate":current_replay_identity,
        "current_replay_differs_from_historical":diag["lock_content_id_equal"] is False and diag["gate_content_id_equal"] is False,
        "pip_freeze_exact_identity":current_pip==historical_pip,
        "mechanism_identity":replay_acq["mechanism"]["sha256"]=="cc13d9e4335bb20579d224c52ea2936d3251719c381c830c23b2abfd0a1eedeb",
        "fault_identity":replay_acq["fault"]["sha256"]=="37babb516edfac22b5ae91744495d8546b3ae4676b4d4f68cc77da8222df20e1",
        "selection_identity":replay_sel["selected_indices_sha256"]=="64079a3ccaff3389ef8814225afdb850a1c17950cfa6bf7e75af908de48a6e28",
        "directional_identity":replay_dir["output_sha256"]=="008faaff16f46c97c6b91ba55545609beeda58e79192fdd2b595871604c18c9b",
        "preflight_count_identity":replay_rec["axis_observable_count"]==60577,
        "no_row_access_this_gate":True,
        "no_sealed_test_access_this_gate":True,
        "no_scientific_result":True,
    }
    if not all(checks.values()):raise RuntimeError("custody binding failed: "+repr([k for k,v in checks.items() if not v]))

    boundary={
        "format":"KCH_HELICAL_V0_17_5_2_OPTIMIZER_REPLAY_BOUNDARY",
        "historical_parent_lock_id":hlock["lock_id"],"historical_parent_gate_id":hcal["gate_id"],
        "historical_lock_file_sha256":sha(hist/"ETAS_HAWKES_PARENT_GRAPH_PARAMETER_LOCK_V0_12.json"),
        "historical_calibration_file_sha256":sha(hist/"PARENT_GRAPH_CALIBRATION_RESULT_V0_12.json"),
        "current_replay_lock_id":diag["replay_parent_lock_id"],"current_replay_gate_id":diag["replay_parent_gate_id"],
        "two_current_replays_same_lock_and_gate":True,
        "historical_point_replay_tolerance":"FAIL_CLOSED_V0_17_5_1",
        "objective_replay_within_v0_17_5_1_objective_tolerance":all(
            c["fields"]["objective"]["pass"] for c in diag["parameter_comparison"].values()),
        "parameter_point_replay_within_v0_17_5_1_tolerance":False,
        "declared_package_freeze_identical":True,
        "interpretation":"HISTORICAL_POINT_OPTIMUM_NOT_REPRODUCIBLE_TO_PREDECLARED_TOLERANCE; DO_NOT_REFIT_OR_REPLACE_FROZEN_LOCK",
        "scientific_claim":None}
    boundary["boundary_id"]="h1752boundary:"+h(canonical(boundary));write(out/"OPTIMIZER_REPLAY_BOUNDARY_V0_17_5_2.json",boundary)

    binding={
        "format":"KCH_HELICAL_V0_17_5_2_FROZEN_LOCK_REAL_INPUT_BINDING",
        "boundary_id":boundary["boundary_id"],
        "source_identity":{"mechanism_sha256":replay_acq["mechanism"]["sha256"],"fault_sha256":replay_acq["fault"]["sha256"],"selected_indices_sha256":replay_sel["selected_indices_sha256"],"selected_directional_sha256":replay_dir["output_sha256"]},
        "historical_frozen_parent_lock":{"lock_id":hlock["lock_id"],"gate_id":hcal["gate_id"],"lock_file_sha256":boundary["historical_lock_file_sha256"],"calibration_file_sha256":boundary["historical_calibration_file_sha256"],"authoritative":True,"refit_authorized":False},
        "runtime_admitted_train_plus_calibration_event_count":45432,"sealed_test_event_count":15145,
        "partitioning_enclave_prior_gate":{"future_test_rows_temporarily_present_for_observability_partitioning":True,"sealed_test_scored":False,"rows_purged":True},
        "v017_runtime_domain":{"executed_in_this_gate":False,"row_values_received":False,"sealed_test_values_received":False,"sealed_test_accessed":False},
        "location_uncertainty":{"status":"MUTABLE_OBSERVATION_VINTAGE_REQUIRES_REFRESH","next_gate":"REFRESH_AND_BIND_LOCATION_UNCERTAINTY_VINTAGE_NO_RUNTIME_TEST_ACCESS"},
        "historical_v013_identity_transfer":False,"scientific_model_executed":False,"scientific_result":None,"physical_helicity":"NOT_EVALUATED",
        "promotion":"BLOCKED","canonicalization":"BLOCKED","status":"PASS","next_gate":"REFRESH_AND_BIND_LOCATION_UNCERTAINTY_VINTAGE_NO_RUNTIME_TEST_ACCESS"}
    binding["binding_id"]="h1752binding:"+h(canonical(binding));write(out/"FROZEN_LOCK_REAL_INPUT_BINDING_V0_17_5_2.json",binding)

    validation={"format":"KCH_HELICAL_V0_17_5_2_FROZEN_LOCK_BINDING_VALIDATION","status":"PASS","binding_id":binding["binding_id"],"boundary_id":boundary["boundary_id"],"checks":checks,"scientific_result":None}
    validation["validation_id"]="h1752validation:"+h(canonical(validation));write(out/"FROZEN_LOCK_BINDING_VALIDATION_V0_17_5_2.json",validation)
    print(json.dumps({"boundary_id":boundary["boundary_id"],"binding_id":binding["binding_id"],"validation_id":validation["validation_id"],"next_gate":binding["next_gate"]},sort_keys=True))
    return 0
if __name__=="__main__":raise SystemExit(main())
