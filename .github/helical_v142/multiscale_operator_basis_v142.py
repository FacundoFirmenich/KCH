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
PARENT_PROTOCOL = ROOT / "construct_successors" / "KCH_HELICAL_V14_MULTISCALE_OPERATOR_BASIS_20261012" / "OPERATOR_BASIS_PROTOCOL_V1_4.json"\nSUCCESSOR_PROTOCOL = ROOT / "construct_successors" / "KCH_HELICAL_V142_OPERATOR_BASIS_REEXECUTION_20261012" / "OPERATOR_BASIS_REEXECUTION_PROTOCOL_V1_4_2.json"\nMASK_SUPPORT_LOCK = ROOT / "construct_successors" / "KCH_HELICAL_V141_MASK_SUPPORT_CALIBRATION_20261012" / "MASK_SUPPORT_LOCK_V1_4_1.json"\nMASK_SUPPORT = json.loads(MASK_SUPPORT_LOCK.read_text())\nSELECTED_SUPPORT_THRESHOLD = float(MASK_SUPPORT["selected_gaussian_support_threshold"])\nMASK_EROSION_ITERATIONS = int(MASK_SUPPORT["native_mask_erosion_iterations"])\nSCALE_SUPPORT_FLOOR = int(MASK_SUPPORT["support_floor_pixels"])\nOUT = Path(os.environ.get("OUT", "/tmp/helical_v142_operator_basis"))
RAW = OUT / "raw"
SAFE = OUT / "safe"
RAW.mkdir(parents=True, exist_ok=True)
SAFE.mkdir(parents=True, exist_ok=True)
atexit.register(lambda: shutil.rmtree(RAW, ignore_errors=True))
USER_AGENT = "KCH-Helical-v1.4.2-multiscale-operator-basis/2026-10-12"
KEYS = [
    "HARPNUM", "T_REC", "NOAA_AR", "QUALITY", "CMASK",
    "MEANJZH", "MEANALP", "CDELT1", "RSUN_OBS", "RSUN_REF"
]
SEGMENTS = ["Br", "Bt", "Bp", "conf_disambig", "bitmap"]


def canonical_sha256(value: Any) -> str:
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(body).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def segment_candidates(raw: str) -> list[str]:
    if raw.startswith("http://") or raw.startswith("https://"):
        return [raw]
    path = raw if raw.startswith("/") else "/" + raw
    return [
        "https://jsoc1.stanford.edu" + path,
        "https://jsoc.stanford.edu" + path,
        "http://jsoc.stanford.edu" + path,
    ]


def download_segment(record_id: str, name: str, raw: str) -> dict[str, Any]:
    record_dir = RAW / record_id
    record_dir.mkdir(parents=True, exist_ok=True)
    target = record_dir / f"{name}.fits"
    attempts: list[dict[str, Any]] = []
    for i, url in enumerate(segment_candidates(raw)):
        try:
            with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=120, stream=True) as response:
                attempts.append({
                    "candidate": i,
                    "status": response.status_code,
                    "content_type": response.headers.get("content-type"),
                    "content_length": response.headers.get("content-length"),
                })
                if response.status_code != 200:
                    continue
                with target.open("wb") as f:
                    for chunk in response.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                if target.stat().st_size <= 2880:
                    target.unlink(missing_ok=True)
                    continue
                return {
                    "bytes": target.stat().st_size,
                    "sha256": sha256_file(target),
                    "path": str(target),
                    "attempts": attempts,
                }
        except Exception as exc:
            attempts.append({"candidate": i, "error": repr(exc)})
    raise RuntimeError(f"segment download failed: {record_id}/{name}: {attempts}")


def load_2d(path: Path) -> tuple[np.ndarray, dict[str, Any]]:
    with fits.open(path, memmap=False) as hdul:
        chosen = None
        for index, hdu in enumerate(hdul):
            if hdu.data is None:
                continue
            arr = np.asarray(hdu.data)
            if arr.ndim == 2:
                chosen = (index, hdu, np.asarray(arr, dtype=np.float64))
                break
        if chosen is None:
            raise RuntimeError(f"no 2-D image HDU in {path}")
        index, hdu, data = chosen
        meta = {
            "hdu_index": index,
            "hdu_type": type(hdu).__name__,
            "hdu_name": getattr(hdu, "name", None),
            "shape": list(data.shape),
            "bunit": hdu.header.get("BUNIT"),
        }
    return data, meta


def relative_error(value: float, target: float) -> float:
    return abs(value - target) / max(abs(value), abs(target), 1e-30)


def sign_or_zero(value: float, atol: float = 1e-15) -> int:
    if not math.isfinite(value) or abs(value) <= atol:
        return 0
    return 1 if value > 0 else -1


def smoothed_component(field: np.ndarray, mask: np.ndarray, sigma: float) -> np.ndarray:
    if sigma == 0:
        return field.copy()
    weight = gaussian_filter(mask.astype(np.float64), sigma=sigma, mode="reflect")
    num = gaussian_filter(np.where(mask, field, 0.0), sigma=sigma, mode="reflect")
    out = np.full_like(field, np.nan, dtype=np.float64)
    np.divide(num, weight, out=out, where=weight > 1e-12)
    return out


def valid_scale_mask(mask: np.ndarray, sigma: float) -> np.ndarray:
    eroded = binary_erosion(
        mask,
        structure=np.ones((3, 3), dtype=bool),
        iterations=MASK_EROSION_ITERATIONS,
        border_value=0,
    )
    if sigma == 0:
        support_weight = mask.astype(np.float64)
    else:
        support_weight = gaussian_filter(mask.astype(np.float64), sigma=sigma, mode="reflect")
    return eroded & (support_weight >= SELECTED_SUPPORT_THRESHOLD)


def operator_set(
    bx: np.ndarray,
    by: np.ndarray,
    bz: np.ndarray,
    mask: np.ndarray,
    dx_m: float,
    sigma: float,
) -> dict[str, float]:
    sx = smoothed_component(bx, mask, sigma)
    sy = smoothed_component(by, mask, sigma)
    sz = smoothed_component(bz, mask, sigma)
    valid = valid_scale_mask(mask, sigma)
    valid &= np.isfinite(sx) & np.isfinite(sy) & np.isfinite(sz)

    dbx_dy, dbx_dx = np.gradient(sx, dx_m, dx_m, edge_order=2)
    dby_dy, dby_dx = np.gradient(sy, dx_m, dx_m, edge_order=2)
    dbz_dy, dbz_dx = np.gradient(sz, dx_m, dx_m, edge_order=2)
    jz = dby_dx - dbx_dy
    hc = sz * jz

    valid &= (
        np.isfinite(jz) & np.isfinite(hc)
        & np.isfinite(dbx_dx) & np.isfinite(dbx_dy)
        & np.isfinite(dby_dx) & np.isfinite(dby_dy)
        & np.isfinite(dbz_dx) & np.isfinite(dbz_dy)
    )
    n = int(np.count_nonzero(valid))
    if n < SCALE_SUPPORT_FLOOR:
        raise RuntimeError(f"scale sigma={sigma}: only {n} valid pixels below floor {SCALE_SUPPORT_FLOOR}")

    def mean(x: np.ndarray) -> float:
        return float(np.mean(x[valid], dtype=np.float64))

    cross = float(np.sum(hc[valid], dtype=np.float64))
    bz2 = float(np.sum(np.square(sz[valid]), dtype=np.float64))
    jz2 = float(np.sum(np.square(jz[valid]), dtype=np.float64))
    norm_denom = math.sqrt(max(bz2 * jz2, 0.0))
    grad_energy = (
        np.square(dbx_dx) + np.square(dbx_dy)
        + np.square(dby_dx) + np.square(dby_dy)
        + np.square(dbz_dx) + np.square(dbz_dy)
    )
    energy = np.square(sx) + np.square(sy) + np.square(sz)

    return {
        "valid_pixels": n,
        "HC_SIGNED_MEAN": mean(hc),
        "HC_NORMALIZED": cross / norm_denom if norm_denom > 0 else 0.0,
        "ALPHA_WEIGHTED_PER_MM": 1e6 * cross / bz2 if bz2 > 0 else 0.0,
        "HC_UNSIGNED_MEAN": mean(np.abs(hc)),
        "MAGNETIC_ENERGY_PROXY": mean(energy),
        "JZ_RMS": math.sqrt(max(mean(np.square(jz)), 0.0)),
        "GRADIENT_ENERGY": mean(grad_energy),
    }


def native_reconciliation(
    bx: np.ndarray,
    by: np.ndarray,
    bz: np.ndarray,
    mask: np.ndarray,
    dx_m: float,
    row: dict[str, Any],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    dby_dx = np.gradient(by, dx_m, axis=1, edge_order=2)
    dbx_dy = np.gradient(bx, dx_m, axis=0, edge_order=2)
    jz = dby_dx - dbx_dy
    hc = bz * jz
    valid = mask & np.isfinite(jz) & np.isfinite(hc)
    cross = float(np.sum(hc[valid], dtype=np.float64))
    bz2 = float(np.sum(np.square(bz[valid]), dtype=np.float64))
    meanjzh = float(np.mean(hc[valid], dtype=np.float64))
    meanalp = 1e6 * cross / bz2

    target_jzh = float(row["MEANJZH"])
    target_alp = float(row["MEANALP"])
    tol_jzh = float(protocol["native_metadata_reconciliation"]["MEANJZH_relative_tolerance"])
    tol_alp = float(protocol["native_metadata_reconciliation"]["MEANALP_relative_tolerance"])
    mask_count = int(np.count_nonzero(mask))
    cmask = int(row["CMASK"])
    checks = {
        "cmask_keyword": cmask,
        "computed_mask_count": mask_count,
        "CMASK_exact": cmask == mask_count,
        "MEANJZH_keyword": target_jzh,
        "MEANJZH_recomputed": meanjzh,
        "MEANJZH_sign_match": sign_or_zero(target_jzh) == sign_or_zero(meanjzh),
        "MEANJZH_relative_error": relative_error(meanjzh, target_jzh),
        "MEANALP_keyword": target_alp,
        "MEANALP_recomputed": meanalp,
        "MEANALP_sign_match": sign_or_zero(target_alp) == sign_or_zero(meanalp),
        "MEANALP_relative_error": relative_error(meanalp, target_alp),
    }
    checks["pass"] = bool(
        checks["CMASK_exact"]
        and checks["MEANJZH_sign_match"]
        and checks["MEANALP_sign_match"]
        and checks["MEANJZH_relative_error"] <= tol_jzh
        and checks["MEANALP_relative_error"] <= tol_alp
    )
    return checks


def transformed_fields(
    kind: str,
    bx: np.ndarray,
    by: np.ndarray,
    bz: np.ndarray,
    mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if kind == "PARITY_X":
        return np.fliplr(bx), -np.fliplr(by), -np.fliplr(bz), np.fliplr(mask)
    if kind == "FIELD_REVERSAL":
        return -bx, -by, -bz, mask.copy()
    if kind == "ROTATION_PI":
        return (
            -np.flipud(np.fliplr(bx)),
            -np.flipud(np.fliplr(by)),
            np.flipud(np.fliplr(bz)),
            np.flipud(np.fliplr(mask)),
        )
    raise KeyError(kind)


def scale_basis(
    bx: np.ndarray,
    by: np.ndarray,
    bz: np.ndarray,
    mask: np.ndarray,
    dx_m: float,
    sigmas: list[float],
) -> dict[str, dict[str, float]]:
    return {
        str(sigma): operator_set(bx, by, bz, mask, dx_m, sigma)
        for sigma in sigmas
    }


def cross_scale(basis: dict[str, dict[str, float]], sigmas: list[float]) -> dict[str, float]:
    hc = np.asarray([basis[str(s)]["HC_SIGNED_MEAN"] for s in sigmas], dtype=np.float64)
    x = np.log1p(np.asarray(sigmas, dtype=np.float64))
    integral = float(np.trapezoid(hc, x))
    sel = np.asarray(sigmas) > 0
    slope = float(np.polyfit(x[sel], np.log(np.maximum(np.abs(hc[sel]), 1e-300)), 1)[0])
    signs = np.asarray([sign_or_zero(float(v)) for v in hc], dtype=np.int64)
    nonzero = signs[signs != 0]
    changes = int(np.sum(nonzero[1:] != nonzero[:-1])) if len(nonzero) > 1 else 0
    return {
        "SIGNED_HC_LOG_SCALE_INTEGRAL": integral,
        "ABS_HC_LOG_SCALE_SLOPE": slope,
        "HC_SIGN_CHANGE_COUNT": changes,
    }


def symmetry_check(
    observed: dict[str, dict[str, float]],
    transformed: dict[str, dict[str, dict[str, float]]],
    sigmas: list[float],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    rel_tol = float(protocol["symmetry_tests"]["relative_tolerance"])
    abs_tol = float(protocol["symmetry_tests"]["zero_absolute_tolerance"])
    signatures = {
        name: {
            "PARITY_X": int(spec["parity_signature"]),
            "FIELD_REVERSAL": int(spec["global_field_reversal_signature"]),
            "ROTATION_PI": int(spec["proper_rotation_pi_signature"]),
        }
        for name, spec in protocol["operators"].items()
    }
    failures: list[dict[str, Any]] = []
    max_rel = 0.0
    for transform, basis in transformed.items():
        for sigma in sigmas:
            key = str(sigma)
            for operator, sig in signatures.items():
                base = float(observed[key][operator])
                value = float(basis[key][operator])
                target = float(sig[transform]) * base
                abs_err = abs(value - target)
                rel_err = relative_error(value, target)
                max_rel = max(max_rel, rel_err)
                passed = abs_err <= abs_tol or rel_err <= rel_tol
                if not passed:
                    failures.append({
                        "transform": transform,
                        "sigma_pixels": sigma,
                        "operator": operator,
                        "observed": base,
                        "transformed": value,
                        "target": target,
                        "relative_error": rel_err,
                    })

    obs_cross = cross_scale(observed, sigmas)
    transformed_cross = {k: cross_scale(v, sigmas) for k, v in transformed.items()}
    cross_signatures = {
        "SIGNED_HC_LOG_SCALE_INTEGRAL": {"PARITY_X": -1, "FIELD_REVERSAL": 1, "ROTATION_PI": 1},
        "ABS_HC_LOG_SCALE_SLOPE": {"PARITY_X": 1, "FIELD_REVERSAL": 1, "ROTATION_PI": 1},
        "HC_SIGN_CHANGE_COUNT": {"PARITY_X": 1, "FIELD_REVERSAL": 1, "ROTATION_PI": 1},
    }
    for transform, vals in transformed_cross.items():
        for operator, sig in cross_signatures.items():
            base = float(obs_cross[operator])
            value = float(vals[operator])
            target = float(sig[transform]) * base
            abs_err = abs(value - target)
            rel_err = relative_error(value, target)
            max_rel = max(max_rel, rel_err)
            passed = abs_err <= abs_tol or rel_err <= rel_tol
            if not passed:
                failures.append({
                    "transform": transform,
                    "sigma_pixels": "CROSS_SCALE",
                    "operator": operator,
                    "observed": base,
                    "transformed": value,
                    "target": target,
                    "relative_error": rel_err,
                })
    return {
        "pass": len(failures) == 0,
        "max_relative_error": max_rel,
        "failures": failures,
        "observed_cross_scale": obs_cross,
        "transformed_cross_scale": transformed_cross,
    }


def execute_record(client: drms.Client, record: dict[str, Any], protocol: dict[str, Any]) -> dict[str, Any]:
    query = record["query"]
    key, seg = client.query(query, key=",".join(KEYS), seg=",".join(SEGMENTS))
    if len(key) != 1 or len(seg) != 1:
        raise RuntimeError(f"{record['id']}: exact query resolved to {len(key)} records")
    row = key.reset_index(drop=True).iloc[0].to_dict()
    segrow = seg.reset_index(drop=True).iloc[0].to_dict()
    if int(row["QUALITY"]) != 0:
        raise RuntimeError(f"{record['id']}: QUALITY={row['QUALITY']} != 0")

    downloads = {
        name: download_segment(record["id"], name, str(segrow[name]))
        for name in SEGMENTS
    }
    arrays: dict[str, np.ndarray] = {}
    fits_meta: dict[str, Any] = {}
    for name in SEGMENTS:
        arr, meta = load_2d(Path(downloads[name]["path"]))
        arrays[name] = arr
        fits_meta[name] = meta
    shapes = {name: tuple(arr.shape) for name, arr in arrays.items()}
    if len(set(shapes.values())) != 1:
        raise RuntimeError(f"{record['id']}: segment shape mismatch {shapes}")

    br, bt, bp = arrays["Br"], arrays["Bt"], arrays["Bp"]
    conf, bitmap = arrays["conf_disambig"], arrays["bitmap"]
    mask = (
        np.isfinite(br) & np.isfinite(bt) & np.isfinite(bp)
        & (bitmap >= 33) & (conf == 90)
    )
    if int(np.count_nonzero(mask)) < int(protocol["record_eligibility"]["minimum_mask_pixels"]):
        raise RuntimeError(f"{record['id']}: insufficient mask support")

    bx, by, bz = bp.copy(), -bt.copy(), br.copy()
    dx_m = float(row["RSUN_REF"]) * math.radians(abs(float(row["CDELT1"])))
    sigmas = [float(x) for x in protocol["scale_space"]["sigma_pixels"]]

    observed = scale_basis(bx, by, bz, mask, dx_m, sigmas)
    transformed: dict[str, dict[str, dict[str, float]]] = {}
    for kind in ["PARITY_X", "FIELD_REVERSAL", "ROTATION_PI"]:
        tx, ty, tz, tm = transformed_fields(kind, bx, by, bz, mask)
        transformed[kind] = scale_basis(tx, ty, tz, tm, dx_m, sigmas)

    symmetry = symmetry_check(observed, transformed, sigmas, protocol)
    reconciliation = native_reconciliation(bx, by, bz, mask, dx_m, row, protocol)

    safe_downloads = {
        name: {"bytes": d["bytes"], "sha256": d["sha256"], "attempts": d["attempts"]}
        for name, d in downloads.items()
    }
    return {
        "id": record["id"],
        "query": query,
        "selection_basis": record["selection_basis"],
        "record": row,
        "pixel_scale_m": dx_m,
        "physical_sigma_Mm": {str(s): s * dx_m / 1e6 for s in sigmas},
        "fits_metadata": fits_meta,
        "source_receipts": safe_downloads,
        "native_reconciliation": reconciliation,
        "observed_basis": observed,
        "symmetry": symmetry,
        "pass": bool(reconciliation["pass"] and symmetry["pass"]),
    }


def main() -> int:
    protocol = json.loads(PARENT_PROTOCOL.read_text())\n    successor_protocol = json.loads(SUCCESSOR_PROTOCOL.read_text())
    client = drms.Client()
    results: list[dict[str, Any]] = []
    support_failures: list[dict[str, str]] = []

    for record in protocol["records"]:
        try:
            results.append(execute_record(client, record, protocol))
        except Exception as exc:
            support_failures.append({"id": record["id"], "error": repr(exc)})

    if support_failures:
        outcome = "INSUFFICIENT_DEVELOPMENT_RECORD_SUPPORT"
        rc = 31
    elif all(r["pass"] for r in results):
        outcome = "MULTISCALE_OPERATOR_BASIS_PASS"
        rc = 0
    else:
        outcome = "MULTISCALE_OPERATOR_BASIS_NOT_RECONCILED"
        rc = 30

    report = {
        "format": "KCH_HELICAL_V1_4_2_MULTISCALE_OPERATOR_BASIS_RESULT",\n        "parent_protocol_sha256": sha256_file(PARENT_PROTOCOL),\n        "successor_protocol_sha256": sha256_file(SUCCESSOR_PROTOCOL),\n        "mask_support_lock_sha256": sha256_file(MASK_SUPPORT_LOCK),\n        "selected_gaussian_support_threshold": SELECTED_SUPPORT_THRESHOLD,\n        "mask_erosion_iterations": MASK_EROSION_ITERATIONS,\n        "scale_support_floor_pixels": SCALE_SUPPORT_FLOOR,
        "scope": protocol["scope"],
        "records_requested": len(protocol["records"]),
        "records_completed": len(results),
        "support_failures": support_failures,
        "results": results,
        "outcome": outcome,
        "scientific_result": None,
        "flare_outcomes_accessed": False,
        "fresh_2026_holdout_accessed": False,
        "physical_helicity": "NOT_EVALUATED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "authority_ceiling": "NONE",
    }
    report["receipt_id"] = "h142basis:" + canonical_sha256(report)
    output = SAFE / "MULTISCALE_OPERATOR_BASIS_RESULT_V1_4_2.json"
    output.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n")

    print(json.dumps({
        "outcome": outcome,
        "receipt_id": report["receipt_id"],
        "records_completed": len(results),
        "support_failures": support_failures,
        "record_summaries": [
            {
                "id": r["id"],
                "pass": r["pass"],
                "cmask_pass": r["native_reconciliation"]["CMASK_exact"],
                "meanjzh_relative_error": r["native_reconciliation"]["MEANJZH_relative_error"],
                "meanalp_relative_error": r["native_reconciliation"]["MEANALP_relative_error"],
                "symmetry_pass": r["symmetry"]["pass"],
                "symmetry_max_relative_error": r["symmetry"]["max_relative_error"],
                "cross_scale": r["symmetry"]["observed_cross_scale"],
            }
            for r in results
        ],
    }, sort_keys=True, indent=2))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
