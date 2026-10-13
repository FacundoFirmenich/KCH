from __future__ import annotations

import atexit
import hashlib
import importlib.util
import json
import math
import os
import shutil
import time
from pathlib import Path
from typing import Any

import drms
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_PATH = Path(os.environ["SELECTED_PROTOCOL_PATH"])
PARENT_OPERATOR_PROTOCOL_PATH = (
    ROOT
    / "construct_successors"
    / "KCH_HELICAL_V14_MULTISCALE_OPERATOR_BASIS_20261012"
    / "OPERATOR_BASIS_PROTOCOL_V1_4.json"
)
OPERATOR_RUNTIME_PATH = (
    ROOT / ".github" / "helical_v142" / "multiscale_operator_basis_v142.py"
)

OUT = Path(os.environ.get("OUT", "/tmp/helical_v16_temporal_lift"))
os.environ["OUT"] = str(OUT)
SAFE = OUT / "safe"
SAFE.mkdir(parents=True, exist_ok=True)
atexit.register(lambda: shutil.rmtree(OUT / "raw", ignore_errors=True))

spec = importlib.util.spec_from_file_location("kch_helical_v142_runtime", OPERATOR_RUNTIME_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("unable to load frozen v1.4.2 operator runtime")
op = importlib.util.module_from_spec(spec)
spec.loader.exec_module(op)

MODELS = [
    "T0_TRIVIAL_IDENTITY",
    "M_MOBIUS_SIGN",
    "H_HELICAL_TRANSLATION",
    "L_LEMNISCATIC_ALTERNATING",
    "G_ACTIVITY_AFFINE",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(obj: Any) -> str:
    body = json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(body).hexdigest()


def py_scalar(v: Any) -> Any:
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def query_exact_with_retry(
    query: str,
    keys: list[str],
    segments: list[str],
    backoff: list[int],
) -> tuple[Any, Any, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    last_exc: Exception | None = None
    for attempt_index, delay in enumerate(backoff):
        if delay:
            time.sleep(delay)
        try:
            client = drms.Client()
            key, seg = client.query(query, key=",".join(keys), seg=",".join(segments))
            attempts.append(
                {
                    "attempt": attempt_index + 1,
                    "delay_before_seconds": delay,
                    "result_rows": int(len(key)),
                    "success": True,
                }
            )
            return key, seg, attempts
        except Exception as exc:
            last_exc = exc
            attempts.append(
                {
                    "attempt": attempt_index + 1,
                    "delay_before_seconds": delay,
                    "success": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
    raise RuntimeError(
        f"metadata query failed after {len(backoff)} attempts for {query}: {last_exc!r}"
    )


def snapshot_query(harp: int, time_tai: str) -> str:
    return f"hmi.sharp_cea_720s[{harp}][{time_tai}]"


def load_snapshot(
    trajectory_id: str,
    harp: int,
    time_tai: str,
    protocol: dict[str, Any],
    parent_operator_protocol: dict[str, Any],
) -> dict[str, Any]:
    query = snapshot_query(harp, time_tai)
    backoff = [
        int(x) for x in protocol["source_resilience"]["fixed_backoff_seconds"]
    ]
    key, seg, metadata_attempts = query_exact_with_retry(
        query,
        list(op.KEYS),
        list(op.SEGMENTS),
        backoff,
    )
    if len(key) != 1 or len(seg) != 1:
        raise RuntimeError(f"{query}: exact query returned {len(key)} rows")
    row = key.reset_index(drop=True).iloc[0].to_dict()
    segrow = seg.reset_index(drop=True).iloc[0].to_dict()
    if int(row["HARPNUM"]) != harp or str(row["T_REC"]) != time_tai:
        raise RuntimeError(f"{query}: exact record identity mismatch")
    if int(row["QUALITY"]) != 0:
        raise RuntimeError(f"{query}: QUALITY={row['QUALITY']} != 0")

    snapshot_id = (
        f"{trajectory_id}__"
        + time_tai.replace(".", "").replace(":", "").replace("_TAI", "")
    )
    receipts: dict[str, Any] = {}
    try:
        for name in op.SEGMENTS:
            receipts[name] = op.download_segment(snapshot_id, name, str(segrow[name]))

        arrays: dict[str, np.ndarray] = {}
        fits_metadata: dict[str, Any] = {}
        for name in op.SEGMENTS:
            arr, meta = op.load_2d(Path(receipts[name]["path"]))
            arrays[name] = arr
            fits_metadata[name] = meta
        shapes = {name: tuple(arr.shape) for name, arr in arrays.items()}
        if len(set(shapes.values())) != 1:
            raise RuntimeError(f"{query}: segment shape mismatch {shapes}")

        br = arrays["Br"]
        bt = arrays["Bt"]
        bp = arrays["Bp"]
        conf = arrays["conf_disambig"]
        bitmap = arrays["bitmap"]
        mask = (
            np.isfinite(br)
            & np.isfinite(bt)
            & np.isfinite(bp)
            & (bitmap >= 33)
            & (conf == 90)
        )
        bx, by, bz = bp.copy(), -bt.copy(), br.copy()
        dx_m = float(row["RSUN_REF"]) * math.radians(abs(float(row["CDELT1"])))

        sigmas = [
            float(x)
            for x in parent_operator_protocol["scale_space"]["sigma_pixels"]
        ]
        basis = op.scale_basis(bx, by, bz, mask, dx_m, sigmas)
        cross = op.cross_scale(basis, sigmas)
        reconciliation = op.native_reconciliation(
            bx,
            by,
            bz,
            mask,
            dx_m,
            row,
            parent_operator_protocol,
        )
        if not reconciliation["pass"]:
            raise RuntimeError(
                f"{query}: native SHARP reconciliation failed: {reconciliation}"
            )

        fiber_names: list[str] = []
        fiber_values: list[float] = []
        for sigma in sigmas:
            scale_key = str(sigma)
            for operator in protocol["direct_field_fiber"]["per_scale_components"]:
                fiber_names.append(f"{operator}@sigma={scale_key}")
                fiber_values.append(float(basis[scale_key][operator]))
        for operator in protocol["direct_field_fiber"]["cross_scale_components"]:
            fiber_names.append(operator)
            fiber_values.append(float(cross[operator]))

        sigma_control = str(float(protocol["activity_control"]["sigma_pixels"]))
        control_values = [
            float(basis[sigma_control][name])
            for name in protocol["activity_control"]["components"]
        ]
        control_logs = np.log(np.maximum(np.asarray(control_values), 1e-300))

        safe_sources = {
            name: {
                "bytes": int(receipt["bytes"]),
                "sha256": str(receipt["sha256"]),
                "attempts": receipt["attempts"],
            }
            for name, receipt in receipts.items()
        }
        return {
            "trajectory_id": trajectory_id,
            "harp": int(harp),
            "requested_time_tai": time_tai,
            "query": query,
            "record": {
                "HARPNUM": int(row["HARPNUM"]),
                "T_REC": str(row["T_REC"]),
                "NOAA_AR": int(row["NOAA_AR"]) if not np.isnan(row["NOAA_AR"]) else None,
                "QUALITY": int(row["QUALITY"]),
                "CMASK": int(row["CMASK"]),
                "MEANJZH": float(row["MEANJZH"]),
                "MEANALP": float(row["MEANALP"]),
            },
            "metadata_attempts": metadata_attempts,
            "pixel_scale_m": dx_m,
            "mask_pixels": int(np.count_nonzero(mask)),
            "fiber_names": fiber_names,
            "fiber": fiber_values,
            "activity_control_names": list(protocol["activity_control"]["components"]),
            "activity_control_raw": control_values,
            "activity_control_log": [float(x) for x in control_logs],
            "native_reconciliation": {
                k: py_scalar(v) for k, v in reconciliation.items()
            },
            "source_receipts": safe_sources,
            "fits_metadata": fits_metadata,
        }
    finally:
        shutil.rmtree(op.RAW / snapshot_id, ignore_errors=True)


def build_transition_rows(
    trajectories: list[dict[str, Any]],
    selected_ids: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for trajectory in trajectories:
        if trajectory["trajectory_id"] not in selected_ids:
            continue
        snapshots = trajectory["snapshots"]
        for k in range(len(snapshots) - 1):
            rows.append(
                {
                    "trajectory_id": trajectory["trajectory_id"],
                    "harp": trajectory["harp"],
                    "k": k,
                    "x": np.asarray(snapshots[k]["fiber"], dtype=np.float64),
                    "y": np.asarray(snapshots[k + 1]["fiber"], dtype=np.float64),
                    "activity_x": np.asarray(
                        snapshots[k]["activity_control_log"], dtype=np.float64
                    ),
                    "activity_y": np.asarray(
                        snapshots[k + 1]["activity_control_log"], dtype=np.float64
                    ),
                }
            )
    return rows


def train_activity_normalizer(
    trajectories: list[dict[str, Any]],
    train_ids: set[str],
    sd_floor: float,
) -> tuple[np.ndarray, np.ndarray]:
    values = []
    for trajectory in trajectories:
        if trajectory["trajectory_id"] in train_ids:
            values.extend(
                np.asarray(s["activity_control_log"], dtype=np.float64)
                for s in trajectory["snapshots"]
            )
    matrix = np.vstack(values)
    mean = np.mean(matrix, axis=0)
    sd = np.std(matrix, axis=0, ddof=0)
    sd = np.maximum(sd, sd_floor)
    return mean, sd


def q_value(activity_log: np.ndarray, mean: np.ndarray, sd: np.ndarray) -> float:
    return float(np.mean((activity_log - mean) / sd))


def attach_delta_q(
    rows: list[dict[str, Any]],
    mean: np.ndarray,
    sd: np.ndarray,
) -> None:
    for row in rows:
        row["delta_q"] = q_value(row["activity_y"], mean, sd) - q_value(
            row["activity_x"], mean, sd
        )


def train_rms_scale(rows: list[dict[str, Any]], floor: float) -> np.ndarray:
    targets = np.vstack([row["y"] for row in rows])
    scale = np.sqrt(np.mean(np.square(targets), axis=0))
    return np.maximum(scale, floor)


def fit_helical(rows: list[dict[str, Any]]) -> np.ndarray:
    return np.mean(np.vstack([r["y"] - r["x"] for r in rows]), axis=0)


def fit_lemniscatic(rows: list[dict[str, Any]]) -> np.ndarray:
    vals = []
    for r in rows:
        s = 1.0 if (int(r["k"]) % 2 == 0) else -1.0
        vals.append(s * (r["y"] - r["x"]))
    return np.mean(np.vstack(vals), axis=0)


def fit_generic_activity(
    rows: list[dict[str, Any]],
    scale: np.ndarray,
    required_rank: int,
    max_condition: float,
) -> tuple[np.ndarray, dict[str, Any]]:
    d = len(scale)
    design_rows: list[np.ndarray] = []
    targets: list[float] = []
    for r in rows:
        zx = r["x"] / scale
        zy = r["y"] / scale
        dq = float(r["delta_q"])
        for component in range(d):
            row = np.zeros(2 + d, dtype=np.float64)
            row[0] = zx[component]
            row[1] = dq
            row[2 + component] = 1.0
            design_rows.append(row)
            targets.append(float(zy[component]))
    X = np.vstack(design_rows)
    y = np.asarray(targets, dtype=np.float64)
    rank = int(np.linalg.matrix_rank(X))
    condition = float(np.linalg.cond(X))
    if rank != required_rank:
        raise RuntimeError(
            f"G_ACTIVITY_AFFINE design rank {rank} != required {required_rank}"
        )
    if not math.isfinite(condition) or condition > max_condition:
        raise RuntimeError(
            f"G_ACTIVITY_AFFINE condition number {condition} exceeds {max_condition}"
        )
    beta, _, _, singular = np.linalg.lstsq(X, y, rcond=None)
    return beta, {
        "rank": rank,
        "condition_number": condition,
        "singular_values": [float(v) for v in singular],
    }


def predict_model(
    model: str,
    row: dict[str, Any],
    scale: np.ndarray,
    parameters: dict[str, Any],
) -> np.ndarray:
    x = row["x"]
    if model == "T0_TRIVIAL_IDENTITY":
        return x.copy()
    if model == "M_MOBIUS_SIGN":
        return -x
    if model == "H_HELICAL_TRANSLATION":
        return x + parameters["helical_b"]
    if model == "L_LEMNISCATIC_ALTERNATING":
        s = 1.0 if (int(row["k"]) % 2 == 0) else -1.0
        return x + s * parameters["lemniscatic_b"]
    if model == "G_ACTIVITY_AFFINE":
        beta = parameters["generic_beta"]
        d = len(scale)
        zx = x / scale
        dq = float(row["delta_q"])
        zy_pred = beta[0] * zx + beta[1] * dq + beta[2 : 2 + d]
        return zy_pred * scale
    raise KeyError(model)


def score_rows(
    model: str,
    rows: list[dict[str, Any]],
    scale: np.ndarray,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    per_transition = []
    errors = []
    abs_errors = []
    for r in rows:
        pred = predict_model(model, r, scale, parameters)
        normalized = (pred - r["y"]) / scale
        sq = np.square(normalized)
        ab = np.abs(normalized)
        errors.extend(float(v) for v in sq)
        abs_errors.extend(float(v) for v in ab)
        per_transition.append(
            {
                "trajectory_id": r["trajectory_id"],
                "harp": int(r["harp"]),
                "k": int(r["k"]),
                "normalized_mse": float(np.mean(sq)),
                "normalized_mae": float(np.mean(ab)),
            }
        )
    return {
        "nmse": float(np.mean(np.asarray(errors, dtype=np.float64))),
        "nmae": float(np.mean(np.asarray(abs_errors, dtype=np.float64))),
        "per_transition": per_transition,
    }


def unique_winner(
    metric: dict[str, float],
    tolerance_relative: float,
) -> str | None:
    ordered = sorted(metric.items(), key=lambda kv: (kv[1], kv[0]))
    if len(ordered) < 2:
        return ordered[0][0] if ordered else None
    best_name, best = ordered[0]
    _, second = ordered[1]
    if abs(second - best) <= tolerance_relative * max(abs(best), abs(second), 1.0):
        return None
    return best_name


def main() -> int:
    protocol = json.loads(PROTOCOL_PATH.read_text())
    parent_operator_protocol = json.loads(PARENT_OPERATOR_PROTOCOL_PATH.read_text())

    trajectories: list[dict[str, Any]] = []
    source_failures: list[dict[str, Any]] = []

    for trajectory_spec in protocol["harp_trajectories"]:
        trajectory = {
            "trajectory_id": trajectory_spec["trajectory_id"],
            "harp": int(trajectory_spec["harp"]),
            "snapshots": [],
        }
        for time_tai in trajectory_spec["times_tai"]:
            try:
                trajectory["snapshots"].append(
                    load_snapshot(
                        trajectory["trajectory_id"],
                        trajectory["harp"],
                        time_tai,
                        protocol,
                        parent_operator_protocol,
                    )
                )
            except Exception as exc:
                source_failures.append(
                    {
                        "trajectory_id": trajectory["trajectory_id"],
                        "harp": trajectory["harp"],
                        "time_tai": time_tai,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                break
        trajectories.append(trajectory)

    complete = [
        t for t in trajectories if len(t["snapshots"]) == 5
    ]
    expected_fiber_names = None
    if complete:
        expected_fiber_names = complete[0]["snapshots"][0]["fiber_names"]
        for trajectory in complete:
            for snapshot in trajectory["snapshots"]:
                if snapshot["fiber_names"] != expected_fiber_names:
                    raise RuntimeError("fiber coordinate order mismatch across snapshots")
                if len(snapshot["fiber"]) != int(protocol["direct_field_fiber"]["dimension"]):
                    raise RuntimeError("fiber dimension mismatch")

    fold_results: list[dict[str, Any]] = []
    model_scores: dict[str, list[float]] = {m: [] for m in MODELS}
    model_mae: dict[str, list[float]] = {m: [] for m in MODELS}
    model_test_transition_count: dict[str, int] = {m: 0 for m in MODELS}
    numerical_failures: list[dict[str, Any]] = []
    all_ids = {t["trajectory_id"] for t in complete}

    if len(complete) == 3 and not source_failures:
        for held_out in complete:
            test_id = held_out["trajectory_id"]
            train_ids = all_ids - {test_id}
            train_rows = build_transition_rows(complete, train_ids)
            test_rows = build_transition_rows(complete, {test_id})

            activity_mean, activity_sd = train_activity_normalizer(
                complete,
                train_ids,
                float(protocol["activity_control"]["normalization_sd_floor"]),
            )
            attach_delta_q(train_rows, activity_mean, activity_sd)
            attach_delta_q(test_rows, activity_mean, activity_sd)

            scale = train_rms_scale(
                train_rows,
                float(protocol["evaluation"]["fiber_scale_floor"]),
            )
            params: dict[str, Any] = {
                "helical_b": fit_helical(train_rows),
                "lemniscatic_b": fit_lemniscatic(train_rows),
            }
            generic_spec = protocol["operational_transport_rivals"]["G_ACTIVITY_AFFINE"][
                "identifiability"
            ]
            try:
                generic_beta, generic_diag = fit_generic_activity(
                    train_rows,
                    scale,
                    int(generic_spec["required_design_rank"]),
                    float(generic_spec["maximum_condition_number"]),
                )
            except Exception as exc:
                numerical_failures.append(
                    {
                        "fold": test_id,
                        "model": "G_ACTIVITY_AFFINE",
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                break
            params["generic_beta"] = generic_beta

            scores = {
                model: score_rows(model, test_rows, scale, params)
                for model in MODELS
            }
            primary = {model: scores[model]["nmse"] for model in MODELS}
            fold_winner = unique_winner(
                primary,
                float(protocol["evaluation"]["tie_tolerance_relative"]),
            )
            for model in MODELS:
                model_scores[model].append(float(scores[model]["nmse"]))
                model_mae[model].append(float(scores[model]["nmae"]))
                model_test_transition_count[model] += len(test_rows)

            fold_results.append(
                {
                    "held_out_trajectory": test_id,
                    "held_out_harp": int(held_out["harp"]),
                    "train_trajectories": sorted(train_ids),
                    "train_transition_count": len(train_rows),
                    "test_transition_count": len(test_rows),
                    "activity_train_mean": [float(v) for v in activity_mean],
                    "activity_train_sd": [float(v) for v in activity_sd],
                    "fiber_train_rms_scale": [float(v) for v in scale],
                    "generic_identifiability": generic_diag,
                    "helical_b": [float(v) for v in params["helical_b"]],
                    "lemniscatic_b": [float(v) for v in params["lemniscatic_b"]],
                    "generic_common_a": float(generic_beta[0]),
                    "generic_common_c": float(generic_beta[1]),
                    "generic_component_intercepts": [float(v) for v in generic_beta[2:]],
                    "scores": scores,
                    "fold_winner": fold_winner,
                }
            )

    support_ok = (
        len(complete) == 3
        and not source_failures
        and not numerical_failures
        and len(fold_results) == 3
    )

    global_scores: dict[str, Any] = {}
    global_winner: str | None = None
    runner_up: str | None = None
    global_margin = None
    fold_wins = {m: 0 for m in MODELS}

    if support_ok:
        for fold in fold_results:
            if fold["fold_winner"] is not None:
                fold_wins[fold["fold_winner"]] += 1
        for model in MODELS:
            global_scores[model] = {
                "mean_nmse": float(np.mean(model_scores[model])),
                "mean_nmae": float(np.mean(model_mae[model])),
                "fold_wins": int(fold_wins[model]),
                "test_transitions": int(model_test_transition_count[model]),
            }
        ordered = sorted(
            MODELS,
            key=lambda m: (global_scores[m]["mean_nmse"], m),
        )
        tie_tol = float(protocol["evaluation"]["tie_tolerance_relative"])
        if len(ordered) >= 2:
            first, second = ordered[0], ordered[1]
            first_score = float(global_scores[first]["mean_nmse"])
            second_score = float(global_scores[second]["mean_nmse"])
            if abs(second_score - first_score) > tie_tol * max(
                abs(first_score), abs(second_score), 1.0
            ):
                global_winner = first
                runner_up = second
                if second_score > 0:
                    global_margin = 1.0 - first_score / second_score

    dominance = False
    if global_winner is not None and runner_up is not None and global_margin is not None:
        dominance = bool(
            model_test_transition_count[global_winner]
            >= int(protocol["dominance_rule"]["minimum_total_test_transitions"])
            and global_margin
            >= float(protocol["dominance_rule"]["global_primary_margin_vs_runner_up"])
            and fold_wins[global_winner]
            >= int(protocol["dominance_rule"]["minimum_fold_wins"])
        )

    outcome_map = {
        "T0_TRIVIAL_IDENTITY": "DEVELOPMENT_TRIVIAL_RIVAL_DOMINATES",
        "M_MOBIUS_SIGN": "DEVELOPMENT_MOBIUS_RIVAL_DOMINATES",
        "H_HELICAL_TRANSLATION": "DEVELOPMENT_HELICAL_RIVAL_DOMINATES",
        "L_LEMNISCATIC_ALTERNATING": "DEVELOPMENT_LEMNISCATIC_RIVAL_DOMINATES",
        "G_ACTIVITY_AFFINE": "DEVELOPMENT_GENERIC_ACTIVITY_RIVAL_DOMINATES",
    }
    if not support_ok:
        outcome = "INSUFFICIENT_TEMPORAL_SUPPORT"
        rc = 31
    elif dominance and global_winner is not None:
        outcome = outcome_map[global_winner]
        rc = 0
    else:
        outcome = "NO_DEVELOPMENT_DOMINANT_LIFT"
        rc = 0

    safe_trajectories = []
    for t in trajectories:
        safe_trajectories.append(
            {
                "trajectory_id": t["trajectory_id"],
                "harp": t["harp"],
                "snapshots": t["snapshots"],
            }
        )

    report = {
        "format": "KCH_HELICAL_V1_6_METADATA_SELECTED_TEMPORAL_RESULT",
        "protocol_sha256": sha256_file(PROTOCOL_PATH),
        "metadata_selection_receipt": protocol["metadata_selection_receipt"],
        "interpretation": protocol["interpretation_boundary"],
        "operator_runtime_git_blob_sha1_expected": "b400baaa8306fcf37ed095607c586f52e3d89911",
        "operator_runtime_sha256": sha256_file(OPERATOR_RUNTIME_PATH),
        "parent_operator_protocol_sha256": sha256_file(
            PARENT_OPERATOR_PROTOCOL_PATH
        ),
        "scope": protocol["scope"],
        "fiber_names": expected_fiber_names,
        "trajectories": safe_trajectories,
        "source_failures": source_failures,
        "numerical_failures": numerical_failures,
        "fold_results": fold_results,
        "global_scores": global_scores,
        "global_winner": global_winner,
        "runner_up": runner_up,
        "global_primary_margin_fraction": global_margin,
        "dominance_rule_pass": dominance,
        "outcome": outcome,
        "development_only": True,
        "scientific_confirmation": False,
        "flare_outcomes_accessed": False,
        "fresh_2026_holdout_accessed": False,
        "physical_helicity": "NOT_EVALUATED",
        "topological_class": "NOT_EVALUATED",
        "universal_ontology": "FORBIDDEN",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "authority_ceiling": "NONE",
    }
    report["receipt_id"] = "h16lift:" + canonical_hash(report)
    output = SAFE / "TEMPORAL_LIFT_DEVELOPMENT_RESULT_V1_6.json"
    output.write_text(
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    )

    print(
        json.dumps(
            {
                "outcome": outcome,
                "receipt_id": report["receipt_id"],
                "complete_trajectories": len(complete),
                "source_failures": source_failures,
                "numerical_failures": numerical_failures,
                "global_scores": global_scores,
                "global_winner": global_winner,
                "runner_up": runner_up,
                "global_primary_margin_fraction": global_margin,
                "dominance_rule_pass": dominance,
                "fold_winners": [
                    {
                        "held_out": f["held_out_trajectory"],
                        "winner": f["fold_winner"],
                    }
                    for f in fold_results
                ],
            },
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
    )
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
