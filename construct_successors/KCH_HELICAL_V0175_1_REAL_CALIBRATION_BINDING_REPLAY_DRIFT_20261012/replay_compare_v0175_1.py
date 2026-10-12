from __future__ import annotations
import math
from typing import Any

FLOAT_KEYS={
"M0","background_rate_per_day","branching_ratio_proxy","c_days",
"magnitude_scaling","network_length_km","network_length_scale_km",
"objective","p","productivity","train_duration_days"}
INTEGER_KEYS={"train_candidate_edge_count","train_event_count"}
CAL_FLOAT_KEYS={
"network_length_km","train_parent_candidate_fraction",
"calibration_parent_candidate_fraction",
"calibration_mean_log_intensity_gain_vs_background",
"calibration_mean_background_probability",
"calibration_median_max_parent_probability"}
CAL_INTEGER_KEYS={
"train_count","calibration_count","test_count","selected_fault_line_count",
"train_top20_edge_count","calibration_top20_edge_count"}

def close(a:float,b:float,abs_tol:float,rel_tol:float):
    av=float(a);bv=float(b);delta=abs(av-bv);limit=max(abs_tol,rel_tol*abs(bv))
    return delta<=limit,delta,limit

def compare_parameter_lock(historical:dict[str,Any], replay:dict[str,Any], contract:dict[str,Any]):
    abs_tol=float(contract["float_acceptance"]["absolute_tolerance"])
    rel_tol=float(contract["float_acceptance"]["relative_tolerance"])
    obj_abs=float(contract["objective_acceptance"]["absolute_tolerance"])
    obj_rel=float(contract["objective_acceptance"]["relative_tolerance"])
    details={};all_pass=True
    for cohort,hparams in historical["cohorts"].items():
        rparams=replay["cohorts"].get(cohort)
        if not isinstance(rparams,dict):
            details[cohort]={"pass":False,"missing":True};all_pass=False;continue
        fields={}
        for key in sorted(set(hparams)|set(rparams)):
            hv=hparams.get(key);rv=rparams.get(key)
            if key=="start_objectives":
                comps=[]
                if not isinstance(hv,list) or not isinstance(rv,list) or len(hv)!=len(rv):
                    fields[key]={"pass":False,"historical":hv,"replay":rv};all_pass=False;continue
                for i,(a,b) in enumerate(zip(rv,hv)):
                    ok,d,l=close(a,b,obj_abs,obj_rel)
                    comps.append({"index":i,"pass":ok,"historical":b,"replay":a,"absolute_delta":d,"limit":l})
                    all_pass=all_pass and ok
                fields[key]={"pass":all(x["pass"] for x in comps),"comparisons":comps}
            elif key in FLOAT_KEYS:
                aa,rr=(obj_abs,obj_rel) if key=="objective" else (abs_tol,rel_tol)
                ok,d,l=close(rv,hv,aa,rr);all_pass=all_pass and ok
                fields[key]={"pass":ok,"historical":hv,"replay":rv,"absolute_delta":d,"limit":l}
            elif key in INTEGER_KEYS:
                ok=int(rv)==int(hv);all_pass=all_pass and ok
                fields[key]={"pass":ok,"historical":hv,"replay":rv}
            else:
                ok=rv==hv;all_pass=all_pass and ok
                fields[key]={"pass":ok,"historical":hv,"replay":rv}
        details[cohort]={"pass":all(v["pass"] for v in fields.values()),"fields":fields}
    return all_pass,details

def compare_calibration(historical:dict[str,Any], replay:dict[str,Any], contract:dict[str,Any]):
    abs_tol=float(contract["calibration_metric_float_acceptance"]["absolute_tolerance"])
    rel_tol=float(contract["calibration_metric_float_acceptance"]["relative_tolerance"])
    hrows={x["cohort"]:x for x in historical["unit_results"]}
    rrows={x["cohort"]:x for x in replay["unit_results"]}
    details={};all_pass=True
    for cohort,hrow in hrows.items():
        rrow=rrows.get(cohort)
        if not isinstance(rrow,dict):
            details[cohort]={"pass":False,"missing":True};all_pass=False;continue
        fields={}
        keys=CAL_FLOAT_KEYS|CAL_INTEGER_KEYS|{"parent_graph_lock_pass","test_values_scored"}
        for key in sorted(keys):
            hv=hrow[key];rv=rrow[key]
            if key in CAL_FLOAT_KEYS:
                ok,d,l=close(rv,hv,abs_tol,rel_tol)
                fields[key]={"pass":ok,"historical":hv,"replay":rv,"absolute_delta":d,"limit":l}
            elif key in CAL_INTEGER_KEYS:
                ok=int(rv)==int(hv);fields[key]={"pass":ok,"historical":hv,"replay":rv}
            else:
                ok=rv==hv;fields[key]={"pass":ok,"historical":hv,"replay":rv}
            all_pass=all_pass and ok
        details[cohort]={"pass":all(v["pass"] for v in fields.values()),"fields":fields}
    return all_pass,details
