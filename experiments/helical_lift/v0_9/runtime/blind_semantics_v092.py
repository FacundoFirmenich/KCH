"""Fail-closed input checks; no cohort selection or directional access."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

import numpy as np


def inspect_blind_inputs(columns: Mapping[str, np.ndarray], event_count: int) -> dict[str, Any]:
    issues: list[str] = []
    if event_count <= 0 or any(value.ndim != 1 or len(value) != event_count for value in columns.values()):
        return {"status": "HOLD", "issues": ["EVENT_VECTOR_LENGTH_MISMATCH"]}

    numeric = ("year", "month", "day", "hour", "minute", "second", "lat_reloc",
               "lon_reloc", "dep_reloc", "mag", "uncer", "npol", "prob")
    for name in numeric:
        values = columns[name]
        if values.dtype.kind not in "iuf" or not np.isfinite(values).all():
            issues.append(f"INVALID_NUMERIC_FIELD:{name}")
    if not issues:
        calendar_ok = True
        for name in ("year", "month", "day", "hour", "minute", "npol"):
            if not np.equal(columns[name], np.floor(columns[name])).all():
                issues.append(f"NONINTEGRAL_FIELD:{name}")
                calendar_ok = False
        if not ((columns["second"] >= 0) & (columns["second"] < 60)).all():
            issues.append("UNCERTIFIED_SECOND_RANGE")
            calendar_ok = False
        if calendar_ok:
            # Validate calendar components without truncation or guessed numeric epoch.
            dates = np.unique(np.column_stack([columns[n] for n in ("year", "month", "day")]), axis=0)
            try:
                for year, month, day in dates:
                    datetime(int(year), int(month), int(day))
                if not ((columns["hour"] >= 0) & (columns["hour"] < 24)).all():
                    raise ValueError("hour")
                if not ((columns["minute"] >= 0) & (columns["minute"] < 60)).all():
                    raise ValueError("minute")
            except ValueError:
                issues.append("INVALID_CALENDAR_COMPONENTS")
        if not ((np.abs(columns["lat_reloc"]) <= 90) & (np.abs(columns["lon_reloc"]) <= 180)).all():
            issues.append("INVALID_GEOGRAPHIC_COORDINATES")

    event_type = columns["ev_bl"]
    if event_type.dtype.kind not in "US":
        issues.append("UNCERTIFIED_EVENT_TYPE_ENCODING")
    else:
        # Exact self-describing words, plus the frozen operator's explicit blast label.
        # Do not silently accept numeric strings, missing values or other abbreviations.
        labels = np.char.lower(event_type.astype(str))
        if not np.isin(labels, ["earthquake", "blast", "b"]).all():
            issues.append("UNCERTIFIED_EVENT_TYPE_ENCODING")
    return {
        "status": "PASS" if not issues else "HOLD",
        "issues": issues,
        "event_count": event_count,
        "ev_bl_dtype": event_type.dtype.str,
        "time_utc_dtype": columns["time_utc"].dtype.str,
        "calendar_components_checked": not any("CALENDAR" in i or "NONINTEGRAL" in i or "NUMERIC" in i or "SECOND" in i for i in issues),
        "numeric_time_utc_epoch_inferred": False,
        "cohort_selection_performed": False,
        "rows_deleted": 0,
        "values_imputed": 0,
    }
