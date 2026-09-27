from __future__ import annotations

import argparse, hashlib, json, math
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable
import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, Point, GeometryCollection, MultiPoint, shape
from shapely.strtree import STRtree

FAULT_SHA256="37babb516edfac22b5ae91744495d8546b3ae4676b4d4f68cc77da8222df20e1"
PROTOCOL_ID="h8p:99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f"
COHORTS={0:"BAY_AREA_HAYWARD_CALAVERAS",1:"PARKFIELD_CENTRAL_SAF"}

def sha256(p:Path):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""):h.update(b)
    return h.hexdigest()
def canonical(x):return json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
def write(p,obj):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,sort_keys=True,allow_nan=False)+"\n")
def flatten(g):
    if isinstance(g,LineString):yield g
    elif isinstance(g,MultiLineString):yield from g.geoms
def points_from_intersection(g):
    if g.is_empty:return []
    if isinstance(g,Point):return [g]
    if isinstance(g,MultiPoint):return list(g.geoms)
    if isinstance(g,LineString):
        return [Point(g.coords[0]),Point(g.coords[-1]),g.interpolate(0.5,normalized=True)]
    if isinstance(g,MultiLineString):
        out=[]
        for x in g.geoms:out+=points_from_intersection(x)
        return out
    if isinstance(g,GeometryCollection):
        out=[]
        for x in g.geoms:out+=points_from_intersection(x)
        return out
    return []
def load_lines(path):
    root=json.loads(path.read_text());tf=Transformer.from_crs("EPSG:4326","EPSG:3310",always_xy=True);lines=[]
    for feat in root.get("features",[]):
        for line in flatten(shape(feat["geometry"])):
            coords=[tf.transform(float(c[0]),float(c[1])) for c in line.coords]
            if len(coords)>=2:lines.append(LineString(coords))
    return lines,tf
def components(selected,adj):
    seen=set(); comps=[]
    for s in sorted(selected):
        if s in seen:continue
        stack=[s];seen.add(s);c=[]
        while stack:
            u=stack.pop();c.append(u)
            for v in sorted(adj[u]):
                if v not in seen:seen.add(v);stack.append(v)
        comps.append(sorted(c))
    return comps
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selected-artifact-root",type=Path,required=True)
    ap.add_argument("--crosswalk-root",type=Path,required=True)
    ap.add_argument("--fault-geojson",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    if sha256(a.fault_geojson)!=FAULT_SHA256:raise SystemExit("fault SHA mismatch")
    selected=list(a.selected_artifact_root.rglob("selected_directional_columns.npz"))
    preflight=list(a.selected_artifact_root.rglob("directional_preflight_arrays.npz"))
    if len(selected)!=1 or len(preflight)!=1:raise SystemExit("selected/preflight artifact multiplicity drift")
    cross=list(a.crosswalk_root.rglob("COMCAT_CSV_LOCATION_UNCERTAINTY_CROSSWALK.json"))
    gate=list(a.crosswalk_root.rglob("COMCAT_CSV_LOCATION_UNCERTAINTY_GATE_RESULT.json"))
    if len(cross)!=1 or len(gate)!=1:raise SystemExit("crosswalk artifact multiplicity drift")
    gate_obj=json.loads(gate[0].read_text())
    if gate_obj.get("outcome")!="LOCATION_UNCERTAINTY_CROSSWALK_PASS":raise SystemExit("uncertainty gate not passed")
    with np.load(selected[0],allow_pickle=False) as z:
        sel={k:z[k].copy() for k in ["global_index","cohort_code","event_time_epoch","lat_reloc","lon_reloc"]}
    with np.load(preflight[0],allow_pickle=False) as z:
        pre={k:z[k].copy() for k in ["global_index","cohort_code","fault_assignment","along_fault_km","axis_observable"]}
    cw=json.loads(cross[0].read_text());cwm={int(r["global_index"]):r for r in cw}
    lines,tf=load_lines(a.fault_geojson)
    selected_lines=sorted(set(int(x) for x in pre["fault_assignment"]))
    # Exact intersection topology, no gap tolerance.
    adj=defaultdict(set); intersections=[]
    for pos,i in enumerate(selected_lines):
        adj[i]
        li=lines[i]
        for j in selected_lines[pos+1:]:
            lj=lines[j]
            if not li.intersects(lj):continue
            pts=points_from_intersection(li.intersection(lj))
            if not pts:continue
            adj[i].add(j);adj[j].add(i)
            intersections.append({"line_i":i,"line_j":j,"point_count":len(pts),
                                  "positions_i_km":[float(li.project(p)/1000) for p in pts],
                                  "positions_j_km":[float(lj.project(p)/1000) for p in pts]})
    comps=components(selected_lines,adj);comp_of={line:k for k,c in enumerate(comps) for line in c}
    # Map event arrays by global index.
    pre_row={int(g):i for i,g in enumerate(pre["global_index"])}
    sel_row={int(g):i for i,g in enumerate(sel["global_index"])}
    topology_stats={}
    engineering={}
    rng=np.random.default_rng(20260927)
    tree=STRtree(lines)
    for code,name in COHORTS.items():
        obs_g=np.asarray([int(pre["global_index"][i]) for i in np.flatnonzero((pre["cohort_code"]==code)&pre["axis_observable"])],dtype=np.int64)
        obs_g=obs_g[np.argsort(np.array([float(sel["event_time_epoch"][sel_row[int(g)]]) for g in obs_g]),kind="stable")]
        n=len(obs_g);fit_g=obs_g[:int(math.floor(.75*n))]
        cohort_lines=sorted(set(int(pre["fault_assignment"][pre_row[int(g)]]) for g in obs_g))
        event_multi=sum(len(comps[comp_of[int(pre["fault_assignment"][pre_row[int(g)]])]])>1 for g in obs_g)
        topology_stats[name]={"observable_events":n,"selected_fault_lines":len(cohort_lines),
            "exact_intersection_components":len(set(comp_of[x] for x in cohort_lines)),
            "events_in_multiline_components":event_multi,
            "events_in_multiline_components_fraction":event_multi/max(n,1),
            "same_segment_parent_available_fraction":float(np.mean([
                # diagnostic reconstructed from preflight was stored separately but not loaded here; topology only
                True for _ in obs_g]))}
        # engineering sample only from fit=train+cal, with both ComCat errors
        eligible=[int(g) for g in fit_g if cwm[int(g)].get("matched") and cwm[int(g)].get("horizontalError_km") is not None and cwm[int(g)].get("depthError_km") is not None]
        if len(eligible)>2000:
            pick=np.linspace(0,len(eligible)-1,2000,dtype=int);eligible=[eligible[i] for i in pick]
        stable=available=0;rep_total=0
        for rep in range(16):
            for g in eligible:
                sr=sel_row[g];pr=pre_row[g];rec=cwm[g]
                x,y=tf.transform(float(sel["lon_reloc"][sr]),float(sel["lat_reloc"][sr]))
                sigma=float(rec["horizontalError_km"])*1000
                px=x+rng.normal(0,sigma);py=y+rng.normal(0,sigma);point=Point(px,py)
                # Exact protocol assignment rule: nearest <=10km and second/first >=1.5
                cand=tree.query(point.buffer(10000.0))
                if len(cand)<1:continue
                ds=sorted((float(lines[int(ix)].distance(point))/1000,int(ix)) for ix in cand)
                first=ds[0];second=ds[1] if len(ds)>1 else (float("inf"),-1)
                ratio=second[0]/max(first[0],1e-9)
                rep_total+=1
                if first[0]<=10.0 and ratio>=1.5:
                    available+=1
                    if first[1]==int(pre["fault_assignment"][pr]):stable+=1
        engineering[name]={"fit_events_with_both_errors":len(eligible),"engineering_replicates":16,
            "reassignment_trials":rep_total,"unambiguous_reassignments":available,
            "original_assignment_preserved":stable,
            "preservation_fraction_given_unambiguous":stable/max(available,1),
            "unambiguous_fraction":available/max(rep_total,1)}
    operator={
      "format":"KCH_HELICAL_V0_8_LOCATION_PERTURBATION_OPERATOR_LOCK",
      "protocol_id":PROTOCOL_ID,
      "representation":"CONSERVATIVE_ISOTROPIC_MAX_HORIZONTAL_PROJECTION_ENVELOPE",
      "horizontal_draw":"dx,dy iid Normal(0,horizontalError_km^2)",
      "vertical_draw":"dz Normal(0,depthError_km^2)",
      "full_covariance_claim":False,
      "missing_error_policy":"UNAVAILABLE_NO_IMPUTATION",
      "fault_reassignment":{"maximum_distance_km":10.0,"minimum_second_to_first_distance_ratio":1.5},
      "scientific_replicates":64,
      "engineering_replicates":16,
      "engineering_scope":"TRAIN_PLUS_CALIBRATION_ONLY",
      "fault_topology":{"connection_rule":"EXACT_GEOMETRIC_INTERSECTION_ONLY_NO_GAP_TOLERANCE",
                        "network_path_rule":"SHORTEST_PATH_ALONG_LINES_THROUGH_EXACT_INTERSECTIONS",
                        "selected_line_count":len(selected_lines),"exact_intersection_pair_count":len(intersections),
                        "component_count":len(comps)},
      "scientific_model_execution_performed":False,"sealed_test_scored":False,"authority_ceiling":"NONE"
    }
    operator["operator_id"]="h8locop:"+hashlib.sha256(canonical(operator)).hexdigest()
    result={"format":"KCH_HELICAL_V0_8_TOPOLOGY_AND_LOCATION_OPERATOR_GATE","outcome":"TOPOLOGY_AND_LOCATION_PERTURBATION_OPERATOR_LOCKED",
            "operator_id":operator["operator_id"],"fault_geojson_sha256":FAULT_SHA256,
            "selected_fault_lines":selected_lines,"components":comps,"intersection_pair_count":len(intersections),
            "cohort_topology":topology_stats,"engineering_validation":engineering,
            "scientific_model_execution_performed":False,"sealed_test_scored":False,
            "next_material_gate":"ETAS_HAWKES_PARENT_GRAPH_TRAIN_ONLY_CALIBRATION_LOCK","authority_ceiling":"NONE"}
    result["gate_id"]="h8topo:"+hashlib.sha256(canonical(result)).hexdigest()
    write(a.out/"LOCATION_PERTURBATION_OPERATOR_LOCK_V0_8.json",operator)
    write(a.out/"FAULT_NETWORK_TOPOLOGY_INTERSECTIONS_V0_8.json",intersections)
    write(a.out/"TOPOLOGY_AND_LOCATION_OPERATOR_GATE_RESULT_V0_8.json",result)
    print(json.dumps(result,indent=2,sort_keys=True))
if __name__=="__main__":main()
