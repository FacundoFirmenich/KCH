from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .component_runner import (
    BACKEND_BASE,
    MODEL_OFFSET,
    STAGES,
    _git_metadata,
    _idata_health,
    _predict,
    _sample_numpyro,
    _save_stage,
    _versions,
)
from .data import DataSurface, canonical_hash, load_surface, sha256_file, stage_frames
from .geometry import sum_zero_projector, validate_basis

TARGET_SUBJECT = "349"
TARGET_DAY = 3
PERTURBATION_MULTIPLIER = 2.5
STRESS_SEED_OFFSET = 41
MODELS = ("P0_POPULATION", "P1_GLOBAL_POOL", "P2_GLOBAL_LOCAL", "P3_LOW_POOL")


def stressed_surface(surface: DataSurface) -> tuple[DataSurface, dict[str, Any]]:
    construction = surface.construction.copy(deep=True)
    x = np.column_stack((np.ones(len(construction)), construction["t"].to_numpy(float)))
    y = construction["y"].to_numpy(float)
    beta = np.linalg.lstsq(x, y, rcond=None)[0]
    residual = y - x @ beta
    residual_sd = float(np.sqrt(np.mean(residual**2)))
    delta_standardized = PERTURBATION_MULTIPLIER * residual_sd
    mask = (construction["Subject"].astype(str) == TARGET_SUBJECT) & (construction["Days"].astype(int) == TARGET_DAY)
    if int(mask.sum()) != 1:
        raise RuntimeError("stress target is not unique")
    before = float(construction.loc[mask, "y"].iloc[0])
    construction.loc[mask, "y"] = before + delta_standardized
    after = float(construction.loc[mask, "y"].iloc[0])
    visible = pd.concat((construction, surface.calibration.copy(deep=True)), ignore_index=True).sort_values(["Days", "Subject"]).reset_index(drop=True)
    stressed = replace(surface, construction=construction, frame_visible=visible)
    receipt = {
        "target_subject": TARGET_SUBJECT,
        "target_day": TARGET_DAY,
        "perturbation_multiplier": PERTURBATION_MULTIPLIER,
        "construction_population_residual_sd_standardized": residual_sd,
        "delta_standardized": delta_standardized,
        "delta_raw_reaction": delta_standardized * surface.y_sd,
        "before_standardized": before,
        "after_standardized": after,
    }
    return stressed, receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)

    surface_clean = load_surface(root)
    surface, stress = stressed_surface(surface_clean)
    module = importlib.import_module("components_numpyro")
    basis_check = validate_basis(surface.basis)
    projector = sum_zero_projector(len(surface.subjects))
    receipt: dict[str, Any] = {
        "gate_id": "KCH-PI-GENESIS-PG006-DECISION-COUPLED-AUTHORITY-FIELD-001",
        "lane": "TRAINING_ONLY_LOCAL_STRESS",
        "backend": "numpyro",
        "backend_family": "NumPyro",
        "model_id": args.model,
        "future_outcomes_visible": False,
        "stress": stress,
        "basis_check": basis_check,
        "versions": _versions(),
        "git": _git_metadata(),
        "stages": [],
    }
    for stage, origin, stage_offset in STAGES:
        train, target, meta = stage_frames(surface, stage, origin)
        arrays = {
            "y": train["y"].to_numpy(float),
            "t": train["t"].to_numpy(float),
            "group": train["subject_index"].to_numpy(np.int32),
            "basis": surface.basis,
            "projector": projector,
        }
        seed = BACKEND_BASE["numpyro"] + MODEL_OFFSET[args.model] + STRESS_SEED_OFFSET + stage_offset
        started = time.time()
        samples, extras = _sample_numpyro(module, arrays, args.model, seed)
        elapsed = time.time() - started
        predictions = _predict(samples, target, args.model, len(surface.subjects))
        semantic = {k: v for k, v in samples.items() if k in {"alpha", "beta", "sigma", "tau_a", "tau_b", "a", "b", "s_a", "s_b"}}
        health = _idata_health(semantic, extras)
        zero_sum = {
            "a_max_abs_sum": float(np.max(np.abs(np.sum(predictions["a"], axis=-1)))) if args.model != "P0_POPULATION" else 0.0,
            "b_max_abs_sum": float(np.max(np.abs(np.sum(predictions["b"], axis=-1)))) if args.model != "P0_POPULATION" else 0.0,
        }
        stage_id = f"{stage}__origin_{origin if origin is not None else meta['origin']}"
        npz = out / f"{stage_id}.npz"
        npz_sha = _save_stage(npz, samples, extras, predictions, train, target)
        receipt["stages"].append({
            "stage_id": stage_id,
            "stage": stage,
            "origin": meta["origin"],
            "target_days": meta["target_days"],
            "outcomes_visible": meta["outcomes_visible"],
            "n_train": int(len(train)),
            "n_target": int(len(target)),
            "seed": seed,
            "elapsed_seconds": elapsed,
            "health": health,
            "zero_sum": zero_sum,
            "npz": npz.name,
            "npz_sha256": npz_sha,
        })
    stress_csv = out / "construction_stressed.csv"
    raw = surface.construction.copy()
    raw["Reaction"] = raw["y"] * surface.y_sd + surface.y_mean
    raw[["rownames", "Reaction", "Days", "Subject"]].to_csv(stress_csv, index=False, lineterminator="\n")
    receipt["construction_stressed_sha256"] = sha256_file(stress_csv)
    receipt["receipt_hash"] = canonical_hash({k: v for k, v in receipt.items() if k != "receipt_hash"})
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        (out / "pip_freeze.txt").write_text(subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True), encoding="utf-8")
    except Exception:
        pass
    print(json.dumps({"receipt_hash": receipt["receipt_hash"], "stress": stress, "stages": len(receipt["stages"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
