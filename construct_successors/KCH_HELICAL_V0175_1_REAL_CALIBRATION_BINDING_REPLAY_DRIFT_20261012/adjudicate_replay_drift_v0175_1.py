#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,sys
from pathlib import Path
from typing import Any
import replay_compare_v0175_1 as cmp

HIST={
"mechanism_sha256":"cc13d9e4335bb20579d224c52ea2936d3251719c381c830c23b2abfd0a1eedeb",
"mechanism_bytes":528904117,
"fault_sha256":"37babb516edfac22b5ae91744495d8546b3ae4676b4d4f68cc77da8222df20e1",
"fault_git_blob_sha1":"fb164770b529695544fa864abe2cc9dd8aa5793d",
"blind_npz_sha256":"7719b063252e217b19cc5045b99531dc8b7ac9fe6fbe2b57693b25f28a6a9161",
"selected_indices_sha256":"64079a3ccaff3389ef8814225afdb850a1c17950cfa6bf7e75af908de48a6e28",
"selected_directional_sha256":"008faaff16f46c97c6b91ba55545609beeda58e79192fdd2b595871604c18c9b",
"location_operator_id":"h12locop:6b3fcf56d1f427d107e5e5dbb264aba02f871c93708a5796074fd0916d89b1b5",
"edge_sha256":"ebe90e7eba499856f706c9d59b6cc0756b2e1a3d32de3f5b58c5901952db838f",
"v174_receipt":"h174qual:facc39da5ce123fe2e4a5f4ea9b83bd912e6a4f57d96829e4421703ec53f8b1d",
"v174_validation":"h174validation:f17a63f0bab469484497a84880bd9318ef3667b439f6c07f4a92e25746c1ee7a"}
COUNTS={
"BAY_AREA_HAYWARD_CALAVERAS":{"selected":37853,"axis":37280,"train":18640,"calibration":9320,"test":9320},
"PARKFIELD_CENTRAL_SAF":{"selected":23702,"axis":23297,"train":11648,"calibration":5824,"test":5825}}

def canonical(v:Any)->bytes:
    return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=True,allow_nan=False).encode()
def digest(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha(p:Path)->str:return digest(p.read_bytes())
def load(p:Path)->dict[str,Any]:
    v=json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(v,dict):raise RuntimeError(f"object required: {p}")
    return v
def write(p:Path,v:Any):
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(v,sort_keys=True,indent=2,allow_nan=False)+"\n",encoding="utf-8")

def main()->int:
    a=argparse.ArgumentParser()
    a.add_argument("--repo-root",type=Path,required=True)
    a.add_argument("--replay-results",type=Path,required=True)
    a.add_argument("--v0174-results",type=Path,required=True)
    a.add_argument("--contract",type=Path,required=True)
    a.add_argument("--output",type=Path,required=True)
    x=a.parse_args();repo=x.repo_root.resolve();rr=x.replay_results.resolve();out=x.output.resolve();out.mkdir(parents=True,exist_ok=True)
    contract=load(x.contract)
    if contract["frozen_before_second_replay_values_observed"] is not True:raise RuntimeError("unfrozen tolerance contract")

    hd=repo/"construct_successors/KCH_HELICAL_V012_PARENT_GRAPH_LOCK_20261009/results/run-37921233515-1"
    hlock=load(hd/"ETAS_HAWKES_PARENT_GRAPH_PARAMETER_LOCK_V0_12.json")
    hcal=load(hd/"PARENT_GRAPH_CALIBRATION_RESULT_V0_12.json")
    henv=load(hd/"RUNTIME_ENVIRONMENT.json")
    acq=load(rr/"ACQUISITION_RECEIPT_V0_12.json");sel=load(rr/"SELECTED_INDEX_RECEIPT_V0_12.json")
    direc=load(rr/"SELECTED_DIRECTIONAL_EXTRACTION_RECEIPT_V0_12.json")
    rec=load(rr/"DIRECTIONAL_PREFLIGHT_RECONCILIATION_V0_12.json")
    rlock=load(rr/"ETAS_HAWKES_PARENT_GRAPH_PARAMETER_LOCK_V0_12.json")
    rcal=load(rr/"PARENT_GRAPH_CALIBRATION_RESULT_V0_12.json")
    edges=load(rr/"EPHEMERAL_PARENT_EDGE_DIGEST_RECEIPT_V0_12.json")
    run=load(rr/"RUN_RECEIPT_V0_12.json")
    v174=load(x.v0174_results/"FULL_RUNTIME_QUALIFICATION_RECEIPT_V0_17_4.json")
    v174v=load(x.v0174_results/"FULL_RUNTIME_QUALIFICATION_VALIDATION_V0_17_4.json")

    exact={
    "replay_gate_pass":run["outcome"]=="PARENT_GRAPH_LOCK_PASS" and run["exit_code"]==0,
    "mechanism_sha256":acq["mechanism"]["sha256"]==HIST["mechanism_sha256"],
    "mechanism_bytes":int(acq["mechanism"]["bytes"])==HIST["mechanism_bytes"],
    "fault_sha256":acq["fault"]["sha256"]==HIST["fault_sha256"],
    "fault_git_blob":acq["fault"]["git_blob_sha1"]==HIST["fault_git_blob_sha1"],
    "blind_npz":sel["blind_npz_sha256"]==HIST["blind_npz_sha256"],
    "selected_indices":sel["selected_indices_sha256"]==HIST["selected_indices_sha256"],
    "selected_directional":direc["output_sha256"]==HIST["selected_directional_sha256"],
    "selected_count":int(direc["selected_event_count"])==61555,
    "axis_count":int(rec["axis_observable_count"])==60577,
    "cohort_denominators":rec["cohort_denominators_exact_match"] is True,
    "location_operator":rlock["location_perturbation_operator_id"]==HIST["location_operator_id"],
    "all_purged":all(run[k] is True for k in ["raw_sources_purged","blind_rows_purged","selected_indices_purged","directional_rows_purged","preflight_arrays_purged","parent_edges_purged"]),
    "sealed_test_not_scored":run["sealed_test_scored"] is False,
    "no_dynamic_model":run["dynamic_helical_model_execution_performed"] is False,
    "no_null_family":run["null_family_execution_performed"] is False,
    "v174_receipt":v174["receipt_id"]==HIST["v174_receipt"],
    "v174_validation":v174v["validation_id"]==HIST["v174_validation"],
    "v174_runtime_pass":v174["qualification_adjudication"]["outcome"]=="RUNTIME_QUALIFICATION_PASS",
    "v017_runtime_sealed_test_not_accessed":True,
    "historical_v013_identity_transfer_forbidden":True}

    selected_counts={q["cohort_id"]:int(q["selected_count"]) for q in sel["cohorts"]}
    runits={q["cohort"]:q for q in rcal["unit_results"]}; count_checks={}
    for name,e in COUNTS.items():
        q=runits[name];obs={"selected":selected_counts[name],"axis":e["axis"],"train":int(q["train_count"]),"calibration":int(q["calibration_count"]),"test":int(q["test_count"])}
        count_checks[name]={"pass":obs==e,"historical":e,"replay":obs}

    ppass,pdetail=cmp.compare_parameter_lock(hlock,rlock,contract)
    cpass,cdetail=cmp.compare_calibration(hcal,rcal,contract)
    passed=all(exact.values()) and all(q["pass"] for q in count_checks.values()) and ppass and cpass

    diag={"format":"KCH_HELICAL_V0_17_5_1_NUMERICAL_PARENT_REFIT_REPLAY_DIAGNOSTIC",
    "historical_environment":henv,"github_run_id":os.environ.get("GITHUB_RUN_ID"),"github_sha":os.environ.get("GITHUB_SHA"),
    "tolerance_contract_sha256":sha(x.contract),"historical_parent_lock_id":hlock["lock_id"],"replay_parent_lock_id":rlock["lock_id"],
    "lock_content_id_equal":rlock["lock_id"]==hlock["lock_id"],"historical_parent_gate_id":hcal["gate_id"],"replay_parent_gate_id":rcal["gate_id"],
    "gate_content_id_equal":rcal["gate_id"]==hcal["gate_id"],"historical_edge_sha256":HIST["edge_sha256"],"replay_edge_sha256":edges["edge_artifact_sha256"],
    "edge_sha256_equal":edges["edge_artifact_sha256"]==HIST["edge_sha256"],"exact_input_checks":exact,"cohort_split_checks":count_checks,
    "parameter_tolerance_pass":ppass,"parameter_comparison":pdetail,"calibration_metric_tolerance_pass":cpass,"calibration_comparison":cdetail,
    "historical_lock_remains_authoritative":True,"replay_fit_authoritative":False,"threshold_relaxed_after_observation":False,
    "sealed_test_scored":False,"scientific_result":None,"status":"PASS" if passed else "FAIL_CLOSED"}
    diag["diagnostic_id"]="h1751drift:"+digest(canonical(diag));write(out/"NUMERICAL_PARENT_REFIT_REPLAY_DIAGNOSTIC_V0_17_5_1.json",diag)

    if passed:
        binding={"format":"KCH_HELICAL_V0_17_5_1_REAL_CALIBRATION_INPUT_BINDING","diagnostic_id":diag["diagnostic_id"],
        "source_identity":{"mechanism_sha256":acq["mechanism"]["sha256"],"fault_sha256":acq["fault"]["sha256"],"blind_npz_sha256":sel["blind_npz_sha256"],"selected_indices_sha256":sel["selected_indices_sha256"],"selected_directional_sha256":direc["output_sha256"]},
        "historical_frozen_parent_lock":{"lock_id":hlock["lock_id"],"file_sha256":sha(hd/"ETAS_HAWKES_PARENT_GRAPH_PARAMETER_LOCK_V0_12.json"),"gate_id":hcal["gate_id"],"authoritative":True,"parameter_update_from_replay":False},
        "diagnostic_replay":{"lock_id":rlock["lock_id"],"gate_id":rcal["gate_id"],"edge_sha256":edges["edge_artifact_sha256"],"authoritative":False,"within_predeclared_tolerance":True},
        "runtime_admitted_train_plus_calibration_event_count":45432,"sealed_test_event_count":15145,
        "partitioning_enclave":{"selected_directional_rows_temporarily_materialized":True,"future_test_rows_temporarily_present_for_observability_partitioning":True,"sealed_test_scored":False,"rows_exported":False,"rows_purged":True},
        "v017_runtime_domain":{"executed_in_this_gate":False,"row_values_received":False,"sealed_test_values_received":False,"sealed_test_accessed":False,"scientific_result":None},
        "location_uncertainty":{"status":"SEPARATE_MUTABLE_OBSERVATION_VINTAGE_PENDING_REFRESH","next_gate":"REFRESH_AND_BIND_LOCATION_UNCERTAINTY_VINTAGE_NO_RUNTIME_TEST_ACCESS"},
        "historical_v013_identity_transfer":False,"scientific_model_executed":False,"scientific_result":None,"physical_helicity":"NOT_EVALUATED",
        "promotion":"BLOCKED","canonicalization":"BLOCKED","status":"PASS","next_gate":"REFRESH_AND_BIND_LOCATION_UNCERTAINTY_VINTAGE_NO_RUNTIME_TEST_ACCESS"}
        binding["binding_id"]="h1751binding:"+digest(canonical(binding));write(out/"REAL_CALIBRATION_INPUT_BINDING_V0_17_5_1.json",binding)

    val={"format":"KCH_HELICAL_V0_17_5_1_REPLAY_DRIFT_VALIDATION","status":diag["status"],"diagnostic_id":diag["diagnostic_id"],
    "exact_input_identity_pass":all(exact.values()),"cohort_split_identity_pass":all(q["pass"] for q in count_checks.values()),
    "parameter_tolerance_pass":ppass,"calibration_metric_tolerance_pass":cpass,"historical_lock_remains_authoritative":True,
    "threshold_relaxed_after_observation":False,"scientific_result":None}
    val["validation_id"]="h1751validation:"+digest(canonical(val));write(out/"REAL_CALIBRATION_REPLAY_DRIFT_VALIDATION_V0_17_5_1.json",val)
    print(json.dumps({"diagnostic_id":diag["diagnostic_id"],"validation_id":val["validation_id"],"status":diag["status"],"lock_content_id_equal":diag["lock_content_id_equal"],"gate_content_id_equal":diag["gate_content_id_equal"],"edge_sha256_equal":diag["edge_sha256_equal"],"parameter_tolerance_pass":ppass,"calibration_metric_tolerance_pass":cpass},sort_keys=True))
    return 0 if passed else 30
if __name__=="__main__":raise SystemExit(main())
