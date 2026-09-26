#!/usr/bin/env python3
"""Post-hoc adversarial audit of CFL G1 discovery result.

This audit was designed after seeing the initial G1 result, so it is not a
confirmation experiment. It probes whether the proto-TOS gain survives stronger,
compute-heavier adaptive regularization baselines and field ablations.
"""
from __future__ import annotations

import json
import runpy
import sys
from pathlib import Path
from typing import Any

import numpy as np
import scipy.io
import scipy.sparse as sp

BASE = Path(__file__).resolve().parent
G1 = runpy.run_path(str(BASE / "run_g1.py"), run_name="g1lib")

N = G1["N"]
ALPHAS = G1["ALPHAS"]
BETAS = G1["BETAS"]
Candidate = G1["Candidate"]


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def edge_laplacian(x: np.ndarray) -> sp.csr_matrix:
    img = x.reshape((N, N), order="F")
    h = np.abs(np.diff(img, axis=1))
    v = np.abs(np.diff(img, axis=0))
    sh = G1["robust_scale"](h)
    sv = G1["robust_scale"](v)
    wh = np.clip(np.exp(-h / sh), 0.03, 8.0)
    wv = np.clip(np.exp(-v / sv), 0.03, 8.0)
    return G1["build_laplacian"](wh, wv)


def phi_edge_only_laplacian(x1: np.ndarray, x2: np.ndarray) -> sp.csr_matrix:
    i1 = x1.reshape((N, N), order="F")
    i2 = x2.reshape((N, N), order="F")
    h = 0.5 * (np.abs(np.diff(i1, axis=1)) + np.abs(np.diff(i2, axis=1)))
    v = 0.5 * (np.abs(np.diff(i1, axis=0)) + np.abs(np.diff(i2, axis=0)))
    wh = np.clip(np.exp(-h / G1["robust_scale"](h)), 0.03, 8.0)
    wv = np.clip(np.exp(-v / G1["robust_scale"](v)), 0.03, 8.0)
    return G1["build_laplacian"](wh, wv)


def tune_irls2(A, b, Aval, bval, preliminary: np.ndarray):
    records = []
    best = None
    L0 = edge_laplacian(preliminary)
    for alpha in ALPHAS:
        for beta in BETAS:
            s1 = G1["solve_quadratic"](A, b, alpha, beta, L0)
            L1 = edge_laplacian(s1.image)
            s2 = G1["solve_quadratic"](A, b, alpha, beta, L1, x0=s1.image)
            val = G1["nrmse"](Aval @ s2.image, bval)
            train = G1["nrmse"](A @ s2.image, b)
            rec = {
                "method": "COMPUTE_HEAVIER_IRLS2",
                "alpha": alpha,
                "beta": beta,
                "val_nrmse": val,
                "train_nrmse": train,
                "solve_seconds": s1.seconds + s2.seconds,
                "cg_iterations": s1.iterations + s2.iterations,
                "cg_info": max(s1.info, s2.info),
            }
            records.append(rec)
            c = Candidate(rec["method"], alpha, beta, val, train, rec["solve_seconds"], rec["cg_info"], rec["cg_iterations"], s2.image)
            if best is None or (c.val_nrmse, c.alpha, c.beta) < (best.val_nrmse, best.alpha, best.beta):
                best = c
    return best, records


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: run_g1_adversarial_audit.py ORIGINAL_BUNDLE_ROOT OUTPUT_DIR")
    root = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    original = json.loads((root / "results" / "RESULTS.json").read_text())
    raw = scipy.io.loadmat(root / "data" / "Data82.mat")
    A = raw["A"].tocsr().astype(np.float64)
    m = np.asarray(raw["m"], dtype=np.float64)

    folds = []
    traces = []
    for fold in range(3):
        parts = G1["fold_angles"](fold)
        A1, b1 = G1["subset"](A, m, parts["o1"])
        A2, b2 = G1["subset"](A, m, parts["o2"])
        Atr, btr = G1["subset"](A, m, parts["train"])
        Aval, bval = G1["subset"](A, m, parts["val"])
        Atest, btest = G1["subset"](A, m, parts["test"])

        old_eval = {e["method"]: e for e in original["folds"][fold]["evaluations"]}
        x1 = G1["solve_quadratic"](A1, b1, old_eval["O1_TIKHONOV"]["alpha"]).image
        x2 = G1["solve_quadratic"](A2, b2, old_eval["O2_TIKHONOV"]["alpha"]).image
        joint_pre = G1["solve_quadratic"](Atr, btr, old_eval["MATCHED_JOINT_TIKHONOV"]["alpha"]).image
        Lphi, _ = G1["phi12_laplacian"](x1, x2)
        tos_sol = G1["solve_quadratic"](
            Atr, btr,
            old_eval["PROTO_TOS_PHI12_O3"]["alpha"],
            old_eval["PROTO_TOS_PHI12_O3"]["beta"],
            Lphi,
        )
        tos_test = G1["nrmse"](Atest @ tos_sol.image, btest)

        Lself = edge_laplacian(joint_pre)
        self_once, rec1 = G1["tune"](
            "SELF_ADAPTIVE_ONCE", Atr, btr, Aval, bval, ALPHAS, BETAS, Lself
        )
        edge_only_L = phi_edge_only_laplacian(x1, x2)
        edge_only, rec2 = G1["tune"](
            "PHI12_EDGE_ONLY_GAMMA0", Atr, btr, Aval, bval, ALPHAS, BETAS, edge_only_L
        )
        irls2, rec3 = tune_irls2(Atr, btr, Aval, bval, joint_pre)

        rng = np.random.default_rng(3300 + fold)
        perm = rng.permutation(N * N)
        shuffled_L, _ = G1["phi12_laplacian"](x1[perm], x2[perm])
        shuffled, rec4 = G1["tune"](
            "SHUFFLED_PHI_NEGATIVE_CONTROL", Atr, btr, Aval, bval, ALPHAS, BETAS, shuffled_L
        )
        for recs in (rec1, rec2, rec3, rec4):
            for r in recs:
                r["fold"] = fold
                traces.append(r)

        candidates = [self_once, edge_only, irls2, shuffled]
        metrics = {
            "PROTO_TOS_PHI12_O3": {
                "test_nrmse": tos_test,
                "validation_nrmse": old_eval["PROTO_TOS_PHI12_O3"]["validation_nrmse"],
                "alpha": old_eval["PROTO_TOS_PHI12_O3"]["alpha"],
                "beta": old_eval["PROTO_TOS_PHI12_O3"]["beta"],
            }
        }
        for c in candidates:
            metrics[c.method] = {
                "test_nrmse": G1["nrmse"](Atest @ c.image, btest),
                "validation_nrmse": c.val_nrmse,
                "training_nrmse": G1["nrmse"](Atr @ c.image, btr),
                "alpha": c.alpha,
                "beta": c.beta,
                "selected_fit_seconds": c.solve_seconds,
                "selected_fit_iterations": c.cg_iterations,
            }
        strongest = min(
            [k for k in metrics if k != "SHUFFLED_PHI_NEGATIVE_CONTROL"],
            key=lambda k: metrics[k]["test_nrmse"],
        )
        strongest_adversary = min(
            ["SELF_ADAPTIVE_ONCE", "PHI12_EDGE_ONLY_GAMMA0", "COMPUTE_HEAVIER_IRLS2"],
            key=lambda k: metrics[k]["test_nrmse"],
        )
        gain_vs_adversary = (
            metrics[strongest_adversary]["test_nrmse"] - tos_test
        ) / metrics[strongest_adversary]["test_nrmse"]
        folds.append({
            "fold": fold,
            "metrics": metrics,
            "strongest_overall": strongest,
            "strongest_adversary": strongest_adversary,
            "proto_tos_relative_gain_vs_strongest_adversary": float(gain_vs_adversary),
            "field_specificity_gain_vs_edge_only": float(
                (metrics["PHI12_EDGE_ONLY_GAMMA0"]["test_nrmse"] - tos_test)
                / metrics["PHI12_EDGE_ONLY_GAMMA0"]["test_nrmse"]
            ),
            "negative_control_is_worse_than_proto_tos": bool(
                metrics["SHUFFLED_PHI_NEGATIVE_CONTROL"]["test_nrmse"] > tos_test
            ),
        })

    gains = [f["proto_tos_relative_gain_vs_strongest_adversary"] for f in folds]
    wins = sum(g > 0.02 for g in gains)
    losses = sum(g < -0.02 for g in gains)
    if wins >= 2:
        outcome = "SURVIVES_POSTHOC_ADVERSARIAL_BASELINES"
    elif losses >= 2:
        outcome = "DEFEATED_BY_ADVERSARIAL_BASELINE"
    else:
        outcome = "ADVERSARIAL_BASELINE_EQUIVALENT"
    result = {
        "status": "POSTHOC_ADVERSARIAL_AUDIT_NOT_CONFIRMATION",
        "designed_after_initial_result": True,
        "folds": folds,
        "aggregate": {
            "relative_gains_vs_strongest_adversary": gains,
            "median_gain": float(np.median(gains)),
            "wins_over_2_percent": wins,
            "losses_over_2_percent": losses,
            "outcome": outcome,
        },
        "interpretation": [
            "This audit cannot upgrade discovery evidence because it was designed after observing G1.",
            "It can downgrade the original interpretation if a stronger adaptive baseline matches or defeats proto-TOS.",
            "Compute parity is approximate: IRLS2 is intentionally compute-heavier than proto-TOS, while all arms use identical measured projections."
        ]
    }
    write_json(out / "ADVERSARIAL_AUDIT_RESULTS.json", result)
    import csv
    with (out / "ADVERSARIAL_TUNING_TRACES.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(traces[0].keys()))
        w.writeheader()
        w.writerows(traces)
    print(json.dumps(result["aggregate"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
