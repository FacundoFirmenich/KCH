from __future__ import annotations

import argparse
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

# Prevent BLAS oversubscription inside process workers.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import helical_v06 as h


def worker(payload: tuple[dict[str, Any], int, int, float, int]) -> dict[str, Any]:
    protocol, branches, n, effect, rep = payload
    contract = protocol["power_analysis"]
    seed = (
        int(contract["seed"])
        + rep
        + int(n) * 11
        + int(effect * 1000) * 101
        + int(branches) * 1_000_003
    )
    cloud = h.synthetic_cloud(n, seed, effect, null=effect == 0.0, branches=branches)
    try:
        result = h.evaluate_unit_once(cloud, protocol)
        return {
            "branches": branches,
            "n": n,
            "effect_scale_km": effect,
            "replicate": rep,
            "status": result.get("status"),
            "relative_rmse_improvement": result.get("relative_rmse_improvement"),
            "mean_nll_gain_per_event": result.get("mean_nll_gain_per_event"),
            "fit_delta_bic": result.get("fit_complexity", {}).get("helix_minus_baseline_delta_bic"),
            "selected_branch_count": result.get("selected_configuration", {}).get("branch_count"),
            "selected_baseline_family": result.get("selected_configuration", {}).get("baseline_family"),
            "selected_segment_scheme": result.get("selected_configuration", {}).get("segment_scheme"),
            "raw_p": result.get("raw_circular_shift_p"),
            "bootstrap_lower_95": result.get("moving_block_bootstrap", {}).get("lower_95"),
            "passed": h._power_pass(result, protocol),
        }
    except Exception as exc:
        return {
            "branches": branches,
            "n": n,
            "effect_scale_km": effect,
            "replicate": rep,
            "status": "FAILED",
            "error": f"{type(exc).__name__}: {exc}",
            "passed": False,
        }


def summarize(protocol: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    contract = protocol["power_analysis"]
    cells: list[dict[str, Any]] = []
    for branches in contract.get("branch_scenarios", [1]):
        for n in contract["sample_sizes"]:
            for effect in contract["effect_scales_km"]:
                cell = [r for r in rows if r["branches"] == branches and r["n"] == n and r["effect_scale_km"] == effect]
                valid = [r for r in cell if r.get("status") == "EVALUATED"]
                improvements = [float(r["relative_rmse_improvement"]) for r in valid]
                dbics = [float(r["fit_delta_bic"]) for r in valid]
                pass_count = sum(bool(r["passed"]) for r in cell)
                cells.append({
                    "branches": branches,
                    "n": n,
                    "effect_scale_km": effect,
                    "replicates": len(cell),
                    "valid": len(valid),
                    "pass_count": pass_count,
                    "pass_rate": pass_count / len(cell) if cell else None,
                    "wilson_95": h.wilson_interval(pass_count, len(cell)) if cell else None,
                    "median_rmse_improvement": float(np.median(improvements)) if improvements else None,
                    "q10_rmse_improvement": float(np.quantile(improvements, 0.1)) if improvements else None,
                    "median_fit_delta_bic": float(np.median(dbics)) if dbics else None,
                })
    null_cells = [c for c in cells if c["effect_scale_km"] == 0.0]
    nonnull = [c for c in cells if c["effect_scale_km"] > 0.0]
    return {
        "format": "KCH_HELICAL_V0_6_POWER_ANALYSIS",
        "contract": contract,
        "decision_thresholds": protocol["decision"],
        "cells": cells,
        "rows": sorted(rows, key=lambda r: (r["branches"], r["n"], r["effect_scale_km"], r["replicate"])),
        "max_false_positive_rate": max(float(c["pass_rate"]) for c in null_cells) if null_cells else None,
        "power_cells_ge_0_8": [c for c in nonnull if float(c["pass_rate"]) >= 0.8],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    protocol = json.loads(Path(args.protocol).read_text(encoding="utf-8"))
    c = protocol["power_analysis"]
    jobs = [
        (protocol, int(branches), int(n), float(effect), int(rep))
        for branches in c.get("branch_scenarios", [1])
        for n in c["sample_sizes"]
        for effect in c["effect_scales_km"]
        for rep in range(int(c["replicates_per_cell"]))
    ]
    rows: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(worker, job) for job in jobs]
        for i, fut in enumerate(as_completed(futures), start=1):
            rows.append(fut.result())
            if i % 25 == 0 or i == len(jobs):
                print(f"completed {i}/{len(jobs)}", flush=True)
    out = summarize(protocol, rows)
    h.write_json(args.output, out)
    print(json.dumps({"max_false_positive_rate": out["max_false_positive_rate"], "power_cells_ge_0_8": out["power_cells_ge_0_8"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
