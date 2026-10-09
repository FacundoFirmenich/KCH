from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import tarfile
import tempfile
import zipfile
import zlib
from pathlib import Path, PurePosixPath

COMMIT = "e458afe20b8172db5a04194224cf21df5ec00dc4"
FILES = {
    ".github/helical_v08_4/source_transport/chunk_00": "da9a691447b022087063b132a03ad1d4399cadd1",
    ".github/helical_v08_4/source_transport/chunk_01": "3082e6ee37ad74319195d37dea59d495fe90f490",
    ".github/helical_v08_4/source_transport/chunk_02": "6449dfb0065b3fd8347cb83bb1b9f07236e6fb89",
}
INDEPENDENT_COMPILER_PATH = ".github/helical_v08_4/source_transport/freeze_null_perturbation_runtime_v2.py.gz.b64"
INDEPENDENT_COMPILER_BLOB = "ae09da82978c18a55afbe2811c04d9a9fc40849e"
REQUIRED = (
    "src/kch_helical_dynamic_v08/null_runtime.py",
    "tests_v0_8_4/test_null_runtime.py",
    "tools/freeze_null_perturbation_runtime.py",
)
LOCKED_CANONICAL_SOURCE_HASHES = {
    "src/kch_helical_dynamic_v08/core.py": "231f2267057906cdc08d0d1299bd9407e431aae3a5eb6e9f3b1cbd951d5ba798",
    "src/kch_helical_dynamic_v08/eligibility.py": "4f882027beea67826fb282f2912c805e087fb320ced23d143e64576555a646a4",
    "src/kch_helical_dynamic_v08/__init__.py": "40335de8a8b8ba096ae70b1a105573ba6d71c0369a89f940dae2dd0e78d9bed8",
    "tests_v0_8_4/test_dynamic_v08_original.py": "993d386e39704237f5be408dcf3daa1e7b7e631c6a0a69f2230fb4b0372e6c7b",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args])


def safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts


def parse_gzip_header_end(data: bytes, offset: int) -> int:
    if offset + 10 > len(data) or data[offset : offset + 2] != b"\x1f\x8b" or data[offset + 2] != 8:
        raise RuntimeError(f"unsupported or absent gzip member at offset {offset}")
    flags = data[offset + 3]
    if flags & 0xE0:
        raise RuntimeError(f"reserved gzip flags at offset {offset}: {flags:#x}")
    index = offset + 10
    if flags & 0x04:
        if index + 2 > len(data):
            raise RuntimeError("truncated gzip FEXTRA length")
        extra_length = struct.unpack_from("<H", data, index)[0]
        index += 2 + extra_length
    for mask, label in ((0x08, "FNAME"), (0x10, "FCOMMENT")):
        if flags & mask:
            try:
                index = data.index(b"\x00", index) + 1
            except ValueError as exc:
                raise RuntimeError(f"unterminated gzip {label}") from exc
    if flags & 0x02:
        index += 2
    if index >= len(data):
        raise RuntimeError("truncated gzip header")
    return index


def recover_concatenated_gzip(data: bytes) -> tuple[bytes, bytes, dict[str, object]]:
    offset = 0
    corrected_parts: list[bytes] = []
    payload_parts: list[bytes] = []
    members: list[dict[str, object]] = []

    while offset < len(data):
        header_end = parse_gzip_header_end(data, offset)
        inflater = zlib.decompressobj(wbits=-zlib.MAX_WBITS)
        supplied = data[header_end:]
        payload = inflater.decompress(supplied) + inflater.flush()
        if not inflater.eof:
            raise RuntimeError(f"member {len(members)} deflate stream did not reach EOF")
        if inflater.unconsumed_tail:
            raise RuntimeError(f"member {len(members)} left unconsumed deflate input")
        consumed_deflate = len(supplied) - len(inflater.unused_data)
        trailer_start = header_end + consumed_deflate
        if trailer_start + 8 > len(data):
            raise RuntimeError(f"member {len(members)} has truncated gzip trailer")
        trailer = data[trailer_start : trailer_start + 8]
        stored_crc32, stored_isize = struct.unpack("<II", trailer)
        computed_crc32 = zlib.crc32(payload) & 0xFFFFFFFF
        computed_isize = len(payload) & 0xFFFFFFFF
        if stored_isize != computed_isize:
            raise RuntimeError(
                f"member {len(members)} ISIZE mismatch: stored={stored_isize}, computed={computed_isize}"
            )
        repaired = stored_crc32 != computed_crc32
        corrected_trailer = struct.pack("<II", computed_crc32, computed_isize)
        member_end = trailer_start + 8
        changed_offsets = [
            trailer_start + index
            for index, (before, after) in enumerate(zip(trailer, corrected_trailer, strict=True))
            if before != after
        ]
        corrected_parts.append(data[offset:trailer_start] + corrected_trailer)
        payload_parts.append(payload)
        members.append(
            {
                "member_index": len(members),
                "start_offset": offset,
                "header_end_offset": header_end,
                "trailer_start_offset": trailer_start,
                "end_offset": member_end,
                "compressed_member_bytes": member_end - offset,
                "uncompressed_bytes": len(payload),
                "payload_sha256": sha(payload),
                "stored_crc32": stored_crc32,
                "computed_crc32": computed_crc32,
                "stored_isize": stored_isize,
                "computed_isize": computed_isize,
                "crc32_repaired": repaired,
                "changed_byte_offsets": changed_offsets,
            }
        )
        offset = member_end
        if offset < len(data) and data[offset : offset + 2] != b"\x1f\x8b":
            raise RuntimeError(
                f"unexpected {len(data) - offset} bytes after gzip member {len(members) - 1}; next bytes={data[offset:offset+8].hex()}"
            )

    corrected = b"".join(corrected_parts)
    payload = b"".join(payload_parts)
    verified = gzip.decompress(corrected)
    if verified != payload:
        raise RuntimeError("corrected concatenated gzip did not round-trip")
    return payload, corrected, {
        "status": "CONCATENATED_GZIP_EXACT" if all(not item["crc32_repaired"] for item in members) else "CONCATENATED_GZIP_MEMBER_CRC32_REPAIRED",
        "member_count": len(members),
        "repair_performed": any(bool(item["crc32_repaired"]) for item in members),
        "repair_scope": "PER_MEMBER_GZIP_TRAILER_CRC32_ONLY",
        "members": members,
        "gzip_sha256_before": sha(data),
        "gzip_sha256_after": sha(corrected),
        "payload_sha256": sha(payload),
    }


def locate_unique(root: Path, required_path: str) -> Path:
    matches = [candidate for candidate in root.rglob(Path(required_path).name) if candidate.as_posix().endswith(required_path)]
    if len(matches) != 1:
        raise RuntimeError(f"required source not uniquely found: {required_path}; matches={len(matches)}")
    return matches[0]


def extract_safe(payload: bytes, destination: Path) -> str:
    buffer = io.BytesIO(payload)
    try:
        with tarfile.open(fileobj=buffer, mode="r:*") as archive:
            members = archive.getmembers()
            if any(not safe_name(member.name) or member.issym() or member.islnk() for member in members):
                raise RuntimeError("unsafe tar member")
            archive.extractall(destination, filter="data")
            return "tar"
    except tarfile.ReadError:
        buffer.seek(0)
        if not zipfile.is_zipfile(buffer):
            raise RuntimeError("decoded payload is neither a safe tar nor zip archive")
        buffer.seek(0)
        with zipfile.ZipFile(buffer) as archive:
            if any(not safe_name(name) for name in archive.namelist()):
                raise RuntimeError("unsafe zip member")
            archive.extractall(destination)
        return "zip"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()

    repo = args.repo_root.resolve()
    output = args.output.resolve()
    receipt = args.receipt.resolve()
    git(repo, "cat-file", "-e", f"{COMMIT}^{{commit}}")

    chunks: list[bytes] = []
    source: list[dict[str, object]] = []
    for path, expected_blob in FILES.items():
        observed_blob = git(repo, "rev-parse", f"{COMMIT}:{path}").decode().strip()
        if observed_blob != expected_blob:
            raise RuntimeError(f"blob mismatch {path}: {observed_blob}")
        raw = git(repo, "show", f"{COMMIT}:{path}")
        compact = b"".join(raw.split())
        chunks.append(raw)
        source.append(
            {
                "path": path,
                "git_blob_sha1": observed_blob,
                "bytes": len(raw),
                "sha256": sha(raw),
                "non_whitespace_bytes": len(compact),
                "non_whitespace_sha256": sha(compact),
            }
        )

    transport = b"".join(chunks)
    compact_transport = b"".join(transport.split())
    compressed = base64.b64decode(compact_transport, validate=True)
    payload, corrected_compressed, gzip_recovery = recover_concatenated_gzip(compressed)

    independent_blob = git(repo, "rev-parse", f"{COMMIT}:{INDEPENDENT_COMPILER_PATH}").decode().strip()
    if independent_blob != INDEPENDENT_COMPILER_BLOB:
        raise RuntimeError(f"independent compiler blob mismatch: {independent_blob}")
    compiler_transport = git(repo, "show", f"{COMMIT}:{INDEPENDENT_COMPILER_PATH}")
    independent_compiler = gzip.decompress(base64.b64decode(b"".join(compiler_transport.split()), validate=True))

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=output.name + ".tmp.", dir=output.parent))
    try:
        archive_type = extract_safe(payload, temporary)
        found: list[dict[str, object]] = []
        for required in REQUIRED:
            materialized = locate_unique(temporary, required)
            found.append(
                {
                    "required_path": required,
                    "materialized_path": materialized.relative_to(temporary).as_posix(),
                    "bytes": materialized.stat().st_size,
                    "sha256": sha(materialized.read_bytes()),
                }
            )

        compiler_path = locate_unique(temporary, "tools/freeze_null_perturbation_runtime.py")
        if compiler_path.read_bytes() != independent_compiler:
            raise RuntimeError("archive compiler does not match independently transported compiler bytes")

        locked_checks: list[dict[str, object]] = []
        for relative, expected_hash in LOCKED_CANONICAL_SOURCE_HASHES.items():
            materialized = locate_unique(temporary, relative)
            observed_hash = sha(materialized.read_bytes())
            passed = observed_hash == expected_hash
            locked_checks.append(
                {"path": relative, "expected_sha256": expected_hash, "observed_sha256": observed_hash, "pass": passed}
            )
            if not passed:
                raise RuntimeError(f"locked canonical source hash mismatch: {relative}: {observed_hash}")

        if output.exists():
            shutil.rmtree(output)
        os.replace(temporary, output)
        temporary = None
    finally:
        if temporary is not None and temporary.exists():
            shutil.rmtree(temporary)

    body: dict[str, object] = {
        "format": "KCH_HELICAL_V0_13_2_HISTORICAL_V084_SOURCE_RECONSTRUCTION_RECEIPT",
        "source_commit": COMMIT,
        "source_files": source,
        "concatenated_transport_bytes": len(transport),
        "compact_base64_bytes": len(compact_transport),
        "compact_base64_mod4": len(compact_transport) % 4,
        "concatenated_base64_sha256": sha(transport),
        "compact_base64_sha256": sha(compact_transport),
        "compressed_sha256_before": sha(compressed),
        "compressed_sha256_after": sha(corrected_compressed),
        "decoded_archive_sha256": sha(payload),
        "gzip_recovery": gzip_recovery,
        "archive_type": archive_type,
        "required_files": found,
        "locked_canonical_source_hash_checks": locked_checks,
        "independent_compiler": {
            "path": INDEPENDENT_COMPILER_PATH,
            "git_blob_sha1": independent_blob,
            "transport_sha256": sha(compiler_transport),
            "decoded_bytes": len(independent_compiler),
            "decoded_sha256": sha(independent_compiler),
            "archive_compiler_exact_match": True,
        },
        "scientific_execution_performed": False,
        "calibration_data_accessed": False,
        "sealed_test_accessed": False,
        "authority": "SOURCE_RECONSTRUCTION_AND_SOFTWARE_INSPECTION_ONLY",
    }
    body["receipt_id"] = "h132v084source:" + sha(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    )
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps(body, indent=2, sort_keys=True, allow_nan=False) + "\n")
    print(json.dumps(body, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
