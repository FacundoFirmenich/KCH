from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .geometry import helmert_basis


@dataclass(frozen=True)
class PreparedData:
    domain: str
    arrays: dict[str, np.ndarray]
    metadata: dict[str, Any]
    preparation_hash: str
    source_hashes: dict[str, str]


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def prepare_grunfeld(root: str | Path, evidence_cut: int) -> PreparedData:
    root = Path(root)
    path = root / "data" / "train" / "grunfeld_train_through_1950.csv"
    frame = pd.read_csv(path).sort_values(["year", "firm"]).reset_index(drop=True)
    train = frame.loc[frame["year"] <= evidence_cut].copy()
    if train.empty:
        raise ValueError("empty training frame")
    firms = sorted(frame["firm"].astype(str).unique())
    index = {name: idx for idx, name in enumerate(firms)}
    train["group"] = train["firm"].astype(str).map(index).astype(int)
    scaler: dict[str, dict[str, float]] = {}
    for column in ("invest", "value", "capital"):
        log_name = f"log_{column}"
        z_name = f"z_{log_name}"
        train[log_name] = np.log1p(train[column].astype(float))
        mean = float(train[log_name].mean())
        scale = float(train[log_name].std(ddof=0))
        if not np.isfinite(scale) or scale <= 0:
            raise ValueError(f"invalid scale for {column}")
        scaler[log_name] = {"mean": mean, "scale": scale}
        train[z_name] = (train[log_name] - mean) / scale
    arrays = {
        "y": train["z_log_invest"].to_numpy(float),
        "x_value": train["z_log_value"].to_numpy(float),
        "x_capital": train["z_log_capital"].to_numpy(float),
        "group": train["group"].to_numpy(np.int32),
        "basis": helmert_basis(len(firms)),
    }
    metadata = {
        "evidence_cut": int(evidence_cut),
        "n_rows": int(len(train)),
        "n_groups": len(firms),
        "firm_names": firms,
        "scaler": scaler,
        "years": [int(train["year"].min()), int(train["year"].max())],
    }
    payload = {"domain": "grunfeld", "arrays": {k: v.tolist() for k, v in arrays.items()}, "metadata": metadata}
    return PreparedData("grunfeld", arrays, metadata, canonical_hash(payload), {str(path.relative_to(root)): sha256_file(path)})


def prepare_baseball(root: str | Path) -> PreparedData:
    root = Path(root)
    path = root / "data" / "train" / "baseball_initial_45.csv"
    frame = pd.read_csv(path)
    if frame.empty or not np.all(frame["at_bats"].to_numpy(int) >= frame["hits"].to_numpy(int)):
        raise ValueError("invalid baseball training data")
    arrays = {
        "at_bats": frame["at_bats"].to_numpy(np.int32),
        "hits": frame["hits"].to_numpy(np.int32),
        "basis": helmert_basis(len(frame)),
    }
    metadata = {"n_groups": int(len(frame)), "player_names": frame["player"].astype(str).tolist(), "training_block": "first_45_at_bats"}
    payload = {"domain": "baseball", "arrays": {k: v.tolist() for k, v in arrays.items()}, "metadata": metadata}
    return PreparedData("baseball", arrays, metadata, canonical_hash(payload), {str(path.relative_to(root)): sha256_file(path)})


def assert_fit_isolation(root: str | Path) -> dict[str, Any]:
    root = Path(root)
    future_dir = root / "data" / "future"
    future_files = sorted(str(p.relative_to(root)) for p in future_dir.rglob("*") if p.is_file()) if future_dir.exists() else []
    return {"future_directory_present": future_dir.exists(), "future_files": future_files, "isolated": not future_files}
