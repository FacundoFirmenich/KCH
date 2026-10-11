"""KCH Helical v0.16 explicit null/perturbation operators.

This module is a new, explicit successor to the partial historical runtime recovered
in v0.15.4.  It does not claim byte or semantic identity with the missing v0.8.4
runtime.  It fixes the operator algebra required by the frozen v0.13 contract and
is intentionally free of file, network, process, database, and pickle access.

All public numerical outputs are IEEE-754 float64 or signed int64 and must be
finite.  Missing or malformed inputs fail closed; there is no imputation.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np
import numpy.typing as npt

PROTOCOL_ID = "h8p:99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f"
RUNTIME_CONTRACT_ID = "h13nullspec:bc68343eee99c797c27795b9c5e73b7bec63764f678ab4c195572281acf79dff"
OPERATOR_VERSION = "0.16.0"


class OperatorContractError(ValueError):
    """Fail-closed contract violation."""


@dataclass(frozen=True)
class ParentState:
    child_index: npt.NDArray[np.int64]
    parent_index: npt.NDArray[np.int64]
    edge_intensity: npt.NDArray[np.float64]
    edge_probability: npt.NDArray[np.float64]
    child_intensity: npt.NDArray[np.float64]
    background_probability: npt.NDArray[np.float64]


@dataclass(frozen=True)
class RewireResult:
    parent_index: npt.NDArray[np.int64]
    child_index: npt.NDArray[np.int64]
    weight: npt.NDArray[np.float64]
    diagnostics: Mapping[str, Any]


@dataclass(frozen=True)
class SimulationResult:
    time_days: npt.NDArray[np.float64]
    magnitude: npt.NDArray[np.float64]
    node_index: npt.NDArray[np.int64]
    parent_index: npt.NDArray[np.int64]
    diagnostics: Mapping[str, Any]


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _as_float64(name: str, value: Any, *, ndim: int | None = None) -> npt.NDArray[np.float64]:
    arr = np.asarray(value, dtype=np.float64)
    if ndim is not None and arr.ndim != ndim:
        raise OperatorContractError(f"{name} must have ndim={ndim}, got {arr.ndim}")
    if not np.all(np.isfinite(arr)):
        raise OperatorContractError(f"{name} contains non-finite values")
    return arr


def _as_int64(name: str, value: Any, *, ndim: int | None = None) -> npt.NDArray[np.int64]:
    raw = np.asarray(value)
    if ndim is not None and raw.ndim != ndim:
        raise OperatorContractError(f"{name} must have ndim={ndim}, got {raw.ndim}")
    if raw.dtype.kind not in "iu":
        if raw.dtype.kind == "f" and np.all(np.isfinite(raw)) and np.all(raw == np.floor(raw)):
            raw = raw.astype(np.int64)
        else:
            raise OperatorContractError(f"{name} must be integral")
    return raw.astype(np.int64, copy=False)


def _as_object_1d(name: str, value: Any) -> npt.NDArray[np.object_]:
    arr = np.asarray(value, dtype=object)
    if arr.ndim != 1:
        raise OperatorContractError(f"{name} must be one-dimensional")
    if any(item is None for item in arr.tolist()):
        raise OperatorContractError(f"{name} contains missing values")
    return arr


def _same_length(**arrays: npt.NDArray[Any]) -> int:
    lengths = {name: int(len(arr)) for name, arr in arrays.items()}
    if not lengths:
        return 0
    unique = set(lengths.values())
    if len(unique) != 1:
        raise OperatorContractError(f"length mismatch: {lengths}")
    return next(iter(unique))


def _scalar_or_array(value: npt.NDArray[np.float64]) -> float | npt.NDArray[np.float64]:
    return float(value) if value.ndim == 0 else value


def _normalize_unsigned_degrees(value: Any) -> npt.NDArray[np.float64]:
    arr = _as_float64("angle", value)
    return np.mod(arr, 360.0).astype(np.float64, copy=False)


def _normalize_signed_degrees(value: Any) -> npt.NDArray[np.float64]:
    arr = _as_float64("angle", value)
    return (np.mod(arr + 180.0, 360.0) - 180.0).astype(np.float64, copy=False)


def _fold_dip_degrees(value: Any) -> npt.NDArray[np.float64]:
    arr = _as_float64("dip", value)
    folded = np.mod(arr, 180.0)
    folded = np.where(folded > 90.0, 180.0 - folded, folded)
    return folded.astype(np.float64, copy=False)


def seeded_rng(namespace: str, seed: int, *, protocol_id: str = PROTOCOL_ID) -> np.random.Generator:
    """Return a content-addressed PCG64DXSM generator.

    The derived seed is independent of process hash state, worker count, and job
    ordering.  Exact bitwise reproducibility is scoped to NumPy 2.1.3, frozen by
    the qualification workflow.
    """
    if not isinstance(namespace, str) or not namespace.strip():
        raise OperatorContractError("namespace must be a non-empty string")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise OperatorContractError("seed must be an integer")
    body = {
        "namespace": namespace,
        "operator_version": OPERATOR_VERSION,
        "protocol_id": protocol_id,
        "root_seed": int(seed),
    }
    digest = hashlib.sha256(_canonical_bytes(body)).digest()
    derived = int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)
    return np.random.Generator(np.random.PCG64DXSM(derived))


def circular_distance_degrees(a: Any, b: Any, period: float = 360.0) -> float | npt.NDArray[np.float64]:
    """Absolute minimal circular distance in [0, period/2]."""
    if not math.isfinite(period) or period <= 0.0:
        raise OperatorContractError("period must be finite and positive")
    aa = _as_float64("a", a)
    bb = _as_float64("b", b)
    delta = np.mod(aa - bb + period / 2.0, period) - period / 2.0
    out = np.abs(delta).astype(np.float64, copy=False)
    return _scalar_or_array(out)


def head_to_normal(head_degrees: Any) -> npt.NDArray[np.float64]:
    """Map azimuthal headings to right-hand horizontal unit normals.

    Convention: x=east, y=north, azimuth clockwise from north.  A northward
    heading therefore has an eastward right normal.
    """
    head = _normalize_unsigned_degrees(head_degrees)
    radians = np.deg2rad(head)
    normal = np.stack((np.cos(radians), -np.sin(radians)), axis=-1).astype(np.float64)
    if not np.all(np.isfinite(normal)):
        raise OperatorContractError("head_to_normal generated non-finite values")
    return normal


def reflected_rake(rake_degrees: Any) -> float | npt.NDArray[np.float64]:
    """Parity reflection in the local fault frame: signed rake -> -signed rake."""
    out = _normalize_signed_degrees(-_as_float64("rake_degrees", rake_degrees))
    return _scalar_or_array(out)


def _mechanism_marks(strike: Any, dip: Any, rake: Any) -> npt.NDArray[np.float64]:
    s = np.deg2rad(_normalize_unsigned_degrees(strike))
    d = np.deg2rad(_fold_dip_degrees(dip))
    r = np.deg2rad(_normalize_signed_degrees(rake))
    s, d, r = np.broadcast_arrays(s, d, r)
    marks = np.stack(
        (
            np.cos(2.0 * s),
            np.sin(2.0 * s),
            np.cos(d),
            np.sin(d),
            np.cos(r),
            np.sin(r),
            np.sin(d) * np.sin(r),
        ),
        axis=-1,
    ).astype(np.float64)
    if not np.all(np.isfinite(marks)):
        raise OperatorContractError("mechanism marks are non-finite")
    return marks


def propagate_mechanism_uncertainty(
    strike_degrees: Any,
    dip_degrees: Any,
    rake_degrees: Any,
    strike_sigma_degrees: Any,
    dip_sigma_degrees: Any,
    rake_sigma_degrees: Any,
    *,
    replicates: int,
    namespace: str,
    seed: int,
) -> Mapping[str, Any]:
    """Generate deterministic posterior mechanism draws without imputation."""
    if isinstance(replicates, bool) or not isinstance(replicates, int) or replicates <= 0:
        raise OperatorContractError("replicates must be a positive integer")
    strike = _as_float64("strike_degrees", strike_degrees, ndim=1)
    dip = _as_float64("dip_degrees", dip_degrees, ndim=1)
    rake = _as_float64("rake_degrees", rake_degrees, ndim=1)
    ss = _as_float64("strike_sigma_degrees", strike_sigma_degrees, ndim=1)
    ds = _as_float64("dip_sigma_degrees", dip_sigma_degrees, ndim=1)
    rs = _as_float64("rake_sigma_degrees", rake_sigma_degrees, ndim=1)
    n = _same_length(strike=strike, dip=dip, rake=rake, strike_sigma=ss, dip_sigma=ds, rake_sigma=rs)
    if np.any(ss < 0.0) or np.any(ds < 0.0) or np.any(rs < 0.0):
        raise OperatorContractError("uncertainty scales must be non-negative")
    rng = seeded_rng(namespace, seed)
    strike_draws = np.mod(rng.normal(strike, ss, size=(replicates, n)), 360.0).astype(np.float64)
    dip_draws = _fold_dip_degrees(rng.normal(dip, ds, size=(replicates, n)))
    rake_draws = _normalize_signed_degrees(rng.normal(rake, rs, size=(replicates, n)))
    for name, arr in (("strike_draws", strike_draws), ("dip_draws", dip_draws), ("rake_draws", rake_draws)):
        if not np.all(np.isfinite(arr)):
            raise OperatorContractError(f"{name} is non-finite")
    return {
        "strike_draws": strike_draws,
        "dip_draws": dip_draws,
        "rake_draws": rake_draws,
        "replicates": int(replicates),
        "event_count": int(n),
        "namespace": namespace,
    }


def posterior_mark_expectations(
    strike_degrees: Any,
    dip_degrees: Any,
    rake_degrees: Any,
    strike_sigma_degrees: Any,
    dip_sigma_degrees: Any,
    rake_sigma_degrees: Any,
    *,
    draws: int,
    namespace: str,
    seed: int,
) -> Mapping[str, Any]:
    """Posterior means/variances for axial and signed mechanism marks."""
    propagated = propagate_mechanism_uncertainty(
        strike_degrees,
        dip_degrees,
        rake_degrees,
        strike_sigma_degrees,
        dip_sigma_degrees,
        rake_sigma_degrees,
        replicates=draws,
        namespace=namespace,
        seed=seed,
    )
    marks = _mechanism_marks(
        propagated["strike_draws"],
        propagated["dip_draws"],
        propagated["rake_draws"],
    )
    mean = np.mean(marks, axis=0, dtype=np.float64)
    variance = np.var(marks, axis=0, ddof=0, dtype=np.float64)
    axial_angle = np.mod(0.5 * np.rad2deg(np.arctan2(mean[:, 1], mean[:, 0])), 180.0).astype(np.float64)
    return {
        "mean_mark": mean,
        "variance_mark": variance,
        "axial_angle_degrees": axial_angle,
        "signed_chirality_mean": mean[:, 6].copy(),
        "draw_count": int(draws),
        "event_count": int(mean.shape[0]),
    }


def permute_within_bins(
    marks: Any,
    cohort: Sequence[Any],
    fault_component_id: Sequence[Any],
    time_days: Any,
    magnitude: Any,
    quality_label: Sequence[Any],
    *,
    rng: np.random.Generator,
) -> tuple[npt.NDArray[np.float64], Mapping[str, Any]]:
    """Permute mark rows only inside the exact v0.13 frozen strata."""
    mark = _as_float64("marks", marks, ndim=2)
    cohorts = _as_object_1d("cohort", cohort)
    components = _as_object_1d("fault_component_id", fault_component_id)
    times = _as_float64("time_days", time_days, ndim=1)
    mags = _as_float64("magnitude", magnitude, ndim=1)
    quality = _as_object_1d("quality_label", quality_label)
    n = _same_length(mark=mark, cohort=cohorts, component=components, time=times, magnitude=mags, quality=quality)
    if not isinstance(rng, np.random.Generator):
        raise OperatorContractError("rng must be numpy.random.Generator")
    strata: dict[tuple[Any, ...], list[int]] = defaultdict(list)
    for i in range(n):
        key = (
            str(cohorts[i]),
            str(components[i]),
            int(math.floor(times[i] / 30.0)),
            int(math.floor(mags[i] / 0.5)),
            str(quality[i]),
        )
        strata[key].append(i)
    out = mark.copy()
    singleton_count = 0
    permuted_count = 0
    for key in sorted(strata, key=lambda item: tuple(map(str, item))):
        idx = np.asarray(strata[key], dtype=np.int64)
        if len(idx) == 1:
            singleton_count += 1
            continue
        perm = rng.permutation(idx)
        out[idx] = mark[perm]
        permuted_count += len(idx)
    return out, {
        "event_count": n,
        "stratum_count": len(strata),
        "singleton_stratum_count": singleton_count,
        "permuted_event_count": permuted_count,
        "marks_only_permuted": True,
    }


def static_logodds(positive_count: Any, total_count: Any, *, alpha: float = 0.5) -> float | npt.NDArray[np.float64]:
    """Jeffreys-smoothed Bernoulli log-odds for static-field diagnostics."""
    pos = _as_float64("positive_count", positive_count)
    total = _as_float64("total_count", total_count)
    if not math.isfinite(alpha) or alpha <= 0.0:
        raise OperatorContractError("alpha must be finite and positive")
    if np.any(pos < 0.0) or np.any(total < 0.0) or np.any(pos > total):
        raise OperatorContractError("counts violate 0 <= positive <= total")
    odds = (pos + alpha) / (total - pos + alpha)
    out = np.log(odds).astype(np.float64, copy=False)
    return _scalar_or_array(out)


def draw_static_fields(
    source_marks: Any,
    source_node: Sequence[Any],
    source_component: Sequence[Any],
    source_cohort: Sequence[Any],
    source_magnitude: Any,
    source_quality: Sequence[Any],
    query_node: Sequence[Any],
    query_component: Sequence[Any],
    query_cohort: Sequence[Any],
    query_magnitude: Any,
    query_quality: Sequence[Any],
    *,
    rng: np.random.Generator,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.int64], Mapping[str, Any]]:
    """Draw marks from node→component→cohort empirical static fields.

    Backoff levels: 0=node+mag+quality, 1=component+mag+quality,
    2=cohort+mag+quality, 3=cohort.  Empty cohort pools fail closed.
    """
    marks = _as_float64("source_marks", source_marks, ndim=2)
    s_node = _as_object_1d("source_node", source_node)
    s_comp = _as_object_1d("source_component", source_component)
    s_cohort = _as_object_1d("source_cohort", source_cohort)
    s_mag = _as_float64("source_magnitude", source_magnitude, ndim=1)
    s_quality = _as_object_1d("source_quality", source_quality)
    _same_length(marks=marks, node=s_node, component=s_comp, cohort=s_cohort, magnitude=s_mag, quality=s_quality)
    q_node = _as_object_1d("query_node", query_node)
    q_comp = _as_object_1d("query_component", query_component)
    q_cohort = _as_object_1d("query_cohort", query_cohort)
    q_mag = _as_float64("query_magnitude", query_magnitude, ndim=1)
    q_quality = _as_object_1d("query_quality", query_quality)
    qn = _same_length(node=q_node, component=q_comp, cohort=q_cohort, magnitude=q_mag, quality=q_quality)
    if not isinstance(rng, np.random.Generator):
        raise OperatorContractError("rng must be numpy.random.Generator")

    level0: dict[tuple[str, int, str], list[int]] = defaultdict(list)
    level1: dict[tuple[str, int, str], list[int]] = defaultdict(list)
    level2: dict[tuple[str, int, str], list[int]] = defaultdict(list)
    level3: dict[str, list[int]] = defaultdict(list)
    for i in range(len(marks)):
        mb = int(math.floor(s_mag[i] / 0.5))
        q = str(s_quality[i]); cohort = str(s_cohort[i])
        level0[(cohort, str(s_node[i]), mb, q)].append(i)
        level1[(cohort, str(s_comp[i]), mb, q)].append(i)
        level2[(cohort, mb, q)].append(i)
        level3[cohort].append(i)

    out = np.empty((qn, marks.shape[1]), dtype=np.float64)
    backoff = np.empty(qn, dtype=np.int64)
    counts = [0, 0, 0, 0]
    for i in range(qn):
        mb = int(math.floor(q_mag[i] / 0.5)); q = str(q_quality[i]); cohort = str(q_cohort[i])
        pools = (
            level0.get((cohort, str(q_node[i]), mb, q), []),
            level1.get((cohort, str(q_comp[i]), mb, q), []),
            level2.get((cohort, mb, q), []),
            level3.get(cohort, []),
        )
        chosen: list[int] | None = None
        level = -1
        for candidate_level, pool in enumerate(pools):
            if pool:
                chosen = pool; level = candidate_level; break
        if chosen is None:
            raise OperatorContractError(f"no static-field pool for cohort={cohort!r}")
        index = chosen[int(rng.integers(0, len(chosen)))]
        out[i] = marks[index]
        backoff[i] = level
        counts[level] += 1
    return out, backoff, {
        "query_count": qn,
        "backoff_counts": {str(i): counts[i] for i in range(4)},
        "maximum_backoff_level": int(np.max(backoff)) if qn else -1,
    }


def eval_intensity(
    parent_time_days: Any,
    child_time_days: Any,
    parent_magnitude: Any,
    network_distance_km: Any,
    parameters: Mapping[str, float],
) -> npt.NDArray[np.float64]:
    """Evaluate the locked positive ETAS/Hawkes edge kernel without refitting."""
    pt = _as_float64("parent_time_days", parent_time_days, ndim=1)
    ct = _as_float64("child_time_days", child_time_days, ndim=1)
    mag = _as_float64("parent_magnitude", parent_magnitude, ndim=1)
    dist = _as_float64("network_distance_km", network_distance_km, ndim=1)
    _same_length(parent_time=pt, child_time=ct, magnitude=mag, distance=dist)
    required = ("productivity", "magnitude_scaling", "c_days", "p", "network_scale_km")
    if any(key not in parameters for key in required):
        raise OperatorContractError(f"parameters must contain {required}")
    k = float(parameters["productivity"]); alpha = float(parameters["magnitude_scaling"])
    c = float(parameters["c_days"]); p = float(parameters["p"]); scale = float(parameters["network_scale_km"])
    mref = float(parameters.get("magnitude_reference", 0.0))
    if not all(math.isfinite(x) for x in (k, alpha, c, p, scale, mref)):
        raise OperatorContractError("parameters must be finite")
    if k <= 0.0 or c <= 0.0 or p <= 1.0 or scale <= 0.0:
        raise OperatorContractError("invalid ETAS/Hawkes parameter domain")
    dt = ct - pt
    if np.any(dt <= 0.0) or np.any(dist < 0.0):
        raise OperatorContractError("parent must precede child and distance must be non-negative")
    exponent = np.clip(alpha * (mag - mref), -700.0, 700.0)
    temporal = (p - 1.0) * (c ** (p - 1.0)) * np.power(dt + c, -p)
    spatial = np.exp(-dist / scale) / scale
    out = (k * np.exp(exponent) * temporal * spatial).astype(np.float64)
    if np.any(out <= 0.0) or not np.all(np.isfinite(out)):
        raise OperatorContractError("edge intensity is not finite and strictly positive")
    return out


def compute_parent_state(
    event_time_days: Any,
    event_magnitude: Any,
    child_index: Any,
    parent_index: Any,
    network_distance_km: Any,
    parameters: Mapping[str, float],
    *,
    background_rate: float | Sequence[float] | npt.NDArray[np.float64] | None = None,
) -> ParentState:
    """Compute normalized fixed-parent probabilities from a locked graph."""
    times = _as_float64("event_time_days", event_time_days, ndim=1)
    mags = _as_float64("event_magnitude", event_magnitude, ndim=1)
    if len(times) != len(mags):
        raise OperatorContractError("event time/magnitude length mismatch")
    child = _as_int64("child_index", child_index, ndim=1)
    parent = _as_int64("parent_index", parent_index, ndim=1)
    distance = _as_float64("network_distance_km", network_distance_km, ndim=1)
    _same_length(child=child, parent=parent, distance=distance)
    n = len(times)
    if np.any(child < 0) or np.any(parent < 0) or np.any(child >= n) or np.any(parent >= n):
        raise OperatorContractError("edge index out of range")
    if np.any(parent == child):
        raise OperatorContractError("self edges are forbidden")
    if len({(int(p), int(c)) for p, c in zip(parent, child, strict=True)}) != len(parent):
        raise OperatorContractError("duplicate parent-child edges are forbidden")
    edge = eval_intensity(times[parent], times[child], mags[parent], distance, parameters)
    if background_rate is None:
        background_rate = float(parameters.get("background_rate_per_day", math.nan))
    bg = np.asarray(background_rate, dtype=np.float64)
    if bg.ndim == 0:
        bg = np.full(n, float(bg), dtype=np.float64)
    if bg.shape != (n,) or not np.all(np.isfinite(bg)) or np.any(bg <= 0.0):
        raise OperatorContractError("background rate must be positive scalar or length-N vector")
    total = bg.copy()
    np.add.at(total, child, edge)
    edge_prob = edge / total[child]
    background_prob = bg / total
    if not np.all(np.isfinite(edge_prob)) or not np.all(np.isfinite(background_prob)):
        raise OperatorContractError("parent probabilities are non-finite")
    return ParentState(child, parent, edge, edge_prob.astype(np.float64), total, background_prob.astype(np.float64))


def _weight_deciles(weight: npt.NDArray[np.float64]) -> npt.NDArray[np.int64]:
    if len(weight) == 0:
        return np.empty(0, dtype=np.int64)
    # Value-based quantile cuts keep tied weights in the same decile.  A
    # rank-only assignment would arbitrarily split exact ties and could make a
    # rewiring stratum appear non-mixable even when every edge has equal weight.
    cuts = np.quantile(weight, np.arange(1, 10, dtype=np.float64) / 10.0, method="linear")
    return np.searchsorted(cuts, weight, side="left").astype(np.int64)


def rewire_parent_graph(
    parent_index: Any,
    child_index: Any,
    weight: Any,
    event_time_days: Any,
    edge_cohort: Sequence[Any],
    *,
    rng: np.random.Generator,
    candidate_allowed: set[tuple[int, int]] | Callable[[int, int], bool] | None = None,
    target_successful_swaps_per_edge: float = 10.0,
    minimum_successful_swaps_per_edge: float = 5.0,
    maximum_proposals_per_edge: int = 100,
) -> RewireResult:
    """Directed double-edge swaps within cohort and weight decile.

    Mixing is measured as successful edge participations / input edge count;
    every accepted swap contributes two participations.
    """
    parent = _as_int64("parent_index", parent_index, ndim=1).copy()
    child = _as_int64("child_index", child_index, ndim=1).copy()
    weights = _as_float64("weight", weight, ndim=1).copy()
    times = _as_float64("event_time_days", event_time_days, ndim=1)
    cohorts = _as_object_1d("edge_cohort", edge_cohort)
    m = _same_length(parent=parent, child=child, weight=weights, cohort=cohorts)
    if m < 2:
        raise OperatorContractError("at least two edges are required")
    if not isinstance(rng, np.random.Generator):
        raise OperatorContractError("rng must be numpy.random.Generator")
    if np.any(parent < 0) or np.any(child < 0) or np.any(parent >= len(times)) or np.any(child >= len(times)):
        raise OperatorContractError("edge index out of range")
    if np.any(parent == child) or np.any(times[parent] >= times[child]):
        raise OperatorContractError("input graph violates directed temporal contract")
    if np.any(weights <= 0.0):
        raise OperatorContractError("weights must be positive")
    if maximum_proposals_per_edge <= 0 or target_successful_swaps_per_edge <= 0.0 or minimum_successful_swaps_per_edge < 0.0:
        raise OperatorContractError("invalid mixing controls")
    if minimum_successful_swaps_per_edge > target_successful_swaps_per_edge:
        raise OperatorContractError("minimum mixing exceeds target")

    decile = _weight_deciles(weights)
    groups: dict[tuple[str, int], list[int]] = defaultdict(list)
    for i in range(m):
        groups[(str(cohorts[i]), int(decile[i]))].append(i)
    eligible_groups = [np.asarray(v, dtype=np.int64) for _, v in sorted(groups.items()) if len(v) >= 2]
    if not eligible_groups:
        raise OperatorContractError("no cohort/weight-decile group supports rewiring")

    edge_set = {(int(p), int(c)) for p, c in zip(parent, child, strict=True)}
    initial_edge_set = set(edge_set)
    target_swaps = int(math.ceil(target_successful_swaps_per_edge * m / 2.0))
    minimum_swaps = int(math.ceil(minimum_successful_swaps_per_edge * m / 2.0))
    maximum_proposals = int(maximum_proposals_per_edge * m)
    successful = 0; proposals = 0

    def allowed(p: int, c: int) -> bool:
        if candidate_allowed is None:
            return True
        if callable(candidate_allowed):
            return bool(candidate_allowed(p, c))
        return (p, c) in candidate_allowed

    while successful < target_swaps and proposals < maximum_proposals:
        group = eligible_groups[int(rng.integers(0, len(eligible_groups)))]
        pick = rng.choice(group, size=2, replace=False)
        e1, e2 = int(pick[0]), int(pick[1]); proposals += 1
        p1, c1 = int(parent[e1]), int(child[e1]); p2, c2 = int(parent[e2]), int(child[e2])
        n1, n2 = (p1, c2), (p2, c1)
        if n1 == (p1, c1) or n2 == (p2, c2) or n1 == n2:
            continue
        if p1 == c2 or p2 == c1 or times[p1] >= times[c2] or times[p2] >= times[c1]:
            continue
        if not allowed(*n1) or not allowed(*n2):
            continue
        old1, old2 = (p1, c1), (p2, c2)
        if {n1, n2} == {old1, old2}:
            continue
        reduced = edge_set - {old1, old2}
        if n1 in reduced or n2 in reduced:
            continue
        edge_set = reduced | {n1, n2}
        child[e1], child[e2] = c2, c1
        successful += 1

    mixing = 2.0 * successful / m
    net_changed_fraction = len(initial_edge_set.symmetric_difference(edge_set)) / (2.0 * m)
    if successful < minimum_swaps or net_changed_fraction <= 0.0:
        raise OperatorContractError(
            "rewiring mixing floor not reached: "
            f"accepted_participations_per_edge={mixing:.6f}, "
            f"minimum={minimum_successful_swaps_per_edge:.6f}, "
            f"net_changed_fraction={net_changed_fraction:.6f}"
        )
    return RewireResult(
        parent,
        child,
        weights,
        {
            "edge_count": m,
            "proposal_count": proposals,
            "successful_swap_count": successful,
            "successful_edge_participations_per_edge": mixing,
            "target_reached": successful >= target_swaps,
            "minimum_reached": successful >= minimum_swaps,
            "net_changed_edge_fraction": net_changed_fraction,
            "in_degree_preserved": True,
            "out_degree_preserved": True,
            "weight_multiset_preserved": True,
        },
    )


def make_rewired_null(
    parent_state: ParentState,
    event_time_days: Any,
    edge_cohort: Sequence[Any],
    *,
    namespace: str,
    seed: int,
    candidate_allowed: set[tuple[int, int]] | Callable[[int, int], bool] | None = None,
    target_successful_swaps_per_edge: float = 10.0,
    minimum_successful_swaps_per_edge: float = 5.0,
    maximum_proposals_per_edge: int = 100,
) -> RewireResult:
    """Content-addressed wrapper for the frozen parent-edge rewiring null."""
    return rewire_parent_graph(
        parent_state.parent_index,
        parent_state.child_index,
        parent_state.edge_intensity,
        event_time_days,
        edge_cohort,
        rng=seeded_rng(namespace, seed),
        candidate_allowed=candidate_allowed,
        target_successful_swaps_per_edge=target_successful_swaps_per_edge,
        minimum_successful_swaps_per_edge=minimum_successful_swaps_per_edge,
        maximum_proposals_per_edge=maximum_proposals_per_edge,
    )


def _sample_omori_delay(rng: np.random.Generator, c: float, p: float, horizon: float) -> float:
    if horizon <= 0.0:
        return math.inf
    u = float(rng.random())
    a = c ** (1.0 - p)
    b = (horizon + c) ** (1.0 - p)
    value = a + u * (b - a)
    return float(value ** (1.0 / (1.0 - p)) - c)


def simulate_catalog(
    *,
    duration_days: float,
    parameters: Mapping[str, float],
    empirical_magnitudes: Any,
    network_nodes: Sequence[Any],
    transition_matrix: Any | None,
    namespace: str,
    seed: int,
    maximum_events: int = 1_000_000,
) -> SimulationResult:
    """Branching-process simulation from locked ETAS/Hawkes parameters.

    No parameter is estimated or updated.  Magnitudes are resampled from the
    supplied empirical distribution; node support is fixed by network_nodes.
    """
    if not math.isfinite(duration_days) or duration_days <= 0.0:
        raise OperatorContractError("duration_days must be finite and positive")
    mags = _as_float64("empirical_magnitudes", empirical_magnitudes, ndim=1)
    if len(mags) == 0:
        raise OperatorContractError("empirical_magnitudes must be nonempty")
    nodes = _as_object_1d("network_nodes", network_nodes)
    if len(nodes) == 0:
        raise OperatorContractError("network_nodes must be nonempty")
    if isinstance(maximum_events, bool) or maximum_events <= 0:
        raise OperatorContractError("maximum_events must be positive")
    required = ("background_rate_per_day", "branching_ratio", "c_days", "p", "magnitude_scaling")
    if any(key not in parameters for key in required):
        raise OperatorContractError(f"simulation parameters must contain {required}")
    mu = float(parameters["background_rate_per_day"]); eta = float(parameters["branching_ratio"])
    c = float(parameters["c_days"]); p = float(parameters["p"]); alpha = float(parameters["magnitude_scaling"])
    if not all(math.isfinite(x) for x in (mu, eta, c, p, alpha)):
        raise OperatorContractError("simulation parameters must be finite")
    if mu <= 0.0 or not (0.0 <= eta < 1.0) or c <= 0.0 or p <= 1.0:
        raise OperatorContractError("simulation parameters outside stable domain")

    if transition_matrix is None:
        trans = np.full((len(nodes), len(nodes)), 1.0 / len(nodes), dtype=np.float64)
    else:
        trans = _as_float64("transition_matrix", transition_matrix, ndim=2)
        if trans.shape != (len(nodes), len(nodes)) or np.any(trans < 0.0):
            raise OperatorContractError("transition_matrix has invalid shape/domain")
        row_sum = np.sum(trans, axis=1)
        if np.any(row_sum <= 0.0):
            raise OperatorContractError("transition_matrix contains empty rows")
        trans = trans / row_sum[:, None]

    rng = seeded_rng(namespace, seed)
    immigrant_count = int(rng.poisson(mu * duration_days))
    events: list[dict[str, Any]] = []
    for _ in range(immigrant_count):
        events.append({
            "id": len(events),
            "time": float(rng.uniform(0.0, duration_days)),
            "magnitude": float(mags[int(rng.integers(0, len(mags)))]),
            "node": int(rng.integers(0, len(nodes))),
            "parent_id": -1,
        })
    events.sort(key=lambda row: (row["time"], row["id"]))
    for new_id, row in enumerate(events): row["id"] = new_id

    mean_factor = float(np.mean(np.exp(np.clip(alpha * (mags - np.mean(mags)), -50.0, 50.0))))
    cursor = 0
    while cursor < len(events):
        parent = events[cursor]; cursor += 1
        factor = math.exp(max(-50.0, min(50.0, alpha * (parent["magnitude"] - float(np.mean(mags)))))) / mean_factor
        count = int(rng.poisson(eta * factor))
        for _ in range(count):
            remaining = duration_days - parent["time"]
            delay = _sample_omori_delay(rng, c, p, remaining)
            child_time = parent["time"] + delay
            if not math.isfinite(delay) or child_time > duration_days:
                continue
            if len(events) >= maximum_events:
                raise OperatorContractError("simulation exceeded maximum_events")
            node = int(rng.choice(len(nodes), p=trans[parent["node"]]))
            events.append({
                "id": len(events),
                "time": child_time,
                "magnitude": float(mags[int(rng.integers(0, len(mags)))]),
                "node": node,
                "parent_id": parent["id"],
            })

    order = sorted(range(len(events)), key=lambda i: (events[i]["time"], events[i]["id"]))
    old_to_new = {events[old]["id"]: new for new, old in enumerate(order)}
    time = np.asarray([events[i]["time"] for i in order], dtype=np.float64)
    magnitude = np.asarray([events[i]["magnitude"] for i in order], dtype=np.float64)
    node = np.asarray([events[i]["node"] for i in order], dtype=np.int64)
    parent = np.asarray([
        -1 if events[i]["parent_id"] < 0 else old_to_new[events[i]["parent_id"]]
        for i in order
    ], dtype=np.int64)
    if len(time) and (not np.all(np.diff(time) >= 0.0) or not np.all(np.isfinite(time))):
        raise OperatorContractError("simulation ordering/finite invariant failed")
    return SimulationResult(
        time,
        magnitude,
        node,
        parent,
        {
            "event_count": int(len(time)),
            "immigrant_count": immigrant_count,
            "parameter_update_performed": False,
            "signed_twist_parameter": 0.0,
        },
    )


def simulate_nonhelical_fixed_parent_weights(
    parent_state: ParentState,
    source_marks: Any,
    source_node: Sequence[Any],
    source_component: Sequence[Any],
    source_cohort: Sequence[Any],
    source_magnitude: Any,
    source_quality: Sequence[Any],
    child_node: Sequence[Any],
    child_component: Sequence[Any],
    child_cohort: Sequence[Any],
    child_magnitude: Any,
    child_quality: Sequence[Any],
    *,
    namespace: str,
    seed: int,
) -> Mapping[str, Any]:
    """Draw child marks from a static field while retaining fixed parent weights."""
    marks, backoff, diagnostics = draw_static_fields(
        source_marks,
        source_node,
        source_component,
        source_cohort,
        source_magnitude,
        source_quality,
        child_node,
        child_component,
        child_cohort,
        child_magnitude,
        child_quality,
        rng=seeded_rng(namespace, seed),
    )
    return {
        "child_marks": marks,
        "backoff_level": backoff,
        "parent_index": parent_state.parent_index.copy(),
        "child_index": parent_state.child_index.copy(),
        "edge_weight": parent_state.edge_intensity.copy(),
        "signed_twist_parameter": 0.0,
        "parameter_update_performed": False,
        "diagnostics": diagnostics,
    }


def score_null_metrics(
    parent_axial_angle_degrees: Any,
    child_axial_angle_degrees: Any,
    candidate_prediction_degrees: Any,
    baseline_prediction_degrees: Any,
    *,
    edge_weight: Any | None = None,
    angular_sigma_degrees: float = 20.0,
) -> Mapping[str, float]:
    """Score frozen axial loss, log-score gain, and signed chirality."""
    parent = _as_float64("parent_axial_angle_degrees", parent_axial_angle_degrees, ndim=1)
    child = _as_float64("child_axial_angle_degrees", child_axial_angle_degrees, ndim=1)
    candidate = _as_float64("candidate_prediction_degrees", candidate_prediction_degrees, ndim=1)
    baseline = _as_float64("baseline_prediction_degrees", baseline_prediction_degrees, ndim=1)
    n = _same_length(parent=parent, child=child, candidate=candidate, baseline=baseline)
    if n == 0:
        raise OperatorContractError("scoring requires at least one edge")
    if edge_weight is None:
        weight = np.ones(n, dtype=np.float64)
    else:
        weight = _as_float64("edge_weight", edge_weight, ndim=1)
        if len(weight) != n or np.any(weight <= 0.0):
            raise OperatorContractError("edge_weight must be positive and length N")
    if not math.isfinite(angular_sigma_degrees) or angular_sigma_degrees <= 0.0:
        raise OperatorContractError("angular_sigma_degrees must be positive")
    weight = weight / np.sum(weight)
    cand_error = np.asarray(circular_distance_degrees(child, candidate, period=180.0), dtype=np.float64)
    base_error = np.asarray(circular_distance_degrees(child, baseline, period=180.0), dtype=np.float64)
    cand_rmse = math.sqrt(float(np.sum(weight * cand_error**2)))
    base_rmse = math.sqrt(float(np.sum(weight * base_error**2)))
    relative = (base_rmse - cand_rmse) / base_rmse if base_rmse > 0.0 else 0.0
    log_gain = float(np.sum(weight * 0.5 * ((base_error / angular_sigma_degrees) ** 2 - (cand_error / angular_sigma_degrees) ** 2)))
    delta = np.deg2rad(2.0 * _normalize_signed_degrees(child - parent))
    signed = float(np.sum(weight * np.sin(delta)))
    axial_loss = float(np.sum(weight * (1.0 - np.cos(delta))))
    result = {
        "candidate_axial_rmse_degrees": float(cand_rmse),
        "baseline_axial_rmse_degrees": float(base_rmse),
        "relative_axial_rmse_improvement": float(relative),
        "mean_log_score_gain_per_edge": log_gain,
        "signed_chirality": signed,
        "axial_loss": axial_loss,
    }
    if not all(math.isfinite(v) for v in result.values()):
        raise OperatorContractError("score contains non-finite value")
    return result


def moving_block_resample(
    time_days: Any,
    *,
    span_days: float,
    rng: np.random.Generator,
) -> npt.NDArray[np.int64]:
    """Overlapping circular moving-block resample, truncated to N."""
    times = _as_float64("time_days", time_days, ndim=1)
    if len(times) == 0 or np.any(np.diff(times) < 0.0):
        raise OperatorContractError("time_days must be nonempty and sorted")
    if not math.isfinite(span_days) or span_days <= 0.0:
        raise OperatorContractError("span_days must be finite and positive")
    if not isinstance(rng, np.random.Generator):
        raise OperatorContractError("rng must be numpy.random.Generator")
    n = len(times)
    positive = np.diff(times); positive = positive[positive > 0.0]
    spacing = float(np.median(positive)) if len(positive) else 1.0
    cycle = max(float(times[-1] - times[0] + spacing), span_days + spacing)
    extended_times = np.concatenate((times, times + cycle))
    extended_index = np.concatenate((np.arange(n, dtype=np.int64), np.arange(n, dtype=np.int64)))
    blocks: list[np.ndarray] = []
    total = 0
    while total < n:
        start = int(rng.integers(0, n)); start_time = extended_times[start]
        end = int(np.searchsorted(extended_times, start_time + span_days, side="left"))
        end = max(end, start + 1)
        block = extended_index[start:min(end, start + n)]
        blocks.append(block); total += len(block)
    return np.concatenate(blocks)[:n].astype(np.int64, copy=False)


REQUIRED_OPERATOR_SYMBOLS = (
    "circular_distance_degrees",
    "compute_parent_state",
    "draw_static_fields",
    "eval_intensity",
    "head_to_normal",
    "make_rewired_null",
    "moving_block_resample",
    "permute_within_bins",
    "posterior_mark_expectations",
    "propagate_mechanism_uncertainty",
    "reflected_rake",
    "rewire_parent_graph",
    "score_null_metrics",
    "seeded_rng",
    "simulate_catalog",
    "simulate_nonhelical_fixed_parent_weights",
    "static_logodds",
)
