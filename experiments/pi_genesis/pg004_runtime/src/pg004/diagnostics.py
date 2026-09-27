from __future__ import annotations

import math
from typing import Any, Mapping

import numpy as np
from scipy.stats import norm, rankdata, wasserstein_distance

_EPS = np.finfo(float).eps


def _split_chains(chains: np.ndarray) -> np.ndarray:
    x = np.asarray(chains, dtype=float)
    if x.ndim != 2:
        raise ValueError("diagnostics require shape (chain, draw)")
    half = x.shape[1] // 2
    if half < 4:
        raise ValueError("at least eight draws per chain are required")
    return np.concatenate((x[:, :half], x[:, -half:]), axis=0)


def _rank_normalize(x: np.ndarray) -> np.ndarray:
    flat = np.asarray(x, dtype=float).reshape(-1)
    ranks = rankdata(flat, method="average")
    values = norm.ppf((ranks - 3.0 / 8.0) / (flat.size + 1.0 / 4.0))
    return values.reshape(np.asarray(x).shape)


def _basic_rhat(chains: np.ndarray) -> float:
    x = _split_chains(chains)
    m, n = x.shape
    means = np.mean(x, axis=1)
    variances = np.var(x, axis=1, ddof=1)
    within = float(np.mean(variances))
    if not math.isfinite(within) or within <= _EPS:
        return 1.0 if float(np.var(means)) <= _EPS else float("inf")
    between = float(n * np.var(means, ddof=1))
    var_plus = ((n - 1.0) / n) * within + between / n
    return float(np.sqrt(max(var_plus / within, 0.0)))


def rank_normalized_rhat(chains: np.ndarray) -> float:
    x = np.asarray(chains, dtype=float)
    ranked = _rank_normalize(x)
    folded = _rank_normalize(np.abs(x - np.median(x)))
    return float(max(_basic_rhat(ranked), _basic_rhat(folded)))


def _autocovariance_fft(x: np.ndarray) -> np.ndarray:
    y = np.asarray(x, dtype=float) - float(np.mean(x))
    n = y.size
    size = 1 << (2 * n - 1).bit_length()
    spectrum = np.fft.rfft(y, size)
    acov = np.fft.irfft(spectrum * np.conjugate(spectrum), size)[:n]
    return acov / np.arange(n, 0, -1)


def _ess_core(chains: np.ndarray) -> float:
    x = _split_chains(np.asarray(chains, dtype=float))
    m, n = x.shape
    means = np.mean(x, axis=1)
    variances = np.var(x, axis=1, ddof=1)
    within = float(np.mean(variances))
    between = float(n * np.var(means, ddof=1))
    var_plus = ((n - 1.0) / n) * within + between / n
    if not math.isfinite(var_plus) or var_plus <= _EPS:
        return float(m * n)
    acov = np.asarray([_autocovariance_fft(chain) for chain in x])
    rho = np.ones(n, dtype=float)
    for lag in range(1, n):
        rho[lag] = 1.0 - (within - float(np.mean(acov[:, lag]))) / var_plus
    pairs: list[float] = []
    for lag in range(1, n - 1, 2):
        pair = float(rho[lag] + rho[lag + 1])
        if not math.isfinite(pair) or pair < 0:
            break
        if pairs:
            pair = min(pair, pairs[-1])
        pairs.append(pair)
    tau_hat = max(-1.0 + 2.0 * (1.0 + sum(pairs)), 1.0 / math.log10(max(m * n, 10)))
    return float(min(m * n / tau_hat, m * n))


def bulk_ess(chains: np.ndarray) -> float:
    return _ess_core(_rank_normalize(np.asarray(chains, dtype=float)))


def tail_ess(chains: np.ndarray) -> float:
    x = np.asarray(chains, dtype=float)
    q05, q95 = np.quantile(x, [0.05, 0.95])
    return float(min(_ess_core((x <= q05).astype(float)), _ess_core((x >= q95).astype(float))))


def bfmi(energy: np.ndarray) -> list[float]:
    values = np.asarray(energy, dtype=float)
    if values.ndim != 2:
        return []
    output = []
    for chain in values:
        var = float(np.var(chain, ddof=1))
        output.append(float(np.mean(np.diff(chain) ** 2) / var) if var > _EPS else float("nan"))
    return output


def scalarize_samples(samples: Mapping[str, np.ndarray], semantic_names: tuple[str, ...]) -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}
    for name in semantic_names:
        if name not in samples:
            raise KeyError(f"missing semantic sample {name}")
        value = np.asarray(samples[name], dtype=float)
        if value.ndim == 2:
            result[name] = value
        elif value.ndim == 3:
            for idx in range(value.shape[-1]):
                result[f"{name}[{idx}]"] = value[..., idx]
        else:
            raise ValueError(f"unsupported shape for {name}: {value.shape}")
    return result


def summarize(values: Mapping[str, np.ndarray]) -> dict[str, dict[str, float]]:
    output: dict[str, dict[str, float]] = {}
    for name, array in values.items():
        x = np.asarray(array, dtype=float)
        if x.ndim != 2:
            raise ValueError(f"{name} is not scalar per draw")
        flat = x.reshape(-1)
        q05, q50, q95 = np.quantile(flat, [0.05, 0.5, 0.95])
        output[name] = {
            "mean": float(np.mean(flat)),
            "sd": float(np.std(flat, ddof=1)),
            "q05": float(q05),
            "q50": float(q50),
            "q95": float(q95),
            "rhat_rank_folded": rank_normalized_rhat(x),
            "ess_bulk": bulk_ess(x),
            "ess_tail": tail_ess(x),
        }
    return output


def health_metrics(summary: Mapping[str, Mapping[str, float]], divergences: int) -> dict[str, Any]:
    max_rhat_name = max(summary, key=lambda k: float(summary[k]["rhat_rank_folded"]))
    min_bulk_name = min(summary, key=lambda k: float(summary[k]["ess_bulk"]))
    min_tail_name = min(summary, key=lambda k: float(summary[k]["ess_tail"]))
    return {
        "max_rhat": float(summary[max_rhat_name]["rhat_rank_folded"]),
        "max_rhat_parameter": max_rhat_name,
        "min_bulk_ess": float(summary[min_bulk_name]["ess_bulk"]),
        "min_bulk_ess_parameter": min_bulk_name,
        "min_tail_ess": float(summary[min_tail_name]["ess_tail"]),
        "min_tail_ess_parameter": min_tail_name,
        "divergences": int(divergences),
    }


def conformance(left: Mapping[str, np.ndarray], right: Mapping[str, np.ndarray], parameters: list[str]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for name in parameters:
        a = np.asarray(left[name], dtype=float).reshape(-1)
        b = np.asarray(right[name], dtype=float).reshape(-1)
        ma, mb = float(np.mean(a)), float(np.mean(b))
        sa, sb = float(np.std(a, ddof=1)), float(np.std(b, ddof=1))
        pooled = max(math.sqrt(0.5 * (sa * sa + sb * sb)), 1e-12)
        metrics[name] = {
            "left_mean": ma,
            "right_mean": mb,
            "left_sd": sa,
            "right_sd": sb,
            "standardized_mean_delta": abs(ma - mb) / pooled,
            "sd_ratio_left_over_right": sa / max(sb, 1e-12),
            "standardized_wasserstein": float(wasserstein_distance(a, b) / pooled),
        }
    return metrics
