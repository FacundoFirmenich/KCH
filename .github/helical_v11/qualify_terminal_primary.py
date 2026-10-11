from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def p_axis(strike: np.ndarray, dip: np.ndarray, rake: np.ndarray) -> np.ndarray:
    s = np.deg2rad(strike); d = np.deg2rad(dip); r = np.deg2rad(rake)
    sv = np.stack([np.cos(s), np.sin(s), np.zeros_like(s)], axis=1)
    dd = np.stack([-np.sin(s) * np.cos(d), np.cos(s) * np.cos(d), np.sin(d)], axis=1)
    normal = np.cross(sv, dd); normal /= np.linalg.norm(normal, axis=1)[:, None]
    slip = np.cos(r)[:, None] * sv + np.sin(r)[:, None] * dd; slip /= np.linalg.norm(slip, axis=1)[:, None]
    axis = normal - slip; axis /= np.linalg.norm(axis, axis=1)[:, None]
    return axis


def build_fixture(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(117711)
    per = 400; n = 800
    cohort = np.repeat(np.array([0, 1], dtype=np.int8), per)
    split = np.tile(
        np.concatenate([
            np.zeros(200, dtype=np.int8),
            np.ones(100, dtype=np.int8),
            np.full(100, 2, dtype=np.int8),
        ]), 2,
    )
    event_time = np.concatenate([np.arange(per, dtype=float) * 86400.0, np.arange(per, dtype=float) * 86400.0 + 1e8])
    fault = np.concatenate([np.arange(per) % 4, 10 + np.arange(per) % 3]).astype(int)
    tangent = np.zeros((n, 3), dtype=float); tangent[:, 0] = 1.0
    strike = rng.uniform(0.0, 360.0, n); dip = rng.uniform(30.0, 80.0, n); rake = rng.uniform(-180.0, 180.0, n)
    axis = p_axis(strike, dip, rake)
    down = np.array([0.0, 0.0, 1.0])
    e1 = np.cross(np.broadcast_to(down, tangent.shape), tangent); e1 /= np.linalg.norm(e1, axis=1)[:, None]
    e2 = np.cross(tangent, e1)
    projection = np.sqrt(np.sum(axis * e1, axis=1) ** 2 + np.sum(axis * e2, axis=1) ** 2)
    observable = projection >= 0.15
    starts = [0]; parents: list[int] = []; dts: list[float] = []; distances: list[float] = []; signs: list[float] = []; curvature: list[float] = []
    for child in range(n):
        begin = 0 if cohort[child] == 0 else per
        candidates = [parent for lag in range(1, 6) if (parent := child - lag) >= begin and cohort[parent] == cohort[child]]
        parents.extend(candidates)
        dts.extend(float(child - parent) for parent in candidates)
        distances.extend(float(abs(child - parent)) for parent in candidates)
        signs.extend([1.0] * len(candidates)); curvature.extend([0.0] * len(candidates)); starts.append(len(parents))
    evid = np.array([f"fixture-{index:04d}" for index in range(n)])
    directional = root / "directional.npz"
    preflight = root / "preflight.npz"
    np.savez_compressed(
        directional,
        strike=strike, dip=dip, rake=rake, mag=rng.uniform(1.0, 4.0, n), uncer=np.full(n, 15.0),
        year=np.full(n, 2024), event_time_epoch=event_time, cohort_code=cohort, split_code=split,
        fault_assignment=fault, nearest_km=np.ones(n), second_km=np.full(n, 3.0), evid=evid,
        nodal_plane_equivalence=np.ones(n),
    )
    np.savez_compressed(
        preflight,
        axis_observable=observable, projection_norm=projection, tangent_ned=tangent,
        along_fault_km=np.arange(n, dtype=float) % 50.0, event_x=np.arange(n, dtype=float), event_y=np.zeros(n),
        candidate_starts=np.asarray(starts, dtype=np.int64), candidate_parent=np.asarray(parents, dtype=np.int64),
        candidate_dt_days=np.asarray(dts, dtype=float), candidate_distance_km=np.asarray(distances, dtype=float),
        candidate_sign=np.asarray(signs, dtype=float), candidate_curvature=np.asarray(curvature, dtype=float),
    )
    return directional, preflight


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    input_root = args.out / "input"; result_root = args.out / "result"
    result_root.mkdir(parents=True, exist_ok=True)
    directional, preflight = build_fixture(input_root)
    command = [
        sys.executable,
        str(args.repo_root / ".github/helical_v11/run_primary_gate_json_safe.py"),
        "--script", str(args.repo_root / ".github/helical_v11/seismic_terminal_primary_gate.py"),
        "--directional", str(directional),
        "--preflight", str(preflight),
        "--protocol", str(args.repo_root / ".github/helical_v11/SEISMIC_TERMINAL_FULL_NETWORK_GATE_V1_1_LOCKED.json"),
        "--out", str(result_root),
    ]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (result_root / "STDOUT.log").write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(f"qualification execution failed: {completed.returncode}\n{completed.stdout}")
    required = [
        "SEISMIC_TERMINAL_FULL_NETWORK_PRIMARY_RESULT_V1_1.json",
        "SEISMIC_TERMINAL_CALIBRATION_GRID_V1_1.csv",
        "SEISMIC_TERMINAL_CALIBRATION_FREEZE_V1_1.json",
        "JSON_CANONICALIZATION_REPAIR_RECEIPT.json",
    ]
    for name in required:
        path = result_root / name
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"missing qualification output {name}")
    result = json.loads((result_root / required[0]).read_text(encoding="utf-8"))
    receipt = {
        "format": "KCH_TERMINAL_SEISMIC_SOFTWARE_QUALIFICATION_V1_1",
        "fixture_authority": "ZERO",
        "scientific_evidence": False,
        "runtime_completed": True,
        "serialization_completed": True,
        "calibration_freeze_created": True,
        "test_adjudication_created": True,
        "outcome": result["outcome"],
        "result_sha256": sha256_file(result_root / required[0]),
        "base_runtime_sha256": sha256_file(args.repo_root / ".github/helical_v11/seismic_terminal_primary_gate.py"),
        "json_adapter_sha256": sha256_file(args.repo_root / ".github/helical_v11/run_primary_gate_json_safe.py"),
        "authority_ceiling": "NONE",
    }
    (args.out / "QUALIFICATION_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
