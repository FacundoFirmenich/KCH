from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

from .canonical import attach_hash


def _matrix(value: Any, *, name: str) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    if result.ndim != 2 or result.shape[0] < 2 or result.shape[1] < 1 or not np.all(np.isfinite(result)):
        raise ValueError(f"{name} must be a finite two-dimensional sample matrix")
    return result


def _logdet_positive(matrix: np.ndarray, ridge: float) -> float:
    regularized = 0.5 * (matrix + matrix.T) + ridge * np.eye(matrix.shape[0])
    sign, value = np.linalg.slogdet(regularized)
    if sign <= 0:
        raise ValueError("regularized covariance is not positive definite")
    return float(value)


def gaussian_information_structure(observations: Any, *, ridge: float = 1e-9) -> dict[str, Any]:
    x = _matrix(observations, name="observations")
    if x.shape[0] <= x.shape[1]:
        raise ValueError("information estimates require more observations than variables")
    if ridge <= 0:
        raise ValueError("ridge must be positive")
    covariance = np.cov(x, rowvar=False, ddof=1)
    covariance = np.atleast_2d(covariance)
    d = covariance.shape[0]
    log2pie = float(np.log(2.0 * np.pi * np.e))

    def entropy(indices: tuple[int, ...]) -> float:
        sub = covariance[np.ix_(indices, indices)]
        return 0.5 * (len(indices) * log2pie + _logdet_positive(sub, ridge))

    full_indices = tuple(range(d))
    h_full = entropy(full_indices)
    h_single = sum(entropy((index,)) for index in full_indices)
    h_leave_one_out = sum(entropy(tuple(j for j in full_indices if j != index)) for index in full_indices)
    total_correlation = h_single - h_full
    dual_total_correlation = h_leave_one_out - (d - 1) * h_full
    o_information = total_correlation - dual_total_correlation
    eigenvalues = np.linalg.eigvalsh(covariance + ridge * np.eye(d))
    p = eigenvalues / eigenvalues.sum()
    effective_rank = float(np.exp(-np.sum(p * np.log(np.maximum(p, 1e-300)))))
    return attach_hash({
        "schema": "kch.gaussian-multivariate-information.v0.1.0",
        "observations": int(x.shape[0]),
        "variables": int(d),
        "ridge": ridge,
        "total_correlation_nats": float(total_correlation),
        "dual_total_correlation_nats": float(dual_total_correlation),
        "o_information_nats": float(o_information),
        "effective_rank": effective_rank,
        "status": "ESTIMATED_GAUSSIAN_LOCAL_NOT_DISTRIBUTION_FREE",
    })


def mdl_comparison(*, holdout_observations: int, joint_nll: float, independent_nll: float,
                   joint_parameters: int, independent_parameters: int) -> dict[str, Any]:
    if holdout_observations < 1 or min(joint_parameters, independent_parameters) < 0:
        raise ValueError("invalid MDL dimensions")
    n = float(holdout_observations)
    joint = float(joint_nll) + 0.5 * joint_parameters * np.log(n)
    independent = float(independent_nll) + 0.5 * independent_parameters * np.log(n)
    return attach_hash({
        "schema": "kch.mdl-holdout-comparison.v0.1.0",
        "holdout_observations": holdout_observations,
        "joint_description_length": joint,
        "independent_description_length": independent,
        "joint_gain": independent - joint,
        "verdict": "JOINT_SHORTER" if joint < independent else "INDEPENDENT_NOT_WORSE",
        "claim_boundary": "One preregistered holdout comparison; not sufficient by itself for octet irreducibility.",
    })


def linear_holdout_utility(x_train: Any, y_train: Any, x_holdout: Any, y_holdout: Any, *, ridge: float = 1e-8) -> dict[str, Any]:
    train = _matrix(x_train, name="x_train")
    hold = _matrix(x_holdout, name="x_holdout")
    yt = np.asarray(y_train, dtype=np.float64).reshape(-1, 1)
    yh = np.asarray(y_holdout, dtype=np.float64).reshape(-1, 1)
    if train.shape[0] != yt.shape[0] or hold.shape[0] != yh.shape[0] or train.shape[1] != hold.shape[1]:
        raise ValueError("train/holdout dimensions do not align")

    def fit_predict(columns: tuple[int, ...]) -> np.ndarray:
        a = np.column_stack((np.ones(train.shape[0]), train[:, columns]))
        b = np.column_stack((np.ones(hold.shape[0]), hold[:, columns]))
        penalty = ridge * np.eye(a.shape[1])
        penalty[0, 0] = 0.0
        beta = np.linalg.solve(a.T @ a + penalty, a.T @ yt)
        return b @ beta

    full_prediction = fit_predict(tuple(range(train.shape[1])))
    full_mse = float(np.mean((full_prediction - yh) ** 2))
    single = []
    for index in range(train.shape[1]):
        mse = float(np.mean((fit_predict((index,)) - yh) ** 2))
        single.append({"feature": index, "mse": mse})
    best = min(single, key=lambda item: item["mse"])
    return attach_hash({
        "schema": "kch.linear-holdout-utility.v0.1.0",
        "train_rows": int(train.shape[0]),
        "holdout_rows": int(hold.shape[0]),
        "features": int(train.shape[1]),
        "full_mse": full_mse,
        "best_single_feature": best,
        "full_gain_over_best_single": best["mse"] - full_mse,
        "status": "FULL_VECTOR_BETTER" if full_mse < best["mse"] else "NO_FULL_VECTOR_GAIN",
        "claim_boundary": "Linear holdout utility does not establish nonlinear emergence or causal irreducibility.",
    })


@dataclass(frozen=True, slots=True)
class _OperatorCandidate:
    level: str
    predict: Callable[[np.ndarray], np.ndarray]
    parameters: dict[str, Any]


def _mse(prediction: np.ndarray, target: np.ndarray) -> float:
    return float(np.mean((prediction - target) ** 2))


def _fit_a0(x: np.ndarray, y: np.ndarray) -> _OperatorCandidate:
    denominator = float(np.sum(x * x))
    c = max(0.0, -float(np.sum(x * y)) / max(denominator, 1e-300))
    return _OperatorCandidate("A0_NEGATIVE_SCALAR", lambda z, c=c: -c * z, {"c": c})


def _fit_a1(x: np.ndarray, y: np.ndarray) -> _OperatorCandidate:
    denominator = np.sum(x * x, axis=0)
    c = np.maximum(0.0, -np.sum(x * y, axis=0) / np.maximum(denominator, 1e-300))
    return _OperatorCandidate("A1_NEGATIVE_DIAGONAL", lambda z, c=c: -z * c, {"diagonal": c.tolist()})


def _fit_a2(x: np.ndarray, y: np.ndarray) -> _OperatorCandidate:
    d = x.shape[1]
    if d > 8:
        raise ValueError("exact signed-permutation search is bounded to dimension <= 8")
    best: tuple[float, tuple[int, ...], np.ndarray] | None = None
    for permutation in itertools.permutations(range(d)):
        xp = x[:, permutation]
        signs = np.where(np.sum(xp * y, axis=0) >= 0.0, 1.0, -1.0)
        error = _mse(xp * signs, y)
        if best is None or error < best[0]:
            best = (error, permutation, signs)
    assert best is not None
    _, permutation, signs = best
    p = np.asarray(permutation, dtype=int)
    s = np.asarray(signs, dtype=np.float64)
    return _OperatorCandidate("A2_SIGNED_PERMUTATION", lambda z, p=p, s=s: z[:, p] * s,
                              {"permutation": list(permutation), "signs": s.tolist()})


def _fit_a3(x: np.ndarray, y: np.ndarray) -> _OperatorCandidate:
    mx, my = x.mean(axis=0), y.mean(axis=0)
    u, _, vt = np.linalg.svd((x - mx).T @ (y - my), full_matrices=False)
    q = u @ vt
    b = my - mx @ q
    return _OperatorCandidate("A3_ORTHOGONAL_AFFINE", lambda z, q=q, b=b: z @ q + b,
                              {"orthogonal": q.tolist(), "intercept": b.tolist()})


def fit_antisymmetry_hierarchy(
    train_x: Any, train_y: Any, calibration_x: Any, calibration_y: Any,
    holdout_x: Any, holdout_y: Any, *, minimum_relative_improvement: float = 0.01,
) -> dict[str, Any]:
    tx, ty = _matrix(train_x, name="train_x"), _matrix(train_y, name="train_y")
    cx, cy = _matrix(calibration_x, name="calibration_x"), _matrix(calibration_y, name="calibration_y")
    hx, hy = _matrix(holdout_x, name="holdout_x"), _matrix(holdout_y, name="holdout_y")
    for left, right, name in ((tx, ty, "train"), (cx, cy, "calibration"), (hx, hy, "holdout")):
        if left.shape != right.shape:
            raise ValueError(f"{name} x/y shapes differ")
    if tx.shape[1] != cx.shape[1] or tx.shape[1] != hx.shape[1]:
        raise ValueError("feature dimensions differ across splits")
    if not 0 <= minimum_relative_improvement < 1:
        raise ValueError("minimum_relative_improvement must be in [0,1)")
    candidates = (_fit_a0(tx, ty), _fit_a1(tx, ty), _fit_a2(tx, ty), _fit_a3(tx, ty))
    selected = candidates[0]
    calibration_rows = []
    best_error = _mse(selected.predict(cx), cy)
    calibration_rows.append({"level": selected.level, "mse": best_error, "advanced": True})
    for candidate in candidates[1:]:
        error = _mse(candidate.predict(cx), cy)
        threshold = best_error * (1.0 - minimum_relative_improvement)
        advanced = error < threshold
        calibration_rows.append({"level": candidate.level, "mse": error, "advanced": advanced})
        if advanced:
            selected, best_error = candidate, error
    holdout_rows = [{"level": item.level, "mse": _mse(item.predict(hx), hy)} for item in candidates]
    selected_holdout = next(item["mse"] for item in holdout_rows if item["level"] == selected.level)
    baseline_holdout = holdout_rows[0]["mse"]
    return attach_hash({
        "schema": "kch.antisymmetry-hierarchy.v0.1.0",
        "selection_split": "CALIBRATION_ONLY",
        "holdout_used_for_selection": False,
        "levels": calibration_rows,
        "selected_level": selected.level,
        "selected_parameters": selected.parameters,
        "holdout": holdout_rows,
        "selected_holdout_gain_over_a0": baseline_holdout - selected_holdout,
        "status": "LOCAL_HOLDOUT_SUPPORT" if selected_holdout < baseline_holdout else "NO_HOLDOUT_ADVANCE_OVER_A0",
        "universal_operator": False,
        "claim_boundary": "The selected operator is local to the supplied frozen splits; transport across new jurisdictions and models remains a separate gate.",
    })

