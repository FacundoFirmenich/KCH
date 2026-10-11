from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np


def wrap_axial(value: np.ndarray | float) -> np.ndarray | float:
    return (value + np.pi / 2.0) % np.pi - np.pi / 2.0


def sdr_from_normal_slip(normal: np.ndarray, slip: np.ndarray) -> tuple[float, float, float]:
    normal = np.asarray(normal, dtype=float)
    slip = np.asarray(slip, dtype=float)
    if normal[2] > 0.0:
        normal = -normal
        slip = -slip
    normal /= np.linalg.norm(normal)
    slip = slip - np.dot(slip, normal) * normal
    slip /= np.linalg.norm(slip)
    dip = math.acos(float(np.clip(-normal[2], -1.0, 1.0)))
    strike = math.atan2(float(-normal[0]), float(normal[1]))
    if strike < 0.0:
        strike += 2.0 * math.pi
    strike_vector = np.array([math.cos(strike), math.sin(strike), 0.0])
    rake_basis = np.array([
        math.cos(dip) * math.sin(strike),
        -math.cos(dip) * math.cos(strike),
        -math.sin(dip),
    ])
    rake = math.atan2(float(np.dot(slip, rake_basis)), float(np.dot(slip, strike_vector)))
    return tuple(float(value) for value in np.rad2deg([strike, dip, rake]))


def sdr_from_phase(phase: float) -> tuple[float, float, float]:
    p_axis = np.array([0.0, math.cos(phase), math.sin(phase)])
    t_axis = np.array([1.0, 0.0, 0.0])
    slip = (t_axis + p_axis) / math.sqrt(2.0)
    normal = (t_axis - p_axis) / math.sqrt(2.0)
    return sdr_from_normal_slip(normal, slip)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def build_fixture(root: Path, effect: float, noise_sd: float, seed: int) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    per_cohort = 1200
    n = 2 * per_cohort
    cohort = np.repeat(np.array([0, 1], dtype=np.int8), per_cohort)
    split_one = np.concatenate([
        np.zeros(600, dtype=np.int8),
        np.ones(300, dtype=np.int8),
        np.full(300, 2, dtype=np.int8),
    ])
    split = np.tile(split_one, 2)
    times = np.concatenate([
        np.arange(per_cohort, dtype=float) * 86400.0,
        1.0e8 + np.arange(per_cohort, dtype=float) * 86400.0,
    ])
    fault = np.concatenate([
        np.full(per_cohort, 4, dtype=int),
        np.full(per_cohort, 14, dtype=int),
    ])
    distances = rng.uniform(0.5, 15.0, n)
    distances[0] = distances[per_cohort] = 0.0
    phases = np.zeros(n, dtype=float)
    for cohort_start in [0, per_cohort]:
        phases[cohort_start] = rng.uniform(-0.5, 0.5)
        for index in range(cohort_start + 1, cohort_start + per_cohort):
            phases[index] = float(wrap_axial(phases[index - 1] + effect * distances[index] + rng.normal(0.0, noise_sd)))
    sdr = np.asarray([sdr_from_phase(float(phase)) for phase in phases])
    tangent = np.zeros((n, 3), dtype=float); tangent[:, 0] = 1.0
    projection = np.ones(n, dtype=float)
    starts = [0]
    parents: list[int] = []
    dt_days: list[float] = []
    candidate_distance: list[float] = []
    signs: list[float] = []
    curvature: list[float] = []
    for index in range(n):
        cohort_start = 0 if index < per_cohort else per_cohort
        if index > cohort_start:
            parents.append(index - 1)
            dt_days.append(1.0)
            candidate_distance.append(float(distances[index]))
            signs.append(1.0)
            curvature.append(0.0)
        starts.append(len(parents))
    directional = root / "directional.npz"
    preflight = root / "preflight.npz"
    np.savez_compressed(
        directional,
        strike=sdr[:, 0], dip=sdr[:, 1], rake=sdr[:, 2],
        mag=rng.uniform(1.0, 4.0, n), uncer=np.full(n, 5.0), year=np.full(n, 2024),
        event_time_epoch=times, cohort_code=cohort, split_code=split, fault_assignment=fault,
        nearest_km=np.ones(n), second_km=np.full(n, 3.0),
        evid=np.asarray([f"positive-{index:05d}" for index in range(n)]),
        nodal_plane_equivalence=np.ones(n),
    )
    np.savez_compressed(
        preflight,
        axis_observable=np.ones(n, dtype=bool), projection_norm=projection, tangent_ned=tangent,
        along_fault_km=rng.uniform(0.0, 50.0, n), event_x=np.arange(n, dtype=float), event_y=np.zeros(n),
        candidate_starts=np.asarray(starts, dtype=np.int64), candidate_parent=np.asarray(parents, dtype=np.int64),
        candidate_dt_days=np.asarray(dt_days, dtype=float), candidate_distance_km=np.asarray(candidate_distance, dtype=float),
        candidate_sign=np.asarray(signs, dtype=float), candidate_curvature=np.asarray(curvature, dtype=float),
    )
    return directional, preflight


def run_gate(repo: Path, root: Path, effect: float, noise: float, seed: int) -> dict:
    directional, preflight = build_fixture(root / "input", effect, noise, seed)
    result_root = root / "result"; result_root.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(repo / ".github/helical_v11/run_primary_gate_json_safe.py"),
        "--script", str(repo / ".github/helical_v11/seismic_terminal_primary_gate.py"),
        "--directional", str(directional), "--preflight", str(preflight),
        "--protocol", str(repo / ".github/helical_v11/SEISMIC_TERMINAL_FULL_NETWORK_GATE_V1_1_LOCKED.json"),
        "--out", str(result_root),
    ]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (result_root / "STDOUT.log").write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(completed.stdout)
    return json.loads((result_root / "SEISMIC_TERMINAL_FULL_NETWORK_PRIMARY_RESULT_V1_1.json").read_text())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    negative = run_gate(args.repo_root, args.out / "null", effect=0.0, noise=0.18, seed=11811)
    positive = run_gate(args.repo_root, args.out / "positive", effect=0.075, noise=0.035, seed=11812)
    null_pass = negative["positive_primary_cohorts"] == 0
    positive_pass = positive["positive_primary_cohorts"] == 2
    receipt = {
        "format": "KCH_TERMINAL_SEISMIC_BIDIRECTIONAL_SOFTWARE_QUALIFICATION_V1_1",
        "fixture_authority": "ZERO",
        "scientific_evidence": False,
        "sdr_coordinate_system": "AKI_RICHARDS_NORTH_EAST_DOWN",
        "null_outcome": negative["outcome"],
        "null_positive_cohorts": negative["positive_primary_cohorts"],
        "null_rejected": null_pass,
        "positive_outcome": positive["outcome"],
        "positive_positive_cohorts": positive["positive_primary_cohorts"],
        "positive_detected": positive_pass,
        "bidirectional_qualification_pass": bool(null_pass and positive_pass),
        "base_runtime_sha256": sha256_file(args.repo_root / ".github/helical_v11/seismic_terminal_primary_gate.py"),
        "authority_ceiling": "NONE",
    }
    (args.out / "BIDIRECTIONAL_QUALIFICATION_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["bidirectional_qualification_pass"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
