from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
from collections import Counter
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def parse_origin(tokens: list[str]) -> datetime:
    year, month, day, hour, minute = map(int, tokens[:5])
    sec = Decimal(tokens[5])
    whole = int(sec)
    micros = int((sec - Decimal(whole)) * Decimal(1_000_000))
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc) + timedelta(
        seconds=whole, microseconds=micros
    )


def collapse_duplicates(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    buckets: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = (
            iso(row["origin"]),
            Decimal(row["tokens"][7]),
            Decimal(row["tokens"][8]),
            Decimal(row["tokens"][9]),
        )
        buckets.setdefault(key, []).append(row)
    kept: list[dict[str, Any]] = []
    removed = 0
    for key in sorted(buckets):
        group = buckets[key]
        group.sort(
            key=lambda r: (
                -r["magnitude"],
                int(r["event_id"]) if r["event_id"].isdigit() else math.inf,
                r["event_id"],
            )
        )
        kept.append(group[0])
        removed += len(group) - 1
    kept.sort(key=lambda r: (r["origin"], r["event_id"], r["line_no"]))
    return kept, removed


THINNING_CONTRACT = {
    "strata": 100,
    "stratum_definition": "EQUAL_COUNT_CHRONOLOGICAL_RANK_QUANTILES",
    "global_extremes_forced": True,
    "within_stratum_rank": "SHA256_UTF8_EVENT_ID_ASCENDING_THEN_ORIGIN_THEN_LINE_NUMBER",
    "allocation": "PROPORTIONAL_LARGEST_REMAINDER_WITH_ONE_PER_NONEMPTY_STRATUM",
}


def deterministic_thin(
    rows: list[dict[str, Any]], limit: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    n = len(rows)
    if n <= limit:
        return rows, {
            "applied": False,
            "input_events": n,
            "output_events": n,
            **THINNING_CONTRACT,
        }

    strata_count = min(int(THINNING_CONTRACT["strata"]), n)
    strata: list[list[dict[str, Any]]] = [[] for _ in range(strata_count)]
    for rank, row in enumerate(rows):
        idx = min(strata_count - 1, (rank * strata_count) // n)
        strata[idx].append(row)

    base = [1 if stratum else 0 for stratum in strata]
    remaining = limit - sum(base)
    eligible = [max(0, len(stratum) - base[i]) for i, stratum in enumerate(strata)]
    total_eligible = sum(eligible)
    quotas = [0.0 if total_eligible == 0 else remaining * count / total_eligible for count in eligible]
    extra = [min(eligible[i], int(math.floor(quotas[i]))) for i in range(strata_count)]
    left = remaining - sum(extra)
    order = sorted(
        range(strata_count),
        key=lambda i: (-(quotas[i] - math.floor(quotas[i])), i),
    )
    for i in order:
        if left <= 0:
            break
        if extra[i] < eligible[i]:
            extra[i] += 1
            left -= 1
    allocation = [base[i] + extra[i] for i in range(strata_count)]

    forced_line_numbers = {rows[0]["line_no"], rows[-1]["line_no"]}
    selected: list[dict[str, Any]] = []
    for i, stratum in enumerate(strata):
        ranked = sorted(
            stratum,
            key=lambda r: (
                0 if r["line_no"] in forced_line_numbers else 1,
                hashlib.sha256(r["event_id"].encode("utf-8")).hexdigest(),
                r["origin"],
                r["line_no"],
            ),
        )
        selected.extend(ranked[: allocation[i]])
    selected = sorted(
        {row["line_no"]: row for row in selected}.values(),
        key=lambda r: (r["origin"], r["event_id"], r["line_no"]),
    )
    if len(selected) != limit:
        raise RuntimeError(f"thinning produced {len(selected)} rows, expected {limit}")
    return selected, {
        "applied": True,
        "input_events": n,
        "output_events": len(selected),
        "allocation": allocation,
        **THINNING_CONTRACT,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--curl-json", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    (out / "windows").mkdir(exist_ok=True)
    (out / "audit").mkdir(exist_ok=True)

    protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    payload = args.source.read_bytes()
    if not payload:
        raise SystemExit("empty source payload")
    prefix = payload[:4096].lstrip().lower()
    if prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html") or b"<body" in prefix:
        raise SystemExit("HTML received instead of catalog")
    if b"\x00" in payload:
        raise SystemExit("NUL byte found in provider payload")
    text = payload.decode("utf-8", errors="strict")
    raw_lines = text.splitlines()

    curl_meta = json.loads(args.curl_json.read_text(encoding="utf-8"))
    response_code = int(curl_meta.get("response_code", 0))
    size_download = int(float(curl_meta.get("size_download", -1)))
    if response_code != 200:
        raise SystemExit(f"HTTP response {response_code}")
    if size_download != len(payload):
        raise SystemExit(f"curl size_download {size_download} != local size {len(payload)}")

    field_hist: Counter[int] = Counter()
    tail4_hist: Counter[str] = Counter()
    solution_hist: Counter[str] = Counter()
    event_type_hist: Counter[str] = Counter()
    magnitude_type_hist: Counter[str] = Counter()
    malformed: list[dict[str, Any]] = []
    parsed: list[dict[str, Any]] = []

    for line_no, raw in enumerate(raw_lines, start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        tokens = raw.split()
        field_hist[len(tokens)] += 1
        if len(tokens) >= 4:
            tail4_hist[" ".join(tokens[-4:])] += 1
        try:
            if len(tokens) < 19:
                raise ValueError("fewer than 19 fields")
            origin = parse_origin(tokens)
            event_id = tokens[6]
            lat = float(tokens[7])
            lon = float(tokens[8])
            depth = float(tokens[9])
            magnitude = float(tokens[10])
            event_type = tokens[-4]
            magnitude_type = tokens[-3]
            solution = tokens[-2]
            relocation_box = tokens[-1]
            if event_type not in {"le", "re", "qb"}:
                raise ValueError(f"unrecognized event type {event_type!r}")
            if solution not in {"1d", "3d", "gc"}:
                raise ValueError(f"un