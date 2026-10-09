#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--payload-dir", required=True, type=Path)
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--output-dir", required=True, type=Path)
    ap.add_argument("--receipt", required=True, type=Path)
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    parts = sorted(args.payload_dir.glob("part_*"))
    expected_names = [row["name"] for row in manifest["chunks"]]
    observed_names = [p.name for p in parts]
    if observed_names != expected_names:
        raise RuntimeError(f"chunk set mismatch: observed={observed_names!r}")

    chunks: list[str] = []
    chunk_receipts = []
    for path, expected in zip(parts, manifest["chunks"], strict=True):
        text = path.read_text(encoding="ascii")
        digest = sha256_bytes(text.encode("ascii"))
        if len(text) != int(expected["chars"]) or digest != expected["sha256"]:
            raise RuntimeError(f"chunk integrity failure: {path.name}")
        chunks.append(text)
        chunk_receipts.append({"name": path.name, "chars": len(text), "sha256": digest})

    joined = "".join(chunks)
    if len(joined) != int(manifest["base64_chars"]):
        raise RuntimeError("base64 character count mismatch")
    gz = base64.b64decode(joined, validate=True)
    if len(gz) != int(manifest["gzip_bytes"]) or sha256_bytes(gz) != manifest["gzip_sha256"]:
        raise RuntimeError("gzip transport integrity mismatch")
    zip_bytes = gzip.decompress(gz)
    if len(zip_bytes) != int(manifest["source_zip_bytes"]) or sha256_bytes(zip_bytes) != manifest["source_zip_sha256"]:
        raise RuntimeError("source ZIP integrity mismatch")

    if args.output_dir.exists():
        shutil.rmtree(args.output_dir)
    args.output_dir.mkdir(parents=True)
    zip_path = args.output_dir / manifest["source_zip"]
    atomic_write(zip_path, zip_bytes)

    extract_root = args.output_dir / "extracted"
    extract_root.mkdir()
    with zipfile.ZipFile(zip_path) as zf:
        bad = zf.testzip()
        if bad is not None:
            raise RuntimeError(f"ZIP CRC failure at {bad}")
        infos = zf.infolist()
        for info in infos:
            candidate = (extract_root / info.filename).resolve()
            if extract_root.resolve() not in candidate.parents and candidate != extract_root.resolve():
                raise RuntimeError(f"unsafe ZIP path: {info.filename}")
        zf.extractall(extract_root)

    roots = [p for p in extract_root.iterdir() if p.is_dir()]
    if len(roots) != 1:
        raise RuntimeError(f"expected one package root, observed {len(roots)}")
    package_root = roots[0]
    required = [
        package_root / "runtime" / "RUN_EXACT_BYTE_TO_BLIND_GATE_V0_9.py",
        package_root / "source_lock" / "HELICAL_DYNAMIC_MARKED_POINT_PROCESS_GATE_V0_8_LOCKED.json",
        package_root / "requirements-runtime.txt",
    ]
    if not all(p.is_file() for p in required):
        raise RuntimeError("reconstructed capsule lacks required runtime files")

    receipt = {
        "format": "KCH_HELICAL_V09_REMOTE_TRANSPORT_RECONSTRUCTION_R2",
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": sha256_file(args.manifest),
        "chunk_count": len(parts),
        "chunks": chunk_receipts,
        "gzip_bytes": len(gz),
        "gzip_sha256": sha256_bytes(gz),
        "zip_bytes": len(zip_bytes),
        "zip_sha256": sha256_bytes(zip_bytes),
        "zip_member_count": len(infos),
        "zip_crc_pass": True,
        "package_root": str(package_root),
        "scientific_protocol_changed": False,
        "authority_ceiling": "NONE",
        "promotion": "BLOCKED",
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(args.receipt, (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode())
    print(package_root)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
