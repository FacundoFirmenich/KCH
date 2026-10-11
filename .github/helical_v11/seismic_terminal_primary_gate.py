from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.special import i0e

DAY = 86400.0
COHORT_NAMES = {0: "BAY_AREA", 1: "PARKFIELD_CENTRAL_SAF"}
MODELS = ["M0", "MT", "MG", "MH"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def wrap_axial(values: np.ndarray) -> np.ndarray:
    return (values + np.pi / 2.0) % np.pi - np.pi / 2.0


def kappa_from_residual(residual: np.ndarray, weights: np.ndarray | None = None) -> float:
    residual = np.asarray(residual, dtype=float)
    if weights is None:
        weights = np.ones_like(residual)
    weights = np.asarray(weights, dtype=float)
    if weights.sum() <= 0:
        return 1e-6
    c = np.sum(weights * np.cos(2.0 * residual)) / weights.sum()
    s = np.sum(weights * np.sin(2.0 * residual)) / weights.sum()
    resultant = min(max(float(np.hypot(c, s)), 0.0), 0.999999)
    if resultant < 0.53:
        kappa = 2 * resultant + resultant**3 + 5 * resultant**5 / 6
    elif resultant < 0.85:
        kappa = -0.4 + 1.39 * resultant + 0.43 / (1 - resultant)
    else:
        kappa = 1 / (resultant**3 - 4 * resultant**2 + 3 * resultant)
    return float(np.clip(kappa, 1e-6, 200.0))


def axial_logpdf(residual: np.ndarray, kappa: float) -> np.ndarray:
    return kappa * np.cos(2.0 * residual) - math.log(math.pi) - (math.log(float(i0e(kappa))) + abs(kappa))


def p_axis(strike_deg: np.ndarray, dip_deg: np.ndarray, rake_deg: np.ndarray) -> np.ndarray:
    strike = np.deg2rad(strike_deg.astype(float))
    dip = np.deg2rad(dip_deg.astype(float))
    rake = np.deg2rad(rake_deg.astype(float))
    strike_vector = np.stack([np.cos(strike), np.sin(strike), np.zeros_like(strike)], axis=1)
    down_dip = np.stack(
        [-np.sin(strike) * np.cos(dip), np.cos(strike) * np.cos(dip), np.sin(dip)], axis=1
    )
    normal = np.cross(strike_vector, down_dip)
    normal /= np.linalg.norm(normal, axis=1)[:, None]
    slip = np.cos(rake)[:, None] * strike_vector + np.sin(rake)[:, None] * down_dip
    slip /= np.linalg.norm(slip, axis=1)[:, None]
    axis = normal - slip
    axis /= np.linalg.norm(axis, axis=1)[:, None]
    return axis


def load_inputs(directional_path: Path, preflight_path: Path) -> dict[str, Any]:
    with np.load(directional_path, allow_pickle=False) as archive:
        directional = {key: archive[key] for key in archive.files}
    with np.load(preflight_path, allow_pickle=False) as archive:
        preflight = {key: archive[key] for key in archive.files}
    n = len(directional["evid"])
    if any(len(value) != n for key, value in directional.items() if key != "evid"):
        raise RuntimeError("directional length mismatch")
    required_preflight = ["axis_observable", "projection_norm", "tangent_ned", "along_fault_km", "candidate_starts"]
    for key in required_preflight:
        if key not in preflight:
            raise RuntimeError(f"missing preflight field {key}")
    axis = p_axis(directional["strike"], directional["dip"], directional["rake"])
    tangents = preflight["tangent_ned"].astype(float)
    down = np.array([0.0, 0.0, 1.0])
    e1 = np.cross(np.broadcast_to(down, tangents.shape), tangents)
    e1 /= np.linalg.norm(e1, axis=1)[:, None]
    e2 = np.cross(tangents, e1)
    x = np.sum(axis * e1, axis=1)
    y = np.sum(axis * e2, axis=1)
    projection = np.sqrt(x * x + y * y)
    if float(np.nanmax(np.abs(projection - preflight["projection_norm"]))) > 1e-10:
        raise RuntimeError("projection mismatch")
    observable = preflight["axis_observable"].astype(bool)
    phase = wrap_axial(np.arctan2(y, x))
    return {
        "D": directional,
        "P": preflight,
        "n": n,
        "observable": observable,
        "phase": phase,
        "zphase": np.exp(2j * phase),
    }


def fit_wrapped_ridge(X: np.ndarray, y: np.ndarray, weights: np.ndarray, ridge: float) -> dict[str, Any]:
    X = np.asarray(X, dtype=float)
    y = np.asarray(y, dtype=float)
    weights = np.asarray(weights, dtype=float)
    if X.shape[1] == 0:
        residual = wrap_axial(y)
        return {"beta": np.zeros(0), "kappa": kappa_from_residual(residual, weights), "n_params": 1}
    penalty = np.ones(X.shape[1])
    penalty[0] = 0.0
    sqrt_weights = np.sqrt(np.maximum(weights, 0.0))
    weighted_X = X * sqrt_weights[:, None]
    matrix = weighted_X.T @ weighted_X + ridge * np.diag(penalty) + 1e-10 * np.eye(X.shape[1])
    beta = np.linalg.solve(matrix, weighted_X.T @ (y * sqrt_weights))
    for _ in range(30):
        prediction = X @ beta
        target = prediction + wrap_axial(y - prediction)
        new_beta = np.linalg.solve(matrix, weighted_X.T @ (target * sqrt_weights))
        if np.max(np.abs(new_beta - beta)) < 1e-10:
            beta = new_beta
            break
        beta = new_beta
    residual = wrap_axial(y - X @ beta)
    return {"beta": beta, "kappa": kappa_from_residual(residual, weights), "n_params": len(beta) + 1}


class StaticField:
    def __init__(self, data: dict[str, Any], fit_indices: np.ndarray, degree: int):
        self.D = data["D"]
        self.P = data["P"]
        self.zphase = data["zphase"]
        self.models: dict[int, tuple] = {}
        global_z = np.mean(self.zphase[fit_indices])
        if abs(global_z) < 1e-12:
            global_z = 1.0 + 0.0j
        self.global_z = global_z / abs(global_z)
        for fault in np.unique(self.D["fault_assignment"][fit_indices]):
            ids = fit_indices[self.D["fault_assignment"][fit_indices] == fault]
            if len(ids) < 20:
                local = np.mean(self.zphase[ids]) if len(ids) else self.global_z
                self.models[int(fault)] = ("const", local / abs(local) if abs(local) > 1e-12 else self.global_z)
                continue
            along = self.P["along_fault_km"][ids].astype(float)
            center = float(np.mean(along))
            scale = float(np.std(along)) or 1.0
            standardized = (along - center) / scale
            local_degree = min(degree, max(0, len(ids) // 10))
            design = np.column_stack([standardized**power for power in range(local_degree + 1)])
            penalty = np.eye(design.shape[1]); penalty[0, 0] = 0.0
            matrix = design.T @ design + penalty
            real = np.linalg.solve(matrix, design.T @ self.zphase[ids].real)
            imag = np.linalg.solve(matrix, design.T @ self.zphase[ids].imag)
            self.models[int(fault)] = ("poly", center, scale, real, imag)

    def predict_z(self, ids: np.ndarray) -> np.ndarray:
        ids = np.asarray(ids, dtype=np.int64)
        output = np.empty(len(ids), dtype=complex)
        faults = self.D["fault_assignment"][ids]
        for fault in np.unique(faults):
            mask = faults == fault
            model = self.models.get(int(fault))
            if model is None:
                output[mask] = self.global_z
            elif model[0] == "const":
                output[mask] = model[1]
            else:
                _, center, scale, real, imag = model
                standardized = (self.P["along_fault_km"][ids[mask]] - center) / scale
                design = np.column_stack([standardized**power for power in range(len(real))])
                values = design @ real + 1j * (design @ imag)
                values[np.abs(values) < 1e-9] = self.global_z
                output[mask] = values
        output /= np.abs(output)
        return output

    def predict_phase(self, ids: np.ndarray) -> np.ndarray:
        return 0.5 * np.angle(self.predict_z(ids))


class FeatureSpec:
    def __init__(self, model: str, continuous: dict[str, np.ndarray], weights: np.ndarray):
        names: list[str] = []
        if model == "MT":
            names = ["logdt"]
        elif model in {"MG", "MH"}:
            names = ["logdt", "logdist", "curvature", "static_delta", "time_norm", "mag_parent"]
            if model == "MH":
                names.append("distance_raw")
        self.model = model
        self.names = names
        self.means: dict[str, float] = {}
        self.scales: dict[str, float] = {}
        for name in names:
            values = np.asarray(continuous[name], dtype=float)
            mean = float(np.sum(weights * values) / max(weights.sum(), 1e-12))
            scale = float(np.sqrt(np.sum(weights * (values - mean) ** 2) / max(weights.sum(), 1e-12)))
            self.means[name] = mean
            self.scales[name] = scale if scale >= 1e-8 else 1.0

    def transform(self, continuous: dict[str, np.ndarray]) -> np.ndarray:
        if self.model == "M0":
            return np.zeros((len(next(iter(continuous.values()))), 0), dtype=float)
        columns = [np.ones(len(next(iter(continuous.values()))), dtype=float)]
        for name in self.names:
            columns.append((np.asarray(continuous[name], dtype=float) - self.means[name]) / self.scales[name])
        return np.column_stack(columns)


def build_graph(data: dict[str, Any], code: int) -> dict[str, np.ndarray]:
    D, P, observable = data["D"], data["P"], data["observable"]
    indices = np.flatnonzero((D["cohort_code"] == code) & observable)
    indices = indices[np.argsort(D["event_time_epoch"][indices], kind="stable")]
    children: list[int] = []
    starts = [0]
    parent: list[int] = []
    child_edge: list[int] = []
    dt_values: list[float] = []
    distances: list[float] = []
    logweights: list[float] = []
    signs: list[float] = []
    curvature: list[float] = []
    raw_sums: list[float] = []
    phases: list[int] = []
    alpha, c_days, p_value, ell = 1.0, 0.05, 1.1, 5.0
    train_with_candidate = 0
    train_count = 0
    for child in indices:
        start, end = int(P["candidate_starts"][child]), int(P["candidate_starts"][child + 1])
        candidate = P["candidate_parent"][start:end].astype(np.int64)
        mask = observable[candidate] & (D["cohort_code"][candidate] == code)
        candidate = candidate[mask]
        dt = P["candidate_dt_days"][start:end][mask].astype(float)
        distance = P["candidate_distance_km"][start:end][mask].astype(float)
        sign = P["candidate_sign"][start:end][mask].astype(float)
        curv = P["candidate_curvature"][start:end][mask].astype(float)
        if len(candidate):
            logweight = alpha * D["mag"][candidate].astype(float) - p_value * np.log(dt + c_days) - distance / ell
            if len(candidate) > 20:
                keep = np.argpartition(logweight, -20)[-20:]
                order = np.lexsort((candidate[keep], -logweight[keep]))
                keep = keep[order]
                candidate, dt, distance, sign, curv, logweight = candidate[keep], dt[keep], distance[keep], sign[keep], curv[keep], logweight[keep]
            else:
                order = np.lexsort((candidate, -logweight))
                candidate, dt, distance, sign, curv, logweight = candidate[order], dt[order], distance[order], sign[order], curv[order], logweight[order]
            shifted = np.exp(logweight - np.max(logweight))
            raw_sum = float(shifted.sum() * np.exp(np.max(logweight)))
        else:
            logweight = np.empty(0, dtype=float)
            raw_sum = 0.0
        phase = int(D["split_code"][child])
        if phase == 0:
            train_count += 1
            train_with_candidate += int(len(candidate) > 0)
        parent.extend(candidate.tolist())
        child_edge.extend([int(child)] * len(candidate))
        dt_values.extend(dt.tolist())
        distances.extend(distance.tolist())
        signs.extend(sign.tolist())
        curvature.extend(curv.tolist())
        logweights.extend(logweight.tolist())
        children.append(int(child))
        raw_sums.append(raw_sum)
        phases.append(phase)
        starts.append(len(parent))
    raw_sums_array = np.asarray(raw_sums, dtype=float)
    target_background = float(np.clip(1.0 - train_with_candidate / max(train_count, 1), 0.05, 0.8))
    train_mask = np.asarray(phases) == 0
    train_sums = raw_sums_array[train_mask]
    low, high = 1e-12, max(1.0, float(np.max(train_sums)) * 100.0 if len(train_sums) else 1.0)
    for _ in range(100):
        middle = (low + high) / 2.0
        mean = float(np.mean(middle / (middle + train_sums))) if len(train_sums) else 1.0
        if mean < target_background:
            low = middle
        else:
            high = middle
    background_scale = (low + high) / 2.0
    background_probability = background_scale / (background_scale + raw_sums_array)
    edge_probability = np.empty(len(parent), dtype=float)
    logweights_array = np.asarray(logweights, dtype=float)
    starts_array = np.asarray(starts, dtype=np.int64)
    for position in range(len(children)):
        left, right = starts_array[position], starts_array[position + 1]
        if right > left:
            local = logweights_array[left:right]
            probability = np.exp(local - np.max(local)); probability /= probability.sum()
            edge_probability[left:right] = (1.0 - background_probability[position]) * probability
    return {
        "children": np.asarray(children, dtype=np.int64),
        "starts": starts_array,
        "parent": np.asarray(parent, dtype=np.int64),
        "child_edge": np.asarray(child_edge, dtype=np.int64),
        "dt": np.asarray(dt_values, dtype=float),
        "distance": np.asarray(distances, dtype=float),
        "sign": np.asarray(signs, dtype=float),
        "curvature": np.asarray(curvature, dtype=float),
        "probability": edge_probability,
        "background_probability": background_probability,
        "phase": np.asarray(phases, dtype=np.int8),
        "background_scale": np.asarray([background_scale]),
    }


def edge_base(data: dict[str, Any], graph: dict[str, np.ndarray], static: StaticField) -> dict[str, Any]:
    D, phase = data["D"], data["phase"]
    parent, child = graph["parent"], graph["child_edge"]
    sign = graph["sign"]
    response = wrap_axial(sign * (phase[child] - phase[parent]))
    static_delta = wrap_axial(sign * (static.predict_phase(child) - static.predict_phase(parent)))
    times = D["event_time_epoch"][child].astype(float)
    child_times = D["event_time_epoch"][graph["children"]].astype(float)
    tmin, tmax = float(np.min(child_times)), float(np.max(child_times))
    continuous = {
        "logdt": np.log1p(graph["dt"]),
        "logdist": np.log1p(graph["distance"]),
        "curvature": graph["curvature"],
        "static_delta": static_delta,
        "time_norm": 2.0 * (times - tmin) / max(tmax - tmin, 1.0) - 1.0,
        "mag_parent": D["mag"][parent].astype(float),
        "distance_raw": graph["distance"].astype(float),
    }
    edge_position = np.repeat(np.arange(len(graph["children"])), np.diff(graph["starts"]))
    return {
        "response": response,
        "continuous": continuous,
        "weights": graph["probability"],
        "edge_phase": graph["phase"][edge_position],
        "edge_position": edge_position,
    }


def fit_models(data: dict[str, Any], graph: dict[str, np.ndarray], phases: list[int], degree: int, ridge: float) -> tuple[StaticField, dict[str, Any], dict[str, FeatureSpec], dict[str, Any], float]:
    fit_children = graph["children"][np.isin(graph["phase"], phases)]
    static = StaticField(data, fit_children, degree)
    base = edge_base(data, graph, static)
    edge_mask = np.isin(base["edge_phase"], phases) & (base["weights"] > 0)
    specs: dict[str, FeatureSpec] = {}
    models: dict[str, Any] = {}
    for model_name in MODELS:
        fit_continuous = {key: value[edge_mask] for key, value in base["continuous"].items()}
        spec = FeatureSpec(model_name, fit_continuous, base["weights"][edge_mask])
        design = spec.transform(fit_continuous)
        models[model_name] = fit_wrapped_ridge(design, base["response"][edge_mask], base["weights"][edge_mask], ridge)
        specs[model_name] = spec
    background_residual = wrap_axial(data["phase"][fit_children] - static.predict_phase(fit_children))
    background_kappa = kappa_from_residual(background_residual)
    return static, base, specs, models, background_kappa


def evaluate(data: dict[str, Any], graph: dict[str, np.ndarray], static: StaticField, base: dict[str, Any], spec: FeatureSpec, model: dict[str, Any], background_kappa: float, phases: list[int]) -> dict[str, Any]:
    design = spec.transform(base["continuous"])
    predicted_delta = design @ model["beta"] if design.shape[1] else np.zeros(len(base["response"]))
    edge_center = wrap_axial(data["phase"][graph["parent"]] + graph["sign"] * predicted_delta)
    edge_density = np.exp(axial_logpdf(wrap_axial(data["phase"][graph["child_edge"]] - edge_center), model["kappa"]))
    child_count = len(graph["children"])
    edge_component = graph["probability"] * edge_density
    edge_density_sum = np.bincount(base["edge_position"], weights=edge_component, minlength=child_count)
    edge_real = np.bincount(base["edge_position"], weights=graph["probability"] * np.cos(2.0 * edge_center), minlength=child_count)
    edge_imag = np.bincount(base["edge_position"], weights=graph["probability"] * np.sin(2.0 * edge_center), minlength=child_count)
    background_center = static.predict_phase(graph["children"])
    background_density = np.exp(axial_logpdf(wrap_axial(data["phase"][graph["children"]] - background_center), background_kappa))
    density = graph["background_probability"] * background_density + edge_density_sum
    real = graph["background_probability"] * np.cos(2.0 * background_center) + edge_real
    imag = graph["background_probability"] * np.sin(2.0 * background_center) + edge_imag
    predicted_phase = 0.5 * np.arctan2(imag, real)
    error = wrap_axial(data["phase"][graph["children"]] - predicted_phase)
    mask = np.isin(graph["phase"], phases)
    score = np.log(np.maximum(density, 1e-300))
    return {
        "mean_log_score": float(np.mean(score[mask])),
        "rmse": float(np.sqrt(np.mean(error[mask] ** 2))),
        "n": int(mask.sum()),
        "logscore_vector": score[mask],
        "error_vector": error[mask],
        "child_ids": graph["children"][mask],
        "child_positions": np.flatnonzero(mask),
    }


def calibration(data: dict[str, Any], graphs: dict[int, dict[str, np.ndarray]]) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = []
    for code in [0, 1]:
        for degree in [0, 1, 2]:
            for ridge in [0.1, 1.0, 10.0]:
                static, base, specs, models, background_kappa = fit_models(data, graphs[code], [0], degree, ridge)
                evaluations = {
                    name: evaluate(data, graphs[code], static, base, specs[name], models[name], background_kappa, [1])
                    for name in MODELS
                }
                n = evaluations["M0"]["n"]
                for name in MODELS:
                    params = models[name]["n_params"]
                    adjusted = evaluations[name]["mean_log_score"] - 0.5 * params * math.log(max(n, 2)) / max(n, 1)
                    rows.append({
                        "code": code, "degree": degree, "ridge": ridge, "model": name,
                        "log_score": evaluations[name]["mean_log_score"], "rmse": evaluations[name]["rmse"],
                        "adjusted": adjusted, "parameters": params,
                    })
    grid = pd.DataFrame(rows)
    selection: dict[str, Any] = {}
    for code in [0, 1]:
        subset = grid[grid["code"] == code]
        nonhelical = subset[subset["model"].isin(["M0", "MT", "MG"])].sort_values(
            ["adjusted", "degree", "ridge", "model"], ascending=[False, True, True, True], kind="stable"
        ).iloc[0]
        helical = subset[(subset["model"] == "MH") & (subset["degree"] == int(nonhelical["degree"]))].sort_values(
            ["adjusted", "ridge"], ascending=[False, True], kind="stable"
        ).iloc[0]
        selection[str(code)] = {
            "baseline_model": str(nonhelical["model"]),
            "static_degree": int(nonhelical["degree"]),
            "baseline_ridge": float(nonhelical["ridge"]),
            "helical_ridge": float(helical["ridge"]),
            "baseline_calibration_adjusted_score": float(nonhelical["adjusted"]),
            "helical_calibration_adjusted_score": float(helical["adjusted"]),
        }
    return grid, selection


def moving_block_bootstrap(times: np.ndarray, score_delta: np.ndarray, error_baseline: np.ndarray, error_helical: np.ndarray, replicates: int, seed: int) -> np.ndarray:
    day_index = np.floor(times / (30.0 * DAY)).astype(int)
    blocks = [np.flatnonzero(day_index == value) for value in np.unique(day_index)]
    rng = np.random.default_rng(seed)
    output = np.empty((replicates, 2), dtype=float)
    target = len(score_delta)
    for replicate in range(replicates):
        chosen: list[int] = []
        while len(chosen) < target:
            block = blocks[int(rng.integers(0, len(blocks)))]
            chosen.extend(block.tolist())
        index = np.asarray(chosen[:target], dtype=int)
        log_gain = float(np.mean(score_delta[index]))
        baseline_rmse = float(np.sqrt(np.mean(error_baseline[index] ** 2)))
        helical_rmse = float(np.sqrt(np.mean(error_helical[index] ** 2)))
        output[replicate] = [log_gain, (baseline_rmse - helical_rmse) / baseline_rmse if baseline_rmse else 0.0]
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directional", type=Path, required=True)
    parser.add_argument("--preflight", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    data = load_inputs(args.directional, args.preflight)
    graphs = {code: build_graph(data, code) for code in [0, 1]}
    grid, selection = calibration(data, graphs)
    grid_path = args.out / "SEISMIC_TERMINAL_CALIBRATION_GRID_V1_1.csv"
    grid.to_csv(grid_path, index=False)
    freeze_body = {
        "format": "KCH_SEISMIC_TERMINAL_CALIBRATION_FREEZE_V1_1",
        "protocol_sha256": sha256_file(args.protocol),
        "directional_sha256": sha256_file(args.directional),
        "preflight_sha256": sha256_file(args.preflight),
        "calibration_grid_sha256": sha256_file(grid_path),
        "selection": selection,
        "test_accessed": False,
        "authority_ceiling": "NONE",
    }
    freeze_body["freeze_id"] = "s11freeze:" + hashlib.sha256(canonical(freeze_body)).hexdigest()
    write_json(args.out / "SEISMIC_TERMINAL_CALIBRATION_FREEZE_V1_1.json", freeze_body)
    results: dict[str, Any] = {}
    metric_rows = []
    for code in [0, 1]:
        chosen = selection[str(code)]
        degree = chosen["static_degree"]
        baseline_name = chosen["baseline_model"]
        static_b, base_b, specs_b, models_b, background_b = fit_models(data, graphs[code], [0, 1], degree, chosen["baseline_ridge"])
        static_h, base_h, specs_h, models_h, background_h = fit_models(data, graphs[code], [0, 1], degree, chosen["helical_ridge"])
        test_baseline = evaluate(data, graphs[code], static_b, base_b, specs_b[baseline_name], models_b[baseline_name], background_b, [2])
        test_helical = evaluate(data, graphs[code], static_h, base_h, specs_h["MH"], models_h["MH"], background_h, [2])
        fit_baseline = evaluate(data, graphs[code], static_b, base_b, specs_b[baseline_name], models_b[baseline_name], background_b, [0, 1])
        fit_helical = evaluate(data, graphs[code], static_h, base_h, specs_h["MH"], models_h["MH"], background_h, [0, 1])
        nfit = fit_baseline["n"]
        bic_baseline = -2.0 * np.sum(fit_baseline["logscore_vector"]) + models_b[baseline_name]["n_params"] * math.log(max(nfit, 2))
        bic_helical = -2.0 * np.sum(fit_helical["logscore_vector"]) + models_h["MH"]["n_params"] * math.log(max(nfit, 2))
        log_gain = test_helical["mean_log_score"] - test_baseline["mean_log_score"]
        rmse_gain = (test_baseline["rmse"] - test_helical["rmse"]) / test_baseline["rmse"] if test_baseline["rmse"] else 0.0
        score_delta = test_helical["logscore_vector"] - test_baseline["logscore_vector"]
        times = data["D"]["event_time_epoch"][test_baseline["child_ids"]].astype(float)
        bootstrap = moving_block_bootstrap(
            times, score_delta, test_baseline["error_vector"], test_helical["error_vector"],
            int(protocol["stability"]["moving_block_bootstrap_replicates"]), 11710 + code,
        )
        gates = {
            "log_score": log_gain >= float(protocol["materiality"]["minimum_mean_log_score_gain_per_test_child"]),
            "rmse": rmse_gain >= float(protocol["materiality"]["minimum_relative_axial_rmse_improvement"]),
            "delta_bic": (bic_helical - bic_baseline) <= float(protocol["materiality"]["maximum_delta_bic_helical_minus_baseline"]),
            "bootstrap_lower": float(np.quantile(bootstrap[:, 0], 0.025)) > float(protocol["materiality"]["cluster_bootstrap_lower_95_must_exceed"]),
        }
        primary_pass = all(gates.values())
        result = {
            "cohort": COHORT_NAMES[code],
            "test_n": test_baseline["n"],
            "baseline_model": baseline_name,
            "static_degree": degree,
            "baseline_ridge": chosen["baseline_ridge"],
            "helical_ridge": chosen["helical_ridge"],
            "baseline_log_score": test_baseline["mean_log_score"],
            "helical_log_score": test_helical["mean_log_score"],
            "log_score_gain": log_gain,
            "baseline_rmse": test_baseline["rmse"],
            "helical_rmse": test_helical["rmse"],
            "relative_rmse_improvement": rmse_gain,
            "bic_baseline": float(bic_baseline),
            "bic_helical": float(bic_helical),
            "delta_bic_helical_minus_baseline": float(bic_helical - bic_baseline),
            "bootstrap_log_gain_q025_median_q975": [float(value) for value in np.quantile(bootstrap[:, 0], [0.025, 0.5, 0.975])],
            "bootstrap_rmse_gain_q025_median_q975": [float(value) for value in np.quantile(bootstrap[:, 1], [0.025, 0.5, 0.975])],
            "primary_gates": gates,
            "primary_gate_pass": primary_pass,
            "heavy_null_and_stability_battery": "REQUIRED" if primary_pass else "LOGICALLY_SHORT_CIRCUITED_AFTER_NECESSARY_GATE_FAILURE",
        }
        results[COHORT_NAMES[code]] = result
        metric_rows.append({key: value for key, value in result.items() if not isinstance(value, (dict, list))})
    positive_primary = sum(int(value["primary_gate_pass"]) for value in results.values())
    if positive_primary == 0:
        outcome = "NONHELICAL_FULL_NETWORK_RIVAL_GENERALIZES"
    elif positive_primary < int(protocol["materiality"]["positive_primary_cohorts_required"]):
        outcome = "LOCAL_DYNAMIC_SIGNAL_REQUIRES_HEAVY_BATTERY_NOT_REPLICATED"
    else:
        outcome = "HEAVY_NULL_AND_STABILITY_BATTERY_REQUIRED_BEFORE_POSITIVE_CLAIM"
    body = {
        "format": "KCH_SEISMIC_TERMINAL_FULL_NETWORK_PRIMARY_RESULT_V1_1",
        "protocol_sha256": sha256_file(args.protocol),
        "freeze_id": freeze_body["freeze_id"],
        "test_access": "OPENED_ONCE_AFTER_CALIBRATION_FREEZE",
        "unit_results": results,
        "positive_primary_cohorts": positive_primary,
        "required_positive_primary_cohorts": int(protocol["materiality"]["positive_primary_cohorts_required"]),
        "outcome": outcome,
        "physical_helicity": "NOT_DEMONSTRATED",
        "universal_absence_of_helicity": "NOT_ESTABLISHED",
        "terminal_closure_authorized": outcome == "NONHELICAL_FULL_NETWORK_RIVAL_GENERALIZES",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "authority_ceiling": "NONE",
    }
    body["gate_result_id"] = "s11g:" + hashlib.sha256(canonical(body)).hexdigest()
    write_json(args.out / "SEISMIC_TERMINAL_FULL_NETWORK_PRIMARY_RESULT_V1_1.json", body)
    pd.DataFrame(metric_rows).to_csv(args.out / "SEISMIC_TERMINAL_PRIMARY_METRICS_V1_1.csv", index=False)
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
