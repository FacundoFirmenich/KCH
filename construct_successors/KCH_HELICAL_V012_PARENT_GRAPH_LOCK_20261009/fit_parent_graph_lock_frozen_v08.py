from __future__ import annotations

import argparse, hashlib, heapq, json, math
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Iterable
import numpy as np
from pyproj import Transformer
from scipy.optimize import minimize
from shapely.geometry import LineString, MultiLineString, shape

PROTOCOL_ID="h8p:99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f"
FAULT_SHA256="37babb516edfac22b5ae91744495d8546b3ae4676b4d4f68cc77da8222df20e1"
COHORTS={0:"BAY_AREA_HAYWARD_CALAVERAS",1:"PARKFIELD_CENTRAL_SAF"}
MAX_AGE_DAYS=30.0
MAX_PATH_KM=20.0
MAX_PARENT_CANDIDATES=20

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
def load_lengths(path):
    root=json.loads(path.read_text());tf=Transformer.from_crs("EPSG:4326","EPSG:3310",always_xy=True);lengths=[]
    for feat in root.get("features",[]):
        for line in flatten(shape(feat["geometry"])):
            coords=[tf.transform(float(c[0]),float(c[1])) for c in line.coords]
            if len(coords)>=2:lengths.append(LineString(coords).length/1000.0)
    return np.asarray(lengths,dtype=float)

class NetworkMetric:
    def __init__(self, lengths, intersections):
        self.lengths=lengths
        self.line_nodes=defaultdict(list)
        node_lines=[]
        for rec in intersections:
            for k in range(int(rec["point_count"])):
                node=len(node_lines)
                i=int(rec["line_i"]);j=int(rec["line_j"])
                pi=float(rec["positions_i_km"][k]);pj=float(rec["positions_j_km"][k])
                self.line_nodes[i].append((pi,node));self.line_nodes[j].append((pj,node))
                node_lines.append(((i,pi),(j,pj)))
        n=len(node_lines);inf=float("inf")
        D=np.full((n,n),inf);np.fill_diagonal(D,0.0)
        for line,items in self.line_nodes.items():
            items.sort()
            for (p1,n1),(p2,n2) in zip(items,items[1:]):
                d=abs(p2-p1)
                if d<D[n1,n2]:D[n1,n2]=D[n2,n1]=d
            # zero-cost links if multiple recorded intersection nodes share same position on same line
            for a in range(len(items)):
                for b in range(a+1,len(items)):
                    if abs(items[a][0]-items[b][0])<=1e-8:
                        D[items[a][1],items[b][1]]=D[items[b][1],items[a][1]]=0.0
        for k in range(n):
            D=np.minimum(D,D[:,k,None]+D[None,k,:])
        self.D=D
        # component id by finite node connectivity; singleton lines receive unique negative id
        self.line_component={}
        comp=0;seen=set()
        for line in sorted(self.line_nodes):
            if line in seen:continue
            stack=[line];seen.add(line)
            while stack:
                u=stack.pop();self.line_component[u]=comp
                nodes={node for _,node in self.line_nodes[u]}
                for v in self.line_nodes:
                    if v in seen:continue
                    if any(np.isfinite(self.D[a,b]) for a in nodes for _,b in self.line_nodes[v]):
                        seen.add(v);stack.append(v)
            comp+=1
    def distance(self,la,sa,lb,sb):
        la=int(la);lb=int(lb);sa=float(sa);sb=float(sb)
        best=abs(sa-sb) if la==lb else float("inf")
        A=self.line_nodes.get(la,());B=self.line_nodes.get(lb,())
        if not A or not B:return best
        if self.line_component.get(la)!=self.line_component.get(lb):return best
        for pa,na in A:
            va=abs(sa-pa)
            for pb,nb in B:
                d=self.D[na,nb]
                if np.isfinite(d):best=min(best,va+d+abs(sb-pb))
        return best

def build_edges(indices,times,faults,along,metric,max_age=MAX_AGE_DAYS,max_path=MAX_PATH_KM):
    times_d=times/86400.0
    child=[];parent=[];dt=[];dist=[]
    hist=deque()
    for cj,g in enumerate(indices):
        t=times_d[g]
        while hist and t-times_d[hist[0][1]]>max_age:hist.popleft()
        for pj,pg in hist:
            d=metric.distance(faults[g],along[g],faults[pg],along[pg])
            if d<=max_path and t>times_d[pg]:
                child.append(cj);parent.append(pj);dt.append(t-times_d[pg]);dist.append(d)
        hist.append((cj,g))
    return {k:np.asarray(v,dtype=(np.int64 if k in {"child","parent"} else np.float64)) for k,v in
            {"child":child,"parent":parent,"dt_days":dt,"distance_km":dist}.items()}

def unpack(x):
    mu=math.exp(x[0]);K=math.exp(x[1]);alpha=float(x[2]);c=math.exp(x[3]);p=1+math.exp(x[4]);ell=math.exp(x[5])
    return mu,K,alpha,c,p,ell

def kernels(dt,d,c,p,ell):
    den_t=1-(c/(c+MAX_AGE_DAYS))**(p-1)
    Ct=(p-1)*c**(p-1)/max(den_t,1e-15)
    gt=Ct*(dt+c)**(-p)
    den_s=ell*(1-math.exp(-MAX_PATH_KM/ell))
    gs=np.exp(-d/ell)/max(den_s,1e-15)
    return gt,gs

def fit_params(train_idx,times,mags,edges,network_length):
    n=len(train_idx); t=times[train_idx]/86400.0; m=mags[train_idx]
    T=max(float(t[-1]-t[0]),1e-6);M0=float(np.min(m))
    child=edges["child"];parent=edges["parent"];dt=edges["dt_days"];d=edges["distance_km"]
    parent_mag=m[parent]
    upper_mu=max(n/T*5,1.0)
    bounds=[(math.log(1e-6),math.log(upper_mu)),(math.log(1e-5),math.log(5.0)),(0.0,3.0),
            (math.log(1e-4),math.log(3.0)),(math.log(0.01),math.log(2.0)),(math.log(0.1),math.log(20.0))]
    rate=n/T
    starts=[
      [math.log(max(rate*.4,1e-5)),math.log(.3),.7,math.log(.01),math.log(.15),math.log(3)],
      [math.log(max(rate*.7,1e-5)),math.log(.15),1.0,math.log(.03),math.log(.30),math.log(5)],
      [math.log(max(rate*.2,1e-5)),math.log(.5),.4,math.log(.003),math.log(.08),math.log(1)],
    ]
    h=np.minimum(MAX_AGE_DAYS,np.maximum(0.0,t[-1]-t))
    def obj(x):
        mu,K,alpha,c,p,ell=unpack(x)
        productivity=np.exp(np.clip(alpha*(m-M0),-50,50))
        branching=K*float(np.mean(productivity))
        if branching>=0.98:return 1e12+1e9*(branching-.98)
        gt,gs=kernels(dt,d,c,p,ell)
        q=K*np.exp(np.clip(alpha*(parent_mag-M0),-50,50))*gt*gs
        sums=np.bincount(child,weights=q,minlength=n)
        lam=mu/max(network_length,1e-9)+sums
        if np.any(~np.isfinite(lam)) or np.any(lam<=0):return 1e15
        den_t=1-(c/(c+MAX_AGE_DAYS))**(p-1)
        G=(1-(c/(c+h))**(p-1))/max(den_t,1e-15)
        comp=mu*T+K*float(np.sum(productivity*G))
        return float(-np.sum(np.log(lam))+comp)
    fits=[]
    for s in starts:
        r=minimize(obj,np.asarray(s,float),method="L-BFGS-B",bounds=bounds,options={"maxiter":250,"ftol":1e-10,"gtol":1e-6})
        fits.append(r)
    best=min(fits,key=lambda r:float(r.fun))
    mu,K,alpha,c,p,ell=unpack(best.x)
    productivity=np.exp(np.clip(alpha*(m-M0),-50,50))
    return {"background_rate_per_day":mu,"productivity":K,"magnitude_scaling":alpha,"c_days":c,"p":p,
            "network_length_scale_km":ell,"M0":M0,"branching_ratio_proxy":K*float(np.mean(productivity)),
            "network_length_km":float(network_length),"train_duration_days":T,"train_event_count":n,
            "train_candidate_edge_count":int(len(child)),"optimizer_success":bool(best.success),
            "optimizer_message":str(best.message),"objective":float(best.fun),
            "start_objectives":[float(r.fun) for r in fits],"parameterization":"STABLE_TRUNCATED_NETWORK_ETAS_PSEUDOLIKELIHOOD_V1"}

def score_graph(indices,times,mags,faults,along,metric,params,history_indices=None):
    mu=params["background_rate_per_day"];K=params["productivity"];alpha=params["magnitude_scaling"];c=params["c_days"];p=params["p"];ell=params["network_length_scale_km"];M0=params["M0"];L=params["network_length_km"]
    all_idx=list(history_indices or [])
    summaries=[]; edge_records=[]
    for g in indices:
        t=float(times[g]/86400.0);cand=[]
        for pg in reversed(all_idx):
            dt=t-float(times[pg]/86400.0)
            if dt>MAX_AGE_DAYS:break
            if dt<=0:continue
            d=metric.distance(faults[g],along[g],faults[pg],along[pg])
            if d>MAX_PATH_KM:continue
            gt,gs=kernels(np.asarray([dt]),np.asarray([d]),c,p,ell)
            q=K*math.exp(max(-50,min(50,alpha*(float(mags[pg])-M0))))*float(gt[0])*float(gs[0])
            cand.append((q,pg,dt,d))
        cand.sort(reverse=True,key=lambda x:(x[0],-x[1]))
        cand=cand[:MAX_PARENT_CANDIDATES]
        trigger=sum(x[0] for x in cand);bg=mu/max(L,1e-9);den=bg+trigger
        probs=[x[0]/den for x in cand] if den>0 else []
        summaries.append({"global_index":int(g),"candidate_count":len(cand),"background_probability":float(bg/den),
                          "max_parent_probability":float(max(probs) if probs else 0.0),
                          "log_intensity":float(math.log(den))})
        for prob,rec in zip(probs,cand):
            q,pg,dt,d=rec;edge_records.append((int(g),int(pg),float(prob),float(dt),float(d)))
        all_idx.append(int(g))
    return summaries,edge_records

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--selected-root",type=Path,required=True);ap.add_argument("--topology-root",type=Path,required=True);ap.add_argument("--fault-geojson",type=Path,required=True);ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    if sha256(a.fault_geojson)!=FAULT_SHA256:raise SystemExit("fault SHA mismatch")
    sel_files=list(a.selected_root.rglob("selected_directional_columns.npz"));pre_files=list(a.selected_root.rglob("directional_preflight_arrays.npz"))
    top_files=list(a.topology_root.rglob("FAULT_NETWORK_TOPOLOGY_INTERSECTIONS_V0_8.json"));op_files=list(a.topology_root.rglob("LOCATION_PERTURBATION_OPERATOR_LOCK_V0_8.json"))
    if any(len(x)!=1 for x in [sel_files,pre_files,top_files,op_files]):raise SystemExit("artifact multiplicity drift")
    with np.load(sel_files[0],allow_pickle=False) as z:
        # intentionally exclude strike/dip/rake
        S={k:z[k].copy() for k in ["global_index","cohort_code","event_time_epoch","mag"]}
    with np.load(pre_files[0],allow_pickle=False) as z:
        P={k:z[k].copy() for k in ["global_index","cohort_code","fault_assignment","along_fault_km","axis_observable"]}
    if not np.array_equal(S["global_index"],P["global_index"]):raise SystemExit("global index alignment drift")
    times=np.asarray(S["event_time_epoch"],float);mags=np.asarray(S["mag"],float);faults=np.asarray(P["fault_assignment"],int);along=np.asarray(P["along_fault_km"],float);obs=np.asarray(P["axis_observable"],bool);codes=np.asarray(S["cohort_code"],int)
    lengths=load_lengths(a.fault_geojson); intersections=json.loads(top_files[0].read_text());metric=NetworkMetric(lengths,intersections)
    unit_results=[];locked={}
    graph_parts=[]
    for code,name in COHORTS.items():
        idx=np.flatnonzero((codes==code)&obs);idx=idx[np.argsort(times[idx],kind="stable")]
        n=len(idx);tr_end=int(math.floor(.5*n));cal_end=int(math.floor(.75*n));train=idx[:tr_end];cal=idx[tr_end:cal_end]
        cohort_lines=sorted(set(int(faults[g]) for g in idx));L=float(np.sum(lengths[cohort_lines]))
        train_edges=build_edges(train,times,faults,along,metric)
        params=fit_params(train,times,mags,train_edges,L);locked[name]=params
        train_summary,train_graph=score_graph(train,times,mags,faults,along,metric,params,history_indices=[])
        cal_history=list(train);cal_summary,cal_graph=score_graph(cal,times,mags,faults,along,metric,params,history_indices=cal_history)
        cal_parent_frac=float(np.mean([x["candidate_count"]>0 for x in cal_summary])) if cal_summary else 0
        train_parent_frac=float(np.mean([x["candidate_count"]>0 for x in train_summary])) if train_summary else 0
        cal_log=np.asarray([x["log_intensity"] for x in cal_summary],float)
        bg_log=math.log(params["background_rate_per_day"]/max(L,1e-9))
        gain=float(np.mean(cal_log-bg_log)) if len(cal_log) else float("-inf")
        cal_bg=float(np.mean([x["background_probability"] for x in cal_summary])) if cal_summary else 1
        cal_maxp=float(np.median([x["max_parent_probability"] for x in cal_summary])) if cal_summary else 0
        pass_gate=bool(params["optimizer_success"] and params["branching_ratio_proxy"]<0.98 and cal_parent_frac>=0.80 and gain>0)
        unit_results.append({"cohort":name,"train_count":len(train),"calibration_count":len(cal),"test_count":n-cal_end,
          "test_values_scored":False,"network_length_km":L,"selected_fault_line_count":len(cohort_lines),
          "train_parent_candidate_fraction":train_parent_frac,"calibration_parent_candidate_fraction":cal_parent_frac,
          "calibration_mean_log_intensity_gain_vs_background":gain,"calibration_mean_background_probability":cal_bg,
          "calibration_median_max_parent_probability":cal_maxp,"parameter_lock":params,"parent_graph_lock_pass":pass_gate,
          "train_top20_edge_count":len(train_graph),"calibration_top20_edge_count":len(cal_graph)})
        graph_parts.extend([(code,0,*x) for x in train_graph]);graph_parts.extend([(code,1,*x) for x in cal_graph])
    all_pass=all(x["parent_graph_lock_pass"] for x in unit_results)
    params_body={"format":"KCH_HELICAL_V0_8_ETAS_HAWKES_PARENT_GRAPH_PARAMETER_LOCK","protocol_id":PROTOCOL_ID,
      "fit_scope":"TRAIN_ONLY","calibration_scope":"DIAGNOSTIC_ONLY_NO_PARAMETER_UPDATE","test_access":"COUNTS_ONLY_NO_TEST_VALUES_SCORED",
      "candidate_contract":{"maximum_parent_age_days":30.0,"maximum_network_path_km":20.0,"maximum_candidate_parents_per_event":20},
      "network_distance_contract":"EXACT_INTERSECTION_SHORTEST_PATH_V0_8","location_perturbation_operator_id":json.loads(op_files[0].read_text())["operator_id"],
      "cohorts":locked,"all_units_pass":all_pass,"scientific_model_execution_performed":False,"authority_ceiling":"NONE"}
    params_body["lock_id"]="h8parent:"+hashlib.sha256(canonical(params_body)).hexdigest()
    result={"format":"KCH_HELICAL_V0_8_PARENT_GRAPH_TRAIN_ONLY_CALIBRATION_GATE","protocol_id":PROTOCOL_ID,"parent_graph_lock_id":params_body["lock_id"],
      "unit_results":unit_results,"outcome":"PARENT_GRAPH_LOCK_PASS" if all_pass else "NOT_IDENTIFIABLE_PARENT_GRAPH",
      "sealed_test_scored":False,"scientific_dynamic_model_execution_performed":False,
      "next_material_gate":"FULL_NULL_AND_PERTURBATION_RUNTIME_FREEZE" if all_pass else None,"authority_ceiling":"NONE"}
    result["gate_id"]="h8pg:"+hashlib.sha256(canonical(result)).hexdigest()
    write(a.out/"ETAS_HAWKES_PARENT_GRAPH_PARAMETER_LOCK_V0_8.json",params_body)
    write(a.out/"PARENT_GRAPH_CALIBRATION_RESULT_V0_8.json",result)
    if graph_parts:
        arr=np.asarray(graph_parts,dtype=float)
        np.savez_compressed(a.out/"FIT_PARENT_GRAPH_EDGES_V0_8.npz",cohort_code=arr[:,0].astype(np.int16),split_code=arr[:,1].astype(np.int8),
          child_global_index=arr[:,2].astype(np.int64),parent_global_index=arr[:,3].astype(np.int64),
          posterior_probability=arr[:,4],dt_days=arr[:,5],network_distance_km=arr[:,6])
    print(json.dumps(result,indent=2,sort_keys=True))
    return 0 if all_pass else 3
if __name__=="__main__":raise SystemExit(main())
