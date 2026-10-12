#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
from typing import Any

ALLOWED = {
    "AUTHORITY_LEASE_V0_17.json",
    "README.md",
    "contracts/CONNECTOR_ARTIFACT_SURFACE_ADJUDICATION_V0_16_6.json",
    "contracts/SPEC_DERIVATION_CONTRACT_V0_17.json",
    "freeze_runtime_v017.py",
    "src/kch_helical_null_v017/__init__.py",
    "src/kch_helical_null_v017/runtime.py",
    "tests/test_runtime_v017.py",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def git_blob(repo: Path, relative: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", f"HEAD:{relative}"],
        text=True,
    ).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    manifest_path = args.manifest.resolve()
    output = args.output.resolve()
    receipt_path = args.receipt.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "KCH_HELICAL_V0_17_2_TEXT_CHUNK_MANIFEST":
        raise RuntimeError("unexpected v0.17.2 chunk manifest format")

    chunks: list[bytes] = []
    observations: list[dict[str, Any]] = []
    for index, row in enumerate(manifest["chunks"]):
        relative = str(row["path"])
        path = repo / relative
        data = path.read_bytes()
        observed_sha256 = sha256(data)
        observed_blob = git_blob(repo, relative)
        if len(data) != int(row["bytes"]):
            raise RuntimeError(f"chunk byte-count mismatch at index {index}")
        if observed_sha256 != row["sha256"]:
            raise RuntimeError(f"chunk SHA-256 mismatch at index {index}")
        if observed_blob != row["git_blob_sha1"]:
            raise RuntimeError(f"chunk Git-blob mismatch at index {index}")
        chunks.append(data)
        observations.append(
            {
                "index": index,
                "path": relative,
                "bytes": len(data),
                "sha256": observed_sha256,
                "git_blob_sha1": observed_blob,
            }
        )

    joined = b"".join(chunks)
    if len(joined) != manifest["chunk_bytes_total"]:
        raise RuntimeError("concatenated Base64 byte-count mismatch")
    if sha256(joined) != manifest["concatenated_base64_sha256"]:
        raise RuntimeError("concatenated Base64 SHA-256 mismatch")

    compressed = base64.b64decode(joined, validate=True)
    if len(compressed) != manifest["decoded_gzip_bytes"]:
        raise RuntimeError("decoded gzip byte-count mismatch")
    if sha256(compressed) != manifest["decoded_gzip_sha256"]:
        raise RuntimeError("decoded gzip SHA-256 mismatch")

    raw_tar = gzip.decompress(compressed)
    if len(raw_tar) != manifest["decompressed_tar_bytes"]:
        raise RuntimeError("decompressed TAR byte-count mismatch")
    if sha256(raw_tar) != manifest["decompressed_tar_sha256"]:
        raise RuntimeError("decompressed TAR SHA-256 mismatch")

    output.mkdir(parents=True, exist_ok=True)
    materialized: list[dict[str, Any]] = []
    with tarfile.open(fileobj=io.BytesIO(raw_tar), mode="r:") as archive:
        members = archive.getmembers()
        names = {member.name for member in members}
        if names != ALLOWED:
            raise RuntimeError(f"source capsule membership mismatch: {sorted(names ^ ALLOWED)}")
        if len(members) != manifest["source_member_count"]:
            raise RuntimeError("source capsule member-count mismatch")
        for member in members:
            pure = PurePosixPath(member.name)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or not member.isfile()
                or member.issym()
                or member.islnk()
            ):
                raise RuntimeError(f"unsafe source capsule member: {member.name}")
            source = archive.extractfile(member)
            if source is None:
                raise RuntimeError(f"unreadable source capsule member: {member.name}")
            data = source.read()
            destination = output / member.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                destination.unlink()
            descriptor = os.open(
                destination,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                0o644,
            )
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            if destination.read_bytes() != data:
                raise RuntimeError(f"post-write byte identity failure: {member.name}")
            materialized.append(
                {
                    "path": member.name,
                    "bytes": len(data),
                    "sha256": sha256(data),
                }
            )

    body: dict[str, Any] = {
        "format": "KCH_HELICAL_V0_17_3_TEXT_CAPSULE_MATERIALIZATION_RECEIPT",
        "manifest_path": manifest_path.relative_to(repo).as_posix(),
        "manifest_git_blob_sha1": git_blob(repo, manifest_path.relative_to(repo).as_posix()),
        "chunks": observations,
        "chunk_count": len(observations),
        "concatenated_base64_sha256": sha256(joined),
        "decoded_gzip_sha256": sha256(compressed),
        "decompressed_tar_sha256": sha256(raw_tar),
        "materialized_members": sorted(materialized, key=lambda item: item["path"]),
        "materialized_member_count": len(materialized),
        "source_bytes_modified": False,
        "scientific_data_included": False,
        "calibration_executed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "status": "PASS",
    }
    body["receipt_id"] = "h173transport:" + sha256(canonical(body))
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(
        json.dumps(body, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"receipt_id": body["receipt_id"], "member_count": len(materialized)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
