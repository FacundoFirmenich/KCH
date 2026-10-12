from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Iterable, Sequence

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize
from scipy.special import i0e

Array = NDArray[np.float64]
EPS = 1e-12


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def content_id(prefix: str, value: Any) -> str:
    return f"{prefix}:{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"


def wrap_angle(x: Array | float) -> Array | float:
    return (np.asarray(x) + np.pi) % (2.0 * np.pi) - np.pi


def wrap_axial(x: Array | float) -> Array | float:
    """Wrap an unoriented axis angle to [-pi/2, pi/2)."""
    return (np.asarray(x) + 0.5 * np.pi) % np.pi - 0.5 * np.pi


def normalize(v: Array, *, eps: float = EPS) -> Array:
    n = float(np.linalg.norm(v))
    if not np.isfinite(n) or n <= eps:
        raise ValueError("cannot normalize zero or non-finite vector")
    return np.asarray(v, dtype=float) / n


def skew(v: Array) -> Array:
    x, y, z = np.asarray(v, dtype=float)
    return np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]], dtype=float)


def rotation_about_axis(axis: Array, angle: float) -> Array:
    a = normalize(np.asarray(axis, dtype=float))
    k = skew(a)
    return np.eye(3) + math.sin(angle) * k + (1.0 - math.cos(angle)) * (k @ k)


def minimal_rotation(a: Array, b: Array) -> Array:
    """Proper minimal rotation carrying unit vector a to unit vector b."""
    a = normalize(np.asarray(a, dtype=float))
    b = normalize(np.asarray(b, dtype=float))
    c = float(np.clip(np.dot(a, b), -1.0, 1.0))
    if c > 1.0 - 1e-12:
        return np.eye(3)
    if c < -1.0 + 1e-12:
        basis = np.eye(3)[int(np.argmin(np.abs(a)))]
        axis = normalize(np.cross(a, basis))
        return rotation_about_axis(axis, np.pi)
    v = np.cross(a, b)
    k = skew(v)
    return np.eye(3) + k + (k @ k) / (1.0 + c)


def local_frame(tangent: Array) -> Array:
    """Return columns (n, b, t), with deterministic cross-section orientation."""
    t = normalize(np.asarray(tangent, dtype=float))
    reference = np.array([0.0, 0.0, 1.0])
    if abs(float(np.dot(reference, t))) > 0.9:
        reference = np.array([1.0, 0.0, 0.0])
    n = normalize(reference - np.dot(reference, t) * t)
    b = normalize(np.cross(t, n))
    return np.column_stack([n, b, t])


def tensor_from_slip_normal(slip: Array, normal: Array) -> Array:
    """Normalized double-couple tensor; invariant to exchanging slip and normal."""
    s = normalize(np.asarray(slip, dtype=float))
    n = normalize(np.asarray(normal, dtype=float))
    if abs(float(np.dot(s, n))) > 1e-8:
        raise ValueError("slip and normal must be orthogonal")
    tensor = np.outer(s, n) + np.outer(n, s)
    tensor = 0.5 * (tensor + tensor.T)
    tensor -= np.trace(tensor) / 3.0 * np.eye(3)
    return tensor / np.linalg.norm(tensor, ord="fro")


def double_couple_tensor(strike_deg: float, dip_deg: float, rake_deg: float) -> Array:
    """Normalized double-couple moment tensor in NED coordinates.

    The construction uses strike, down-dip, normal, and slip vectors directly,
    so exchanging the two nodal planes leaves the tensor invariant.
    """
    phi = math.radians(float(strike_deg))
    delta = math.radians(float(dip_deg))
    lam = math.radians(float(rake_deg))
    strike = np.array([math.cos(phi), math.sin(phi), 0.0], dtype=float)
    down_dip = np.array(
        [-math.sin(phi) * math.cos(delta), math.cos(phi) * math.cos(delta), math.sin(delta)],
        dtype=float,
    )
    normal = normalize(np.cross(strike, down_dip))
    slip = normalize(math.cos(lam) * strike + math.sin(lam) * down_dip)
    return tensor_from_slip_normal(slip, normal)


def tensor_from_axis_phase(phase: float, tangent: Array) -> Array:
    """Construct a normalized trace-free symmetric tensor with projective P-axis phase."""
    frame = local_frame(tangent)
    n, b, t = frame[:, 0], frame[:, 1], frame[:, 2]
    p = math.cos(phase) * n + math.sin(phase) * b
    q = -math.sin(phase) * n + math.cos(phase) * b
    # Eigenvalues are distinct, trace free; p is the compressional (minimum) axis.
    tensor = -1.0 * np.outer(p, p) + 0.35 * np.outer(q, q) + 0.65 * np.outer(t, t)
    tensor -= np.trace(tensor) / 3.0 * np.eye(3)
    return tensor / np.linalg.norm(tensor, ord="fro")


def projective_axis_phase(tensor: Array, tangent: Array, *, min_projection: float = 0.15) -> float:
    tensor = np.asarray(tensor, dtype=float)
    if tensor.shape != (3, 3) or not np.allclose(tensor, tensor.T, atol=1e-10):
        raise ValueError("tensor must be a symmetric 3x3 matrix")
    values, vectors = np.linalg.eigh(tensor)
    p_axis = vectors[:, int(np.argmin(values))]
    frame = local_frame(tangent)
    n, b = frame[:, 0], frame[:, 1]
    xy = np.array([np.dot(p_axis, n), np.dot(p_axis, b)], dtype=float)
    norm = float(np.linalg.norm(xy))
    if norm < min_projection:
        raise ValueError("principal axis is insufficiently observable in the fault cross-section")
    phase = math.atan2(float(xy[1]), float(xy[0]))
    return float(wrap_axial(phase))


def transport_tensor(tensor: Array, tangent_from: Array, tangent_to: Array) -> Array:
    r = minimal_rotation(tangent_from, tangent_to)
    transported = r @ np.asarray(tensor, dtype=float) @ r.T
    return 0.5 * (transported + transported.T)


def signed_axial_increment(
    parent_tensor: Array,
    child_tensor: Array,
    tangent_parent: Array,
    tangent_child: Array,
) -> float:
    transported = transport_tensor(parent_tensor, tangent_parent, tangent_child)
    parent_phase = projective_axis_phase(transported, tangent_child)
    child_phase = projective_axis_phase(child_tensor, tangent_child)
    return float(wrap_axial(child_phase - parent_phase))


def commutator_chirality(parent_tensor: Array, child_tensor: Array, tangent: Array) -> float:
    a = np.asarray(parent_tensor, dtype=float)
    b = np.asarray(child_tensor, dtype=float)
    comm = b @ a - a @ b
    axial = np.array([comm[2, 1], comm[0, 2], comm[1, 0]], dtype=float)
    denom = float(np.linalg.norm(comm, ord="fro"))
    if denom <= EPS:
        return 0.0
    return float(np.dot(normalize(tangent), axial) / denom)


def _a1_inv(r: float) -> float:
    r = float(np.clip(r, 0.0, 0.999999999))
    if r < 0.53:
        return 2 * r + r**3 + 5 * r**5 / 6
    if r < 0.85:
        return -0.4 + 1.39 * r + 0.43 / (1 - r)
    return 1 / (r**3 - 4 * r**2 + 3 * r)


def axial_log_density(residual: Array, concentration: float) -> Array:
    kappa = max(float(concentration), 1e-9)
    # Axial von Mises density on an interval of length pi.
    log_i0 = math.log(float(i0e(kappa))) + abs(kappa)
    return kappa * np.cos(2.0 * residual) - math.log(np.pi) - log_i0


@dataclass(frozen=True)
class CircularFit:
    beta: Array
    concentration: float
    log_likelihood: float
    bic: float
    parameter_count: int
    converged: bool
    design_names: tuple[str, ...]

    def predict(self, x: Array) -> Array:
        return np.asarray(wrap_axial(np.asarray(x, dtype=float) @ self.beta), dtype=float)

    def to_dict(self) -> dict[str, Any]:
        return {
            "beta": {name: float(value) for name, value in zip(self.design_names, self.beta)},
            "concentration": float(self.concentration),
            "log_likelihood": float(self.log_likelihood),
            "bic": float(self.bic),
            "parameter_count": int(self.parameter_count),
            "converged": bool(self.converged),
        }


def fit_axial_regression(
    x: Array,
    y: Array,
    names: Sequence[str],
    *,
    weights: Array | None = None,
    ridge: float = 1e-6,
    initial: Array | None = None,
) -> CircularFit:
    x = np.asarray(x, dtype=float)
    y = np.asarray(wrap_axial(np.asarray(y, dtype=float)), dtype=float)
    if x.ndim != 2 or y.ndim != 1 or len(x) != len(y):
        raise ValueError("incompatible design/response dimensions")
    if x.shape[1] != len(names):
        raise ValueError("design names do not match design columns")
    if len(y) <= x.shape[1] + 2:
        raise ValueError("insufficient observations for circular regression")
    w = np.ones(len(y), dtype=float) if weights is None else np.asarray(weights, dtype=float)
    w = w / np.mean(w)

    def objective(beta: Array) -> tuple[float, Array]:
        residual = np.asarray(wrap_axial(y - x @ beta), dtype=float)
        value = float(np.sum(w * (1.0 - np.cos(2.0 * residual))) + ridge * np.dot(beta, beta))
        # d(1-cos(2r))/dbeta = -2 sin(2r) x, because dr/dbeta=-x.
        gradient = -2.0 * (x.T @ (w * np.sin(2.0 * residual))) + 2.0 * ridge * beta
        return value, gradient

    start = np.zeros(x.shape[1], dtype=float) if initial is None else np.asarray(initial, dtype=float)
    result = minimize(
        fun=lambda b: objective(b)[0],
        x0=start,
        jac=lambda b: objective(b)[1],
        method="L-BFGS-B",
        options={"maxiter": 800, "ftol": 1e-12, "gtol": 1e-8},
    )
    beta = np.asarray(result.x, dtype=float)
    residual = np.asarray(wrap_axial(y - x @ beta), dtype=float)
    resultant = float(abs(np.mean(np.exp(2j * residual))))
    concentration = _a1_inv(resultant)
    log_likelihood = float(np.sum(axial_log_density(residual, concentration)))
    k = x.shape[1] + 1
    bic = float(k * math.log(len(y)) - 2.0 * log_likelihood)
    return CircularFit(
        beta=beta,
        concentration=concentration,
        log_likelihood=log_likelihood,
        bic=bic,
        parameter_count=k,
        converged=bool(result.success),
        design_names=tuple(names),
    )


def score_fit(fit: CircularFit, x: Array, y: Array) -> dict[str, Any]:
    y = np.asarray(wrap_axial(np.asarray(y, dtype=float)), dtype=float)
    prediction = fit.predict(x)
    residual = np.asarray(wrap_axial(y - prediction), dtype=float)
    log_score = axial_log_density(residual, fit.concentration)
    return {
        "count": int(len(y)),
        "mean_log_score": float(np.mean(log_score)),
        "total_log_score": float(np.sum(log_score)),
        "circular_rmse_rad": float(np.sqrt(np.mean(residual**2))),
        "circular_mae_rad": float(np.mean(np.abs(residual))),
        "residual": residual,
        "per_edge_log_score": log_score,
    }


@dataclass(frozen=True)
class EdgeTable:
    y: Array
    path_km: Array
    log_dt: Array
    curvature: Array
    static_delta: Array
    magnitude_parent: Array
    quality: Array
    segment: NDArray[np.int64]
    event_index: NDArray[np.int64]
    sigma_angle: Array

    def __len__(self) -> int:
        return len(self.y)

    def subset(self, index: Array | NDArray[np.int64]) -> "EdgeTable":
        return EdgeTable(**{name: np.asarray(getattr(self, name))[index] for name in self.__dataclass_fields__})


def _segment_columns(segment: NDArray[np.int64], levels: Sequence[int]) -> tuple[list[Array], list[str]]:
    cols: list[Array] = []
    names: list[str] = []
    for level in levels[1:]:
        cols.append((segment == level).astype(float))
        names.append(f"segment_{level}")
    return cols, names


def design_matrix(edges: EdgeTable, family: str, segment_levels: Sequence[int]) -> tuple[Array, tuple[str, ...]]:
    columns: list[Array] = [np.ones(len(edges), dtype=float)]
    names = ["intercept"]
    if family in {"TEMPORAL", "GEOMETRIC", "NETWORK", "HELICAL"}:
        columns.append(edges.log_dt)
        names.append("log_dt")
    if family in {"GEOMETRIC", "NETWORK", "HELICAL"}:
        columns.extend([edges.curvature, edges.static_delta, edges.magnitude_parent, edges.quality])
        names.extend(["curvature", "static_delta", "magnitude_parent", "quality"])
    if family in {"NETWORK", "HELICAL"}:
        seg_cols, seg_names = _segment_columns(edges.segment, segment_levels)
        columns.extend(seg_cols)
        names.extend(seg_names)
    if family == "HELICAL":
        columns.append(edges.path_km)
        names.append("path_km")
    return np.column_stack(columns), tuple(names)


def chronological_split(n: int, train_fraction: float = 0.5, calibration_fraction: float = 0.25) -> dict[str, NDArray[np.int64]]:
    if n < 40:
        raise ValueError("at least 40 edges are required")
    train_end = int(math.floor(train_fraction * n))
    cal_end = int(math.floor((train_fraction + calibration_fraction) * n))
    if not (5 < train_end < cal_end < n - 5):
        raise ValueError("invalid chronological split")
    return {
        "train": np.arange(0, train_end, dtype=np.int64),
        "calibration": np.arange(train_end, cal_end, dtype=np.int64),
        "test": np.arange(cal_end, n, dtype=np.int64),
        "fit": np.arange(0, cal_end, dtype=np.int64),
    }


def select_baseline(edges: EdgeTable, split: dict[str, NDArray[np.int64]]) -> tuple[str, dict[str, Any]]:
    levels = sorted(set(int(x) for x in edges.segment.tolist()))
    candidates: list[dict[str, Any]] = []
    for family in ("NULL", "TEMPORAL", "GEOMETRIC", "NETWORK"):
        x, names = design_matrix(edges, family, levels)
        fit = fit_axial_regression(x[split["train"]], edges.y[split["train"]], names)
        score = score_fit(fit, x[split["calibration"]], edges.y[split["calibration"]])
        penalized = score["mean_log_score"] - 0.002 * fit.parameter_count
        candidates.append(
            {
                "family": family,
                "penalized_calibration_score": float(penalized),
                "calibration_mean_log_score": float(score["mean_log_score"]),
                "parameter_count": fit.parameter_count,
                "fit": fit,
            }
        )
    candidates.sort(key=lambda row: (-row["penalized_calibration_score"], row["parameter_count"], row["family"]))
    return str(candidates[0]["family"]), {
        "selected": candidates[0]["family"],
        "candidates": [
            {k: v for k, v in row.items() if k != "fit"}
            for row in candidates
        ],
    }


def moving_block_bootstrap_lower(values: Array, *, seed: int, replicates: int = 199) -> dict[str, Any]:
    values = np.asarray(values, dtype=float)
    n = len(values)
    block = max(2, int(round(n ** (1.0 / 3.0))))
    rng = np.random.default_rng(seed)
    means = np.empty(replicates, dtype=float)
    for r in range(replicates):
        sample: list[float] = []
        while len(sample) < n:
            start = int(rng.integers(0, max(1, n - block + 1)))
            sample.extend(values[start : start + block].tolist())
        means[r] = float(np.mean(sample[:n]))
    return {
        "replicates": replicates,
        "block_length": block,
        "observed_mean": float(np.mean(values)),
        "lower_95": float(np.quantile(means, 0.025)),
        "upper_95": float(np.quantile(means, 0.975)),
        "positive_fraction": float(np.mean(means > 0.0)),
    }


def _permutation_p_value(
    edges: EdgeTable,
    split: dict[str, NDArray[np.int64]],
    baseline_family: str,
    observed_gain: float,
    *,
    seed: int,
    permutations: int,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    levels = sorted(set(int(x) for x in edges.segment.tolist()))
    fit_index = split["fit"]
    test_index = split["test"]
    xb, names_b = design_matrix(edges, baseline_family, levels)
    xh, names_h = design_matrix(edges, "HELICAL", levels)
    base_fit = fit_axial_regression(xb[fit_index], edges.y[fit_index], names_b)
    base_test = score_fit(base_fit, xb[test_index], edges.y[test_index])
    null_gains = np.empty(permutations, dtype=float)
    for r in range(permutations):
        perm = np.arange(len(edges))
        # Preserve broad temporal and segment structure while destroying path-phase coupling.
        for segment in levels:
            members = np.flatnonzero(edges.segment == segment)
            if len(members) > 2:
                shift = int(rng.integers(1, len(members)))
                perm[members] = np.roll(members, shift)
        x_perm = xh.copy()
        path_col = names_h.index("path_km")
        x_perm[:, path_col] = edges.path_km[perm]
        fit = fit_axial_regression(x_perm[fit_index], edges.y[fit_index], names_h)
        score = score_fit(fit, x_perm[test_index], edges.y[test_index])
        null_gains[r] = score["mean_log_score"] - base_test["mean_log_score"]
    p = (1.0 + float(np.sum(null_gains >= observed_gain))) / (permutations + 1.0)
    return {
        "permutations": permutations,
        "raw_p": float(p),
        "null_gain_median": float(np.median(null_gains)),
        "null_gain_q95": float(np.quantile(null_gains, 0.95)),
    }


def evaluate_dynamic_gate(
    edges: EdgeTable,
    *,
    seed: int = 20260927,
    permutations: int = 99,
    bootstrap_replicates: int = 199,
    uncertainty_replicates: int = 32,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    thresholds = thresholds or {
        "minimum_log_score_gain": 0.02,
        "minimum_rmse_improvement": 0.05,
        "maximum_delta_bic": -10.0,
        "maximum_null_p": 0.05,
        "minimum_bootstrap_lower": 0.0,
        "minimum_uncertainty_pass_fraction": 0.8,
        "minimum_reverse_sign_consistency": 0.8,
    }
    split = chronological_split(len(edges))
    levels = sorted(set(int(x) for x in edges.segment.tolist()))
    baseline_family, baseline_selection = select_baseline(edges, split)
    xb, names_b = design_matrix(edges, baseline_family, levels)
    xh, names_h = design_matrix(edges, "HELICAL", levels)
    fit_index = split["fit"]
    test_index = split["test"]
    baseline_fit = fit_axial_regression(xb[fit_index], edges.y[fit_index], names_b)
    helical_fit = fit_axial_regression(xh[fit_index], edges.y[fit_index], names_h)
    baseline_test = score_fit(baseline_fit, xb[test_index], edges.y[test_index])
    helical_test = score_fit(helical_fit, xh[test_index], edges.y[test_index])
    log_gain = float(helical_test["mean_log_score"] - baseline_test["mean_log_score"])
    rmse_improvement = float(
        (baseline_test["circular_rmse_rad"] - helical_test["circular_rmse_rad"])
        / max(baseline_test["circular_rmse_rad"], EPS)
    )
    delta_bic = float(helical_fit.bic - baseline_fit.bic)
    per_edge_gain = np.asarray(helical_test["per_edge_log_score"]) - np.asarray(baseline_test["per_edge_log_score"])
    bootstrap = moving_block_bootstrap_lower(per_edge_gain, seed=seed + 101, replicates=bootstrap_replicates)
    null = _permutation_p_value(
        edges,
        split,
        baseline_family,
        log_gain,
        seed=seed + 211,
        permutations=permutations,
    )
    path_index = names_h.index("path_km")
    kappa_hat = float(helical_fit.beta[path_index])

    # Time reversal must reverse the signed transport coefficient under the same geometry.
    reverse_edges = EdgeTable(
        y=np.asarray(wrap_axial(-edges.y), dtype=float),
        path_km=edges.path_km.copy(),
        log_dt=edges.log_dt.copy(),
        curvature=-edges.curvature.copy(),
        static_delta=np.asarray(wrap_axial(-edges.static_delta), dtype=float),
        magnitude_parent=edges.magnitude_parent.copy(),
        quality=edges.quality.copy(),
        segment=edges.segment.copy(),
        event_index=edges.event_index.copy(),
        sigma_angle=edges.sigma_angle.copy(),
    )
    xh_reverse, names_reverse = design_matrix(reverse_edges, "HELICAL", levels)
    reverse_fit = fit_axial_regression(xh_reverse[fit_index], reverse_edges.y[fit_index], names_reverse)
    kappa_reverse = float(reverse_fit.beta[names_reverse.index("path_km")])
    reverse_consistency = 1.0 if (abs(kappa_hat) > 1e-9 and np.sign(kappa_hat) == -np.sign(kappa_reverse)) else 0.0

    rng = np.random.default_rng(seed + 307)
    uncertainty_passes: list[bool] = []
    perturbed_kappas: list[float] = []
    for _ in range(uncertainty_replicates):
        perturbed_y = np.asarray(
            wrap_axial(edges.y + rng.normal(0.0, np.maximum(edges.sigma_angle, 1e-4))),
            dtype=float,
        )
        perturbed = EdgeTable(
            y=perturbed_y,
            path_km=edges.path_km,
            log_dt=edges.log_dt,
            curvature=edges.curvature,
            static_delta=edges.static_delta,
            magnitude_parent=edges.magnitude_parent,
            quality=edges.quality,
            segment=edges.segment,
            event_index=edges.event_index,
            sigma_angle=edges.sigma_angle,
        )
        xb_p, _ = design_matrix(perturbed, baseline_family, levels)
        xh_p, _ = design_matrix(perturbed, "HELICAL", levels)
        bf = fit_axial_regression(xb_p[fit_index], perturbed.y[fit_index], names_b)
        hf = fit_axial_regression(xh_p[fit_index], perturbed.y[fit_index], names_h)
        bs = score_fit(bf, xb_p[test_index], perturbed.y[test_index])
        hs = score_fit(hf, xh_p[test_index], perturbed.y[test_index])
        gain = float(hs["mean_log_score"] - bs["mean_log_score"])
        kappa = float(hf.beta[path_index])
        perturbed_kappas.append(kappa)
        uncertainty_passes.append(
            gain >= thresholds["minimum_log_score_gain"]
            and np.sign(kappa) == np.sign(kappa_hat)
        )
    uncertainty_fraction = float(np.mean(uncertainty_passes))

    gates = {
        "log_score_gain": log_gain >= thresholds["minimum_log_score_gain"],
        "rmse_improvement": rmse_improvement >= thresholds["minimum_rmse_improvement"],
        "delta_bic": delta_bic <= thresholds["maximum_delta_bic"],
        "null_p": null["raw_p"] <= thresholds["maximum_null_p"],
        "bootstrap": bootstrap["lower_95"] > thresholds["minimum_bootstrap_lower"],
        "uncertainty": uncertainty_fraction >= thresholds["minimum_uncertainty_pass_fraction"],
        "time_reversal": reverse_consistency >= thresholds["minimum_reverse_sign_consistency"],
    }
    positive = all(gates.values())
    return {
        "outcome": "DYNAMIC_HELICAL_TRANSPORT_SUPPORTED" if positive else "NONHELICAL_DYNAMIC_RIVAL_SUFFICIENT",
        "baseline_selection": baseline_selection,
        "baseline_family": baseline_family,
        "baseline_fit": baseline_fit.to_dict(),
        "helical_fit": helical_fit.to_dict(),
        "baseline_test": {k: v for k, v in baseline_test.items() if k not in {"residual", "per_edge_log_score"}},
        "helical_test": {k: v for k, v in helical_test.items() if k not in {"residual", "per_edge_log_score"}},
        "mean_log_score_gain_per_edge": log_gain,
        "relative_circular_rmse_improvement": rmse_improvement,
        "helix_minus_baseline_delta_bic": delta_bic,
        "signed_twist_rate_rad_per_km": kappa_hat,
        "time_reversed_twist_rate_rad_per_km": kappa_reverse,
        "time_reversal_sign_consistency": reverse_consistency,
        "moving_block_bootstrap": bootstrap,
        "path_permutation_null": null,
        "uncertainty_pass_fraction": uncertainty_fraction,
        "uncertainty_twist_rate_median": float(np.median(perturbed_kappas)),
        "thresholds": thresholds,
        "gates": gates,
        "positive": positive,
        "split_counts": {key: int(len(value)) for key, value in split.items()},
    }


def _reflect(value: float, low: float, high: float) -> float:
    while value < low or value > high:
        if value < low:
            value = low + (low - value)
        if value > high:
            value = high - (value - high)
    return value


def simulate_edges(
    n_events: int,
    *,
    seed: int,
    scenario: str,
    twist_rate: float = 0.0,
    noise_sd: float = 0.18,
    measurement_sd: float = 0.025,
) -> EdgeTable:
    if n_events < 80:
        raise ValueError("n_events must be at least 80")
    if scenario not in {"NULL", "TIME_ONLY", "STATIC_FIELD", "REGIME_DRIFT", "HELICAL"}:
        raise ValueError(f"unknown scenario {scenario}")
    rng = np.random.default_rng(seed)
    length = 35.0
    time = np.zeros(n_events)
    s = np.zeros(n_events)
    segment = np.zeros(n_events, dtype=np.int64)
    magnitude = np.zeros(n_events)
    static_phase = np.zeros(n_events)
    residual_phase = np.zeros(n_events)
    psi = np.zeros(n_events)
    parent = np.full(n_events, -1, dtype=np.int64)
    curvature_at = lambda z: 0.055 * math.sin(2.0 * math.pi * z / length)
    static_at = lambda z, seg: 0.35 * math.sin(2.0 * math.pi * z / length) + 0.13 * seg

    s[0] = length * 0.5
    segment[0] = 0
    magnitude[0] = 1.5 + rng.exponential(0.45)
    static_phase[0] = static_at(s[0], segment[0])
    residual_phase[0] = rng.normal(0.0, noise_sd)
    psi[0] = float(wrap_axial(static_phase[0] + residual_phase[0]))

    for j in range(1, n_events):
        time[j] = time[j - 1] + rng.exponential(0.6)
        candidates = np.arange(max(0, j - 30), j)
        dt = time[j] - time[candidates]
        # Prefer recent parents but retain graph ambiguity.
        weights = np.exp(-dt / 4.0)
        weights /= np.sum(weights)
        p = int(rng.choice(candidates, p=weights))
        parent[j] = p
        step = rng.normal(0.0, 1.35)
        s[j] = _reflect(s[p] + step, 0.0, length)
        segment[j] = 0 if s[j] < length * 0.52 else 1
        magnitude[j] = 1.2 + rng.exponential(0.5)
        static_phase[j] = static_at(s[j], int(segment[j]))
        path = abs(s[j] - s[p])
        logdt = math.log1p((time[j] - time[p]) / 0.6)
        increment = rng.normal(0.0, noise_sd)
        if scenario == "TIME_ONLY":
            increment += 0.10 * logdt
        elif scenario == "REGIME_DRIFT":
            increment += 0.11 if segment[j] == 1 else -0.08
        elif scenario == "HELICAL":
            increment += twist_rate * path + 0.035 * logdt
        # STATIC_FIELD is entirely represented by static_phase; residual has no dynamic drift.
        residual_phase[j] = float(wrap_axial(residual_phase[p] + increment))
        psi[j] = float(wrap_axial(static_phase[j] + residual_phase[j]))

    rows: dict[str, list[float | int]] = {
        "y": [],
        "path_km": [],
        "log_dt": [],
        "curvature": [],
        "static_delta": [],
        "magnitude_parent": [],
        "quality": [],
        "segment": [],
        "event_index": [],
        "sigma_angle": [],
    }
    for j in range(1, n_events):
        p = int(parent[j])
        path = abs(s[j] - s[p])
        rows["y"].append(float(wrap_axial(psi[j] - psi[p])))
        rows["path_km"].append(path)
        rows["log_dt"].append(math.log1p((time[j] - time[p]) / 0.6))
        rows["curvature"].append(curvature_at(s[j]) - curvature_at(s[p]))
        rows["static_delta"].append(float(wrap_axial(static_phase[j] - static_phase[p])))
        rows["magnitude_parent"].append(magnitude[p] - 1.0)
        rows["quality"].append(1.0 - measurement_sd / 0.2)
        rows["segment"].append(int(segment[j]))
        rows["event_index"].append(j)
        rows["sigma_angle"].append(measurement_sd)
    return EdgeTable(
        y=np.asarray(rows["y"], dtype=float),
        path_km=np.asarray(rows["path_km"], dtype=float),
        log_dt=np.asarray(rows["log_dt"], dtype=float),
        curvature=np.asarray(rows["curvature"], dtype=float),
        static_delta=np.asarray(rows["static_delta"], dtype=float),
        magnitude_parent=np.asarray(rows["magnitude_parent"], dtype=float),
        quality=np.asarray(rows["quality"], dtype=float),
        segment=np.asarray(rows["segment"], dtype=np.int64),
        event_index=np.asarray(rows["event_index"], dtype=np.int64),
        sigma_angle=np.asarray(rows["sigma_angle"], dtype=float),
    )


def fast_gate_metrics(edges: EdgeTable) -> dict[str, Any]:
    split = chronological_split(len(edges))
    levels = sorted(set(int(x) for x in edges.segment.tolist()))
    family, _ = select_baseline(edges, split)
    xb, names_b = design_matrix(edges, family, levels)
    xh, names_h = design_matrix(edges, "HELICAL", levels)
    bf = fit_axial_regression(xb[split["fit"]], edges.y[split["fit"]], names_b)
    hf = fit_axial_regression(xh[split["fit"]], edges.y[split["fit"]], names_h)
    bs = score_fit(bf, xb[split["test"]], edges.y[split["test"]])
    hs = score_fit(hf, xh[split["test"]], edges.y[split["test"]])
    gain = float(hs["mean_log_score"] - bs["mean_log_score"])
    rmse = float((bs["circular_rmse_rad"] - hs["circular_rmse_rad"]) / max(bs["circular_rmse_rad"], EPS))
    path_idx = names_h.index("path_km")
    kappa = float(hf.beta[path_idx])
    # Approximate coefficient uncertainty from a local linearization of the circular residual.
    residual = np.asarray(wrap_axial(edges.y[split["fit"]] - xh[split["fit"]] @ hf.beta), dtype=float)
    sigma2 = float(np.var(residual, ddof=max(1, xh.shape[1])))
    gram_inv = np.linalg.pinv(xh[split["fit"]].T @ xh[split["fit"]])
    se = math.sqrt(max(sigma2 * float(gram_inv[path_idx, path_idx]), EPS))
    z = abs(kappa) / se
    return {
        "baseline_family": family,
        "mean_log_score_gain_per_edge": gain,
        "relative_circular_rmse_improvement": rmse,
        "helix_minus_baseline_delta_bic": float(hf.bic - bf.bic),
        "signed_twist_rate_rad_per_km": kappa,
        "twist_rate_abs_z": float(z),
        "fast_positive": bool(gain >= 0.02 and rmse >= 0.05 and (hf.bic - bf.bic) <= -10.0 and z >= 2.58),
    }
