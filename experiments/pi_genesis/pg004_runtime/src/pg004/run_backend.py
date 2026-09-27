from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from .data import assert_fit_isolation, prepare_baseball, prepare_grunfeld, sha256_file
from .diagnostics import bfmi, health_metrics, scalarize_samples, summarize
from .geometry import validate_basis

EXPECTED_IR_SHA = "105dc2449fd7bdc7836e88b302d6db49892b9147a4a217b59f4f378661875397"
PROTOCOL_COMMIT = "f3324ec62716da0f3eca8a7b34367b9880a9bb94"
DRAWS = 500
WARMUP = 500
CHAINS = 4
TARGET_ACCEPT = 0.90
MAX_TREE_DEPTH = 10
SEEDS = {"grunfeld_1950": 2026092701, "baseball": 2026092702, "grunfeld_1946": 2026092711, "grunfeld_1948": 2026092712}


def _canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _versions() -> dict[str, str]:
    names = ["numpy", "scipy", "pandas", "arviz", "pymc", "pytensor", "jax", "jaxlib", "numpyro"]
    out: dict[str, str] = {"python": platform.python_version()}
    from importlib.metadata import PackageNotFoundError, version
    for name in names:
        try:
            out[name] = version(name)
        except PackageNotFoundError:
            continue
    return out


def _git_metadata() -> dict[str, str | None]:
    def run(*args: str) -> str | None:
        try:
            return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            return None
    return {"commit": os.getenv("GITHUB_SHA") or run("git", "rev-parse", "HEAD"), "ref": os.getenv("GITHUB_REF_NAME"), "run_id": os.getenv("GITHUB_RUN_ID"), "job": os.getenv("GITHUB_JOB")}


def _save_npz(path: Path, samples: Mapping[str, np.ndarray], extras: Mapping[str, np.ndarray]) -> str:
    payload = {f"sample__{k}": np.asarray(v) for k, v in samples.items()}
    payload.update({f"extra__{k}": np.asarray(v) for k, v in extras.items()})
    np.savez_compressed(path, **payload)
    return sha256_file(path)


def _semantic_names(domain: str) -> tuple[str, ...]:
    if domain == "grunfeld":
        return ("alpha", "beta_value", "beta_capital", "tau_alpha", "sigma", "a")
    return ("alpha", "tau_player", "theta", "a")


def _health_names(domain: str, encoding: str) -> tuple[str, ...]:
    semantic = list(_semantic_names(domain))
    semantic.append("z" if encoding == "centered_J" else "u")
    return tuple(semantic)


def _extract_pymc(idata: Any, names: tuple[str, ...]) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    samples: dict[str, np.ndarray] = {}
    for name in names:
        if name in idata.posterior:
            samples[name] = np.asarray(idata.posterior[name].values, dtype=float)
    stats = idata.sample_stats
    extras: dict[str, np.ndarray] = {}
    for source, target in (("diverging", "diverging"), ("energy", "energy"), ("tree_depth", "tree_depth"), ("acceptance_rate", "acceptance_rate")):
        if source in stats:
            extras[target] = np.asarray(stats[source].values)
    return samples, extras


def _run_pymc(data: Any, domain: str, encoding: str, seed: int):
    import pymc as pm
    models = importlib.import_module("pg004_models_pymc")
    if models.IR_SHA256 != EXPECTED_IR_SHA:
        raise RuntimeError("PyMC generated source has wrong IR hash")
    model = models.build_grunfeld(data.arrays, encoding) if domain == "grunfeld" else models.build_baseball(data.arrays, encoding)
    with model:
        idata = pm.sample(draws=DRAWS, tune=WARMUP, chains=CHAINS, cores=min(CHAINS, os.cpu_count() or 1), random_seed=[seed + i * 1009 for i in range(CHAINS)], target_accept=TARGET_ACCEPT, progressbar=False, quiet=True, compute_convergence_checks=False, return_inferencedata=True, nuts_sampler_kwargs={"max_treedepth": MAX_TREE_DEPTH})
    return _extract_pymc(idata, _health_names(domain, encoding))


def _run_numpyro(data: Any, domain: str, encoding: str, seed: int):
    import jax
    import jax.numpy as jnp
    import numpyro
    from numpyro.infer import MCMC, NUTS
    models = importlib.import_module("pg004_models_numpyro")
    if models.IR_SHA256 != EXPECTED_IR_SHA:
        raise RuntimeError("NumPyro generated source has wrong IR hash")
    numpyro.enable_x64()
    if domain == "grunfeld":
        model = models.grunfeld_model
        kwargs = {"y": jnp.asarray(data.arrays["y"]), "x_value": jnp.asarray(data.arrays["x_value"]), "x_capital": jnp.asarray(data.arrays["x_capital"]), "group": jnp.asarray(data.arrays["group"]), "basis": jnp.asarray(data.arrays["basis"]), "encoding": encoding}
    else:
        model = models.baseball_model
        kwargs = {"at_bats": jnp.asarray(data.arrays["at_bats"]), "hits": jnp.asarray(data.arrays["hits"]), "basis": jnp.asarray(data.arrays["basis"]), "encoding": encoding}
    kernel = NUTS(model, target_accept_prob=TARGET_ACCEPT, max_tree_depth=MAX_TREE_DEPTH)
    mcmc = MCMC(kernel, num_warmup=WARMUP, num_samples=DRAWS, num_chains=CHAINS, chain_method="sequential", progress_bar=False)
    mcmc.run(jax.random.PRNGKey(seed), extra_fields=("diverging", "potential_energy", "num_steps", "accept_prob"), **kwargs)
    raw = mcmc.get_samples(group_by_chain=True)
    samples = {name: np.asarray(value, dtype=float) for name, value in raw.items()}
    tau = samples["tau_alpha"] if domain == "grunfeld" else samples["tau_player"]
    if encoding == "centered_J":
        z = samples["z"]
        a = tau[..., None] * (z - np.mean(z, axis=-1, keepdims=True))
    else:
        u = samples["u"]
        a = tau[..., None] * np.einsum("ij,cdj->cdi", np.asarray(data.arrays["basis"], dtype=float), u)
    samples["a"] = a
    if domain == "baseball":
        samples["theta"] = 1.0 / (1.0 + np.exp(-(samples["alpha"][..., None] + a)))
    fields = mcmc.get_extra_fields(group_by_chain=True)
    extras = {"diverging": np.asarray(fields.get("diverging", np.zeros((CHAINS, DRAWS), dtype=bool))), "energy": np.asarray(fields.get("potential_energy", np.empty((0,))), dtype=float), "num_steps": np.asarray(fields.get("num_steps", np.empty((0,))), dtype=float), "acceptance_rate": np.asarray(fields.get("accept_prob", np.empty((0,))), dtype=float)}
    return samples, extras


def _plan(backend: str, domain: str) -> list[tuple[int | None, str, int]]:
    if domain == "baseball":
        return [(None, "centered_J", SEEDS["baseball"]), (None, "orthonormal_Jminus1", SEEDS["baseball"])]
    plan = [(1950, "centered_J", SEEDS["grunfeld_1950"]), (1950, "orthonormal_Jminus1", SEEDS["grunfeld_1950"])]
    if backend == "numpyro":
        plan += [(1946, "orthonormal_Jminus1", SEEDS["grunfeld_1946"]), (1948, "orthonormal_Jminus1", SEEDS["grunfeld_1948"])]
    return plan


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("pymc", "numpyro"), required=True)
    parser.add_argument("--domain", choices=("grunfeld", "baseball"), required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    isolation = assert_fit_isolation(root)
    if not isolation["isolated"]:
        raise RuntimeError(f"future evidence visible to fit job: {isolation}")
    ir_path = root / "ir" / "PG004_MODEL_IR.json"
    if sha256_file(ir_path) != EXPECTED_IR_SHA:
        raise RuntimeError("frozen IR hash mismatch")
    generated_path = root / "generated" / f"pg004_models_{args.backend}.py"
    receipt: dict[str, Any] = {"backend": args.backend, "backend_family": "PyMC" if args.backend == "pymc" else "NumPyro", "domain": args.domain, "protocol_commit": PROTOCOL_COMMIT, "ir_sha256": EXPECTED_IR_SHA, "generated_source": str(generated_path.relative_to(root)), "generated_source_sha256": sha256_file(generated_path), "fit_isolation": isolation, "versions": _versions(), "git": _git_metadata(), "sampling": {"chains": CHAINS, "warmup": WARMUP, "draws": DRAWS, "target_accept": TARGET_ACCEPT, "max_tree_depth": MAX_TREE_DEPTH}, "episodes": []}
    runner = _run_pymc if args.backend == "pymc" else _run_numpyro
    for cut, encoding, seed in _plan(args.backend, args.domain):
        data = prepare_grunfeld(root, int(cut)) if args.domain == "grunfeld" else prepare_baseball(root)
        basis_check = validate_basis(data.arrays["basis"])
        if not basis_check["valid"]:
            raise RuntimeError(f"invalid zero-sum basis: {basis_check}")
        started = time.time()
        samples, extras = runner(data, args.domain, encoding, seed)
        elapsed = time.time() - started
        health_samples = scalarize_samples(samples, _health_names(args.domain, encoding))
        summary = summarize(health_samples)
        divergences = int(np.asarray(extras.get("diverging", [])).sum())
        health = health_metrics(summary, divergences)
        health["bfmi"] = bfmi(np.asarray(extras.get("energy", [])))
        zero_sum_error = float(np.max(np.abs(np.sum(samples["a"], axis=-1))))
        stem = f"{args.domain}__cut_{cut if cut is not None else 'na'}__{encoding}"
        npz_path = output / f"{stem}.npz"
        npz_sha = _save_npz(npz_path, samples, extras)
        receipt["episodes"].append({"id": stem, "cut": cut, "encoding": encoding, "seed": seed, "preparation_hash": data.preparation_hash, "source_hashes": data.source_hashes, "basis_check": basis_check, "zero_sum_max_abs": zero_sum_error, "elapsed_seconds": elapsed, "health": health, "summary": summary, "npz": npz_path.name, "npz_sha256": npz_sha, "semantic_names": list(_semantic_names(args.domain)), "health_names": list(_health_names(args.domain, encoding))})
    receipt["receipt_hash"] = _canonical_hash({k: v for k, v in receipt.items() if k != "receipt_hash"})
    receipt_path = output / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
    (output / "pip_freeze.txt").write_text(subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True), encoding="utf-8")
    print(json.dumps({"receipt": str(receipt_path), "receipt_hash": receipt["receipt_hash"], "episodes": len(receipt["episodes"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
