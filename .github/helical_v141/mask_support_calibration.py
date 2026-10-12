from __future__ import annotations

import atexit
import hashlib
import json
import math
import os
import shutil
from pathlib import Path
from typing import Any

import drms
import numpy as np
import requests
from astropy.io import fits
from scipy.ndimage import binary_erosion, gaussian_filter

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "construct_successors" / "KCH_HELICAL_V14_MULTISCALE_OPERATOR_BASIS_20261012" / "OPERATOR_BASIS_PROTOCOL_V1_4.json"
CAL = ROOT / "construct_successors" / "KCH_HELICAL_V141_MASK_SUPPORT_CALIBRATION_20261012" / "MASK_SUPPORT_CALIBRATION_PROTOCOL_V1_4_1.json"
OUT = Path(os.environ.get("OUT", "/tmp/helical_v141_mask_support"))
RAW = OUT / "raw"
SAFE = OUT / "safe"
RAW.mkdir(parents=True, exist_ok=True)
SAFE.mkdir(parents=True, exist_ok=True)
atexit.register(lambda: shutil.rmtree(RAW, ignore_errors=True))
SEGMENTS = ["Br", "Bt", "Bp", "conf_disambig", "bitmap"]
USER_AGENT = "KCH-Helical-v1.4.1-mask-support/2026-10-12"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(obj: Any) -> str:
    body = json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(body).hexdigest()


def candidates(raw: str) -> list[str]:
    if raw.startswith("http://") or raw.startswith("https://"):
        return [raw]
    path = raw if raw.startswith("/") else "/" + raw
    return [
        "https://jsoc1.stanford.edu" + path,
        "https://jsoc.stanford.edu" + path,
        "http://jsoc.stanford.edu" + path,
    ]


def download(record_id: str, name: str, raw: str) -> dict[str, Any]:
    d = RAW / record_id
    d.mkdir(parents=True, exist_ok=True)
    target = d / f"{name}.fits"
    attempts = []
    for i, url in enumerate(candidates(raw)):
        try:
            with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=120, stream=True) as r:
                attempts.append({"candidate": i, "status": r.status_code})
                if r.status_code != 200:
                    continue
                with target.open("wb") as f:
                    for chunk in r.iter_content(1024 * 1024):
                        if chunk:
                            f.write(chunk)
                if target.stat().st_size <= 2880:
                    target.unlink(missing_ok=True)
                    continue
                return {
                    "path": str(target),
                    "bytes": target.stat().st_size,
                    "sha256": sha256_file(target),
                    "attempts": attempts,
                }
        except Exception as exc:
            attempts.append({"candidate": i, "error": repr(exc)})
    raise RuntimeError(f"{record_id}/{name}: download failed: {attempts}")


def load_2d(path: Path) -> np.ndarray:
    with fits.open(path, memmap=False) as hdul:
        for hdu in hdul:
            if hdu.data is None:
                continue
            arr = np.asarray(hdu.data)
            if arr.ndim == 2:
                return np.asarray(arr, dtype=np.float64)
    raise RuntimeError(f"no 2-D image in {path}")


def execute_record(client: drms.Client, record: dict[str, Any], sigmas: list[float],
                   thresholds: list[float], erosion_iterations: int) -> dict[str, Any]:
    key, seg = client.query(
        record["query"],
        key="HARPNUM,T_REC,QUALITY,CMASK",
        seg=",".join(SEGMENTS),
    )
    if len(key) != 1 or len(seg) != 1:
        raise RuntimeError(f"{record['id']}: exact query resolved to {len(key)} records")
    row = key.reset_index(drop=True).iloc[0].to_dict()
    if int(row["QUALITY"]) != 0:
        raise RuntimeError(f"{record['id']}: QUALITY={row['QUALITY']} != 0")
    segrow = seg.reset_index(drop=True).iloc[0].to_dict()
    receipts = {name: download(record["id"], name, str(segrow[name])) for name in SEGMENTS}
    arrays = {name: load_2d(Path(receipts[name]["path"])) for name in SEGMENTS}
    shapes = {name: tuple(arr.shape) for name, arr in arrays.items()}
    if len(set(shapes.values())) != 1:
        raise RuntimeError(f"{record['id']}: shape mismatch {shapes}")
    mask = (
        np.isfinite(arrays["Br"])
        & np.isfinite(arrays["Bt"])
        & np.isfinite(arrays["Bp"])
        & (arrays["bitmap"] >= 33)
        & (arrays["conf_disambig"] == 90)
    )
    eroded = binary_erosion(
        mask,
        structure=np.ones((3, 3), dtype=bool),
        iterations=erosion_iterations,
        border_value=0,
    )
    counts: dict[str, dict[str, int]] = {}
    for sigma in sigmas:
        if sigma == 0:
            weight = mask.astype(np.float64)
        else:
            weight = gaussian_filter(mask.astype(np.float64), sigma=sigma, mode="reflect")
        counts[str(sigma)] = {
            str(thr): int(np.count_nonzero(eroded & (weight >= thr)))
            for thr in thresholds
        }
    safe_receipts = {
        name: {"bytes": rec["bytes"], "sha256": rec["sha256"], "attempts": rec["attempts"]}
        for name, rec in receipts.items()
    }
    return {
        "id": record["id"],
        "query": record["query"],
        "shape": list(next(iter(arrays.values())).shape),
        "cmask_keyword": int(row["CMASK"]),
        "native_mask_count": int(np.count_nonzero(mask)),
        "eroded_native_count": int(np.count_nonzero(eroded)),
        "counts": counts,
        "source_receipts": safe_receipts,
    }


def main() -> int:
    parent = json.loads(PARENT.read_text())
    cal = json.loads(CAL.read_text())
    thresholds = [float(x) for x in cal["candidate_gaussian_support_thresholds"]]
    sigmas = [float(x) for x in parent["scale_space"]["sigma_pixels"]]
    erosion_iterations = int(cal["native_mask_erosion_iterations"])
    floor = int(cal["support_floor_pixels"])

    client = drms.Client()
    results = []
    failures = []
    for record in parent["records"]:
        try:
            results.append(execute_record(client, record, sigmas, thresholds, erosion_iterations))
        except Exception as exc:
            failures.append({"id": record["id"], "error": repr(exc)})

    threshold_min_support: dict[str, int] = {}
    if not failures and len(results) == len(parent["records"]):
        for thr in thresholds:
            vals = [
                rec["counts"][str(sigma)][str(thr)]
                for rec in results
                for sigma in sigmas
            ]
            threshold_min_support[str(thr)] = int(min(vals))

    admissible = [
        thr for thr in thresholds
        if threshold_min_support.get(str(thr), -1) >= floor
    ]
    selected = max(admissible) if admissible else None
    outcome = "MASK_SUPPORT_CALIBRATION_PASS" if selected is not None and not failures else "MASK_SUPPORT_CALIBRATION_FAIL"
    rc = 0 if outcome == "MASK_SUPPORT_CALIBRATION_PASS" else 31

    report = {
        "format": "KCH_HELICAL_V1_4_1_MASK_SUPPORT_CALIBRATION_RESULT",
        "parent_protocol_sha256": sha256_file(PARENT),
        "calibration_protocol_sha256": sha256_file(CAL),
        "candidate_thresholds": thresholds,
        "sigma_pixels": sigmas,
        "erosion_iterations": erosion_iterations,
        "support_floor_pixels": floor,
        "selection_rule": cal["selection_rule"],
        "records": results,
        "support_failures": failures,
        "threshold_min_support": threshold_min_support,
        "selected_gaussian_support_threshold": selected,
        "outcome": outcome,
        "operator_values_accessed": False,
        "flare_outcomes_accessed": False,
        "fresh_2026_holdout_accessed": False,
        "scientific_result": None,
        "physical_helicity": "NOT_EVALUATED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "authority_ceiling": "NONE",
    }
    report["receipt_id"] = "h141mask:" + canonical_hash(report)
    (SAFE / "MASK_SUPPORT_CALIBRATION_RESULT_V1_4_1.json").write_text(
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    )
    print(json.dumps({
        "outcome": outcome,
        "receipt_id": report["receipt_id"],
        "selected_gaussian_support_threshold": selected,
        "threshold_min_support": threshold_min_support,
        "record_support": [
            {
                "id": r["id"],
                "native_mask_count": r["native_mask_count"],
                "eroded_native_count": r["eroded_native_count"],
                "counts": r["counts"],
            }
            for r in results
        ],
        "support_failures": failures,
    }, sort_keys=True, indent=2))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
