from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.special import logsumexp, softmax


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def weights_and_regret(field: np.lib.npyio.NpzFile, split: str, temperature: float) -> tuple[np.ndarray, np.ndarray]:
    z = np.asarray(field[f"pred_z__{split}"], dtype=float)
    if z.shape[1] % 4:
        raise ValueError("field prediction width is not divisible by four programs")
    z = z.reshape(z.shape[0], z.shape[1] // 4, 4)
    regret = np.maximum(np.exp(z) - 0.005, 0.0)
    weights = softmax(-regret / temperature, axis=2)
    return weights, regret


def mixture_nlpd(full: np.lib.npyio.NpzFile, field: np.lib.npyio.NpzFile, split: str, temperature: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    y = np.asarray(full[f"{split}_y"], dtype=float)
    mu = np.asarray(full[f"{split}_mu_components"], dtype=float)
    sigma = np.asarray(full[f"{split}_sigma_components"], dtype=float)
    weights, regret = weights_and_regret(field, split, temperature)
    draws = min(weights.shape[0], mu.shape[1])
    weights = weights[:draws]
    regret = regret[:draws]
    mu = mu[:, :draws]
    sigma = sigma[:, :draws]
    log_density = np.empty((draws, y.size, 4), dtype=float)
    for m in range(4):
        scale = sigma[m, :, None]
        log_density[:, :, m] = -0.5 * np.log(2.0 * np.pi) - np.log(scale) - 0.5 * ((y[None, :] - mu[m]) / scale) ** 2
    log_mixture = logsumexp(np.log(np.clip(weights, 1e-300, None)) + log_density, axis=2)
    log_predictive = logsumexp(log_mixture, axis=0) - np.log(draws)
    return -log_predictive, weights, regret


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("pymc", "numpyro"), required=True)
    parser.add_argument("--field-dir", type=Path, required=True)
    parser.add_argument("--freeze", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    freeze = json.loads(args.freeze.read_text(encoding="utf-8"))
    temperature = float(freeze["selected_temperature"])
    feature_mean = np.asarray(freeze["common_advantage_feature_mean"], dtype=float)
    feature_sd = np.asarray(freeze["common_advantage_feature_sd"], dtype=float)
    if np.any(feature_sd <= 0):
        raise RuntimeError("non-positive frozen feature scale")

    full_path = args.field_dir / f"field_input_{args.backend}_full.npz"
    field_path = args.field_dir / "regret_field.npz"
    receipt_path = args.field_dir / "receipt.json"
    full = np.load(full_path, allow_pickle=False)
    field = np.load(field_path, allow_pickle=False)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt["receipt_hash"] != freeze["field_receipts"][args.backend]:
        raise RuntimeError("field receipt does not match frozen calibration receipt")

    nlpd_mix, weights_cal, regret_cal = mixture_nlpd(full, field, "calibration", temperature)
    component_nlpd = np.asarray(full["calibration_nlpd_components"], dtype=float)
    advantage = np.min(component_nlpd, axis=1) - nlpd_mix
    entropy_cal = np.mean(-np.sum(weights_cal * np.log(np.clip(weights_cal, 1e-300, None)), axis=2), axis=0)
    spread_cal = np.mean(np.max(regret_cal, axis=2) - np.min(regret_cal, axis=2), axis=0)
    horizon_cal = np.asarray(full["calibration_day"], dtype=float) - 5.0
    x_raw = np.column_stack((entropy_cal, spread_cal, horizon_cal))

    weights_final, regret_final = weights_and_regret(field, "final", temperature)
    entropy_final = np.mean(-np.sum(weights_final * np.log(np.clip(weights_final, 1e-300, None)), axis=2), axis=0)
    spread_final = np.mean(np.max(regret_final, axis=2) - np.min(regret_final, axis=2), axis=0)
    horizon_final = np.asarray(full["final_day"], dtype=float) - 7.0
    x_final_raw = np.column_stack((entropy_final, spread_final, horizon_final))

    x = (x_raw - feature_mean) / feature_sd
    x_final = (x_final_raw - feature_mean) / feature_sd
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.output, y=advantage, X=x, X_final=x_final)

    metadata = {
        "gate_id": freeze["gate_id"],
        "freeze_sha256": sha256_file(args.freeze),
        "backend": args.backend,
        "temperature": temperature,
        "field_receipt": receipt["receipt_hash"],
        "field_npz_sha256": sha256_file(field_path),
        "full_input_sha256": sha256_file(full_path),
        "feature_names": freeze["advantage_features"],
        "feature_mean": feature_mean.tolist(),
        "feature_sd": feature_sd.tolist(),
        "calibration_mean_mixture_nlpd": float(np.mean(nlpd_mix)),
        "calibration_mean_point_oracle_nlpd": float(np.mean(np.min(component_nlpd, axis=1))),
        "calibration_mean_advantage": float(np.mean(advantage)),
        "calibration_positive_advantage_fraction": float(np.mean(advantage > 0.0)),
        "output_sha256": sha256_file(args.output),
        "future_outcomes_visible": False,
    }
    meta_path = args.output.with_suffix(".json")
    meta_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(metadata, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
