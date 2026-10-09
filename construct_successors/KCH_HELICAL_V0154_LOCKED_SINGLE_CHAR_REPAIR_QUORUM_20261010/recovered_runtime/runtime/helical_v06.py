from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import random
import tarfile
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from numpy.typing import NDArray
from sklearn.mixture import GaussianMixture
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import SplineTransformer
from sklearn.linear_model import Ridge

Array = NDArray[np.float64]


# ----------------------------- canonical helpers -----------------------------

def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def content_id(prefix: str, value: Any) -> str:
    return f"{prefix}:{sha256_bytes(canonical_bytes(value))}"


def write_json(path: str | Path, value: Any) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def protocol_body_sha256(protocol: Mapping[str, Any]) -> str:
    body = dict(protocol)
    body.pop("protocol_id", None)
    body.pop("protocol_sha256", None)
    return sha256_bytes(canonical_bytes(body))


# ----------------------------- data contracts --------------------------------

@dataclass(frozen=True)
class EventCloud:
    catalog_id: str
    event_id: NDArray[np.str_]
    timestamp_s: Array
    latitude: Array
    longitude: Array
    depth_km: Array
    sigma_x_km: Array
    sigma_y_km: Array
    sigma_z_km: Array
    cluster_id: NDArray[np.str_]
    metadata: dict[str, Any]

    def __len__(self) -> int:
        return int(self.timestamp_s.size)

    def subset(self, indices: Sequence[int], *, catalog_id: str | None = None) -> "EventCloud":
        idx = np.asarray(indices, dtype=int)
        return EventCloud(
            catalog_id=catalog_id or self.catalog_id,
            event_id=self.event_id[idx],
            timestamp_s=self.timestamp_s[idx],
            latitude=self.latitude[idx],
            longitude=self.longitude[idx],
            depth_km=self.depth_km[idx],
            sigma_x_km=self.sigma_x_km[idx],
            sigma_y_km=self.sigma_y_km[idx],
            sigma_z_km=self.sigma_z_km[idx],
            cluster_id=self.cluster_id[idx],
            metadata=dict(self.metadata),
        )


@dataclass(frozen=True)
class CoordinateFrame:
    lat0_deg: float
    lon0_deg: float
    depth0_km: float


@dataclass
class BasisModel:
    family: str
    parameter_count: int
    degree: int | None = None
    n_knots: int | None = None
    spline: SplineTransformer | None = None

    def fit_transform(self, s: Array) -> Array:
        x = np.asarray(s, dtype=float).reshape(-1, 1)
        if self.family.startswith("POLY"):
            assert self.degree is not None
            return np.column_stack([np.asarray(s, dtype=float) ** d for d in range(self.degree + 1)])
        if self.family.startswith("SPLINE"):
            assert self.n_knots is not None
            self.spline = SplineTransformer(
                n_knots=self.n_knots,
                degree=3,
                include_bias=True,
                knots="quantile",
                extrapolation="linear",
            )
            out = self.spline.fit_transform(x)
            self.parameter_count = int(out.shape[1])
            return np.asarray(out, dtype=float)
        raise ValueError(f"unknown basis family {self.family}")

    def transform(self, s: Array) -> Array:
        x = np.asarray(s, dtype=float).reshape(-1, 1)
        if self.family.startswith("POLY"):
            assert self.degree is not None
            return np.column_stack([np.asarray(s, dtype=float) ** d for d in range(self.degree + 1)])
        if self.family.startswith("SPLINE"):
            if self.spline is None:
                raise RuntimeError("spline basis not fitted")
            return np.asarray(self.spline.transform(x), dtype=float)
        raise ValueError(f"unknown basis family {self.family}")


@dataclass(frozen=True)
class BranchFrame:
    label: int
    center_xyz: tuple[float, float, float]
    basis_columns: tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]
    train_count: int


@dataclass
class BranchBaseline:
    label: int
    frame: BranchFrame
    basis: BasisModel
    coef_u: Array
    coef_v: Array
    covariance: Array
    covariance_inv: Array
    covariance_logdet: float
    train_s_min: float
    train_s_max: float


@dataclass
class SegmentCorrection:
    lower: float
    upper: float
    wavelength: float
    wavenumber: float
    phase_origin: float
    coef_u: Array
    coef_v: Array
    determinant: float
    amplitude_rms: float
    design_condition: float
    train_count: int


@dataclass
class BranchHelix:
    label: int
    baseline: BranchBaseline
    segments: list[SegmentCorrection]
    segment_scheme: str
    covariance: Array
    covariance_inv: Array
    covariance_logdet: float


@dataclass
class FittedConfiguration:
    branch_count: int
    baseline_family: str
    segment_scheme: str
    gmm: GaussianMixture
    baselines: dict[int, BranchBaseline]
    helices: dict[int, BranchHelix]
    selected_turns_grid: tuple[float, ...]
    complexity_parameters_baseline: int
    complexity_parameters_helix: int
    train_selection_score_baseline: float
    calibration_selection_score_baseline: float
    train_selection_score_helix: float
    calibration_selection_score_helix: float


# ----------------------------- parsing ---------------------------------------

def _dt_to_seconds(dt: datetime) -> float:
    return dt.timestamp()


def _safe_float(token: str) -> float:
    value = float(token)
    if not math.isfinite(value):
        raise ValueError(f"non-finite number {token!r}")
    return value


def _parse_second(year: int, month: int, day: int, hour: int, minute: int, second: float) -> float:
    base = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
    return _dt_to_seconds(base + timedelta(seconds=float(second)))


def parse_hypodd24(path: str | Path, catalog_id: str) -> EventCloud:
    rows: list[list[str]] = []
    for line_no, raw in enumerate(Path(path).read_text(encoding="utf-8", errors="strict").splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        fields = raw.split()
        if len(fields) != 24:
            raise ValueError(f"{catalog_id}: line {line_no}: expected 24 fields, got {len(fields)}")
        rows.append(fields)
    if not rows:
        raise ValueError(f"{catalog_id}: no rows")
    event_id = np.asarray([r[0] for r in rows], dtype=str)
    lat = np.asarray([_safe_float(r[1]) for r in rows])
    lon = np.asarray([_safe_float(r[2]) for r in rows])
    dep = np.asarray([_safe_float(r[3]) for r in rows])
    ex = np.asarray([_safe_float(r[7]) / 1000.0 for r in rows])
    ey = np.asarray([_safe_float(r[8]) / 1000.0 for r in rows])
    ez = np.asarray([_safe_float(r[9]) / 1000.0 for r in rows])
    ts = np.asarray([
        _parse_second(int(r[10]), int(r[11]), int(r[12]), int(r[13]), int(r[14]), _safe_float(r[15]))
        for r in rows
    ])
    clusters = np.asarray([r[23] for r in rows], dtype=str)
    return EventCloud(
        catalog_id=catalog_id,
        event_id=event_id,
        timestamp_s=ts,
        latitude=lat,
        longitude=lon,
        depth_km=dep,
        sigma_x_km=ex,
        sigma_y_km=ey,
        sigma_z_km=ez,
        cluster_id=clusters,
        metadata={"parser": "HYPODD24", "row_count": len(rows), "source_sha256": sha256_file(path)},
    )


def parse_growclust25_text(text: str, catalog_id: str, source_sha256: str) -> EventCloud:
    rows: list[list[str]] = []
    for line_no, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        fields = raw.split()
        if len(fields) != 25:
            raise ValueError(f"{catalog_id}: line {line_no}: expected 25 fields, got {len(fields)}")
        rows.append(fields)
    if not rows:
        raise ValueError(f"{catalog_id}: no rows")
    event_id = np.asarray([r[6] for r in rows], dtype=str)
    ts = np.asarray([
        _parse_second(int(r[0]), int(r[1]), int(r[2]), int(r[3]), int(r[4]), _safe_float(r[5]))
        for r in rows
    ])
    lat = np.asarray([_safe_float(r[7]) for r in rows])
    lon = np.asarray([_safe_float(r[8]) for r in rows])
    dep = np.asarray([_safe_float(r[9]) for r in rows])
    # GrowClust eh is horizontal uncertainty. Use it conservatively on both horizontal axes.
    eh = np.asarray([max(0.0, _safe_float(r[19])) for r in rows])
    ez = np.asarray([max(0.0, _safe_float(r[20])) for r in rows])
    clusters = np.asarray([r[12] for r in rows], dtype=str)
    nbranch = np.asarray([int(float(r[13])) for r in rows])
    relocated = nbranch > 1
    if int(np.sum(relocated)) >= 1:
        event_id = event_id[relocated]
        ts = ts[relocated]
        lat = lat[relocated]
        lon = lon[relocated]
        dep = dep[relocated]
        eh = eh[relocated]
        ez = ez[relocated]
        clusters = clusters[relocated]
    return EventCloud(
        catalog_id=catalog_id,
        event_id=event_id,
        timestamp_s=ts,
        latitude=lat,
        longitude=lon,
        depth_km=dep,
        sigma_x_km=eh,
        sigma_y_km=eh,
        sigma_z_km=ez,
        cluster_id=clusters,
        metadata={
            "parser": "GROWCLUST25",
            "row_count_after_relocated_filter": int(event_id.size),
            "source_sha256": source_sha256,
            "relocated_filter": "nbranch>1",
        },
    )


def parse_growclust25(path: str | Path, catalog_id: str) -> EventCloud:
    source = Path(path)
    return parse_growclust25_text(source.read_text(encoding="utf-8", errors="strict"), catalog_id, sha256_file(source))


def extract_growclust_from_tar(path: str | Path, catalog_id: str) -> tuple[EventCloud, dict[str, Any]]:
    source = Path(path)
    candidates: list[tuple[int, str, str]] = []
    with tarfile.open(source, "r:gz") as archive:
        members = [m for m in archive.getmembers() if m.isfile()]
        for member in members:
            name = member.name
            if name.startswith("/") or ".." in Path(name).parts:
                raise ValueError(f"unsafe tar member {name!r}")
            handle = archive.extractfile(member)
            if handle is None:
                continue
            data = handle.read()
            try:
                text = data.decode("utf-8", errors="strict")
            except UnicodeDecodeError:
                continue
            count = 0
            valid = True
            for raw in text.splitlines():
                if not raw.strip() or raw.lstrip().startswith("#"):
                    continue
                if len(raw.split()) != 25:
                    valid = False
                    break
                count += 1
            if valid and count >= 250:
                candidates.append((count, name, text))
    if not candidates:
        raise ValueError(f"{catalog_id}: no eligible 25-field catalog member in tar")
    candidates.sort(key=lambda item: (-item[0], item[1]))
    count, name, text = candidates[0]
    cloud = parse_growclust25_text(text, catalog_id, sha256_bytes(text.encode("utf-8")))
    receipt = {
        "tar_sha256": sha256_file(source),
        "selected_member": name,
        "selected_member_rows": count,
        "eligible_members": [{"name": n, "rows": c} for c, n, _ in candidates],
        "selection_rule": "highest_valid_25_field_row_count_then_lexicographic",
    }
    return cloud, receipt


# ----------------------------- audit/selection -------------------------------

def audit_cloud(cloud: EventCloud) -> dict[str, Any]:
    if len(cloud) == 0:
        raise ValueError("empty cloud")
    order = np.argsort(cloud.timestamp_s, kind="stable")
    ts_sorted = cloud.timestamp_s[order]
    unique_ids = len(set(cloud.event_id.tolist()))
    counts: dict[str, int] = {}
    for cid in cloud.cluster_id.tolist():
        counts[cid] = counts.get(cid, 0) + 1
    return {
        "catalog_id": cloud.catalog_id,
        "event_count": len(cloud),
        "unique_event_ids": unique_ids,
        "duplicate_event_ids": len(cloud) - unique_ids,
        "chronological_input": bool(np.all(np.diff(cloud.timestamp_s) >= 0.0)),
        "first_time_utc": datetime.fromtimestamp(float(ts_sorted[0]), tz=timezone.utc).isoformat(),
        "last_time_utc": datetime.fromtimestamp(float(ts_sorted[-1]), tz=timezone.utc).isoformat(),
        "cluster_count": len(counts),
        "largest_clusters": sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10],
        "sigma_median_km": [
            float(np.median(cloud.sigma_x_km)),
            float(np.median(cloud.sigma_y_km)),
            float(np.median(cloud.sigma_z_km)),
        ],
        "metadata": cloud.metadata,
    }


def select_largest_eligible_cluster(cloud: EventCloud, min_events: int, max_events: int) -> tuple[EventCloud, dict[str, Any]]:
    counts: dict[str, int] = {}
    for cid in cloud.cluster_id.tolist():
        counts[cid] = counts.get(cid, 0) + 1
    eligible = sorted(((count, cid) for cid, count in counts.items() if count >= min_events), key=lambda x: (-x[0], x[1]))
    if eligible:
        selected_count, selected_cluster = eligible[0]
        indices = np.flatnonzero(cloud.cluster_id == selected_cluster)
        rule = "largest_cluster_ge_min_events_then_cluster_id"
    else:
        if len(cloud) < min_events:
            raise ValueError(f"{cloud.catalog_id}: no cluster and full catalog below min_events={min_events}")
        selected_count, selected_cluster = len(cloud), "__FULL_CATALOG_FALLBACK__"
        indices = np.arange(len(cloud), dtype=int)
        rule = "full_catalog_fallback_no_cluster_ge_min_events"
    # Stable chronological order first.
    indices = indices[np.argsort(cloud.timestamp_s[indices], kind="stable")]
    original_count = int(indices.size)
    if indices.size > max_events:
        # Deterministic approximately uniform chronological subsample preserving endpoints.
        positions = np.linspace(0, indices.size - 1, num=max_events)
        chosen = np.unique(np.rint(positions).astype(int))
        indices = indices[chosen]
    selected = cloud.subset(indices, catalog_id=f"{cloud.catalog_id}::cluster={selected_cluster}")
    receipt = {
        "selection_rule": rule,
        "selected_cluster_id": selected_cluster,
        "selected_cluster_original_count": original_count,
        "selected_count_after_cap": len(selected),
        "min_events": min_events,
        "max_events": max_events,
        "eligible_cluster_counts": [{"cluster_id": cid, "count": count} for count, cid in eligible],
        "subsample_rule": "uniform_chronological_indices_preserve_endpoints" if original_count > max_events else "none",
    }
    return selected, receipt


# ----------------------------- coordinates -----------------------------------
EARTH_RADIUS_KM = 6371.0088


def fit_coordinate_frame(cloud: EventCloud, train_indices: Sequence[int]) -> CoordinateFrame:
    idx = np.asarray(train_indices, dtype=int)
    return CoordinateFrame(
        lat0_deg=float(np.median(cloud.latitude[idx])),
        lon0_deg=float(np.median(cloud.longitude[idx])),
        depth0_km=float(np.median(cloud.depth_km[idx])),
    )


def to_local_xyz(cloud: EventCloud, frame: CoordinateFrame) -> Array:
    lat0 = math.radians(frame.lat0_deg)
    x = EARTH_RADIUS_KM * math.cos(lat0) * np.radians(cloud.longitude - frame.lon0_deg)
    y = EARTH_RADIUS_KM * np.radians(cloud.latitude - frame.lat0_deg)
    z = cloud.depth_km - frame.depth0_km
    return np.column_stack([x, y, z]).astype(float)


def make_time_split(n: int, train_fraction: float, calibration_fraction: float) -> dict[str, NDArray[np.int64]]:
    if n < 12:
        raise ValueError("n too small for time split")
    n_train = max(1, int(math.floor(n * train_fraction)))
    n_cal = max(1, int(math.floor(n * calibration_fraction)))
    if n_train + n_cal >= n:
        raise ValueError("invalid split fractions")
    return {
        "train": np.arange(0, n_train, dtype=int),
        "calibration": np.arange(n_train, n_train + n_cal, dtype=int),
        "test": np.arange(n_train + n_cal, n, dtype=int),
        "fit": np.arange(0, n_train + n_cal, dtype=int),
    }


# ----------------------------- geometry --------------------------------------

def _deterministic_basis(points: Array) -> tuple[Array, Array]:
    center = np.mean(points, axis=0)
    centered = points - center
    _, _, vt = np.linalg.svd(centered, full_matrices=False)
    basis = vt.T.astype(float)
    # Deterministic sign for principal axis: largest-magnitude coordinate positive.
    for col in range(3):
        vec = basis[:, col]
        pivot = int(np.argmax(np.abs(vec)))
        if vec[pivot] < 0:
            basis[:, col] *= -1.0
    # Enforce right-handedness.
    if np.linalg.det(basis) < 0:
        basis[:, 2] *= -1.0
    return center, basis


def fit_branch_frames(xyz: Array, train_indices: Array, labels: NDArray[np.int64], branch_count: int, min_branch_train: int) -> dict[int, BranchFrame]:
    frames: dict[int, BranchFrame] = {}
    for label in range(branch_count):
        idx = train_indices[labels == label]
        if idx.size < min_branch_train:
            raise ValueError(f"branch {label}: only {idx.size} train events")
        center, basis = _deterministic_basis(xyz[idx])
        frames[label] = BranchFrame(
            label=label,
            center_xyz=tuple(float(v) for v in center),
            basis_columns=tuple(tuple(float(v) for v in basis[:, c]) for c in range(3)),  # type: ignore[arg-type]
            train_count=int(idx.size),
        )
    return frames


def project_to_branch(xyz: Array, frame: BranchFrame) -> Array:
    center = np.asarray(frame.center_xyz, dtype=float)
    basis = np.column_stack(frame.basis_columns)
    return (xyz - center) @ basis


def gmm_parameter_count(k: int, dimension: int = 3) -> int:
    # full covariance: means + symmetric covariance + mixing weights
    return int(k * dimension + k * dimension * (dimension + 1) // 2 + (k - 1))


def _branch_axis_ratio(points: Array) -> float:
    if points.shape[0] < 4:
        return 0.0
    centered = points - np.mean(points, axis=0)
    cov = np.cov(centered.T, ddof=1)
    eig = np.linalg.eigvalsh(np.asarray(cov, dtype=float))
    eig = np.sort(np.maximum(eig, 1e-12))[::-1]
    return float(math.sqrt(eig[0] / eig[1]))


def fit_gmm_candidates(
    xyz: Array,
    train_indices: Array,
    max_branches: int,
    min_branch_train: int,
    min_branch_axis_ratio: float,
    random_seed: int,
) -> list[tuple[GaussianMixture, dict[str, Any]]]:
    """Fit structurally admissible branch candidates without selecting on helicity.

    A component is a candidate fault branch/ribbon only if it is sufficiently populated
    and elongated. This prevents a GMM from buying explanatory power by tessellating a
    periodic tube into compact blobs and then calling those blobs independent branches.
    """
    train = xyz[train_indices]
    out: list[tuple[GaussianMixture, dict[str, Any]]] = []
    for k in range(1, max_branches + 1):
        if train.shape[0] < k * min_branch_train:
            continue
        gmm = GaussianMixture(
            n_components=k,
            covariance_type="full",
            reg_covar=1e-5,
            n_init=20,
            max_iter=1000,
            random_state=random_seed + k,
            init_params="kmeans",
        )
        gmm.fit(train)
        labels = np.asarray(gmm.predict(train), dtype=np.int64)
        counts = np.bincount(labels, minlength=k)
        ratios = [
            _branch_axis_ratio(train[labels == label])
            for label in range(k)
        ]
        count_valid = bool(np.all(counts >= min_branch_train))
        shape_valid = bool(all(ratio >= min_branch_axis_ratio for ratio in ratios))
        valid = count_valid and shape_valid
        report = {
            "branch_count": k,
            "gmm_bic": float(gmm.bic(train)),
            "gmm_parameter_count": gmm_parameter_count(k),
            "train_counts": counts.tolist(),
            "branch_axis_ratios": ratios,
            "minimum_axis_ratio": min_branch_axis_ratio,
            "count_valid": count_valid,
            "shape_valid": shape_valid,
            "valid": valid,
        }
        if valid:
            out.append((gmm, report))
    if not out:
        raise ValueError("no structurally admissible GMM branching model")
    return out


# ----------------------------- regression ------------------------------------
BASELINE_FAMILIES: tuple[tuple[str, int | None], ...] = (
    ("POLY0", 0),
    ("POLY1", 1),
    ("POLY2", 2),
    ("SPLINE4", 4),
    ("SPLINE6", 6),
)


def make_basis(family: str) -> BasisModel:
    if family.startswith("POLY"):
        degree = int(family[-1])
        return BasisModel(family=family, degree=degree, n_knots=None, parameter_count=degree + 1)
    if family.startswith("SPLINE"):
        n_knots = int(family.replace("SPLINE", ""))
        return BasisModel(family=family, degree=None, n_knots=n_knots, parameter_count=0)
    raise ValueError(f"unknown family {family}")


def _fit_linear(design: Array, target: Array, alpha: float = 1e-8) -> Array:
    model = Ridge(alpha=alpha, fit_intercept=False, solver="svd")
    model.fit(design, target)
    return np.asarray(model.coef_, dtype=float)


def _covariance(residuals: Array) -> tuple[Array, Array, float]:
    if residuals.shape[0] < 3:
        raise ValueError("too few residuals")
    cov = np.cov(residuals.T, ddof=1)
    cov = np.asarray(cov, dtype=float)
    if cov.shape != (2, 2):
        cov = np.eye(2) * float(np.var(residuals))
    floor = max(1e-8, 1e-6 * float(np.trace(cov)) / 2.0)
    cov += np.eye(2) * floor
    sign, logdet = np.linalg.slogdet(cov)
    if sign <= 0:
        raise ValueError("non-positive covariance")
    inv = np.linalg.inv(cov)
    return cov, inv, float(logdet)


def _nll(residuals: Array, inv: Array, logdet: float) -> float:
    quad = np.einsum("ni,ij,nj->n", residuals, inv, residuals)
    return float(0.5 * np.sum(2.0 * math.log(2.0 * math.pi) + logdet + quad))


def _rmse(residuals: Array) -> float:
    return float(math.sqrt(np.mean(np.sum(residuals * residuals, axis=1))))


def _mae_radial(residuals: Array) -> float:
    return float(np.mean(np.sqrt(np.sum(residuals * residuals, axis=1))))


def fit_baseline_for_family(
    xyz: Array,
    all_labels: NDArray[np.int64],
    frames: Mapping[int, BranchFrame],
    train_indices: Array,
    evaluation_indices: Array,
    family: str,
) -> tuple[dict[int, BranchBaseline], dict[str, float | int]]:
    baselines: dict[int, BranchBaseline] = {}
    train_nll = 0.0
    eval_nll = 0.0
    parameter_count = 0
    for label, frame in frames.items():
        train_idx = train_indices[all_labels[train_indices] == label]
        eval_idx = evaluation_indices[all_labels[evaluation_indices] == label]
        if train_idx.size < 20:
            raise ValueError(f"branch {label}: insufficient train points for baseline family {family}")
        train_proj = project_to_branch(xyz[train_idx], frame)
        eval_proj = project_to_branch(xyz[eval_idx], frame)
        basis = make_basis(family)
        x_train = basis.fit_transform(train_proj[:, 0])
        coef_u = _fit_linear(x_train, train_proj[:, 1])
        coef_v = _fit_linear(x_train, train_proj[:, 2])
        pred_train = np.column_stack([x_train @ coef_u, x_train @ coef_v])
        res_train = train_proj[:, 1:3] - pred_train
        cov, inv, logdet = _covariance(res_train)
        x_eval = basis.transform(eval_proj[:, 0])
        pred_eval = np.column_stack([x_eval @ coef_u, x_eval @ coef_v])
        res_eval = eval_proj[:, 1:3] - pred_eval
        train_nll += _nll(res_train, inv, logdet)
        eval_nll += _nll(res_eval, inv, logdet)
        parameter_count += 2 * x_train.shape[1] + 3
        baselines[label] = BranchBaseline(
            label=label,
            frame=frame,
            basis=basis,
            coef_u=coef_u,
            coef_v=coef_v,
            covariance=cov,
            covariance_inv=inv,
            covariance_logdet=logdet,
            train_s_min=float(np.min(train_proj[:, 0])),
            train_s_max=float(np.max(train_proj[:, 0])),
        )
    return baselines, {
        "train_nll": float(train_nll),
        "evaluation_nll": float(eval_nll),
        "parameter_count": int(parameter_count),
    }


def baseline_predict(baseline: BranchBaseline, projected: Array) -> Array:
    design = baseline.basis.transform(projected[:, 0])
    return np.column_stack([design @ baseline.coef_u, design @ baseline.coef_v])


SEGMENT_SCHEMES: dict[str, tuple[float, ...]] = {
    "ONE": (),
    "TWO_EQUAL": (0.5,),
    "THREE_EQUAL": (1.0 / 3.0, 2.0 / 3.0),
}


def _segment_bounds(s_train: Array, scheme: str) -> list[tuple[float, float]]:
    if scheme not in SEGMENT_SCHEMES:
        raise ValueError(f"unknown segment scheme {scheme}")
    cuts = [-math.inf]
    for q in SEGMENT_SCHEMES[scheme]:
        cuts.append(float(np.quantile(s_train, q)))
    cuts.append(math.inf)
    return list(zip(cuts[:-1], cuts[1:]))


def _segment_mask(s: Array, lower: float, upper: float, *, final: bool) -> NDArray[np.bool_]:
    if final:
        return (s >= lower) & (s <= upper)
    return (s >= lower) & (s < upper)


def fit_branch_helix(
    baseline: BranchBaseline,
    xyz: Array,
    labels: NDArray[np.int64],
    train_indices: Array,
    scheme: str,
    turns_grid: Sequence[float],
    min_segment_train: int,
    max_design_condition: float,
) -> BranchHelix:
    label = baseline.label
    idx = train_indices[labels[train_indices] == label]
    proj = project_to_branch(xyz[idx], baseline.frame)
    base_pred = baseline_predict(baseline, proj)
    residual = proj[:, 1:3] - base_pred
    bounds = _segment_bounds(proj[:, 0], scheme)
    segments: list[SegmentCorrection] = []
    correction = np.zeros_like(residual)
    for segment_index, (lower, upper) in enumerate(bounds):
        mask = _segment_mask(proj[:, 0], lower, upper, final=segment_index == len(bounds) - 1)
        count = int(np.sum(mask))
        if count < min_segment_train:
            raise ValueError(f"branch {label} segment {segment_index}: count {count} < {min_segment_train}")
        s = proj[mask, 0]
        r = residual[mask]
        span = float(np.max(s) - np.min(s))
        if span <= 1e-6:
            raise ValueError("segment has negligible span")
        best: tuple[float, float, Array, Array, float, float] | None = None
        for turns in turns_grid:
            wavelength = span / float(turns)
            k = 2.0 * math.pi / wavelength
            phase = k * (s - float(np.min(s)))
            design = np.column_stack([np.cos(phase), np.sin(phase)])
            condition = float(np.linalg.cond(design))
            if not math.isfinite(condition) or condition > max_design_condition:
                continue
            coef_u = _fit_linear(design, r[:, 0])
            coef_v = _fit_linear(design, r[:, 1])
            pred = np.column_stack([design @ coef_u, design @ coef_v])
            res = r - pred
            cov, inv, logdet = _covariance(res)
            nll = _nll(res, inv, logdet)
            p = 4 + 3
            bic = 2.0 * nll + p * math.log(max(count, 2))
            determinant = float(coef_u[0] * coef_v[1] - coef_u[1] * coef_v[0])
            amplitude = float(math.sqrt(np.mean(np.sum(pred * pred, axis=1))))
            candidate = (bic, wavelength, coef_u, coef_v, determinant, amplitude)
            if best is None or candidate[0] < best[0]:
                best = candidate
        if best is None:
            raise ValueError("no identifiable helix frequency")
        bic, wavelength, coef_u, coef_v, determinant, amplitude = best
        k = 2.0 * math.pi / wavelength
        phase_origin = float(np.min(proj[mask, 0]))
        phase_all = k * (proj[mask, 0] - phase_origin)
        design_all = np.column_stack([np.cos(phase_all), np.sin(phase_all)])
        correction[mask] = np.column_stack([design_all @ coef_u, design_all @ coef_v])
        segments.append(SegmentCorrection(
            lower=float(lower),
            upper=float(upper),
            wavelength=float(wavelength),
            wavenumber=float(k),
            phase_origin=phase_origin,
            coef_u=np.asarray(coef_u, dtype=float),
            coef_v=np.asarray(coef_v, dtype=float),
            determinant=float(determinant),
            amplitude_rms=float(amplitude),
            design_condition=float(np.linalg.cond(design_all)),
            train_count=count,
        ))
    helix_residual = residual - correction
    cov, inv, logdet = _covariance(helix_residual)
    return BranchHelix(
        label=label,
        baseline=baseline,
        segments=segments,
        segment_scheme=scheme,
        covariance=cov,
        covariance_inv=inv,
        covariance_logdet=logdet,
    )


def helix_correction(model: BranchHelix, projected: Array) -> Array:
    s = projected[:, 0]
    out = np.zeros((len(projected), 2), dtype=float)
    # The phase origin is each segment's finite lower bound if available; otherwise the observed minimum.
    for i, segment in enumerate(model.segments):
        mask = _segment_mask(s, segment.lower, segment.upper, final=i == len(model.segments) - 1)
        if not np.any(mask):
            continue
        phase = segment.wavenumber * (s[mask] - segment.phase_origin)
        design = np.column_stack([np.cos(phase), np.sin(phase)])
        out[mask] = np.column_stack([design @ segment.coef_u, design @ segment.coef_v])
    return out


# ----------------------------- model selection/evaluation --------------------

def _predict_labels(gmm: GaussianMixture, xyz: Array) -> NDArray[np.int64]:
    return np.asarray(gmm.predict(xyz), dtype=np.int64)


def _aggregate_model_metrics(
    xyz: Array,
    indices: Array,
    labels: NDArray[np.int64],
    baselines: Mapping[int, BranchBaseline],
    helices: Mapping[int, BranchHelix] | None,
) -> dict[str, Any]:
    residuals: list[Array] = []
    nll = 0.0
    per_event_sq: list[float] = []
    per_event_nll: list[float] = []
    branch_rows: list[dict[str, Any]] = []
    for label, baseline in baselines.items():
        idx = indices[labels[indices] == label]
        if idx.size == 0:
            continue
        proj = project_to_branch(xyz[idx], baseline.frame)
        pred = baseline_predict(baseline, proj)
        if helices is None:
            cov_inv = baseline.covariance_inv
            logdet = baseline.covariance_logdet
        else:
            model = helices[label]
            pred = pred + helix_correction(model, proj)
            cov_inv = model.covariance_inv
            logdet = model.covariance_logdet
        res = proj[:, 1:3] - pred
        radial_sq = np.sum(res * res, axis=1)
        quad = np.einsum("ni,ij,nj->n", res, cov_inv, res)
        event_nll = 0.5 * (2.0 * math.log(2.0 * math.pi) + logdet + quad)
        residuals.append(res)
        per_event_sq.extend(float(v) for v in radial_sq)
        per_event_nll.extend(float(v) for v in event_nll)
        nll += float(np.sum(event_nll))
        branch_rows.append({
            "label": int(label),
            "count": int(idx.size),
            "rmse_km": float(math.sqrt(np.mean(radial_sq))),
            "mean_nll": float(np.mean(event_nll)),
        })
    if not residuals:
        raise ValueError("no evaluable points")
    res_all = np.vstack(residuals)
    return {
        "count": int(res_all.shape[0]),
        "rmse_km": _rmse(res_all),
        "mae_radial_km": _mae_radial(res_all),
        "nll": float(nll),
        "mean_nll": float(nll / res_all.shape[0]),
        "per_event_sq": per_event_sq,
        "per_event_nll": per_event_nll,
        "branches": branch_rows,
    }


def select_configuration(
    xyz: Array,
    split: Mapping[str, Array],
    protocol: Mapping[str, Any],
) -> tuple[FittedConfiguration, dict[str, Any]]:
    """Select branching and nonhelical geometry before selecting helicity.

    Branch count and baseline family are jointly selected only by the nonhelical
    predictive model on calibration data.  Helicity never gets to choose the branch
    partition that it will later compete against.
    """
    random_seed = int(protocol["random_seed"])
    model_grid = protocol["model_grid"]
    ident = protocol["identifiability"]
    penalty_weight = float(model_grid.get("selection_penalty_weight", 0.15))
    n_train = len(split["train"])

    gmm_candidates = fit_gmm_candidates(
        xyz,
        split["train"],
        max_branches=int(model_grid["max_branches"]),
        min_branch_train=int(ident["min_branch_train"]),
        min_branch_axis_ratio=float(ident.get("min_branch_axis_ratio", 1.5)),
        random_seed=random_seed,
    )

    structure_rows: list[dict[str, Any]] = []
    structure_objects: list[tuple[GaussianMixture, NDArray[np.int64], dict[int, BranchFrame], dict[int, BranchBaseline], dict[str, Any]]] = []
    for gmm, gmm_report in gmm_candidates:
        labels = _predict_labels(gmm, xyz)
        try:
            frames = fit_branch_frames(
                xyz,
                split["train"],
                labels[split["train"]],
                int(gmm.n_components),
                int(ident["min_branch_train"]),
            )
        except (ValueError, np.linalg.LinAlgError) as exc:
            structure_rows.append({**gmm_report, "status": "INVALID_FRAME", "error": str(exc)})
            continue
        for family, _ in BASELINE_FAMILIES:
            try:
                baselines, metrics = fit_baseline_for_family(
                    xyz, labels, frames, split["train"], split["calibration"], family
                )
                shared_params = int(metrics["parameter_count"]) + int(gmm_report["gmm_parameter_count"])
                score = float(metrics["evaluation_nll"]) + penalty_weight * shared_params * math.log(max(n_train, 2))
                row = {
                    **gmm_report,
                    "baseline_family": family,
                    **metrics,
                    "shared_parameter_count": shared_params,
                    "selection_penalty_weight": penalty_weight,
                    "selection_score": score,
                    "status": "OK",
                    "object_index": len(structure_objects),
                }
                structure_rows.append(row)
                structure_objects.append((gmm, labels, frames, baselines, row))
            except (ValueError, np.linalg.LinAlgError) as exc:
                structure_rows.append({
                    **gmm_report,
                    "baseline_family": family,
                    "status": "INVALID_BASELINE",
                    "error": str(exc),
                })

    if not structure_objects:
        raise ValueError("no valid nonhelical branching/baseline configuration")
    gmm, labels, frames, baselines, selected_baseline_row = min(
        structure_objects,
        key=lambda item: (
            float(item[4]["selection_score"]),
            int(item[4]["branch_count"]),
            int(item[4]["shared_parameter_count"]),
            str(item[4]["baseline_family"]),
        ),
    )
    baseline_family = str(selected_baseline_row["baseline_family"])

    turns_grid = tuple(float(v) for v in model_grid["turns_per_segment"])
    helix_candidates: list[dict[str, Any]] = []
    helix_models: dict[str, dict[int, BranchHelix]] = {}
    for scheme in model_grid["segment_schemes"]:
        try:
            branches: dict[int, BranchHelix] = {}
            for label, baseline in baselines.items():
                branches[label] = fit_branch_helix(
                    baseline,
                    xyz,
                    labels,
                    split["train"],
                    str(scheme),
                    turns_grid,
                    min_segment_train=int(ident["min_segment_train"]),
                    max_design_condition=float(ident["max_design_condition"]),
                )
            train_metrics = _aggregate_model_metrics(xyz, split["train"], labels, baselines, branches)
            cal_metrics = _aggregate_model_metrics(xyz, split["calibration"], labels, baselines, branches)
            segment_count = sum(len(branch.segments) for branch in branches.values())
            extra_params = 7 * segment_count
            helix_params = int(selected_baseline_row["parameter_count"]) + extra_params
            # Baseline/GMM complexity is identical across these candidates and cancels.
            score = float(cal_metrics["nll"]) + penalty_weight * extra_params * math.log(max(n_train, 2))
            helix_candidates.append({
                "scheme": scheme,
                "segment_count_total": segment_count,
                "extra_parameter_count": extra_params,
                "parameter_count": helix_params,
                "train_nll": train_metrics["nll"],
                "calibration_nll": cal_metrics["nll"],
                "selection_penalty_weight": penalty_weight,
                "selection_score": score,
                "status": "OK",
            })
            helix_models[str(scheme)] = branches
        except (ValueError, np.linalg.LinAlgError) as exc:
            helix_candidates.append({"scheme": scheme, "status": "INVALID", "error": str(exc)})
    valid_helices = [row for row in helix_candidates if row["status"] == "OK"]
    if not valid_helices:
        raise ValueError("no valid helical candidate")
    selected_helix_row = min(
        valid_helices,
        key=lambda row: (
            float(row["selection_score"]),
            int(row["extra_parameter_count"]),
            str(row["scheme"]),
        ),
    )
    scheme = str(selected_helix_row["scheme"])
    helices = helix_models[scheme]

    config = FittedConfiguration(
        branch_count=int(gmm.n_components),
        baseline_family=baseline_family,
        segment_scheme=scheme,
        gmm=gmm,
        baselines=baselines,
        helices=helices,
        selected_turns_grid=turns_grid,
        complexity_parameters_baseline=int(selected_baseline_row["parameter_count"]),
        complexity_parameters_helix=int(selected_helix_row["parameter_count"]),
        train_selection_score_baseline=float(selected_baseline_row["train_nll"]),
        calibration_selection_score_baseline=float(selected_baseline_row["selection_score"]),
        train_selection_score_helix=float(selected_helix_row["train_nll"]),
        calibration_selection_score_helix=float(selected_helix_row["selection_score"]),
    )
    report = {
        "selection_principle": "nonhelical branching/baseline first; helicity conditional on frozen partition",
        "branching_baseline_candidates": structure_rows,
        "selected_nonhelical_structure": selected_baseline_row,
        "helix_candidates": helix_candidates,
        "selected_helix": selected_helix_row,
    }
    return config, report

def refit_selected_configuration(
    xyz: Array,
    split: Mapping[str, Array],
    selected: FittedConfiguration,
    protocol: Mapping[str, Any],
) -> FittedConfiguration:
    # Geometry and branch count are refitted on train+calibration, while every hyperparameter remains frozen.
    fit_indices = split["fit"]
    gmm = GaussianMixture(
        n_components=selected.branch_count,
        covariance_type="full",
        reg_covar=1e-5,
        n_init=10,
        max_iter=500,
        random_state=int(protocol["random_seed"]) + 701,
        init_params="kmeans",
    )
    gmm.fit(xyz[fit_indices])
    labels = _predict_labels(gmm, xyz)
    frames = fit_branch_frames(
        xyz,
        fit_indices,
        labels[fit_indices],
        selected.branch_count,
        int(protocol["identifiability"]["min_branch_fit"]),
    )
    baselines, baseline_metrics = fit_baseline_for_family(
        xyz, labels, frames, fit_indices, split["test"], selected.baseline_family
    )
    helices: dict[int, BranchHelix] = {}
    for label, baseline in baselines.items():
        helices[label] = fit_branch_helix(
            baseline,
            xyz,
            labels,
            fit_indices,
            selected.segment_scheme,
            selected.selected_turns_grid,
            min_segment_train=int(protocol["identifiability"]["min_segment_fit"]),
            max_design_condition=float(protocol["identifiability"]["max_design_condition"]),
        )
    segment_count = sum(len(branch.segments) for branch in helices.values())
    return FittedConfiguration(
        branch_count=selected.branch_count,
        baseline_family=selected.baseline_family,
        segment_scheme=selected.segment_scheme,
        gmm=gmm,
        baselines=baselines,
        helices=helices,
        selected_turns_grid=selected.selected_turns_grid,
        complexity_parameters_baseline=int(baseline_metrics["parameter_count"]),
        complexity_parameters_helix=int(baseline_metrics["parameter_count"]) + 7 * segment_count,
        train_selection_score_baseline=selected.train_selection_score_baseline,
        calibration_selection_score_baseline=selected.calibration_selection_score_baseline,
        train_selection_score_helix=selected.train_selection_score_helix,
        calibration_selection_score_helix=selected.calibration_selection_score_helix,
    )


def support_mask(xyz: Array, train_indices: Array, test_indices: Array, multiplier: float) -> tuple[NDArray[np.bool_], dict[str, Any]]:
    k = min(6, len(train_indices))
    nn = NearestNeighbors(n_neighbors=k)
    nn.fit(xyz[train_indices])
    train_dist, _ = nn.kneighbors(xyz[train_indices])
    within = train_dist[:, -1]
    threshold = float(np.quantile(within, 0.95) * multiplier)
    test_dist, _ = nn.kneighbors(xyz[test_indices], n_neighbors=1)
    distance = test_dist[:, 0]
    mask = distance <= threshold
    return mask, {
        "knn_k_train": k,
        "train_q95_kth_neighbor_km": float(np.quantile(within, 0.95)),
        "multiplier": multiplier,
        "support_threshold_km": threshold,
        "test_support_fraction": float(np.mean(mask)),
        "test_supported_count": int(np.sum(mask)),
        "test_count": int(mask.size),
        "test_nearest_distance_median_km": float(np.median(distance)),
        "test_nearest_distance_p95_km": float(np.quantile(distance, 0.95)),
    }


def _fixed_prediction_arrays(
    xyz: Array,
    indices: Array,
    config: FittedConfiguration,
) -> tuple[Array, Array, Array, NDArray[np.int64], Array]:
    labels = _predict_labels(config.gmm, xyz)
    obs_rows: list[Array] = []
    base_rows: list[Array] = []
    helix_rows: list[Array] = []
    label_rows: list[int] = []
    s_rows: list[float] = []
    for idx in indices:
        label = int(labels[idx])
        baseline = config.baselines[label]
        proj = project_to_branch(xyz[[idx]], baseline.frame)
        base = baseline_predict(baseline, proj)
        correction = helix_correction(config.helices[label], proj)
        obs_rows.append(proj[0, 1:3])
        base_rows.append(base[0])
        helix_rows.append((base + correction)[0])
        label_rows.append(label)
        s_rows.append(float(proj[0, 0]))
    return (
        np.asarray(obs_rows),
        np.asarray(base_rows),
        np.asarray(helix_rows),
        np.asarray(label_rows, dtype=np.int64),
        np.asarray(s_rows),
    )


def circular_shift_pvalue(
    obs: Array,
    base: Array,
    helix: Array,
    labels: NDArray[np.int64],
    s: Array,
    permutations: int,
) -> tuple[float, float, list[float]]:
    residual = obs - base
    correction = helix - base
    observed = float(np.sum(np.sum(residual * residual, axis=1) - np.sum((residual - correction) ** 2, axis=1)))
    nulls: list[float] = []
    for b in range(1, permutations + 1):
        shifted = np.zeros_like(residual)
        for label in sorted(set(labels.tolist())):
            idx = np.flatnonzero(labels == label)
            order = idx[np.argsort(s[idx], kind="stable")]
            n = len(order)
            if n <= 1:
                shifted[order] = residual[order]
                continue
            offset = 1 + ((b * 104729 + label * 8191) % (n - 1))
            shifted[order] = residual[np.roll(order, offset)]
        gain = float(np.sum(np.sum(shifted * shifted, axis=1) - np.sum((shifted - correction) ** 2, axis=1)))
        nulls.append(gain)
    p = (1.0 + sum(value >= observed for value in nulls)) / (permutations + 1.0)
    return observed, float(p), nulls


def moving_block_bootstrap_ci(loss_gain: Array, replicates: int, seed: int) -> dict[str, Any]:
    n = int(loss_gain.size)
    if n < 10:
        return {"status": "INSUFFICIENT", "count": n}
    block = max(5, int(round(n ** (1.0 / 3.0))))
    starts = np.arange(0, max(1, n - block + 1), dtype=int)
    rng = np.random.default_rng(seed)
    means: list[float] = []
    blocks_needed = int(math.ceil(n / block))
    for _ in range(replicates):
        pieces = []
        for _ in range(blocks_needed):
            start = int(rng.choice(starts))
            pieces.append(loss_gain[start:start + block])
        sample = np.concatenate(pieces)[:n]
        means.append(float(np.mean(sample)))
    return {
        "status": "OK",
        "replicates": replicates,
        "block_length": block,
        "observed_mean_gain_km2": float(np.mean(loss_gain)),
        "lower_95": float(np.quantile(means, 0.025)),
        "upper_95": float(np.quantile(means, 0.975)),
        "positive_fraction": float(np.mean(np.asarray(means) > 0.0)),
    }


def evaluate_unit_once(
    cloud: EventCloud,
    protocol: Mapping[str, Any],
    *,
    xyz_override: Array | None = None,
    selected_hyperparameters: FittedConfiguration | None = None,
) -> dict[str, Any]:
    order = np.argsort(cloud.timestamp_s, kind="stable")
    cloud = cloud.subset(order)
    split = make_time_split(len(cloud), float(protocol["split"]["train_fraction"]), float(protocol["split"]["calibration_fraction"]))
    frame = fit_coordinate_frame(cloud, split["train"])
    xyz = to_local_xyz(cloud, frame) if xyz_override is None else np.asarray(xyz_override, dtype=float)

    if selected_hyperparameters is None:
        selected, selection_report = select_configuration(xyz, split, protocol)
    else:
        selected = selected_hyperparameters
        selection_report = {"status": "HYPERPARAMETERS_FIXED_FROM_ORIGINAL_RUN"}
    fitted = refit_selected_configuration(xyz, split, selected, protocol)

    supported, support_report = support_mask(
        xyz,
        split["fit"],
        split["test"],
        float(protocol["support_overlap"]["radius_multiplier"]),
    )
    supported_test = split["test"][supported]
    if supported_test.size < int(protocol["identifiability"]["min_supported_test"]):
        return {
            "status": "NOT_IDENTIFIABLE_SPATIAL_EXTRAPOLATION",
            "catalog_id": cloud.catalog_id,
            "event_count": len(cloud),
            "split_counts": {k: int(len(v)) for k, v in split.items()},
            "support": support_report,
            "selection": selection_report,
        }

    labels = _predict_labels(fitted.gmm, xyz)
    fit_baseline_metrics = _aggregate_model_metrics(xyz, split["fit"], labels, fitted.baselines, None)
    fit_helix_metrics = _aggregate_model_metrics(xyz, split["fit"], labels, fitted.baselines, fitted.helices)
    fit_n = int(fit_baseline_metrics["count"])
    baseline_bic = 2.0 * float(fit_baseline_metrics["nll"]) + fitted.complexity_parameters_baseline * math.log(max(fit_n, 2))
    helix_bic = 2.0 * float(fit_helix_metrics["nll"]) + fitted.complexity_parameters_helix * math.log(max(fit_n, 2))
    fit_delta_bic = float(helix_bic - baseline_bic)

    baseline_metrics = _aggregate_model_metrics(xyz, supported_test, labels, fitted.baselines, None)
    helix_metrics = _aggregate_model_metrics(xyz, supported_test, labels, fitted.baselines, fitted.helices)
    rmse_improvement = (float(baseline_metrics["rmse_km"]) - float(helix_metrics["rmse_km"])) / float(baseline_metrics["rmse_km"])
    mean_nll_gain = float(baseline_metrics["mean_nll"]) - float(helix_metrics["mean_nll"])

    obs, base, helix, fixed_labels, s = _fixed_prediction_arrays(xyz, supported_test, fitted)
    baseline_sq = np.sum((obs - base) ** 2, axis=1)
    helix_sq = np.sum((obs - helix) ** 2, axis=1)
    loss_gain = baseline_sq - helix_sq
    observed_gain, raw_p, nulls = circular_shift_pvalue(
        obs,
        base,
        helix,
        fixed_labels,
        s,
        int(protocol["null_test"]["permutations"]),
    )
    bootstrap = moving_block_bootstrap_ci(
        loss_gain,
        int(protocol["bootstrap"]["replicates"]),
        int(protocol["random_seed"]) + 909,
    )

    fit_indices = split["fit"]
    fit_labels = _predict_labels(fitted.gmm, xyz)
    helix_identifiability: list[dict[str, Any]] = []
    for label, branch in fitted.helices.items():
        idx = fit_indices[fit_labels[fit_indices] == label]
        sigma = np.sqrt(
            cloud.sigma_x_km[idx] ** 2 + cloud.sigma_y_km[idx] ** 2 + cloud.sigma_z_km[idx] ** 2
        )
        median_sigma = float(np.median(sigma)) if sigma.size else 0.0
        for segment_index, segment in enumerate(branch.segments):
            helix_identifiability.append({
                "branch": label,
                "segment": segment_index,
                "wavelength_km": segment.wavelength,
                "pitch_km_per_turn": segment.wavelength,
                "chirality": "RIGHT" if segment.determinant > 0 else "LEFT" if segment.determinant < 0 else "DEGENERATE",
                "determinant": segment.determinant,
                "amplitude_rms_km": segment.amplitude_rms,
                "median_location_sigma_norm_km": median_sigma,
                "amplitude_to_sigma": segment.amplitude_rms / median_sigma if median_sigma > 0 else None,
                "design_condition": segment.design_condition,
                "train_count": segment.train_count,
            })

    return {
        "status": "EVALUATED",
        "catalog_id": cloud.catalog_id,
        "event_count": len(cloud),
        "coordinate_frame": asdict(frame),
        "split_counts": {k: int(len(v)) for k, v in split.items()},
        "support": support_report,
        "selection": selection_report,
        "selected_configuration": {
            "branch_count": fitted.branch_count,
            "baseline_family": fitted.baseline_family,
            "segment_scheme": fitted.segment_scheme,
            "complexity_parameters_baseline": fitted.complexity_parameters_baseline,
            "complexity_parameters_helix": fitted.complexity_parameters_helix,
        },
        "fit_complexity": {
            "fit_count": fit_n,
            "baseline_nll": float(fit_baseline_metrics["nll"]),
            "helix_nll": float(fit_helix_metrics["nll"]),
            "baseline_parameter_count": fitted.complexity_parameters_baseline,
            "helix_parameter_count": fitted.complexity_parameters_helix,
            "baseline_bic": float(baseline_bic),
            "helix_bic": float(helix_bic),
            "helix_minus_baseline_delta_bic": fit_delta_bic,
        },
        "baseline": {k: v for k, v in baseline_metrics.items() if not k.startswith("per_event")},
        "helix": {k: v for k, v in helix_metrics.items() if not k.startswith("per_event")},
        "relative_rmse_improvement": float(rmse_improvement),
        "mean_nll_gain_per_event": float(mean_nll_gain),
        "observed_sse_gain_km2": observed_gain,
        "raw_circular_shift_p": raw_p,
        "null_gain_quantiles": {
            "q05": float(np.quantile(nulls, 0.05)),
            "median": float(np.quantile(nulls, 0.5)),
            "q95": float(np.quantile(nulls, 0.95)),
        },
        "moving_block_bootstrap": bootstrap,
        "helical_segments": helix_identifiability,
        "per_event_loss_gain_km2": [float(v) for v in loss_gain],
    }


def uncertainty_stability(
    cloud: EventCloud,
    protocol: Mapping[str, Any],
    original: dict[str, Any],
) -> dict[str, Any]:
    if original.get("status") != "EVALUATED":
        return {"status": "NOT_RUN_ORIGINAL_NOT_EVALUATED"}
    order = np.argsort(cloud.timestamp_s, kind="stable")
    ordered = cloud.subset(order)
    split = make_time_split(len(ordered), float(protocol["split"]["train_fraction"]), float(protocol["split"]["calibration_fraction"]))
    frame = fit_coordinate_frame(ordered, split["train"])
    base_xyz = to_local_xyz(ordered, frame)
    selected, _ = select_configuration(base_xyz, split, protocol)
    rng = np.random.default_rng(int(protocol["uncertainty"]["seed"]))
    rows: list[dict[str, Any]] = []
    for replicate in range(int(protocol["uncertainty"]["replicates"])):
        noise = np.column_stack([
            rng.normal(0.0, ordered.sigma_x_km),
            rng.normal(0.0, ordered.sigma_y_km),
            rng.normal(0.0, ordered.sigma_z_km),
        ])
        try:
            row = evaluate_unit_once(ordered, protocol, xyz_override=base_xyz + noise, selected_hyperparameters=selected)
            rows.append({
                "replicate": replicate,
                "status": row.get("status"),
                "relative_rmse_improvement": row.get("relative_rmse_improvement"),
                "mean_nll_gain_per_event": row.get("mean_nll_gain_per_event"),
                "raw_circular_shift_p": row.get("raw_circular_shift_p"),
            })
        except Exception as exc:  # fail closed, record exact class/message
            rows.append({"replicate": replicate, "status": "FAILED", "error": f"{type(exc).__name__}: {exc}"})
    valid = [r for r in rows if r.get("status") == "EVALUATED"]
    improvements = np.asarray([float(r["relative_rmse_improvement"]) for r in valid], dtype=float)
    nll_gains = np.asarray([float(r["mean_nll_gain_per_event"]) for r in valid], dtype=float)
    return {
        "status": "OK" if valid else "NO_VALID_REPLICATES",
        "replicates_requested": int(protocol["uncertainty"]["replicates"]),
        "replicates_valid": len(valid),
        "positive_rmse_fraction": float(np.mean(improvements > 0.0)) if valid else 0.0,
        "threshold_rmse_fraction": float(np.mean(improvements >= float(protocol["decision"]["minimum_rmse_improvement"]))) if valid else 0.0,
        "positive_nll_fraction": float(np.mean(nll_gains > 0.0)) if valid else 0.0,
        "median_rmse_improvement": float(np.median(improvements)) if valid else None,
        "median_nll_gain": float(np.median(nll_gains)) if valid else None,
        "rows": rows,
    }


def holm_adjust(p_values: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(((float(p), key) for key, p in p_values.items()), key=lambda item: (item[0], item[1]))
    m = len(ordered)
    adjusted: dict[str, float] = {}
    running = 0.0
    for rank, (p, key) in enumerate(ordered, start=1):
        value = min(1.0, (m - rank + 1) * p)
        running = max(running, value)
        adjusted[key] = running
    return adjusted


def adjudicate_units(units: list[dict[str, Any]], protocol: Mapping[str, Any]) -> dict[str, Any]:
    raw = {row["unit_id"]: float(row["evaluation"]["raw_circular_shift_p"]) for row in units if row["evaluation"].get("status") == "EVALUATED"}
    adjusted = holm_adjust(raw)
    positives: list[str] = []
    rows: list[dict[str, Any]] = []
    for unit in units:
        evaluation = unit["evaluation"]
        uid = unit["unit_id"]
        if evaluation.get("status") != "EVALUATED":
            rows.append({"unit_id": uid, "outcome": evaluation.get("status"), "reasons": [evaluation.get("status")]})
            continue
        stability = unit["uncertainty_stability"]
        bootstrap = evaluation["moving_block_bootstrap"]
        reasons: list[str] = []
        if evaluation["relative_rmse_improvement"] < float(protocol["decision"]["minimum_rmse_improvement"]):
            reasons.append("rmse_improvement_below_minimum")
        if evaluation["mean_nll_gain_per_event"] < float(protocol["decision"]["minimum_mean_nll_gain"]):
            reasons.append("mean_nll_gain_below_minimum")
        if float(evaluation["fit_complexity"]["helix_minus_baseline_delta_bic"]) > float(protocol["decision"]["maximum_fit_delta_bic"]):
            reasons.append("fit_delta_bic_not_strongly_negative")
        if adjusted.get(uid, 1.0) > float(protocol["decision"]["familywise_alpha"]):
            reasons.append("holm_adjusted_null_p_above_alpha")
        if bootstrap.get("status") != "OK" or float(bootstrap.get("lower_95", -math.inf)) <= 0.0:
            reasons.append("moving_block_bootstrap_lower_bound_not_positive")
        if float(evaluation["support"]["test_support_fraction"]) < float(protocol["support_overlap"]["minimum_fraction"]):
            reasons.append("spatial_support_fraction_below_minimum")
        if stability.get("status") != "OK" or float(stability.get("threshold_rmse_fraction", 0.0)) < float(protocol["uncertainty"]["minimum_threshold_pass_fraction"]):
            reasons.append("uncertainty_threshold_stability_below_minimum")
        outcome = "LOCAL_HELICITY_UNIT_POSITIVE" if not reasons else "NONHELICAL_OR_INSUFFICIENT_LOCAL_HELICITY"
        if not reasons:
            positives.append(uid)
        rows.append({
            "unit_id": uid,
            "outcome": outcome,
            "reasons": reasons,
            "raw_p": evaluation["raw_circular_shift_p"],
            "holm_p": adjusted.get(uid),
            "relative_rmse_improvement": evaluation["relative_rmse_improvement"],
            "mean_nll_gain_per_event": evaluation["mean_nll_gain_per_event"],
            "fit_delta_bic": evaluation["fit_complexity"]["helix_minus_baseline_delta_bic"],
            "bootstrap_lower_95": bootstrap.get("lower_95"),
            "uncertainty_threshold_pass_fraction": stability.get("threshold_rmse_fraction"),
        })

    valid = [unit for unit in units if unit["evaluation"].get("status") == "EVALUATED"]
    total_base_sse = 0.0
    total_helix_sse = 0.0
    for unit in valid:
        e = unit["evaluation"]
        n = int(e["baseline"]["count"])
        total_base_sse += n * float(e["baseline"]["rmse_km"]) ** 2
        total_helix_sse += n * float(e["helix"]["rmse_km"]) ** 2
    aggregate_improvement = (
        (math.sqrt(total_base_sse / sum(int(u["evaluation"]["baseline"]["count"]) for u in valid))
         - math.sqrt(total_helix_sse / sum(int(u["evaluation"]["helix"]["count"]) for u in valid)))
        / math.sqrt(total_base_sse / sum(int(u["evaluation"]["baseline"]["count"]) for u in valid))
        if valid and total_base_sse > 0 else None
    )
    required = int(protocol["decision"]["minimum_positive_catalogs"])
    if len(positives) >= required and aggregate_improvement is not None and aggregate_improvement >= float(protocol["decision"]["minimum_rmse_improvement"]):
        aggregate_outcome = "LOCAL_PIECEWISE_HELICITY_REPLICATES"
    elif len(positives) == 1:
        aggregate_outcome = "LOCAL_HELICITY_SINGLE_CATALOG_ONLY"
    elif valid and len(positives) == 0:
        aggregate_outcome = "NONHELICAL_BRANCHING_RIVALS_GENERALIZE"
    else:
        aggregate_outcome = "MIXED_OR_NOT_IDENTIFIABLE"
    return {
        "unit_adjudications": rows,
        "raw_p_values": raw,
        "holm_adjusted_p_values": adjusted,
        "positive_unit_ids": positives,
        "positive_count": len(positives),
        "required_positive_catalogs": required,
        "aggregate_weighted_rmse_improvement": aggregate_improvement,
        "aggregate_outcome": aggregate_outcome,
        "physical_helicity": "NOT_DEMONSTRATED",
        "dynamic_claim": "OUTSIDE_STATIC_CATALOG_PROTOCOL",
        "authority_ceiling": "NONE",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }


# ----------------------------- top-level gate ---------------------------------

def load_source(source: Mapping[str, Any], root: Path) -> tuple[EventCloud, dict[str, Any]]:
    path = root / str(source["relative_path"])
    parser = source["parser"]
    if parser == "GROWCLUST25":
        return parse_growclust25(path, str(source["catalog_id"])), {}
    if parser == "GROWCLUST25_TAR_GZ":
        return extract_growclust_from_tar(path, str(source["catalog_id"]))
    if parser == "HYPODD24":
        return parse_hypodd24(path, str(source["catalog_id"])), {}
    raise ValueError(f"unknown parser {parser}")


def run_gate(protocol_path: str | Path, data_root: str | Path, output_dir: str | Path) -> dict[str, Any]:
    protocol = json.loads(Path(protocol_path).read_text(encoding="utf-8"))
    data_root = Path(data_root)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    protocol_file_sha = sha256_file(protocol_path)
    protocol_sha = protocol_body_sha256(protocol)
    if protocol_sha != protocol["protocol_sha256"]:
        raise ValueError(f"protocol body hash mismatch: {protocol_sha} != {protocol['protocol_sha256']}")
    expected_id = f"h6p:{protocol_sha}"
    if protocol.get("protocol_id") != expected_id:
        raise ValueError(f"protocol id mismatch: {protocol.get('protocol_id')} != {expected_id}")

    unit_results: list[dict[str, Any]] = []
    acquisition_rows: list[dict[str, Any]] = []
    for source in protocol["sources"]:
        path = data_root / str(source["relative_path"])
        if not path.exists():
            acquisition_rows.append({"catalog_id": source["catalog_id"], "status": "MISSING", "path": str(path)})
            continue
        actual_sha = sha256_file(path)
        acquisition_rows.append({
            "catalog_id": source["catalog_id"],
            "status": "PRESENT",
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": actual_sha,
        })
        cloud, extraction = load_source(source, data_root)
        audit = audit_cloud(cloud)
        selected, selection = select_largest_eligible_cluster(
            cloud,
            int(protocol["unit_selection"]["minimum_cluster_events"]),
            int(protocol["unit_selection"]["maximum_events_per_unit"]),
        )
        try:
            evaluation = evaluate_unit_once(selected, protocol)
            stability = uncertainty_stability(selected, protocol, evaluation)
        except Exception as exc:
            evaluation = {"status": "FAILED", "error": f"{type(exc).__name__}: {exc}"}
            stability = {"status": "NOT_RUN"}
        unit_id = str(source["catalog_id"])
        unit = {
            "unit_id": unit_id,
            "source": source,
            "source_sha256": actual_sha,
            "audit": audit,
            "extraction": extraction,
            "selection": selection,
            "evaluation": evaluation,
            "uncertainty_stability": stability,
        }
        unit_results.append(unit)
        write_json(output / f"UNIT_{unit_id}.json", unit)

    if len(acquisition_rows) != len(protocol["sources"]) or any(row["status"] != "PRESENT" for row in acquisition_rows):
        result = {
            "format": "KCH_HELICAL_V0_6_GATE_RESULT",
            "version": "0.6.0",
            "protocol_sha256": protocol_sha,
            "protocol_file_sha256": protocol_file_sha,
            "outcome": "BLOCKED_EXACT_BYTE_ACQUISITION",
            "acquisition": acquisition_rows,
            "unit_results": unit_results,
            "authority_ceiling": "NONE",
        }
    else:
        adjudication = adjudicate_units(unit_results, protocol)
        body = {
            "format": "KCH_HELICAL_V0_6_GATE_RESULT",
            "version": "0.6.0",
            "protocol_id": protocol["protocol_id"],
            "protocol_sha256": protocol_sha,
            "protocol_file_sha256": protocol_file_sha,
            "executed_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "acquisition": acquisition_rows,
            "unit_results": unit_results,
            "adjudication": adjudication,
            "outcome": adjudication["aggregate_outcome"],
            "authority_ceiling": "NONE",
        }
        result = {"gate_result_id": content_id("v6g", body), **body}
    write_json(output / "V0_6_GATE_RESULT.json", result)
    return result


# ----------------------------- synthetic power -------------------------------

def wilson_interval(successes: int, trials: int, z: float = 1.959963984540054) -> dict[str, float]:
    if trials <= 0:
        return {"lower": 0.0, "upper": 1.0}
    p = successes / trials
    denom = 1.0 + z * z / trials
    center = (p + z * z / (2.0 * trials)) / denom
    half = z * math.sqrt(p * (1.0 - p) / trials + z * z / (4.0 * trials * trials)) / denom
    return {"lower": max(0.0, center - half), "upper": min(1.0, center + half)}



def synthetic_cloud(
    n: int,
    seed: int,
    effect_scale: float,
    *,
    null: bool = False,
    branches: int = 2,
) -> EventCloud:
    rng = np.random.default_rng(seed)
    t = np.sort(rng.uniform(0.0, 1.0, size=n))
    branch = rng.integers(0, branches, size=n)
    # Spatial support is deliberately independent of event time so the future-only split
    # tests repeated sampling of a cloud, not extrapolation along a material trajectory.
    s = rng.uniform(0.0, 12.0, size=n) + rng.normal(0.0, 0.15, size=n)
    xyz = np.zeros((n, 3), dtype=float)
    for b in range(branches):
        mask = branch == b
        sb = s[mask]
        # True branches are widely separated elongated ribbons; the GMM should model
        # branch topology, not split successive phases of the same helical tube.
        offset = (b - (branches - 1) / 2.0) * 7.0
        base_y = offset + 0.08 * sb + 0.018 * sb ** 2
        base_z = -0.35 * offset + 0.04 * sb - 0.012 * sb ** 2
        if null:
            hu = np.zeros_like(sb)
            hv = np.zeros_like(sb)
        else:
            # Exactly representable by the preregistered TWO_EQUAL family: a fixed
            # change point at the spatial midpoint, pitch change, and chirality flip.
            split = sb < 6.0
            phase1 = 2.0 * math.pi * sb / (3.5 + 0.3 * b)
            phase2 = 2.0 * math.pi * (sb - 6.0) / (2.2 + 0.2 * b)
            hu = effect_scale * np.where(split, np.cos(phase1), np.cos(phase2))
            hv = effect_scale * np.where(split, np.sin(phase1), -np.sin(phase2))
        xyz[mask, 0] = sb
        xyz[mask, 1] = base_y + hu + rng.normal(0.0, 0.35, size=np.sum(mask))
        xyz[mask, 2] = base_z + hv + rng.normal(0.0, 0.35, size=np.sum(mask))
    # Convert local xyz to synthetic lat/lon/depth.
    lat0, lon0, dep0 = 34.0, -117.0, 8.0
    lat = lat0 + np.degrees(xyz[:, 1] / EARTH_RADIUS_KM)
    lon = lon0 + np.degrees(xyz[:, 0] / (EARTH_RADIUS_KM * math.cos(math.radians(lat0))))
    dep = dep0 + xyz[:, 2]
    sigma = np.full(n, 0.03)
    return EventCloud(
        catalog_id=f"SYNTH_N{n}_E{effect_scale}_S{seed}",
        event_id=np.asarray([f"s{i}" for i in range(n)], dtype=str),
        timestamp_s=1_700_000_000.0 + t * 86400.0,
        latitude=lat,
        longitude=lon,
        depth_km=dep,
        sigma_x_km=sigma,
        sigma_y_km=sigma,
        sigma_z_km=sigma,
        cluster_id=np.asarray(["1"] * n, dtype=str),
        metadata={"synthetic": True, "effect_scale": effect_scale, "null": null, "branches": branches},
    )


def _power_pass(result: Mapping[str, Any], protocol: Mapping[str, Any]) -> bool:
    return bool(
        result.get("status") == "EVALUATED"
        and float(result["relative_rmse_improvement"]) >= float(protocol["decision"]["minimum_rmse_improvement"])
        and float(result["mean_nll_gain_per_event"]) >= float(protocol["decision"]["minimum_mean_nll_gain"])
        and float(result["fit_complexity"]["helix_minus_baseline_delta_bic"]) <= float(protocol["decision"]["maximum_fit_delta_bic"])
        and float(result["raw_circular_shift_p"]) <= float(protocol["decision"]["familywise_alpha"])
        and result["moving_block_bootstrap"].get("status") == "OK"
        and float(result["moving_block_bootstrap"].get("lower_95", -1.0)) > 0.0
        and float(result["support"]["test_support_fraction"]) >= float(protocol["support_overlap"]["minimum_fraction"])
    )


def run_power_analysis(protocol: Mapping[str, Any], output_path: str | Path) -> dict[str, Any]:
    contract = protocol["power_analysis"]
    rows: list[dict[str, Any]] = []
    for branches in contract.get("branch_scenarios", [1, 2]):
        for n in contract["sample_sizes"]:
            for effect in contract["effect_scales_km"]:
                for rep in range(int(contract["replicates_per_cell"])):
                    seed = (
                        int(contract["seed"])
                        + rep
                        + int(n) * 11
                        + int(effect * 1000) * 101
                        + int(branches) * 1_000_003
                    )
                    cloud = synthetic_cloud(
                        int(n), seed, float(effect), null=float(effect) == 0.0, branches=int(branches)
                    )
                    try:
                        result = evaluate_unit_once(cloud, protocol)
                        passed = _power_pass(result, protocol)
                        rows.append({
                            "branches": int(branches),
                            "n": int(n),
                            "effect_scale_km": float(effect),
                            "replicate": rep,
                            "status": result.get("status"),
                            "relative_rmse_improvement": result.get("relative_rmse_improvement"),
                            "mean_nll_gain_per_event": result.get("mean_nll_gain_per_event"),
                            "fit_delta_bic": result.get("fit_complexity", {}).get("helix_minus_baseline_delta_bic"),
                            "selected_branch_count": result.get("selected_configuration", {}).get("branch_count"),
                            "selected_baseline_family": result.get("selected_configuration", {}).get("baseline_family"),
                            "selected_segment_scheme": result.get("selected_configuration", {}).get("segment_scheme"),
                            "raw_p": result.get("raw_circular_shift_p"),
                            "bootstrap_lower_95": result.get("moving_block_bootstrap", {}).get("lower_95"),
                            "passed": bool(passed),
                        })
                    except Exception as exc:
                        rows.append({
                            "branches": int(branches),
                            "n": int(n),
                            "effect_scale_km": float(effect),
                            "replicate": rep,
                            "status": "FAILED",
                            "error": f"{type(exc).__name__}: {exc}",
                            "passed": False,
                        })
    cells: list[dict[str, Any]] = []
    for branches in contract.get("branch_scenarios", [1, 2]):
        for n in contract["sample_sizes"]:
            for effect in contract["effect_scales_km"]:
                cell = [
                    r for r in rows
                    if r["branches"] == int(branches)
                    and r["n"] == int(n)
                    and r["effect_scale_km"] == float(effect)
                ]
                valid_improvements = [
                    float(r["relative_rmse_improvement"])
                    for r in cell if r.get("relative_rmse_improvement") is not None
                ]
                cells.append({
                    "branches": int(branches),
                    "n": int(n),
                    "effect_scale_km": float(effect),
                    "replicates": len(cell),
                    "valid": sum(r["status"] == "EVALUATED" for r in cell),
                    "pass_rate": float(np.mean([r["passed"] for r in cell])) if cell else None,
                    "median_rmse_improvement": float(np.median(valid_improvements)) if valid_improvements else None,
                    "median_fit_delta_bic": float(np.median([
                        float(r["fit_delta_bic"]) for r in cell if r.get("fit_delta_bic") is not None
                    ])) if any(r.get("fit_delta_bic") is not None for r in cell) else None,
                })
    null_cells = [c for c in cells if c["effect_scale_km"] == 0.0]
    nonnull_cells = [c for c in cells if c["effect_scale_km"] > 0.0]
    summary = {
        "format": "KCH_HELICAL_V0_6_POWER_ANALYSIS",
        "contract": contract,
        "decision_thresholds": protocol["decision"],
        "cells": cells,
        "rows": rows,
        "max_false_positive_rate": max(float(c["pass_rate"]) for c in null_cells) if null_cells else None,
        "power_cells_ge_0_8": [c for c in nonnull_cells if float(c["pass_rate"]) >= 0.8],
    }
    write_json(output_path, summary)
    return summary


# ----------------------------- CLI -------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="KCH Helical Lift v0.6 local/piecewise gate")
    sub = parser.add_subparsers(dest="command", required=True)
    gate = sub.add_parser("run-gate")
    gate.add_argument("--protocol", required=True)
    gate.add_argument("--data-root", required=True)
    gate.add_argument("--output-dir", required=True)
    power = sub.add_parser("power")
    power.add_argument("--protocol", required=True)
    power.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "run-gate":
        result = run_gate(args.protocol, args.data_root, args.output_dir)
        print(json.dumps({"outcome": result["outcome"], "gate_result_id": result.get("gate_result_id")}, indent=2))
    elif args.command == "power":
        protocol = json.loads(Path(args.protocol).read_text(encoding="utf-8"))
        result = run_power_analysis(protocol, args.output)
        print(json.dumps({"max_false_positive_rate": result["max_false_positive_rate"], "power_cells_ge_0_8": result["power_cells_ge_0_8"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
