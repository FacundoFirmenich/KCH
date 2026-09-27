from __future__ import annotations

import argparse
import importlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import arviz as az
import numpy as np

from .data import canonical_hash, load_surface, sha256_file, stage_frames
from .geometry import sum_zero_projector, validate_basis

COMPONENT_IR_SHA256 = "280403a5fbdc1f8817218a4ac8f5d5b0d8e530934834c0cc3b400881d53f0f8a"
PROTOCOL_SHA256 = "4600564daa17b4349b88e5f366da82d3a51907674e39de53cf3bdfc9f303ddd7"
MODELS = ("P0_POPULATION", "P1_GLOBAL_POOL", "P2_GLOBAL_LOCAL", "P3_LOW_POOL")
CHAINS = 4
WARMUP = 800
DRAWS = 800
TARGET_ACCEPT = 0.95
MAX_TREE_DEPTH = 12
BACKEND_BASE = {"pymc": 2026092761, "numpyro": 2026092762}
MODEL_OFFSET = {"P0_POPULATION": 0, "P1_GLOBAL_POOL": 100, "P2_GLOBAL_LOCAL": 200, "P3_LOW_POOL": 300}
STAGES = (("crossfit", 2, 11), ("crossfit", 3, 12), ("crossfit", 4, 13), ("calibration", None, 21), ("final", None, 31))


def _versions() -> dict[str, str]:
    import importlib.metadata as md
    names = ["numpy", "scipy", "pandas", "arviz", "pymc", "pytensor", "jax", "jaxlib", "numpyro"]
    out = {"python": platform.python_version()}
    for name in names:
        try:
            out[name] = md.version(name)
        except md.PackageNotFoundError:
            pass
    return out


def _git_metadata() -> dict[str, str | None]:
    def cmd(*args: str) -> str | None:
        try:
            return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            return None
    return {"commit": os.getenv("GITHUB_SHA") or cmd("git", "rev-parse", "HEAD"), "ref": os.getenv("GITHUB_REF_NAME"), "run_id": os.getenv("GITHUB_RUN_ID"), "job": os.getenv("GITHUB_JOB")}


def _idata_health(samples: dict[str, np.ndarray], extras: dict[str, np.ndarray]) -> dict[str, Any]:
    idata = az.from_dict(posterior={k: np.asarray(v) for k, v in samples.items()})
    rhat_ds = az.rhat(idata, method="rank")
    bulk_ds = az.ess(idata, method="bulk")
    tail_ds = az.ess(idata, method="tail")
    def extrema(ds: Any, mode: str) -> tuple[float, str]:
        vals: list[tuple[float, str]] = []
        for name in ds.data_vars:
            arr = np.asarray(ds[name].values, dtype=float).reshape(-1)
            for idx, val in enumerate(arr):
                if np.isfinite(val):
                    vals.append((float(val), f"{name}[{idx}]" if arr.size > 1 else name))
        if not vals:
            return float("nan"), "NONE"
        return max(vals) if mode == "max" else min(vals)
    max_rhat, max_rhat_name = extrema(rhat_ds, "max")
    min_bulk, min_bulk_name = extrema(bulk_ds, "min")
    min_tail, min_tail_name = extrema(tail_ds, "min")
    divergences = int(np.asarray(extras.get("diverging", []), dtype=bool).sum())
    bfmi_values: list[float] = []
    energy = np.asarray(extras.get("energy", []), dtype=float)
    if energy.ndim == 2:
        for chain in energy:
            var = float(np.var(chain, ddof=1))
            bfmi_values.append(float(np.mean(np.diff(chain) ** 2) / var) if var > 0 else float("nan"))
    return {"max_rank_folded_rhat": max_rhat, "max_rhat_parameter": max_rhat_name, "min_bulk_ess": min_bulk, "min_bulk_parameter": min_bulk_name, "min_tail_ess": min_tail, "min_tail_parameter": min_tail_name, "divergences": divergences, "bfmi": bfmi_values}


def _sample_pymc(model_module: Any, arrays: dict[str, np.ndarray], model_id: str, seed: int) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    import pymc as pm
    if model_module.IR_SHA256 != COMPONENT_IR_SHA256:
        raise RuntimeError("PyMC source IR hash mismatch")
    model = model_module.build_component(arrays, model_id)
    with model:
        step = pm.NUTS(target_accept=TARGET_ACCEPT, max_treedepth=MAX_TREE_DEPTH)
        idata = pm.sample(draws=DRAWS, tune=WARMUP, chains=CHAINS, cores=min(CHAINS, os.cpu_count() or 1), random_seed=[seed + 1009 * i for i in range(CHAINS)], step=step, progressbar=False, compute_convergence_checks=False, return_inferencedata=True)
    samples = {name: np.asarray(idata.posterior[name].values, dtype=float) for name in idata.posterior.data_vars}
    extras: dict[str, np.ndarray] = {}
    for source, target in (("diverging", "diverging"), ("energy", "energy"), ("tree_depth", "tree_depth"), ("acceptance_rate", "acceptance_rate")):
        if source in idata.sample_stats:
            extras[target] = np.asarray(idata.sample_stats[source].values)
    return samples, extras


def _sample_numpyro(model_module: Any, arrays: dict[str, np.ndarray], model_id: str, seed: int) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    import jax
    import jax.numpy as jnp
    import numpyro
    from numpyro.infer import MCMC, NUTS
    if model_module.IR_SHA256 != COMPONENT_IR_SHA256:
        raise RuntimeError("NumPyro source IR hash mismatch")
    numpyro.enable_x64()
    kernel = NUTS(model_module.component_model, target_accept_prob=TARGET_ACCEPT, max_tree_depth=MAX_TREE_DEPTH)
    mcmc = MCMC(kernel, num_warmup=WARMUP, num_samples=DRAWS, num_chains=CHAINS, chain_method="sequential", progress_bar=False)
    kwargs = {"y": jnp.asarray(arrays["y"]), "t": jnp.asarray(arrays["t"]), "group": jnp.asarray(arrays["group"]), "basis": jnp.asarray(arrays["basis"]), "projector": jnp.asarray(arrays["projector"]), "model_id": model_id}
    mcmc.run(jax.random.PRNGKey(seed), extra_fields=("diverging", "potential_energy", "num_steps", "accept_prob"), **kwargs)
    samples = {name: np.asarray(value, dtype=float) for name, value in mcmc.get_samples(group_by_chain=True).items()}
    fields = mcmc.get_extra_fields(group_by_chain=True)
    extras = {"diverging": np.asarray(fields.get("diverging", np.zeros((CHAINS, DRAWS), dtype=bool))), "energy": np.asarray(fields.get("potential_energy", np.empty((0,))), dtype=float), "num_steps": np.asarray(fields.get("num_steps", np.empty((0,))), dtype=float), "acceptance_rate": np.asarray(fields.get("accept_prob", np.empty((0,))), dtype=float)}
    return samples, extras


def _predict(samples: dict[str, np.ndarray], target: Any, model_id: str, j: int) -> dict[str, np.ndarray]:
    alpha = np.asarray(samples["alpha"], dtype=float).reshape(-1)
    beta = np.asarray(samples["beta"], dtype=float).reshape(-1)
    sigma = np.asarray(samples["sigma"], dtype=float).reshape(-1)
    group = target.subject_index.to_numpy(int)
    t = target.t.to_numpy(float)
    mu = alpha[:, None] + beta[:, None] * t[None, :]
    if model_id == "P0_POPULATION":
        effect = np.zeros_like(mu)
        a = np.zeros((alpha.size, j), dtype=float)
        b = np.zeros((alpha.size, j), dtype=float)
    else:
        a = np.asarray(samples["a"], dtype=float).reshape(-1, j)
        b = np.asarray(samples["b"], dtype=float).reshape(-1, j)
        effect = a[:, group] + b[:, group] * t[None, :]
        mu = mu + effect
    output: dict[str, np.ndarray] = {"mu": mu, "sigma": sigma, "effect": effect, "a": a, "b": b}
    if model_id == "P2_GLOBAL_LOCAL":
        s_a = np.asarray(samples["s_a"], dtype=float).reshape(-1, j)
        s_b = np.asarray(samples["s_b"], dtype=float).reshape(-1, j)
        local_var = s_a[:, group] ** 2 + (t[None, :] ** 2) * s_b[:, group] ** 2
        output["kappa"] = 1.0 / (1.0 + local_var / np.maximum(sigma[:, None] ** 2, 1e-12))
        output["s_a"] = s_a
        output["s_b"] = s_b
    return output


def _save_stage(path: Path, samples: dict[str, np.ndarray], extras: dict[str, np.ndarray], predictions: dict[str, np.ndarray], train: Any, target: Any) -> str:
    payload: dict[str, np.ndarray] = {}
    for name, value in samples.items(): payload[f"sample__{name}"] = np.asarray(value)
    for name, value in extras.items(): payload[f"extra__{name}"] = np.asarray(value)
    for name, value in predictions.items(): payload[f"pred__{name}"] = np.asarray(value)
    payload.update({"target__subject_index": target.subject_index.to_numpy(np.int32), "target__day": target.Days.to_numpy(np.int32), "target__t": target.t.to_numpy(float), "target__y": target.y.to_numpy(float) if "y" in target else np.full(len(target), np.nan), "train__day": train.Days.to_numpy(np.int32), "train__subject_index": train.subject_index.to_numpy(np.int32), "train__y": train.y.to_numpy(float)})
    np.savez_compressed(path, **payload)
    return sha256_file(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("pymc", "numpyro"), required=True)
    parser.add_argument("--model", choices=MODELS, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve(); out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    surface = load_surface(root)
    if sha256_file(root / "ir" / "PG006_COMPONENT_IR.json") != COMPONENT_IR_SHA256:
        raise RuntimeError("component IR bytes mismatch")
    module = importlib.import_module("components_pymc" if args.backend == "pymc" else "components_numpyro")
    runner = _sample_pymc if args.backend == "pymc" else _sample_numpyro
    basis_check = validate_basis(surface.basis); projector = sum_zero_projector(len(surface.subjects))
    receipt: dict[str, Any] = {"gate_id": "KCH-PI-GENESIS-PG006-DECISION-COUPLED-AUTHORITY-FIELD-001", "backend": args.backend, "backend_family": "PyMC" if args.backend == "pymc" else "NumPyro", "model_id": args.model, "protocol_sha256": PROTOCOL_SHA256, "component_ir_sha256": COMPONENT_IR_SHA256, "generated_source": module.__file__, "generated_source_sha256": sha256_file(module.__file__), "data_preparation_hash": surface.preparation_hash, "basis_check": basis_check, "sampling": {"chains": CHAINS, "warmup": WARMUP, "draws": DRAWS, "target_accept": TARGET_ACCEPT, "max_tree_depth": MAX_TREE_DEPTH}, "versions": _versions(), "git": _git_metadata(), "future_outcomes_visible": False, "stages": []}
    for stage, origin, stage_offset in STAGES:
        train, target, meta = stage_frames(surface, stage, origin)
        arrays = {"y": train.y.to_numpy(float), "t": train.t.to_numpy(float), "group": train.subject_index.to_numpy(np.int32), "basis": surface.basis, "projector": projector}
        seed = BACKEND_BASE[args.backend] + MODEL_OFFSET[args.model] + stage_offset
        started = time.time(); samples, extras = runner(module, arrays, args.model, seed); elapsed = time.time() - started
        predictions = _predict(samples, target, args.model, len(surface.subjects))
        semantic = {k: v for k, v in samples.items() if k in {"alpha", "beta", "sigma", "tau_a", "tau_b", "a", "b", "s_a", "s_b"}}
        health = _idata_health(semantic, extras)
        zero_sum = {"a_max_abs_sum": float(np.max(np.abs(np.sum(predictions["a"], axis=-1)))) if args.model != "P0_POPULATION" else 0.0, "b_max_abs_sum": float(np.max(np.abs(np.sum(predictions["b"], axis=-1)))) if args.model != "P0_POPULATION" else 0.0}
        stage_id = f"{stage}__origin_{origin if origin is not None else meta['origin']}"; npz = out / f"{stage_id}.npz"
        npz_sha = _save_stage(npz, samples, extras, predictions, train, target)
        receipt["stages"].append({"stage_id": stage_id, "stage": stage, "origin": meta["origin"], "target_days": meta["target_days"], "outcomes_visible": meta["outcomes_visible"], "n_train": int(len(train)), "n_target": int(len(target)), "seed": seed, "elapsed_seconds": elapsed, "health": health, "zero_sum": zero_sum, "npz": npz.name, "npz_sha256": npz_sha})
    receipt["receipt_hash"] = canonical_hash({k: v for k, v in receipt.items() if k != "receipt_hash"})
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try: (out / "pip_freeze.txt").write_text(subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True), encoding="utf-8")
    except Exception: pass
    print(json.dumps({"receipt": str(out / "receipt.json"), "receipt_hash": receipt["receipt_hash"], "stages": len(receipt["stages"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
