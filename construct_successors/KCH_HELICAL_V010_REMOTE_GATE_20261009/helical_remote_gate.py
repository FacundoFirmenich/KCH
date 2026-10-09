from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import pickletools
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterable, Mapping
import urllib.parse
import urllib.request

import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString, MultiLineString, Point, shape
from shapely.strtree import STRtree

VERSION = "0.10.0"
PROTOCOL_ID = "h8p:99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f"
PROTOCOL_SEMANTIC_SHA256 = "99c4816147023000b8fd3b1c386a0b1b35fb232b33782875477f3b46f7a1542f"
DATASET_ID = "2np9vw5v7w"
DATASET_VERSION = 2
DOI = "10.17632/2np9vw5v7w.2"
MECHANISM_BASENAME = "focmec_ca_final.pickle"
SNAPSHOT_URL = f"https://api.data.mendeley.com/datasets/{DATASET_ID}?version={DATASET_VERSION}"
FAULT_REPOSITORY = "GEMScienceTools/gem-global-active-faults"
FAULT_COMMIT = "56816508ad92fd6846dad1163b1c8c01376a2cd1"
FAULT_PATH = "geojson/gem_active_faults_harmonized.geojson"
FAULT_BASENAME = "gem_active_faults_harmonized.geojson"
FAULT_URL = f"https://raw.githubusercontent.com/{FAULT_REPOSITORY}/{FAULT_COMMIT}/{FAULT_PATH}"
FAULT_GIT_BLOB_SHA1 = "fb164770b529695544fa864abe2cc9dd8aa5793d"
FAULT_BYTES = 10_622_730
ALLOWED = {
    "nc_sc", "ev_bl", "year", "month", "day", "hour", "minute", "second",
    "time_utc", "evid", "lat_reloc", "lon_reloc", "dep_reloc", "mag", "uncer", "npol", "prob",
}
SEALED = {
    "strike", "dip", "rake", "strike_orig", "dip_orig", "rake_orig",
    "ftype", "p_azi", "p_dip", "t_azi", "t_dip",
}
NUMERIC = {
    "year", "month", "day", "hour", "minute", "second", "lat_reloc", "lon_reloc",
    "dep_reloc", "mag", "uncer", "npol", "prob",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def cid(prefix: str, value: Any) -> str:
    return prefix + ":" + hashlib.sha256(canonical(value)).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def git_blob_sha1(path: Path) -> str:
    size = path.stat().st_size
    h = hashlib.sha1()
    h.update(f"blob {size}\0".encode("ascii"))
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def safe_url(url: str) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(url)
    return {
        "scheme": parsed.scheme,
        "host": parsed.hostname,
        "path": parsed.path,
        "query_keys": sorted(urllib.parse.parse_qs(parsed.query, keep_blank_values=True)),
        "query_values_recorded": False,
    }


def request_json(url: str, timeout: int) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.mendeley-public-dataset.1+json,application/json",
        "Accept-Encoding": "identity",
        "User-Agent": "KCH-Helical-Lift/0.10 exact-byte gate",
    })
    started = time.monotonic()
    with urllib.request.urlopen(req, timeout=timeout) as response:
        raw = response.read(64 * 1024 * 1024 + 1)
        if len(raw) > 64 * 1024 * 1024:
            raise RuntimeError("metadata response exceeds 64 MiB")
        receipt = {
            "requested": safe_url(url),
            "effective": safe_url(response.geturl()),
            "status": int(response.status),
            "content_type": response.headers.get("Content-Type"),
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "elapsed_seconds": time.monotonic() - started,
        }
    return json.loads(raw.decode("utf-8")), receipt, raw


def stream_download(url: str, output: Path, timeout: int, expected_bytes: int | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={
        "Accept": "application/octet-stream,*/*",
        "Accept-Encoding": "identity",
        "User-Agent": "KCH-Helical-Lift/0.10 exact-byte gate",
    })
    started = time.monotonic()
    h = hashlib.sha256()
    total = 0
    tmp = output.with_suffix(output.suffix + ".part")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(req, timeout=timeout) as response, tmp.open("wb") as handle:
        while True:
            block = response.read(8 * 1024 * 1024)
            if not block:
                break
            handle.write(block)
            h.update(block)
            total += len(block)
        handle.flush()
        os.fsync(handle.fileno())
        if expected_bytes is not None and total != expected_bytes:
            raise RuntimeError(f"byte count mismatch for {output.name}: {total} != {expected_bytes}")
        receipt = {
            "requested": safe_url(url),
            "effective": safe_url(response.geturl()),
            "status": int(response.status),
            "content_type": response.headers.get("Content-Type"),
            "content_length_header": response.headers.get("Content-Length"),
            "etag": response.headers.get("ETag"),
            "last_modified": response.headers.get("Last-Modified"),
            "bytes": total,
            "sha256": h.hexdigest(),
            "elapsed_seconds": time.monotonic() - started,
        }
    os.replace(tmp, output)
    return receipt


def walk_files(value: Any) -> list[dict[str, Any]]:
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    def visit(node: Any) -> None:
        if isinstance(node, dict):
            filename = node.get("filename") or node.get("file_name") or node.get("name")
            file_id = node.get("id") or node.get("uuid") or node.get("file_id")
            if filename and file_id:
                key = (str(filename), str(file_id))
                rows[key] = {"filename": str(filename), "file_id": str(file_id), "raw": node}
            for child in node.values():
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)
    visit(value)
    return list(rows.values())


def unique_int(node: Any, keys: set[str]) -> int | None:
    found: set[int] = set()
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in keys:
                    try:
                        n = int(child)
                        if n > 0:
                            found.add(n)
                    except Exception:
                        pass
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(node)
    return next(iter(found)) if len(found) == 1 else None


def unique_sha256(node: Any) -> str | None:
    found: set[str] = set()
    keys = {"sha256", "sha_256", "sha256_hash", "checksum_sha256"}
    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if str(key).lower() in keys and isinstance(child, str):
                    candidate = child.lower().removeprefix("sha256:")
                    if len(candidate) == 64 and all(c in "0123456789abcdef" for c in candidate):
                        found.add(candidate)
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(node)
    return next(iter(found)) if len(found) == 1 else None


def audit_protocol(path: Path) -> tuple[dict[str, Any], dict[str, str]]:
    raw = path.read_bytes()
    protocol = json.loads(raw.decode("utf-8"))
    stripped = dict(protocol)
    protocol_id = stripped.pop("protocol_id")
    declared = stripped.pop("protocol_sha256")
    observed = hashlib.sha256(canonical(stripped)).hexdigest()
    if protocol_id != PROTOCOL_ID or declared != PROTOCOL_SEMANTIC_SHA256 or observed != PROTOCOL_SEMANTIC_SHA256:
        raise RuntimeError("frozen protocol semantic identity mismatch")
    if protocol.get("status") != "LOCKED_BEFORE_REAL_MECHANISM_ANGLE_ACCESS":
        raise RuntimeError("protocol lock state mismatch")
    return protocol, {
        "protocol_id": protocol_id,
        "protocol_semantic_sha256": observed,
        "protocol_file_sha256": hashlib.sha256(raw).hexdigest(),
    }


def write_extractor(directory: Path) -> tuple[Path, Path]:
    extractor = directory / "extractor.py"
    dockerfile = directory / "Dockerfile"
    extractor.write_text(r'''from __future__ import annotations
import hashlib, json, os, pickle, pickletools, sys
from pathlib import Path
from typing import Any, Mapping
import numpy as np
ALLOWED = {"nc_sc","ev_bl","year","month","day","hour","minute","second","time_utc","evid","lat_reloc","lon_reloc","dep_reloc","mag","uncer","npol","prob"}
NUMERIC = {"year","month","day","hour","minute","second","lat_reloc","lon_reloc","dep_reloc","mag","uncer","npol","prob"}
def sha(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(8*1024*1024),b""): h.update(b)
    return h.hexdigest()
def mapping(root: Any) -> Mapping[str,Any]:
    if isinstance(root,Mapping): return root
    if hasattr(root,"to_dict"):
        value=root.to_dict()
        if isinstance(value,Mapping): return value
    raise TypeError(type(root).__name__)
def vector(name: str, value: Any) -> np.ndarray:
    a=np.asarray(value)
    if a.ndim==0: a=a.reshape(1)
    if a.ndim!=1: raise ValueError(f"{name}: expected 1-D, got {a.shape}")
    if name in NUMERIC:
        a=np.asarray(a,dtype=np.float64)
        if not np.all(np.isfinite(a)): raise ValueError(f"{name}: non-finite")
        return a
    return np.asarray([str(x) for x in a],dtype=np.str_)
def main() -> int:
    source=Path(sys.argv[1]); out=Path(sys.argv[2]); expected=sys.argv[3]
    if sha(source)!=expected: raise SystemExit("source hash mismatch")
    opcode_count=0
    with source.open("rb") as f:
        for _ in pickletools.genops(f): opcode_count += 1
    with source.open("rb") as f: root=pickle.load(f)
    m=mapping(root)
    missing=sorted(ALLOWED-set(m))
    if missing: raise KeyError(f"missing allowed fields: {missing}")
    arrays={name:vector(name,m[name]) for name in sorted(ALLOWED)}
    lengths={name:int(len(value)) for name,value in arrays.items()}
    distinct=sorted(set(lengths.values()))
    if len(distinct)!=1: raise ValueError(f"length mismatch: {lengths}")
    out.mkdir(parents=True,exist_ok=True)
    target=out/"blind_columns.npz"; tmp=out/"blind_columns.tmp.npz"
    np.savez_compressed(tmp,**arrays); os.replace(tmp,target)
    with np.load(target,allow_pickle=False) as loaded:
        if set(loaded.files)!=set(arrays): raise ValueError("NPZ field mismatch")
        for name in loaded.files:
            a=loaded[name]
            if a.dtype.kind=="O" or a.dtype.hasobject or a.ndim!=1: raise ValueError(f"unsafe {name}")
    receipt={"format":"KCH_HELICAL_V010_ISOLATED_EXTRACTION","source_sha256":expected,"source_bytes":source.stat().st_size,"output_sha256":sha(target),"output_bytes":target.stat().st_size,"event_count":distinct[0],"fields":sorted(arrays),"sealed_fields_emitted":[],"angle_fields_accessed_for_selection":False,"pickle_opcode_count":opcode_count,"network_available":False,"authority_ceiling":"NONE","promotion":"BLOCKED"}
    receipt["receipt_id"]="h10extract:"+hashlib.sha256(json.dumps(receipt,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    (out/"EXTRACTION_RECEIPT_V0_10.json").write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    return 0
if __name__=="__main__": raise SystemExit(main())
''', encoding="utf-8")
    dockerfile.write_text(
        "FROM python:3.11-slim\n"
        "RUN python -m pip install --no-cache-dir numpy==2.1.3\n"
        "COPY extractor.py /opt/extractor.py\n"
        "ENTRYPOINT [\"python\",\"/opt/extractor.py\"]\n",
        encoding="utf-8",
    )
    return extractor, dockerfile


def isolated_extract(mechanism: Path, mechanism_sha: str, output: Path, build_dir: Path) -> dict[str, Any]:
    write_extractor(build_dir)
    image = "kch-helical-v010-extractor:local"
    subprocess.run(["docker", "build", "--pull", "-t", image, str(build_dir)], check=True)
    image_id = subprocess.check_output(["docker", "image", "inspect", "--format", "{{.Id}}", image], text=True).strip()
    output.mkdir(parents=True, exist_ok=True)
    os.chmod(output, 0o777)
    command = [
        "docker", "run", "--rm", "--network", "none", "--read-only",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true",
        "--pids-limit", "128", "--memory", "6g", "--memory-swap", "6g", "--cpus", "2",
        "--user", "65534:65534", "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size=268435456",
        "-v", f"{mechanism.parent}:/input:ro", "-v", f"{output}:/output:rw",
        image, f"/input/{mechanism.name}", "/output", mechanism_sha,
    ]
    started = time.monotonic()
    completed = subprocess.run(command, text=True, capture_output=True)
    isolation = {
        "container_image_id": image_id,
        "network_mode": "none",
        "read_only_root": True,
        "capabilities_dropped": "ALL",
        "no_new_privileges": True,
        "non_root_uid": 65534,
        "returncode": completed.returncode,
        "elapsed_seconds": time.monotonic() - started,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }
    write_json(output / "ISOLATION_RECEIPT_V0_10.json", isolation)
    if completed.returncode != 0:
        raise RuntimeError(f"isolated extraction failed: {completed.stderr[-1000:]}")
    receipt = json.loads((output / "EXTRACTION_RECEIPT_V0_10.json").read_text(encoding="utf-8"))
    if receipt.get("sealed_fields_emitted") != [] or receipt.get("angle_fields_accessed_for_selection") is not False:
        raise RuntimeError("blind extraction barrier violation")
    npz = output / "blind_columns.npz"
    if sha256_file(npz) != receipt.get("output_sha256"):
        raise RuntimeError("safe NPZ hash mismatch")
    with np.load(npz, allow_pickle=False) as loaded:
        if set(loaded.files) != ALLOWED or set(loaded.files) & SEALED:
            raise RuntimeError("safe NPZ allow-list mismatch")
        for name in loaded.files:
            a = loaded[name]
            if a.dtype.kind == "O" or a.dtype.hasobject or a.ndim != 1:
                raise RuntimeError(f"unsafe NPZ array: {name}")
    return {**receipt, "isolation_receipt": isolation}


def flatten_lines(geometry: Any) -> Iterable[LineString]:
    if isinstance(geometry, LineString):
        yield geometry
    elif isinstance(geometry, MultiLineString):
        yield from geometry.geoms


def fault_index(path: Path) -> tuple[tuple[LineString, ...], STRtree, Transformer, int]:
    root = json.loads(path.read_text(encoding="utf-8"))
    transformer = Transformer.from_crs("EPSG:4326", "EPSG:3310", always_xy=True)
    lines: list[LineString] = []
    for feature in root.get("features", []):
        geom = shape(feature.get("geometry"))
        for line in flatten_lines(geom):
            coords = [transformer.transform(x, y) for x, y in line.coords]
            if len(coords) >= 2:
                lines.append(LineString(coords))
    if not lines:
        raise RuntimeError("fault GeoJSON has no line geometries")
    values = tuple(lines)
    return values, STRtree(values), transformer, len(root.get("features", []))


def parse_times(columns: Mapping[str, np.ndarray]) -> np.ndarray:
    raw = columns["time_utc"]
    values: list[float] = []
    ok = True
    for value in raw:
        try:
            text = str(value).replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            values.append(dt.timestamp())
        except Exception:
            ok = False
            break
    if ok:
        return np.asarray(values, dtype=float)
    values = []
    for parts in zip(columns["year"], columns["month"], columns["day"], columns["hour"], columns["minute"], columns["second"]):
        year, month, day, hour, minute = [int(float(x)) for x in parts[:5]]
        second = float(parts[5]); whole = int(math.floor(second)); micro = int(round((second - whole) * 1_000_000))
        dt = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
        values.append(dt.timestamp() + whole + micro / 1_000_000)
    return np.asarray(values, dtype=float)


def quality_mask(columns: Mapping[str, np.ndarray], protocol: Mapping[str, Any]) -> np.ndarray:
    rule = protocol["blind_eligibility"]["quality_filter"]
    mask = np.ones(len(columns["evid"]), dtype=bool)
    event_type = np.asarray(columns["ev_bl"]).astype(str)
    if rule["earthquake_not_blast"]:
        lowered = np.char.lower(event_type)
        mask &= lowered != "b"
        mask &= lowered != "blast"
    mask &= np.asarray(columns["uncer"], dtype=float) <= float(rule["maximum_mechanism_uncertainty_deg"])
    mask &= np.asarray(columns["npol"], dtype=float) >= float(rule["minimum_number_of_polarities"])
    mask &= np.asarray(columns["prob"], dtype=float) >= float(rule["minimum_solution_probability"])
    lat = np.asarray(columns["lat_reloc"], dtype=float)
    lon = np.asarray(columns["lon_reloc"], dtype=float)
    dep = np.asarray(columns["dep_reloc"], dtype=float)
    mask &= np.isfinite(lat) & np.isfinite(lon) & np.isfinite(dep)
    return mask


def assign_faults(lat: np.ndarray, lon: np.ndarray, lines: tuple[LineString, ...], tree: STRtree, transformer: Transformer, max_km: float, ratio: float) -> np.ndarray:
    assigned = np.full(len(lat), -1, dtype=np.int64)
    for i, (la, lo) in enumerate(zip(lat, lon)):
        x, y = transformer.transform(float(lo), float(la))
        point = Point(x, y)
        candidates = np.asarray(tree.query(point, predicate="dwithin", distance=max_km * 2000.0), dtype=np.int64)
        if len(candidates) == 0:
            continue
        distances = sorted((float(point.distance(lines[int(idx)])) / 1000.0, int(idx)) for idx in candidates)
        d1, idx1 = distances[0]
        d2 = distances[1][0] if len(distances) > 1 else math.inf
        if d1 <= max_km and (math.isinf(d2) or d2 / max(d1, 1e-9) >= ratio):
            assigned[i] = idx1
    return assigned


def eligibility(npz: Path, fault: Path, protocol: Mapping[str, Any], lineage: Mapping[str, Any]) -> dict[str, Any]:
    with np.load(npz, allow_pickle=False) as loaded:
        columns = {name: loaded[name].copy() for name in loaded.files}
    lines, tree, transformer, feature_count = fault_index(fault)
    qmask = quality_mask(columns, protocol)
    lat = np.asarray(columns["lat_reloc"], dtype=float)
    lon = np.asarray(columns["lon_reloc"], dtype=float)
    times = parse_times(columns)
    assignment_rule = protocol["blind_eligibility"]["fault_assignment"]
    rows: list[dict[str, Any]] = []
    for candidate in protocol["candidate_cohorts"]:
        lat_min, lat_max, lon_min, lon_max = map(float, candidate["bbox"])
        indices = np.flatnonzero(qmask & (lat >= lat_min) & (lat <= lat_max) & (lon >= lon_min) & (lon <= lon_max))
        if len(indices):
            assigned = assign_faults(lat[indices], lon[indices], lines, tree, transformer, float(assignment_rule["maximum_distance_km"]), float(assignment_rule["minimum_second_to_first_distance_ratio"])) >= 0
            count = int(np.sum(assigned)); coverage = count / len(indices)
            selected_times = times[indices][assigned]
            span = (float(np.max(selected_times)) - float(np.min(selected_times))) / (365.2425 * 86400.0) if len(selected_times) >= 2 else 0.0
        else:
            count = 0; coverage = 0.0; span = 0.0
        eligible = (
            count >= int(protocol["blind_eligibility"]["minimum_eligible_events"])
            and count * float(protocol["future_only_split"]["sealed_test"]) >= int(protocol["blind_eligibility"]["minimum_test_events"])
            and span >= float(protocol["blind_eligibility"]["minimum_time_span_years"])
            and coverage >= float(protocol["blind_eligibility"]["minimum_fault_assignment_coverage"])
        )
        rows.append({
            "candidate_id": candidate["id"], "role": candidate["role"],
            "quality_and_bbox_count": int(len(indices)),
            "unambiguous_fault_assigned_count": count,
            "fault_assignment_coverage": float(coverage),
            "time_span_years": float(span), "eligible": bool(eligible),
        })
    primary = sorted((r for r in rows if r["role"] == "PRIMARY" and r["eligible"]), key=lambda r: (-r["unambiguous_fault_assigned_count"], r["candidate_id"]))[:3]
    minimum = int(protocol["blind_eligibility"]["minimum_primary_cohorts_to_execute"])
    body = {
        "format": "KCH_HELICAL_V0_10_BLIND_ELIGIBILITY_RESULT",
        "protocol_id": protocol["protocol_id"],
        "angle_fields_accessed": False,
        "sealed_fields": sorted(SEALED),
        "fault_feature_count": feature_count,
        "fault_line_count": len(lines),
        "candidate_results": rows,
        "selected_primary_cohorts": [r["candidate_id"] for r in primary],
        "execution_authorized": len(primary) >= minimum,
        "outcome": "ELIGIBILITY_PASS" if len(primary) >= minimum else "NOT_IDENTIFIABLE_MECHANISM_COVERAGE",
        "lineage": dict(lineage),
        "directional_unsealing_performed": False,
        "model_fitting_performed": False,
        "scientific_execution_performed": False,
        "physical_helicity": "NOT_EVALUATED",
        "authority_ceiling": "NONE",
        "promotion": "BLOCKED",
        "canonicalization": "BLOCKED",
    }
    return {"eligibility_result_id": cid("h10elig", body), **body}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    workspace = args.workspace.resolve(); raw = workspace / "raw"; blind = workspace / "blind"; results = workspace / "results"; build = workspace / "extractor_image"
    for path in (raw, blind, results, build): path.mkdir(parents=True, exist_ok=True)
    started = utc_now(); protocol, protocol_lock = audit_protocol(args.protocol)
    run: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_10_REMOTE_GATE_RECEIPT", "version": VERSION,
        "started_at_utc": started, **protocol_lock,
        "directional_fields_unsealed": False, "model_fitting_performed": False,
        "scientific_execution_performed": False, "physical_helicity": "NOT_EVALUATED",
        "authority_ceiling": "NONE", "promotion": "BLOCKED", "canonicalization": "BLOCKED",
    }
    exit_code = 50
    try:
        snapshot, snapshot_receipt, snapshot_raw = request_json(SNAPSHOT_URL, args.timeout)
        matches = [row for row in walk_files(snapshot) if Path(row["filename"]).name == MECHANISM_BASENAME]
        if len(matches) != 1:
            raise RuntimeError(f"expected one exact mechanism file; observed {len(matches)}")
        match = matches[0]; file_id = match["file_id"]
        expected_bytes = unique_int(match["raw"], {"size", "file_size", "content_length", "bytes"})
        expected_sha = unique_sha256(match["raw"])
        mechanism_url = f"https://api.data.mendeley.com/datasets/{DATASET_ID}/files/{file_id}/file_downloaded?version={DATASET_VERSION}"
        mechanism = raw / MECHANISM_BASENAME; fault = raw / FAULT_BASENAME
        mechanism_receipt = stream_download(mechanism_url, mechanism, args.timeout, expected_bytes)
        if expected_sha and mechanism_receipt["sha256"] != expected_sha:
            raise RuntimeError("mechanism SHA-256 differs from provider declaration")
        fault_receipt = stream_download(FAULT_URL, fault, args.timeout, FAULT_BYTES)
        fault_blob = git_blob_sha1(fault)
        if fault_blob != FAULT_GIT_BLOB_SHA1:
            raise RuntimeError(f"fault Git blob mismatch: {fault_blob}")
        (raw / "mendeley_dataset_snapshot_v2.json").write_bytes(snapshot_raw)
        acquisition = {
            "format": "KCH_HELICAL_V0_10_EXACT_BYTE_ACQUISITION", "outcome": "EXACT_BYTE_ACQUISITION_PASS",
            "all_or_none_pass": True, "transaction_committed": True,
            "dataset": {"id": DATASET_ID, "version": DATASET_VERSION, "doi": DOI, "file_id": file_id, "basename": MECHANISM_BASENAME},
            "provider_expected_bytes": expected_bytes, "provider_expected_sha256": expected_sha,
            "metadata_snapshot": snapshot_receipt, "mechanism": mechanism_receipt,
            "fault": {**fault_receipt, "repository": FAULT_REPOSITORY, "commit": FAULT_COMMIT, "path": FAULT_PATH, "git_blob_sha1": fault_blob},
            **protocol_lock, "directional_fields_accessed": False, "pickle_opened": False,
            "authority_ceiling": "NONE", "promotion": "BLOCKED",
        }
        acquisition["receipt_id"] = cid("h10acq", acquisition)
        write_json(results / "ACQUISITION_RECEIPT_V0_10.json", acquisition)
        extraction = isolated_extract(mechanism, mechanism_receipt["sha256"], blind, build)
        write_json(results / "EXTRACTION_RECEIPT_V0_10.json", extraction)
        lineage = {
            **protocol_lock,
            "acquisition_receipt_id": acquisition["receipt_id"],
            "mechanism_sha256": mechanism_receipt["sha256"],
            "mechanism_bytes": mechanism_receipt["bytes"],
            "fault_sha256": fault_receipt["sha256"],
            "fault_git_blob_sha1": fault_blob,
            "safe_npz_sha256": extraction["output_sha256"],
            "isolated_pickle_boundary": True,
            "direct_pickle_opened_outside_isolation": False,
        }
        result = eligibility(blind / "blind_columns.npz", fault, protocol, lineage)
        write_json(results / "BLIND_ELIGIBILITY_RESULT_V0_10.json", result)
        if result["outcome"] == "ELIGIBILITY_PASS":
            request = {
                "format": "KCH_HELICAL_V0_10_DIRECTIONAL_UNSEAL_REQUEST",
                "eligibility_result_id": result["eligibility_result_id"],
                "selected_primary_cohorts": result["selected_primary_cohorts"],
                "requested_fields": sorted(SEALED),
                "directional_unsealing_performed": False,
                "model_fitting_authorized": False,
                "scientific_interpretation_authorized": False,
                "requires_new_finite_authority": True,
                "requires_new_append_only_successor": True,
                "authority_ceiling": "NONE",
                "promotion": "BLOCKED",
            }
            request["request_id"] = cid("h10unsealreq", request)
            write_json(results / "DIRECTIONAL_UNSEAL_REQUEST_V0_10.json", request)
            exit_code = 0
        else:
            exit_code = 30
        run.update({
            "outcome": result["outcome"], "eligibility_result_id": result["eligibility_result_id"],
            "selected_primary_cohorts": result["selected_primary_cohorts"],
            "exact_mechanism_bytes_materialized": True, "exact_fault_bytes_materialized": True,
            "blind_eligibility_executed": True,
        })
    except Exception as exc:
        run.update({
            "outcome": "REMOTE_GATE_FAILED_CLOSED", "error_type": type(exc).__name__, "error": str(exc),
            "exact_mechanism_bytes_materialized": (raw / MECHANISM_BASENAME).exists(),
            "exact_fault_bytes_materialized": (raw / FAULT_BASENAME).exists(),
            "blind_eligibility_executed": (results / "BLIND_ELIGIBILITY_RESULT_V0_10.json").exists(),
        })
        exit_code = 50
    finally:
        run["completed_at_utc"] = utc_now(); run["raw_sources_purged"] = True; run["exit_code"] = exit_code
        run["run_receipt_id"] = cid("h10run", run)
        write_json(results / "RUN_RECEIPT_V0_10.json", run)
        shutil.rmtree(raw, ignore_errors=True)
        shutil.rmtree(blind, ignore_errors=True)
        shutil.rmtree(build, ignore_errors=True)
        print(json.dumps(run, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
