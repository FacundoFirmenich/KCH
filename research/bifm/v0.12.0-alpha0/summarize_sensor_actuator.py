#!/usr/bin/env python3
"""BIFM v0.12 — multilingual sensor/actuator and future-only router audit.

The summary stage consumes four frozen language artifacts. Development rows are
used for all quantiles, model fitting, sensor-family choice and route-threshold
selection. Confirmatory rows are untouched until those objects are frozen.
"""
from __future__ import annotations

import json
import math
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

LANGS = ("eng_Latn", "fra_Latn", "spa_Latn", "por_Latn")
INROOT = Path(os.environ.get("BIFM_INPUT", "language_artifacts"))
OUT = Path(os.environ.get("BIFM_OUT", "bifm_v012_summary"))
OUT.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(20261018)
BOOT_DRAWS = 2000
HARM_CAP = 0.10
MIN_COVERAGE = 0.05
BENEFIT_THRESHOLD = 0.02
THRESHOLDS = np.linspace(0.20, 0.90, 15)

BASE_FEATURES = [
    "temp08_margin",
    "temp08_entropy",
]
TALM_FEATURES = [
    "talm_full_js_vs_baseline",
    "talm_choice_js_vs_baseline",
    "talm_top10_overlap",
    "talm_top50_overlap",
    "talm_delta_l2",
    "talm_delta_linf",
    "talm_constant_shift_residual",
]
TALON_FEATURES = [
    "talon_full_js_vs_temp08",
    "talon_choice_js_vs_temp08",
    "talon_top10_overlap",
    "talon_top50_overlap",
    "talon_delta_l2",
    "talon_delta_linf",
    "talon_constant_shift_residual",
]
FEATURE_SETS = {
    "baseline_only": BASE_FEATURES,
    "talm_sensor": BASE_FEATURES + TALM_FEATURES,
    "talon_sensor": BASE_FEATURES + TALON_FEATURES,
    "combined_sensor": BASE_FEATURES + TALM_FEATURES + TALON_FEATURES,
}


def dump(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")


def locate_one(pattern: str) -> Path:
    paths = list(INROOT.rglob(pattern))
    if len(paths) != 1:
        raise RuntimeError(f"Expected one {pattern}, got {paths}")
    return paths[0]


def load_inputs() -> tuple[pd.DataFrame, dict[str, Any]]:
    frames = []
    receipts = {}
    for lang in LANGS:
        csv_path = locate_one(f"{lang}_item_records.csv")
        receipt_path = locate_one(f"{lang}_receipt.json")
        frame = pd.read_csv(csv_path)
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt["status"] != "PASS":
            raise RuntimeError(f"Non-PASS receipt for {lang}: {receipt['status']}")
        if list(frame["language"].unique()) != [lang]:
            raise AssertionError(f"Language mismatch in {csv_path}")
        frames.append(frame)
        receipts[lang] = receipt
    all_data = pd.concat(frames, ignore_index=True)
    reference = set(all_data[all_data.language == LANGS[0]].item_key)
    for lang in LANGS[1:]:
        current = set(all_data[all_data.language == lang].item_key)
        if current != reference:
            raise AssertionError(f"Parallel key mismatch for {lang}")
    revisions = {
        (
            r["model"]["revision"],
            r["dataset"]["revision"],
            r["operators"]["source"]["blob_sha"],
        )
        for r in receipts.values()
    }
    if len(revisions) != 1:
        raise AssertionError(f"Revision mismatch across languages: {revisions}")
    return all_data, receipts


def fit_sensor(frame: pd.DataFrame, features: list[str]) -> tuple[Any, bool]:
    y = (frame["actuator_delta_correct_prob"] >= BENEFIT_THRESHOLD).astype(int)
    if y.nunique() < 2:
        return None, False
    numeric = Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
        ]
    )
    pre = ColumnTransformer([("numeric", numeric, features)], remainder="drop")
    model = Pipeline(
        [
            ("pre", pre),
            (
                "logistic",
                LogisticRegression(
                    C=1.0,
                    class_weight="balanced",
                    max_iter=2000,
                    random_state=20261018,
                ),
            ),
        ]
    )
    model.fit(frame[features], y)
    return model, True


def sensor_scores(model: Any, fitted: bool, frame: pd.DataFrame, features: list[str]) -> np.ndarray:
    if fitted:
        return model.predict_proba(frame[features])[:, 1]
    margin = frame["temp08_margin"].to_numpy(float)
    js = frame.get("talon_choice_js_vs_temp08", pd.Series(np.zeros(len(frame)))).to_numpy(float)
    raw = -margin + 5.0 * js
    raw = (raw - np.nanmedian(raw)) / (np.nanstd(raw) + 1e-9)
    return 1.0 / (1.0 + np.exp(-raw))


def safe_auc(y: np.ndarray, p: np.ndarray) -> dict[str, float | None]:
    if len(np.unique(y)) < 2:
        return {"auroc": None, "auprc": None, "brier": float(np.mean((p - y) ** 2))}
    return {
        "auroc": float(roc_auc_score(y, p)),
        "auprc": float(average_precision_score(y, p)),
        "brier": float(brier_score_loss(y, p)),
    }


def route_utility(frame: pd.DataFrame, route: np.ndarray) -> dict[str, float | int]:
    route = route.astype(bool)
    coverage = float(route.mean()) if len(route) else 0.0
    if route.sum() == 0:
        return {
            "coverage": coverage,
            "routed_n": 0,
            "mean_delta_correct_prob_all": 0.0,
            "mean_delta_correct_prob_routed": 0.0,
            "harm_rate_routed": 0.0,
            "rescue_rate_routed": 0.0,
            "net_utility": 0.0,
        }
    delta = frame["actuator_delta_correct_prob"].to_numpy(float)
    harm = frame["actuator_harm"].to_numpy(float)
    rescue = frame["actuator_rescue"].to_numpy(float)
    utility_item = delta - 0.25 * harm
    return {
        "coverage": coverage,
        "routed_n": int(route.sum()),
        "mean_delta_correct_prob_all": float(np.mean(delta * route)),
        "mean_delta_correct_prob_routed": float(delta[route].mean()),
        "harm_rate_routed": float(harm[route].mean()),
        "rescue_rate_routed": float(rescue[route].mean()),
        "net_utility": float(np.mean(utility_item * route)),
    }


def choose_threshold(frame: pd.DataFrame, scores: np.ndarray) -> dict[str, Any]:
    candidates = []
    for threshold in THRESHOLDS:
        route = scores >= threshold
        metrics = route_utility(frame, route)
        eligible = (
            metrics["coverage"] >= MIN_COVERAGE
            and metrics["harm_rate_routed"] <= HARM_CAP
            and metrics["net_utility"] > 0.0
        )
        candidates.append({"threshold": float(threshold), "eligible": bool(eligible), **metrics})
    eligible = [c for c in candidates if c["eligible"]]
    if not eligible:
        return {"threshold": None, "policy": "ABSTAIN_ALL", "candidates": candidates}
    best = max(eligible, key=lambda c: (c["net_utility"], -c["harm_rate_routed"], c["threshold"]))
    return {"threshold": best["threshold"], "policy": "SELECTIVE_ACTUATION", "candidates": candidates}


def performance(frame: pd.DataFrame, prefix: str) -> dict[str, float]:
    return {
        "n": int(len(frame)),
        "accuracy": float(frame[f"{prefix}_correct"].mean()),
        "mean_correct_prob": float(frame[f"{prefix}_correct_prob"].mean()),
        "mean_log_loss": float(frame[f"{prefix}_log_loss"].mean()),
        "mean_brier": float(frame[f"{prefix}_brier"].mean()),
    }


def routed_performance(frame: pd.DataFrame, route: np.ndarray) -> dict[str, float]:
    route = route.astype(bool)
    correct = np.where(
        route,
        frame["talon_actuator_correct"].to_numpy(float),
        frame["temp08_control_correct"].to_numpy(float),
    )
    correct_prob = np.where(
        route,
        frame["talon_actuator_correct_prob"].to_numpy(float),
        frame["temp08_control_correct_prob"].to_numpy(float),
    )
    log_loss = np.where(
        route,
        frame["talon_actuator_log_loss"].to_numpy(float),
        frame["temp08_control_log_loss"].to_numpy(float),
    )
    brier = np.where(
        route,
        frame["talon_actuator_brier"].to_numpy(float),
        frame["temp08_control_brier"].to_numpy(float),
    )
    return {
        "n": int(len(frame)),
        "coverage": float(route.mean()),
        "accuracy": float(correct.mean()),
        "mean_correct_prob": float(correct_prob.mean()),
        "mean_log_loss": float(log_loss.mean()),
        "mean_brier": float(brier.mean()),
    }


def paired_bootstrap(frame: pd.DataFrame, route: np.ndarray) -> dict[str, float]:
    n = len(frame)
    if n == 0:
        return {"delta_accuracy_q025": 0.0, "delta_accuracy_q975": 0.0, "delta_correct_prob_q025": 0.0, "delta_correct_prob_q975": 0.0}
    control_correct = frame["temp08_control_correct"].to_numpy(float)
    act_correct = frame["talon_actuator_correct"].to_numpy(float)
    control_prob = frame["temp08_control_correct_prob"].to_numpy(float)
    act_prob = frame["talon_actuator_correct_prob"].to_numpy(float)
    routed_correct = np.where(route, act_correct, control_correct)
    routed_prob = np.where(route, act_prob, control_prob)
    acc_deltas = np.empty(BOOT_DRAWS)
    prob_deltas = np.empty(BOOT_DRAWS)
    for b in range(BOOT_DRAWS):
        idx = RNG.integers(0, n, size=n)
        acc_deltas[b] = routed_correct[idx].mean() - control_correct[idx].mean()
        prob_deltas[b] = routed_prob[idx].mean() - control_prob[idx].mean()
    aq = np.quantile(acc_deltas, [0.025, 0.5, 0.975])
    pq = np.quantile(prob_deltas, [0.025, 0.5, 0.975])
    return {
        "delta_accuracy_q025": float(aq[0]),
        "delta_accuracy_median": float(aq[1]),
        "delta_accuracy_q975": float(aq[2]),
        "delta_correct_prob_q025": float(pq[0]),
        "delta_correct_prob_median": float(pq[1]),
        "delta_correct_prob_q975": float(pq[2]),
    }


def main() -> None:
    started = time.time()
    data, receipts = load_inputs()
    development = data[data.split == "development"].copy()
    confirmatory = data[data.split == "confirmatory"].copy()

    # Freeze language-local headroom thresholds from development only.
    headroom_thresholds = {}
    for lang in LANGS:
        local = development[development.language == lang]
        q25, q75 = np.quantile(local["temp08_margin"], [0.25, 0.75])
        headroom_thresholds[lang] = {"high_eig_margin_max": float(q25), "low_eig_margin_min": float(q75)}

    def assign_stratum(row: pd.Series) -> str:
        thresholds = headroom_thresholds[row.language]
        if row.temp08_margin <= thresholds["high_eig_margin_max"]:
            return "EIG_TARGET_HIGH_HEADROOM"
        if row.temp08_margin >= thresholds["low_eig_margin_min"]:
            return "EIG_CONTROL_LOW_HEADROOM"
        return "MID_HEADROOM"

    development["eig_stratum"] = development.apply(assign_stratum, axis=1)
    confirmatory["eig_stratum"] = confirmatory.apply(assign_stratum, axis=1)
    development["benefit_target"] = (
        development["actuator_delta_correct_prob"] >= BENEFIT_THRESHOLD
    ).astype(int)
    confirmatory["benefit_target"] = (
        confirmatory["actuator_delta_correct_prob"] >= BENEFIT_THRESHOLD
    ).astype(int)

    sensor_models = {}
    dev_sensor_diagnostics = []
    confirm_sensor_diagnostics = []
    confirm_scores_by_family = {}
    for family, features in FEATURE_SETS.items():
        model, fitted = fit_sensor(development, features)
        dev_scores = sensor_scores(model, fitted, development, features)
        conf_scores = sensor_scores(model, fitted, confirmatory, features)
        sensor_models[family] = {"model": model, "fitted": fitted, "features": features}
        confirm_scores_by_family[family] = conf_scores
        for split_name, frame, scores, sink in (
            ("development", development, dev_scores, dev_sensor_diagnostics),
            ("confirmatory", confirmatory, conf_scores, confirm_sensor_diagnostics),
        ):
            y = frame["benefit_target"].to_numpy(int)
            diag = safe_auc(y, scores)
            rho = spearmanr(frame["actuator_delta_correct_prob"], scores, nan_policy="omit")
            sink.append(
                {
                    "sensor_family": family,
                    "split": split_name,
                    **diag,
                    "spearman_delta_correct_prob": None if np.isnan(rho.statistic) else float(rho.statistic),
                    "positive_rate": float(y.mean()),
                    "n": int(len(frame)),
                }
            )

    # Select sensor family and threshold independently per language using development only.
    policies = {}
    policy_rows = []
    for lang in LANGS:
        dev_local = development[development.language == lang].copy()
        candidates = []
        for family, spec in sensor_models.items():
            scores = sensor_scores(spec["model"], spec["fitted"], dev_local, spec["features"])
            threshold_spec = choose_threshold(dev_local, scores)
            if threshold_spec["threshold"] is None:
                objective = 0.0
                harm = 0.0
                coverage = 0.0
            else:
                selected = next(c for c in threshold_spec["candidates"] if c["threshold"] == threshold_spec["threshold"])
                objective = selected["net_utility"]
                harm = selected["harm_rate_routed"]
                coverage = selected["coverage"]
            candidates.append(
                {
                    "sensor_family": family,
                    "threshold_spec": threshold_spec,
                    "objective": float(objective),
                    "harm_rate": float(harm),
                    "coverage": float(coverage),
                }
            )
        best = max(candidates, key=lambda c: (c["objective"], -c["harm_rate"], c["coverage"], c["sensor_family"]))
        if best["objective"] <= 0.0 or best["threshold_spec"]["threshold"] is None:
            policy = {"sensor_family": best["sensor_family"], "threshold": None, "policy": "ABSTAIN_ALL", "development_candidates": candidates}
        else:
            policy = {"sensor_family": best["sensor_family"], "threshold": best["threshold_spec"]["threshold"], "policy": "SELECTIVE_ACTUATION", "development_candidates": candidates}
        policies[lang] = policy
        policy_rows.append({"language": lang, "sensor_family": policy["sensor_family"], "threshold": policy["threshold"], "policy": policy["policy"], "development_objective": best["objective"], "development_harm_rate": best["harm_rate"], "development_coverage": best["coverage"]})

    results = []
    parallel_rows = []
    for lang in LANGS:
        policy = policies[lang]
        local = confirmatory[confirmatory.language == lang].copy().reset_index(drop=True)
        spec = sensor_models[policy["sensor_family"]]
        scores = sensor_scores(spec["model"], spec["fitted"], local, spec["features"])
        if policy["threshold"] is None:
            route = np.zeros(len(local), dtype=bool)
        else:
            route = scores >= float(policy["threshold"])
        local["sensor_score"] = scores
        local["route"] = route.astype(int)
        for stratum in ("ALL", "EIG_TARGET_HIGH_HEADROOM", "MID_HEADROOM", "EIG_CONTROL_LOW_HEADROOM"):
            subset = local if stratum == "ALL" else local[local.eig_stratum == stratum]
            if len(subset) == 0:
                continue
            sub_route = subset["route"].to_numpy(bool)
            target = subset["benefit_target"].to_numpy(int)
            sensor_diag = safe_auc(target, subset["sensor_score"].to_numpy(float))
            results.append(
                {
                    "language": lang,
                    "stratum": stratum,
                    "policy": policy["policy"],
                    "sensor_family": policy["sensor_family"],
                    "threshold": policy["threshold"],
                    "sensor": sensor_diag,
                    "control": performance(subset, "temp08_control"),
                    "always_on_actuator": performance(subset, "talon_actuator"),
                    "routed": routed_performance(subset, sub_route),
                    "route_utility": route_utility(subset, sub_route),
                    "paired_bootstrap": paired_bootstrap(subset, sub_route),
                    "mean_talm_sensor_js": float(subset["talm_choice_js_vs_baseline"].mean()),
                    "mean_talon_sensor_js": float(subset["talon_choice_js_vs_temp08"].mean()),
                    "mean_actuator_js": float(subset["actuator_choice_js_vs_temp08"].mean()),
                    "n": int(len(subset)),
                }
            )
        for row in local.itertuples(index=False):
            parallel_rows.append(
                {
                    "item_key": row.item_key,
                    "language": lang,
                    "eig_stratum": row.eig_stratum,
                    "sensor_score": row.sensor_score,
                    "route": row.route,
                    "actuator_delta_correct_prob": row.actuator_delta_correct_prob,
                    "actuator_rescue": row.actuator_rescue,
                    "actuator_harm": row.actuator_harm,
                    "actuator_choice_changed": row.actuator_choice_changed,
                }
            )

    parallel = pd.DataFrame(parallel_rows)
    cross = []
    for key, group in parallel.groupby("item_key"):
        if len(group) != len(LANGS):
            raise AssertionError(f"Non-parallel confirmatory key {key}: {len(group)} languages")
        beneficial = (group["actuator_delta_correct_prob"] >= BENEFIT_THRESHOLD).astype(int)
        cross.append(
            {
                "item_key": key,
                "languages_beneficial": int(beneficial.sum()),
                "languages_routed": int(group["route"].sum()),
                "languages_rescued": int(group["actuator_rescue"].sum()),
                "languages_harmed": int(group["actuator_harm"].sum()),
                "delta_correct_prob_mean": float(group["actuator_delta_correct_prob"].mean()),
                "delta_correct_prob_sd": float(group["actuator_delta_correct_prob"].std(ddof=0)),
                "sensor_score_mean": float(group["sensor_score"].mean()),
                "sensor_score_sd": float(group["sensor_score"].std(ddof=0)),
            }
        )
    cross_frame = pd.DataFrame(cross)

    result = {
        "status": "PASS",
        "languages": list(LANGS),
        "development_n_per_language": int((development.language == LANGS[0]).sum()),
        "confirmatory_n_per_language": int((confirmatory.language == LANGS[0]).sum()),
        "benefit_threshold_correct_probability": BENEFIT_THRESHOLD,
        "harm_cap": HARM_CAP,
        "minimum_route_coverage": MIN_COVERAGE,
        "headroom_thresholds_from_development": headroom_thresholds,
        "policies_selected_on_development_only": policies,
        "development_sensor_diagnostics": dev_sensor_diagnostics,
        "confirmatory_sensor_diagnostics": confirm_sensor_diagnostics,
        "confirmatory_local_results": results,
        "parallel_item_summary": {
            "n_parallel_items": int(len(cross_frame)),
            "items_beneficial_in_all_four_languages": int((cross_frame.languages_beneficial == 4).sum()),
            "items_beneficial_in_no_language": int((cross_frame.languages_beneficial == 0).sum()),
            "items_with_cross_language_sign_heterogeneity": int(((cross_frame.languages_beneficial > 0) & (cross_frame.languages_beneficial < 4)).sum()),
            "items_harmed_in_any_language": int((cross_frame.languages_harmed > 0).sum()),
        },
        "operator_roles": {
            "talm_mass_right_soft": "sensor_only",
            "talon_mass_right": "sensor_only",
            "talon_mass_right_no_preserve_exploratory": "offline_actuator_ablation; no authority",
        },
        "claim_boundary": [
            "All feature selection, sensor fitting, language-local policy choice and route thresholds use development rows only.",
            "Confirmatory results are jurisdictional by language and headroom stratum; pooled values are diagnostic only.",
            "A good sensor need not be a good actuator and an actuator benefit does not confer execution authority.",
            "The operator formulas are registry-conformant reimplementations, not byte-identical historical-source claims.",
        ],
        "software": {"python": sys.version, "numpy": np.__version__, "pandas": pd.__version__, "platform": platform.platform()},
        "elapsed_seconds": time.time() - started,
    }
    dump(OUT / "sensor_actuator_summary.json", result)
    pd.DataFrame(policy_rows).to_csv(OUT / "development_selected_policies.csv", index=False)
    pd.DataFrame(results).to_json(OUT / "confirmatory_local_results.jsonl", orient="records", lines=True, force_ascii=False)
    parallel.to_csv(OUT / "parallel_confirmatory_items.csv", index=False)
    cross_frame.to_csv(OUT / "cross_language_item_summary.csv", index=False)
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()
