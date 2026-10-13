#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

def mode_label(x):
    return "OUTSIDE" if x == "OUTSIDE_DECLARED_DOMAIN" else x.split(":", 1)[0]

def actionable_label(x):
    mo = mode_label(x)
    if mo in {"APPLY", "TOP_2"}:
        return "ACTIONABLE"
    if mo == "OUTSIDE":
        return "OUTSIDE"
    return "NONACTIONABLE"

def load_family(kernel_path: Path):
    d=json.loads(kernel_path.read_text())
    nodes=d["nodes"]; floor=int(d["domain_floor"])
    roots={}
    for r in d["roots"]:
        roots.setdefault(int(r["class_id"]),r)
    classes=sorted(roots)
    probes=[m for m in range(1<<12) if m.bit_count()>=floor]
    qindex={f"{m:03x}":i for i,m in enumerate(probes)}
    def ev(root,mask):
        n=nodes[root]
        while "label" not in n:
            q=int(n["query_index"])
            root=int(n["if_included"] if ((mask>>q)&1) else n["if_excluded"])
            n=nodes[root]
        return str(n["label"])
    exact=[[ev(int(roots[c]["root"]),m) for m in probes] for c in classes]
    mode=[[mode_label(x) for x in row] for row in exact]
    act=[[actionable_label(x) for x in row] for row in exact]
    return classes, qindex, {"EXACT":exact,"MODE":mode,"ACTIONABLE":act}

def decode_codebook(hypotheses, target_ids, queries, transcript, t, mats, qindex):
    # Each target child must have one deterministic codeword under this stage.
    representatives={}
    for h in hypotheses:
        representatives.setdefault(target_ids[h], h)
    codewords={}
    for target, h in representatives.items():
        word=[]
        for q in queries:
            qi=qindex[q["mask_hex"]]
            word.append(mats[q["sensor"]][h][qi])
        codewords[target]=word

    if len(transcript) != len(queries):
        return {
            "status":"QUERY_COUNT_MISMATCH",
            "expected":len(queries),
            "observed":len(transcript),
            "permission_granted":False,
        }

    admissible=[]
    distances={}
    for target,word in codewords.items():
        dist=sum(str(transcript[i]) != str(word[i]) for i in range(len(word)))
        distances[str(target)]=dist
        if dist <= t:
            admissible.append(target)

    if len(admissible)==1:
        return {
            "status":"IDENTIFIED",
            "target_id":admissible[0],
            "distances":distances,
            "permission_granted":False,
        }
    if not admissible:
        return {
            "status":"OUT_OF_ERROR_MODEL",
            "distances":distances,
            "permission_granted":False,
        }
    return {
        "status":"ABSTAIN_AMBIGUOUS",
        "candidate_target_ids":admissible,
        "distances":distances,
        "permission_granted":False,
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--kernel",type=Path,required=True)
    p.add_argument("--policy",type=Path,required=True)
    p.add_argument("--t",type=int,choices=[0,1,2],required=True)
    p.add_argument("--stage",choices=["ACTIONABLE","MODE","EXACT"],required=True)
    p.add_argument("--parent-id",type=int)
    p.add_argument("--transcript",type=Path,required=True)
    a=p.parse_args()

    policy=json.loads(a.policy.read_text())
    classes,qindex,mats=load_family(a.kernel)
    transcript=json.loads(a.transcript.read_text())

    if a.stage=="ACTIONABLE":
        queries=[{"sensor":"ACTIONABLE","mask_hex":x}
                 for x in policy["stage1_actionable"][str(a.t)]]
        groups={int(k):v for k,v in policy["actionable_groups"].items()}
        target_ids={h:pid for pid,g in groups.items() for h in g}
        hypotheses=classes
    elif a.stage=="MODE":
        if a.parent_id is None:
            raise SystemExit("--parent-id required for MODE")
        node=policy["stage2_mode"][str(a.t)][str(a.parent_id)]
        hypotheses=policy["actionable_groups"][str(a.parent_id)]
        if node["status"]=="NO_REFINEMENT_REQUIRED":
            print(json.dumps({"status":"NO_REFINEMENT_REQUIRED","permission_granted":False},indent=2));return
        queries=(
            [{"sensor":"MODE","mask_hex":x} for x in node["mode_probes"]]+
            [{"sensor":"EXACT","mask_hex":x} for x in node["exact_repair_probes"]]
        )
        mode_groups={int(k):v for k,v in policy["mode_groups"].items()}
        target_ids={h:mid for mid,g in mode_groups.items() for h in g}
    else:
        if a.parent_id is None:
            raise SystemExit("--parent-id required for EXACT")
        node=policy["stage3_exact"][str(a.t)][str(a.parent_id)]
        hypotheses=policy["mode_groups"][str(a.parent_id)]
        if node["status"]=="NO_REFINEMENT_REQUIRED":
            print(json.dumps({"status":"NO_REFINEMENT_REQUIRED","permission_granted":False},indent=2));return
        queries=[{"sensor":"EXACT","mask_hex":x} for x in node["exact_probes"]]
        target_ids={h:h for h in hypotheses}

    result=decode_codebook(
        hypotheses,target_ids,queries,transcript,a.t,mats,qindex
    )
    result["queries"]=queries
    print(json.dumps(result,indent=2))

if __name__=="__main__":
    main()
