from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .geometry import helmert_basis, validate_basis

SUBJECT_ORDER = ["308", "309", "310", "330", "331", "332", "333", "334", "335", "337", "349", "350", "351", "352", "369", "370", "371", "372"]
CONSTRUCTION_SHA256 = "0c9c4b2d365a9a32b84c0221548c54b3c884c2fc68d4f3b436f78cd9fde7c5ee"
CALIBRATION_SHA256 = "aa3fc9cdd1de05f4dc7f78d64e39257fe6c6ed0eb74d8d6f796287eedd5b59ff"
PROTOCOL_SHA256 = "4600564daa17b4349b88e5f366da82d3a51907674e39de53cf3bdfc9f303ddd7"


@dataclass(frozen=True)
class DataSurface:
    frame_visible: pd.DataFrame
    construction: pd.DataFrame
    calibration: pd.DataFrame
    future_design: pd.DataFrame
    subjects: list[str]
    subject_index: dict[str, int]
    y_mean: float
    y_sd: float
    basis: np.ndarray
    preparation_hash: str


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_frame(frame: pd.DataFrame, idx: dict[str, int], y_mean: float, y_sd: float) -> pd.DataFrame:
    out = frame.copy()
    out["Subject"] = out["Subject"].astype(str)
    out["subject_index"] = out["Subject"].map(idx).astype(int)
    out["t"] = (out["Days"].astype(float) - 2.5) / 2.5
    if "Reaction" in out:
        out["y"] = (out["Reaction"].astype(float) - y_mean) / y_sd
    return out.sort_values(["Days", "Subject"]).reset_index(drop=True)


def load_surface(root: str | Path) -> DataSurface:
    root = Path(root)
    p_con = root / "data" / "train" / "construction_days_0_5.csv"
    p_cal = root / "data" / "calibration" / "calibration_days_6_7.csv"
    p_design = root / "data" / "design" / "future_days_8_9_design.csv"
    p_protocol = root / "protocol" / "PG006_FROZEN_PROTOCOL.json"
    if sha256_file(p_con) != CONSTRUCTION_SHA256:
        raise RuntimeError("construction bytes do not match frozen commitment")
    if sha256_file(p_cal) != CALIBRATION_SHA256:
        raise RuntimeError("calibration bytes do not match frozen commitment")
    if sha256_file(p_protocol) != PROTOCOL_SHA256:
        raise RuntimeError("protocol bytes do not match frozen commitment")
    if (root / "data" / "future").exists():
        raise RuntimeError("future outcome directory is visible to a fitting runtime")
    con = pd.read_csv(p_con)
    cal = pd.read_csv(p_cal)
    design = pd.read_csv(p_design)
    con["Subject"] = con["Subject"].astype(str)
    cal["Subject"] = cal["Subject"].astype(str)
    design["Subject"] = design["Subject"].astype(str)
    if sorted(con.Subject.unique()) != SUBJECT_ORDER:
        raise RuntimeError("subject order or membership mismatch")
    if set(cal.Subject.unique()) != set(SUBJECT_ORDER) or set(design.Subject.unique()) != set(SUBJECT_ORDER):
        raise RuntimeError("calibration/design subject mismatch")
    if set(con.Days.unique()) != set(range(6)) or set(cal.Days.unique()) != {6, 7} or set(design.Days.unique()) != {8, 9}:
        raise RuntimeError("temporal surface mismatch")
    y_mean = float(con.Reaction.mean())
    y_sd = float(con.Reaction.std(ddof=0))
    if not np.isfinite(y_sd) or y_sd <= 0:
        raise RuntimeError("invalid response scale")
    idx = {s: i for i, s in enumerate(SUBJECT_ORDER)}
    con_n = _normalize_frame(con, idx, y_mean, y_sd)
    cal_n = _normalize_frame(cal, idx, y_mean, y_sd)
    design_n = _normalize_frame(design, idx, y_mean, y_sd)
    visible = pd.concat([con_n, cal_n], ignore_index=True).sort_values(["Days", "Subject"]).reset_index(drop=True)
    basis = helmert_basis(len(SUBJECT_ORDER))
    check = validate_basis(basis)
    if not check["valid"]:
        raise RuntimeError(check)
    payload = {
        "construction_sha256": CONSTRUCTION_SHA256,
        "calibration_sha256": CALIBRATION_SHA256,
        "protocol_sha256": PROTOCOL_SHA256,
        "subjects": SUBJECT_ORDER,
        "y_mean": y_mean,
        "y_sd": y_sd,
        "time": "(Days-2.5)/2.5",
    }
    return DataSurface(visible, con_n, cal_n, design_n, SUBJECT_ORDER, idx, y_mean, y_sd, basis, canonical_hash(payload))


def stage_frames(surface: DataSurface, stage: str, origin: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    if stage == "crossfit":
        if origin not in {2, 3, 4}:
            raise ValueError("crossfit origin must be 2, 3 or 4")
        train = surface.construction.loc[surface.construction.Days <= origin].copy()
        target_days = [d for d in (origin + 1, origin + 2) if d <= 5]
        target = surface.construction.loc[surface.construction.Days.isin(target_days)].copy()
        meta = {"stage": stage, "origin": origin, "target_days": target_days, "outcomes_visible": True}
    elif stage == "calibration":
        train = surface.construction.copy()
        target = surface.calibration.copy()
        meta = {"stage": stage, "origin": 5, "target_days": [6, 7], "outcomes_visible": True}
    elif stage == "final":
        train = surface.frame_visible.copy()
        target = surface.future_design.copy()
        meta = {"stage": stage, "origin": 7, "target_days": [8, 9], "outcomes_visible": False}
    else:
        raise ValueError(stage)
    return train.sort_values(["Days", "Subject"]).reset_index(drop=True), target.sort_values(["Days", "Subject"]).reset_index(drop=True), meta


def deterministic_context_features(train: pd.DataFrame, target: pd.DataFrame) -> dict[str, np.ndarray]:
    x_all = np.column_stack([np.ones(len(train)), train.t.to_numpy(float)])
    y_all = train.y.to_numpy(float)
    beta_pool = np.linalg.lstsq(x_all, y_all, rcond=None)[0]
    features = {"empirical_slope": [], "last_residual": [], "residual_dispersion": []}
    for subject in target.Subject.astype(str):
        sf = train.loc[train.Subject.astype(str) == subject].sort_values("Days")
        x = np.column_stack([np.ones(len(sf)), sf.t.to_numpy(float)])
        y = sf.y.to_numpy(float)
        coef = np.linalg.lstsq(x, y, rcond=None)[0]
        resid = y - x @ coef
        last_x = np.array([1.0, float(sf.t.iloc[-1])])
        last_resid = float(sf.y.iloc[-1] - last_x @ beta_pool)
        dispersion = float(np.sqrt(np.mean(resid**2))) if len(resid) > 2 else 0.0
        features["empirical_slope"].append(float(coef[1]))
        features["last_residual"].append(last_resid)
        features["residual_dispersion"].append(dispersion)
    return {k: np.asarray(v, dtype=float) for k, v in features.items()}
