from __future__ import annotations

import argparse
import hashlib
import json
import runpy
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

COHORTS = ["BAY_AREA", "PARKFIELD_CENTRAL_SAF"]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--preflight-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args, passthrough = parser.parse_known_args()
    args.out.mkdir(parents=True, exist_ok=True)

    frames = {
        cohort: pd.read_csv(args.preflight_root / "assigned" / f"{cohort}.csv.gz", low_memory=False)
        for cohort in COHORTS
    }
    memberships: dict[str, list[str]] = {}
    for cohort, frame in frames.items():
        for event_id in frame["event_id"].astype(str):
            memberships.setdefault(event_id, []).append(cohort)
    overlaps = sorted(event_id for event_id, regions in memberships.items() if len(set(regions)) > 1)
    overlap_set = set(overlaps)
    filtered_counts = {
        cohort: int((~frame["event_id"].astype(str).isin(overlap_set)).sum())
        for cohort, frame in frames.items()
    }
    body = {
        "format": "KCH_SEISMIC_COHORT_OVERLAP_ABSTENTION_RECEIPT_V1_1",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "cohorts": COHORTS,
        "overlapping_event_count": len(overlaps),
        "overlapping_event_ids_sha256": sha256_bytes(("\n".join(overlaps) + "\n").encode("utf-8")),
        "policy": "ABSTAIN_OVERLAPPING_EVENT_FROM_ALL_PRIMARY_COHORTS",
        "policy_selected_before_directional_product_access": True,
        "event_cloud_geometry_used_to_resolve_overlap": False,
        "directional_fields_used_to_resolve_overlap": False,
        "rows_before": {cohort: int(len(frame)) for cohort, frame in frames.items()},
        "rows_after": filtered_counts,
        "authority_ceiling": "NONE",
    }
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    body["receipt_id"] = "s11overlap:" + sha256_bytes(canonical)
    (args.out / "COHORT_OVERLAP_ABSTENTION_RECEIPT.json").write_text(
        json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    original_read_csv = pd.read_csv
    original_to_datetime = pd.to_datetime

    def filtered_read_csv(path, *positional, **kwargs):
        frame = original_read_csv(path, *positional, **kwargs)
        candidate = Path(str(path))
        if candidate.name in {f"{cohort}.csv.gz" for cohort in COHORTS} and candidate.parent.name == "assigned":
            frame = frame[~frame["event_id"].astype(str).isin(overlap_set)].copy()
        return frame

    def mixed_to_datetime(arg, *positional, **kwargs):
        kwargs.setdefault("format", "mixed")
        return original_to_datetime(arg, *positional, **kwargs)

    pd.read_csv = filtered_read_csv
    pd.to_datetime = mixed_to_datetime
    sys.argv = [
        str(args.script),
        "--preflight-root", str(args.preflight_root),
        "--out", str(args.out),
        *passthrough,
    ]
    try:
        runpy.run_path(str(args.script), run_name="__main__")
    except SystemExit as exc:
        return int(exc.code or 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
