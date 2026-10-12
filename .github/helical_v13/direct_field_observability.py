from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
from typing import Any

import drms
import numpy as np
import requests
from astropy.io import fits

OUT = Path(os.environ.get("OUT", "/tmp/helical_v13_direct_field"))
OUT.mkdir(parents=True, exist_ok=True)

QUERY = os.environ.get(
    "SHARP_QUERY", "hmi.sharp_cea_720s[5249][2015.03.02_12:00:00_TAI]"
)
KEYS = [
    "HARPNUM",
    "T_REC",
    "NOAA_AR",
    "QUALITY",
    "CMASK",
    "MEANJZH",
    "TOTUSJH",
    "ABSNJZH",
    "MEANALP",
    "CDELT1",
    "RSUN_OBS",
    "RSUN_REF",
]
SEGMENTS = ["Br", "Bt", "Bp", "conf_disambig", "bitmap"]
USER_AGENT = "KCH-Helical-v1.3-direct-field-observability/2026-10-12"


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


def download_segment(name: str, raw: str) -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    target = OUT / f"{name}.fits"
    for i, url in enumerate(segment_candidates(raw)):
        try:
            with requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=120,
                stream=True,
            ) as r:
                attempt = {
                    "candidate": i,
                    "url": url,
                    "status": r.status_code,
                    "content_type": r.headers.get("content-type"),
                    "content_length": r.headers.get("content-length"),
                }
                attempts.append(attempt)
                if r.status_code != 200:
                    continue
                with target.open("wb") as f:
                    for chunk in r.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                if target.stat().st_size <= 2880:
                    target.unlink(missing_ok=True)
                    continue
                return {
                    "segment": name,
                    "path": str(target),
                    "bytes": target.stat().st_size,
                    "sha256": sha256_file(target),
                    "url": url,
                    "attempts": attempts,
                }
        except Exception as exc:
            attempts.append({"candidate": i, "url": url, "error": repr(exc)})
    raise RuntimeError(f"unable to download segment {name}: {attempts}")


def load_fits_array(path: Path) -> tuple[np.ndarray, dict[str, Any]]:
    with fits.open(path, memmap=False) as hdul:
        data = np.asarray(hdul[0].data, dtype=np.float64)
        header = hdul[0].header
        meta = {
            "shape": list(data.shape),
            "bitpix": int(header.get("BITPIX", 0)),
            "bunit": header.get("BUNIT"),
            "ctype1": header.get("CTYPE1"),
            "ctype2": header.get("CTYPE2"),
            "crpix1": header.get("CRPIX1"),
            "crpix2": header.get("CRPIX2"),
            "crval1": header.get("CRVAL1"),
            "crval2": header.get("CRVAL2"),
            "cdelt1": header.get("CDELT1"),
            "cdelt2": header.get("CDELT2"),
        }
    if data.ndim != 2:
        raise RuntimeError(f"expected 2-D FITS array at {path}, got {data.shape}")
    return data, meta


def finite_mean(x: np.ndarray, mask: np.ndarray) -> float:
    vals = x[mask]
    if vals.size == 0:
        return float("nan")
    return float(np.mean(vals, dtype=np.float64))


def compute_metrics(
    bx_g: np.ndarray,
    by_g: np.ndarray,
    bz_g: np.ndarray,
    mask: np.ndarray,
    dx_m: float,
) -> dict[str, float]:
    # Local Cartesian convention locked for this adapter probe:
    # x = +phi (westward), y = -theta (northward), z = +r (outward).
    # Thus Bx = Bp, By = -Bt, Bz = Br.
    dby_dx = np.gradient(by_g, dx_m, axis=1, edge_order=2)
    dbx_dy = np.gradient(bx_g, dx_m, axis=0, edge_order=2)
    curlz_g_per_m = dby_dx - dbx_dy
    hc = bz_g * curlz_g_per_m

    m = mask & np.isfinite(curlz_g_per_m) & np.isfinite(hc)
    n = int(np.count_nonzero(m))
    if n == 0:
        raise RuntimeError("no finite high-confidence HARP pixels after derivatives")

    bz2 = float(np.sum(np.square(bz_g[m]), dtype=np.float64))
    curl2 = float(np.sum(np.square(curlz_g_per_m[m]), dtype=np.float64))
    cross = float(np.sum(hc[m], dtype=np.float64))
    denom = math.sqrt(max(bz2 * curl2, 0.0))
    alpha_per_m = cross / bz2 if bz2 > 0 else float("nan")

    energy = np.square(bx_g) + np.square(by_g) + np.square(bz_g)
    unsigned_hc = np.abs(hc)
    return {
        "mask_count": n,
        "mean_current_helicity_G2_per_m": finite_mean(hc, m),
        "mean_unsigned_current_helicity_G2_per_m": finite_mean(unsigned_hc, m),
        "normalized_current_helicity": cross / denom if denom > 0 else float("nan"),
        "alpha_weighted_per_Mm": alpha_per_m * 1.0e6,
        "mean_energy_proxy_G2": finite_mean(energy, m),
        "rms_Br_G": float(np.sqrt(finite_mean(np.square(bz_g), m))),
        "rms_Bh_G": float(np.sqrt(finite_mean(np.square(bx_g) + np.square(by_g), m))),
        "polarity_balance": float(np.sum(bz_g[m], dtype=np.float64) / np.sum(np.abs(bz_g[m]), dtype=np.float64)),
    }


def sign_or_zero(x: float, atol: float = 1e-15) -> int:
    if not math.isfinite(x) or abs(x) <= atol:
        return 0
    return 1 if x > 0 else -1


def rel_delta(a: float, b: float) -> float:
    scale = max(abs(a), abs(b), 1e-30)
    return abs(a - b) / scale


def main() -> int:
    client = drms.Client()
    key, seg = client.query(QUERY, key=",".join(KEYS), seg=",".join(SEGMENTS))
    if len(key) != 1 or len(seg) != 1:
        raise RuntimeError(f"query must resolve to exactly one record; got {len(key)}")
    row = key.reset_index(drop=True).iloc[0].to_dict()
    segrow = seg.reset_index(drop=True).iloc[0].to_dict()
    if int(row.get("QUALITY", -1)) != 0:
        raise RuntimeError(f"development record QUALITY must be 0; got {row.get('QUALITY')}")

    downloads = {name: download_segment(name, str(segrow[name])) for name in SEGMENTS}
    arrays: dict[str, np.ndarray] = {}
    fits_meta: dict[str, Any] = {}
    for name in SEGMENTS:
        arr, meta = load_fits_array(Path(downloads[name]["path"]))
        arrays[name] = arr
        fits_meta[name] = meta
    shapes = {name: tuple(arr.shape) for name, arr in arrays.items()}
    if len(set(shapes.values())) != 1:
        raise RuntimeError(f"segment shape mismatch: {shapes}")

    br = arrays["Br"]
    bt = arrays["Bt"]
    bp = arrays["Bp"]
    conf = arrays["conf_disambig"]
    bitmap = arrays["bitmap"]
    base_mask = (
        np.isfinite(br)
        & np.isfinite(bt)
        & np.isfinite(bp)
        & (bitmap >= 33)
        & (conf == 90)
    )

    cdelt1_deg = abs(float(row["CDELT1"]))
    rsun_ref_m = float(row["RSUN_REF"])
    dx_m = rsun_ref_m * math.radians(cdelt1_deg)
    if not (math.isfinite(dx_m) and dx_m > 0):
        raise RuntimeError(f"invalid physical pixel scale: {dx_m}")

    bx = bp.copy()
    by = -bt.copy()
    bz = br.copy()
    observed = compute_metrics(bx, by, bz, base_mask, dx_m)

    # Improper reflection x -> -x. Magnetic B is an axial vector:
    # B' = det(R) R B = (Bx, -By, -Bz) after array reflection.
    parity = compute_metrics(
        np.fliplr(bx),
        -np.fliplr(by),
        -np.fliplr(bz),
        np.fliplr(base_mask),
        dx_m,
    )
    # Global field reversal, expected to preserve Bz * curl(B)_z.
    field_reversal = compute_metrics(-bx, -by, -bz, base_mask, dx_m)
    # Proper pi rotation about z, expected to preserve pseudoscalar helicity.
    rotation_pi = compute_metrics(
        -np.flipud(np.fliplr(bx)),
        -np.flipud(np.fliplr(by)),
        np.flipud(np.fliplr(bz)),
        np.flipud(np.fliplr(base_mask)),
        dx_m,
    )

    h0 = observed["mean_current_helicity_G2_per_m"]
    e0 = observed["mean_energy_proxy_G2"]
    symmetry = {
        "parity_helicity_sign_flip": sign_or_zero(parity["mean_current_helicity_G2_per_m"]) == -sign_or_zero(h0),
        "parity_helicity_relative_antisymmetry": rel_delta(parity["mean_current_helicity_G2_per_m"], -h0),
        "parity_energy_relative_invariance": rel_delta(parity["mean_energy_proxy_G2"], e0),
        "field_reversal_helicity_relative_invariance": rel_delta(field_reversal["mean_current_helicity_G2_per_m"], h0),
        "field_reversal_energy_relative_invariance": rel_delta(field_reversal["mean_energy_proxy_G2"], e0),
        "rotation_pi_helicity_relative_invariance": rel_delta(rotation_pi["mean_current_helicity_G2_per_m"], h0),
        "rotation_pi_energy_relative_invariance": rel_delta(rotation_pi["mean_energy_proxy_G2"], e0),
    }

    metadata_meanjzh = float(row["MEANJZH"])
    metadata_meanalp = float(row["MEANALP"])
    metadata_checks = {
        "cmask_keyword": int(row["CMASK"]),
        "computed_high_confidence_mask_count": int(np.count_nonzero(base_mask)),
        "cmask_exact_match": int(row["CMASK"]) == int(np.count_nonzero(base_mask)),
        "MEANJZH_keyword_G2_per_m": metadata_meanjzh,
        "MEANJZH_recomputed_G2_per_m": h0,
        "MEANJZH_sign_match": sign_or_zero(metadata_meanjzh) == sign_or_zero(h0),
        "MEANJZH_relative_difference": rel_delta(metadata_meanjzh, h0),
        "MEANALP_keyword_per_Mm": metadata_meanalp,
        "MEANALP_recomputed_weighted_per_Mm": observed["alpha_weighted_per_Mm"],
        "MEANALP_sign_match": sign_or_zero(metadata_meanalp) == sign_or_zero(observed["alpha_weighted_per_Mm"]),
        "MEANALP_relative_difference": rel_delta(metadata_meanalp, observed["alpha_weighted_per_Mm"]),
    }

    toler = 5e-10
    required_symmetry = [
        symmetry["parity_helicity_sign_flip"],
        symmetry["parity_helicity_relative_antisymmetry"] <= toler,
        symmetry["parity_energy_relative_invariance"] <= toler,
        symmetry["field_reversal_helicity_relative_invariance"] <= toler,
        symmetry["field_reversal_energy_relative_invariance"] <= toler,
        symmetry["rotation_pi_helicity_relative_invariance"] <= toler,
        symmetry["rotation_pi_energy_relative_invariance"] <= toler,
    ]
    adapter_supported = bool(
        all(required_symmetry)
        and metadata_checks["cmask_exact_match"]
        and metadata_checks["MEANJZH_sign_match"]
        and metadata_checks["MEANALP_sign_match"]
    )

    report = {
        "format": "KCH_HELICAL_V1_3_DIRECT_FIELD_OBSERVABILITY_PROBE",
        "scope": "DEVELOPMENT_ONLY_ADAPTER_OBSERVABILITY_NO_CONFIRMATORY_SCORING",
        "query": QUERY,
        "record": row,
        "coordinate_convention": {
            "x": "+phi / westward",
            "y": "-theta / northward",
            "z": "+r / outward",
            "Bx": "Bp",
            "By": "-Bt",
            "Bz": "Br",
            "pixel_scale_m": dx_m,
            "derivative": "numpy.gradient second-order edges on CEA grid",
        },
        "mask_contract": "bitmap>=33 AND conf_disambig==90 AND finite(Br,Bt,Bp)",
        "downloads": downloads,
        "fits_metadata": fits_meta,
        "metrics": {
            "observed": observed,
            "x_parity_reflection": parity,
            "global_field_reversal": field_reversal,
            "proper_rotation_pi_about_z": rotation_pi,
        },
        "symmetry_tests": symmetry,
        "metadata_reconciliation": metadata_checks,
        "adapter_supported": adapter_supported,
        "outcome": "DIRECT_FIELD_ADAPTER_OBSERVABILITY_PASS" if adapter_supported else "DIRECT_FIELD_ADAPTER_NOT_YET_RECONCILED",
        "scientific_result": None,
        "fresh_2026_holdout_accessed": False,
        "physical_helicity": "NOT_EVALUATED",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
        "authority_ceiling": "NONE",
    }
    canonical = json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    report["receipt_id"] = "h13field:" + hashlib.sha256(canonical).hexdigest()
    out = OUT / "DIRECT_FIELD_OBSERVABILITY_PROBE_V1_3.json"
    out.write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n")
    print(json.dumps({
        "outcome": report["outcome"],
        "receipt_id": report["receipt_id"],
        "query": QUERY,
        "mask_count": observed["mask_count"],
        "cmask": int(row["CMASK"]),
        "MEANJZH_keyword": metadata_meanjzh,
        "MEANJZH_recomputed": h0,
        "MEANALP_keyword": metadata_meanalp,
        "MEANALP_recomputed": observed["alpha_weighted_per_Mm"],
        "symmetry_tests": symmetry,
    }, sort_keys=True, indent=2))

    # Raw FITS are ephemeral by policy; leave only the aggregate receipt for artifact export.
    for name in SEGMENTS:
        Path(downloads[name]["path"]).unlink(missing_ok=True)
    return 0 if adapter_supported else 30


if __name__ == "__main__":
    raise SystemExit(main())
