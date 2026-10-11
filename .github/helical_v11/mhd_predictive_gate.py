from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

BASE_CHANNELS = ["USFLUX", "MEANSHR", "SHRGT45", "R_VALUE", "TOTUSJZ", "TOTPOT", "AREA_ACR", "LAT_FWT", "LON_FWT"]
UNSIGNED_CHANNELS = ["ABSNJZH", "TOTUSJH"]
SIGNED_CHANNELS = ["MEANJZH", "MEANALP"]
MODEL_FAMILIES = ["B", "U", "H"]
PERIODS = ["TRAIN", "CALIBRATION", "TEST_A", "TEST_B"]


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


def locate(root: Path, name: str) -> Path:
    matches = list(root.rglob(name))
    if len(matches) != 1:
        raise RuntimeError(f"expected one {name} below {root}, observed {matches}")
    return matches[0]


def signed_log1p(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    return np.sign(numeric) * np.log1p(np.abs(numeric))


def prepare_frame(census_path: Path, protocol: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, list[str]]]:
    frame = pd.read_csv(census_path, compression="gzip", low_memory=False)
    required = {"NOAA_AR", "origin_utc", "period", *BASE_CHANNELS, *UNSIGNED_CHANNELS, *SIGNED_CHANNELS}
    labels = [target["label"] for target in protocol["primary_targets"]]
    missing = sorted(required.union(labels) - set(frame.columns))
    if missing:
        raise RuntimeError(f"census missing required columns: {missing}")
    frame["origin_utc"] = pd.to_datetime(frame["origin_utc"], utc=True, errors="raise")
    frame["NOAA_AR"] = pd.to_numeric(frame["NOAA_AR"], errors="raise").astype(int)
    frame["period"] = frame["period"].astype(str)
    if not set(frame["period"].unique()).issubset(set(PERIODS)):
        raise RuntimeError(f"unexpected periods: {sorted(frame['period'].unique())}")
    crossing = frame.groupby("NOAA_AR")["period"].nunique()
    if int((crossing > 1).sum()) != 0:
        raise RuntimeError("active-region split leakage detected")
    frame = frame.sort_values(["NOAA_AR", "origin_utc", "HARPNUM"], kind="stable").reset_index(drop=True)
    all_channels = BASE_CHANNELS + UNSIGNED_CHANNELS + SIGNED_CHANNELS
    feature_columns: dict[str, list[str]] = {"B": [], "U": [], "H": []}
    for channel in all_channels:
        transformed = signed_log1p(frame[channel])
        current_name = f"{channel}__slog_current"
        delta_name = f"{channel}__slog_delta6h"
        frame[current_name] = transformed
        frame[delta_name] = transformed.groupby(frame["NOAA_AR"], sort=False).diff().fillna(0.0)
        if channel in BASE_CHANNELS:
            feature_columns["B"].extend([current_name, delta_name])
        elif channel in UNSIGNED_CHANNELS:
            feature_columns["U"].extend([current_name, delta_name])
        else:
            feature_columns["H"].extend([current_name, delta_name])
    feature_columns["U"] = feature_columns["B"] + feature_columns["U"]
    hemisphere = np.sign(pd.to_numeric(frame["LAT_FWT"], errors="coerce").fillna(0.0).to_numpy(dtype=float))
    for channel in SIGNED_CHANNELS:
        for suffix in ["slog_current", "slog_delta6h"]:
            source = f"{channel}__{suffix}"
            target = f"{channel}__{suffix}__hemisphere_interaction"
            frame[target] = frame[source].to_numpy(dtype=float) * hemisphere
            feature_columns["H"].append(target)
    feature_columns["H"] = feature_columns["U"] + feature_columns["H"]
    for label in labels:
        frame[label] = pd.to_numeric(frame[label], errors="raise").astype(int)
        if not set(frame[label].unique()).issubset({0, 1}):
            raise RuntimeError(f"nonbinary label {label}")
    return frame, feature_columns


def equal_ar_weights(frame: pd.DataFrame) -> np.ndarray:
    counts = frame.groupby("NOAA_AR")["NOAA_AR"].transform("count").to_numpy(dtype=float)
    weights = 1.0 / counts
    return weights * (len(weights) / weights.sum())


def make_estimator(C: float, seed: int) -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median", add_indicator=True)),
            ("scaler", StandardScaler()),
            (
                "logistic",
                LogisticRegression(
                    C=float(C),
                    penalty="l2",
                    solver="lbfgs",
                    max_iter=3000,
                    random_state=seed,
                ),
            ),
        ]
    )


def fit_estimator(frame: pd.DataFrame, features: list[str], label: str, C: float, seed: int) -> Pipeline:
    model = make_estimator(C, seed)
    weights = equal_ar_weights(frame)
    model.fit(frame[features], frame[label].to_numpy(dtype=int), logistic__sample_weight=weights)
    return model


def probabilities(model: Pipeline, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    p = model.predict_proba(frame[features])[:, 1]
    return np.clip(p, 1e-9, 1.0 - 1e-9)


def weighted_mean(values: np.ndarray, weights: np.ndarray) -> float:
    return float(np.sum(values * weights) / np.sum(weights))


def log_scores(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    return y * np.log(p) + (1 - y) * np.log(1.0 - p)


def ece(y: np.ndarray, p: np.ndarray, w: np.ndarray, bins: int = 10) -> float:
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = float(np.sum(w))
    value = 0.0
    for index in range(bins):
        left, right = edges[index], edges[index + 1]
        mask = (p >= left) & ((p < right) if index < bins - 1 else (p <= right))
        if not np.any(mask):
            continue
        bin_weight = float(np.sum(w[mask]))
        value += (bin_weight / total) * abs(weighted_mean(y[mask], w[mask]) - weighted_mean(p[mask], w[mask]))
    return float(value)


def metrics(frame: pd.DataFrame, label: str, p: np.ndarray) -> dict[str, float]:
    y = frame[label].to_numpy(dtype=int)
    w = equal_ar_weights(frame)
    scores = log_scores(y, p)
    brier = weighted_mean((y - p) ** 2, w)
    if len(np.unique(y)) == 2:
        auprc = float(average_precision_score(y, p, sample_weight=w))
    else:
        auprc = float("nan")
    return {
        "weighted_log_score": weighted_mean(scores, w),
        "weighted_log_loss": -weighted_mean(scores, w),
        "weighted_brier": brier,
        "weighted_rmse": math.sqrt(brier),
        "weighted_auprc": auprc,
        "weighted_ece": ece(y, p, w),
    }


def per_ar_score_difference(frame: pd.DataFrame, label: str, p_h: np.ndarray, p_u: np.ndarray) -> pd.Series:
    y = frame[label].to_numpy(dtype=int)
    delta = log_scores(y, p_h) - log_scores(y, p_u)
    temp = pd.DataFrame({"NOAA_AR": frame["NOAA_AR"].to_numpy(dtype=int), "delta": delta})
    return temp.groupby("NOAA_AR", sort=True)["delta"].mean()


def normal_power(delta: float, sd: float, n_clusters: int, alpha: float) -> float:
    if sd <= 1e-15:
        return 1.0
    normal = NormalDist()
    z_alpha = normal.inv_cdf(1.0 - alpha)
    noncentral = delta * math.sqrt(n_clusters) / sd
    return float(normal.cdf(noncentral - z_alpha))


def select_lock(census_path: Path, protocol_path: Path, output: Path) -> int:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    frame, features = prepare_frame(census_path, protocol)
    train = frame[frame["period"] == "TRAIN"].copy()
    calibration = frame[frame["period"] == "CALIBRATION"].copy()
    tests = {name: frame[frame["period"] == name].copy() for name in ["TEST_A", "TEST_B"]}
    seed = int(protocol["resampling"]["random_seed"])
    selections: dict[str, Any] = {}
    calibration_differences: dict[str, Any] = {}
    for target in protocol["primary_targets"]:
        label = target["label"]
        target_selection: dict[str, Any] = {}
        calibration_predictions: dict[str, np.ndarray] = {}
        for family in MODEL_FAMILIES:
            candidates = []
            for C in protocol["estimator"]["C_grid"]:
                model = fit_estimator(train, features[family], label, float(C), seed)
                p = probabilities(model, calibration, features[family])
                result = metrics(calibration, label, p)
                candidates.append({"C": float(C), **result})
            candidates.sort(key=lambda row: (row["weighted_log_loss"], row["C"]))
            winner = candidates[0]
            target_selection[family] = {"selected_C": winner["C"], "calibration_metrics": winner, "candidate_grid": candidates}
            model = fit_estimator(train, features[family], label, winner["C"], seed)
            calibration_predictions[family] = probabilities(model, calibration, features[family])
        per_ar = per_ar_score_difference(calibration, label, calibration_predictions["H"], calibration_predictions["U"])
        sd = float(per_ar.std(ddof=1)) if len(per_ar) > 1 else 0.0
        material = float(protocol["power_gate"]["material_log_score_gain"])
        alpha = float(protocol["materiality"]["holm_family_alpha"]) / 6.0
        power = {
            name: normal_power(material, sd, int(part["NOAA_AR"].nunique()), alpha)
            for name, part in tests.items()
        }
        target_selection["power_before_test_open"] = {
            "calibration_active_regions": int(len(per_ar)),
            "calibration_ar_difference_sd": sd,
            "material_delta": material,
            "familywise_alpha_per_test": alpha,
            "test_active_regions": {name: int(part["NOAA_AR"].nunique()) for name, part in tests.items()},
            "estimated_power": power,
            "minimum_required": float(protocol["power_gate"]["minimum_power"]),
            "pass": all(value >= float(protocol["power_gate"]["minimum_power"]) for value in power.values()),
        }
        selections[target["name"]] = target_selection
        calibration_differences[target["name"]] = {
            "active_region_count": int(len(per_ar)),
            "mean": float(per_ar.mean()),
            "sd": sd,
        }
    all_power_pass = all(value["power_before_test_open"]["pass"] for value in selections.values())
    body = {
        "format": "KCH_MHD_MODEL_SELECTION_LOCK_V1_1",
        "protocol_sha256": sha256_file(protocol_path),
        "census_sha256": sha256_file(census_path),
        "protocol_status": protocol["status"],
        "selection_uses_periods": ["TRAIN", "CALIBRATION"],
        "test_metrics_evaluated": False,
        "selections": selections,
        "calibration_differences": calibration_differences,
        "all_power_gates_pass": all_power_pass,
        "test_open_authorized": all_power_pass,
        "authority_ceiling": "NONE",
    }
    body["selection_lock_id"] = "mhd11lock:" + hashlib.sha256(canonical(body)).hexdigest()
    write_json(output, body)
    print(json.dumps(body, indent=2, sort_keys=True))
    return 0 if all_power_pass else 3


def holm_adjust(rows: list[dict[str, Any]], alpha: float) -> None:
    order = sorted(range(len(rows)), key=lambda index: rows[index]["raw_p"])
    m = len(rows)
    running = 0.0
    for rank, index in enumerate(order):
        adjusted = min(1.0, (m - rank) * rows[index]["raw_p"])
        running = max(running, adjusted)
        rows[index]["holm_p"] = running
    for row in rows:
        row["holm_pass"] = bool(row["holm_p"] <= alpha)


def evaluate(census_path: Path, protocol_path: Path, lock_path: Path, out: Path) -> int:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    if lock.get("test_open_authorized") is not True:
        raise RuntimeError("power gate did not authorize test open")
    if lock.get("protocol_sha256") != sha256_file(protocol_path) or lock.get("census_sha256") != sha256_file(census_path):
        raise RuntimeError("selection lock source identity mismatch")
    frame, features = prepare_frame(census_path, protocol)
    fitting = frame[frame["period"].isin(["TRAIN", "CALIBRATION"])].copy()
    seed = int(protocol["resampling"]["random_seed"])
    rng = np.random.default_rng(seed)
    bootstrap_reps = int(protocol["resampling"]["cluster_bootstrap_replicates"])
    sign_reps = int(protocol["resampling"]["cluster_sign_flip_replicates"])
    metric_rows: list[dict[str, Any]] = []
    p_rows: list[dict[str, Any]] = []
    model_receipts: list[dict[str, Any]] = []
    for target in protocol["primary_targets"]:
        target_name, label = target["name"], target["label"]
        models: dict[str, Pipeline] = {}
        for family in MODEL_FAMILIES:
            C = float(lock["selections"][target_name][family]["selected_C"])
            models[family] = fit_estimator(fitting, features[family], label, C, seed)
            model_receipts.append({"target": target_name, "family": family, "C": C, "feature_count": len(features[family])})
        for period in ["TEST_A", "TEST_B"]:
            test = frame[frame["period"] == period].copy()
            predictions = {family: probabilities(models[family], test, features[family]) for family in MODEL_FAMILIES}
            family_metrics = {family: metrics(test, label, predictions[family]) for family in MODEL_FAMILIES}
            per_ar = per_ar_score_difference(test, label, predictions["H"], predictions["U"])
            observed = float(per_ar.mean())
            ar_values = per_ar.to_numpy(dtype=float)
            boot = np.empty(bootstrap_reps, dtype=float)
            for replicate in range(bootstrap_reps):
                boot[replicate] = float(rng.choice(ar_values, size=len(ar_values), replace=True).mean())
            lower = float(np.quantile(boot, 0.025))
            positive_fraction = float(np.mean(boot > 0.0))
            null = np.empty(sign_reps, dtype=float)
            for replicate in range(sign_reps):
                signs = rng.choice(np.array([-1.0, 1.0]), size=len(ar_values), replace=True)
                null[replicate] = float(np.mean(ar_values * signs))
            raw_p = float((1 + np.sum(null >= observed)) / (sign_reps + 1))
            row = {
                "target": target_name,
                "period": period,
                "test_windows": int(len(test)),
                "test_active_regions": int(test["NOAA_AR"].nunique()),
                "positive_windows": int(test[label].sum()),
                "positive_active_regions": int(test.groupby("NOAA_AR")[label].max().sum()),
                "log_score_gain_H_minus_U": family_metrics["H"]["weighted_log_score"] - family_metrics["U"]["weighted_log_score"],
                "log_score_gain_H_minus_B": family_metrics["H"]["weighted_log_score"] - family_metrics["B"]["weighted_log_score"],
                "relative_rmse_improvement_H_minus_U": (family_metrics["U"]["weighted_rmse"] - family_metrics["H"]["weighted_rmse"]) / family_metrics["U"]["weighted_rmse"],
                "auprc_gain_H_minus_U": family_metrics["H"]["weighted_auprc"] - family_metrics["U"]["weighted_auprc"],
                "ece_difference_H_minus_U": family_metrics["H"]["weighted_ece"] - family_metrics["U"]["weighted_ece"],
                "cluster_bootstrap_lower_95": lower,
                "cluster_bootstrap_positive_fraction": positive_fraction,
                "raw_p": raw_p,
                "metrics_B": family_metrics["B"],
                "metrics_U": family_metrics["U"],
                "metrics_H": family_metrics["H"],
            }
            metric_rows.append(row)
            p_rows.append(row)
    holm_adjust(p_rows, float(protocol["materiality"]["holm_family_alpha"]))
    thresholds = protocol["materiality"]
    for row in metric_rows:
        row["gates"] = {
            "log_score": row["log_score_gain_H_minus_U"] >= float(thresholds["minimum_log_score_gain_nats_per_window"]),
            "beats_baseline": row["log_score_gain_H_minus_B"] > 0.0,
            "rmse": row["relative_rmse_improvement_H_minus_U"] >= float(thresholds["minimum_relative_rmse_improvement"]),
            "auprc": row["auprc_gain_H_minus_U"] >= float(thresholds["minimum_auprc_gain"]),
            "ece": row["ece_difference_H_minus_U"] <= float(thresholds["maximum_ece_degradation"]),
            "bootstrap_lower": row["cluster_bootstrap_lower_95"] > float(thresholds["cluster_bootstrap_lower_95_must_exceed"]),
            "bootstrap_fraction": row["cluster_bootstrap_positive_fraction"] >= float(thresholds["signed_channel_positive_bootstrap_fraction"]),
            "holm": bool(row["holm_pass"]),
        }
        row["positive"] = all(row["gates"].values())
    horizon_status: dict[str, Any] = {}
    for target in [item["name"] for item in protocol["primary_targets"]]:
        subset = [row for row in metric_rows if row["target"] == target]
        horizon_status[target] = {
            "periods": {row["period"]: bool(row["positive"]) for row in subset},
            "replicated_positive": len(subset) == 2 and all(row["positive"] for row in subset),
        }
    positive_horizons = sum(int(status["replicated_positive"]) for status in horizon_status.values())
    required = int(thresholds["required_positive_horizons_for_family_claim"])
    outcome = "SIGNED_HELICITY_FORECASTING_SUPPORTED_REPLICATED" if positive_horizons >= required else "UNSIGNED_MAGNITUDE_OR_NONHELICAL_RIVAL_SUFFICIENT"
    serializable_rows = []
    for row in metric_rows:
        serializable_rows.append({key: value for key, value in row.items() if key not in {"metrics_B", "metrics_U", "metrics_H"}})
    result = {
        "format": "KCH_MHD_HELICITY_FORECAST_GATE_RESULT_V1_1",
        "protocol_sha256": sha256_file(protocol_path),
        "selection_lock_id": lock["selection_lock_id"],
        "census_sha256": sha256_file(census_path),
        "outcome": outcome,
        "positive_replicated_horizons": positive_horizons,
        "required_positive_replicated_horizons": required,
        "horizon_status": horizon_status,
        "metrics": serializable_rows,
        "model_receipts": model_receipts,
        "physical_helicity": "NOT_DEMONSTRATED" if outcome != "SIGNED_HELICITY_FORECASTING_SUPPORTED_REPLICATED" else "PREDICTIVE_SIGNED_PROXY_SUPPORTED_NOT_DIRECT_PHYSICAL_CAUSATION",
        "universal_absence_of_helicity": "NOT_ESTABLISHED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "authority_ceiling": "NONE",
    }
    result["gate_result_id"] = "mhd11g:" + hashlib.sha256(canonical(result)).hexdigest()
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "MHD_HELICITY_FORECAST_GATE_RESULT_V1_1.json", result)
    flat_rows = []
    for row in metric_rows:
        flat = {key: value for key, value in row.items() if not isinstance(value, dict)}
        flat.update({f"gate_{key}": value for key, value in row["gates"].items()})
        flat_rows.append(flat)
    pd.DataFrame(flat_rows).to_csv(out / "MHD_CONFIRMATORY_METRICS_V1_1.csv", index=False)
    write_json(out / "MHD_MODEL_RECEIPTS_V1_1.json", model_receipts)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    select = sub.add_parser("select-lock")
    select.add_argument("--census", type=Path, required=True)
    select.add_argument("--protocol", type=Path, required=True)
    select.add_argument("--output", type=Path, required=True)
    evaluate_parser = sub.add_parser("evaluate")
    evaluate_parser.add_argument("--census", type=Path, required=True)
    evaluate_parser.add_argument("--protocol", type=Path, required=True)
    evaluate_parser.add_argument("--lock", type=Path, required=True)
    evaluate_parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "select-lock":
        return select_lock(args.census, args.protocol, args.output)
    return evaluate(args.census, args.protocol, args.lock, args.out)


if __name__ == "__main__":
    raise SystemExit(main())
