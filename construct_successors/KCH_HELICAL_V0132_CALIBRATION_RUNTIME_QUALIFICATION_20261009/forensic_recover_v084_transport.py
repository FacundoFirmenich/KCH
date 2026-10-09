from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shutil
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path, PurePosixPath

COMMIT = "e458afe20b8172db5a04194224cf21df5ec00dc4"
CHUNKS = (
    (".github/helical_v08_4/source_transport/chunk_00", "da9a691447b022087063b132a03ad1d4399cadd1"),
    (".github/helical_v08_4/source_transport/chunk_01", "3082e6ee37ad74319195d37dea59d495fe90f490"),
    (".github/helical_v08_4/source_transport/chunk_02", "6449dfb0065b3fd8347cb83bb1b9f07236e6fb89"),
)
TARGET_BASENAMES = {
    "null_runtime.py",
    "test_null_runtime.py",
    "freeze_null_perturbation_runtime.py",
    "core.py",
    "eligibility.py",
    "test_dynamic_v08_original.py",
    "protocol.json",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(repo: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(repo), *args])


def safe_relative(name: str) -> bool:
    path = PurePosixPath(name)
    return bool(name) and not path.is_absolute() and ".." not in path.parts


def parse_gzip_header_end(data: bytes) -> int:
    if len(data) < 10 or data[:3] != b"\x1f\x8b\x08":
        raise RuntimeError("source transport is not a supported gzip stream")
    flags = data[3]
    if flags & 0xE0:
        raise RuntimeError(f"reserved gzip flags set: {flags:#x}")
    index = 10
    if flags & 0x04:
        if index + 2 > len(data):
            raise RuntimeError("truncated FEXTRA")
        extra_length = struct.unpack_from("<H", data, index)[0]
        index += 2 + extra_length
    for mask, label in ((0x08, "FNAME"), (0x10, "FCOMMENT")):
        if flags & mask:
            try:
                index = data.index(b"\x00", index) + 1
            except ValueError as exc:
                raise RuntimeError(f"unterminated {label}") from exc
    if flags & 0x02:
        index += 2
    if index >= len(data):
        raise RuntimeError("truncated gzip header")
    return index


def parse_octal(field: bytes) -> int:
    cleaned = field.rstrip(b"\x00 ").lstrip(b" ")
    if not cleaned:
        return 0
    if any(byte not in b"01234567" for byte in cleaned):
        raise ValueError(f"non-octal tar field: {cleaned!r}")
    return int(cleaned, 8)


def tar_checksum(block: bytes) -> tuple[int, int]:
    stored = parse_octal(block[148:156])
    mutable = bytearray(block)
    mutable[148:156] = b"        "
    return stored, sum(mutable)


def decode_tar_name(block: bytes) -> str:
    name = block[:100].split(b"\x00", 1)[0]
    prefix = block[345:500].split(b"\x00", 1)[0]
    raw = prefix + (b"/" if prefix and name else b"") + name
    return raw.decode("utf-8", errors="strict")


def scan_partial_tar(payload: bytes, output: Path) -> dict[str, object]:
    offset = 0
    members: list[dict[str, object]] = []
    recovered: list[dict[str, object]] = []
    stop_reason = "END_OF_PREFIX"
    zero_blocks = 0

    while offset + 512 <= len(payload):
        block = payload[offset : offset + 512]
        if block == b"\x00" * 512:
            zero_blocks += 1
            offset += 512
            if zero_blocks >= 2:
                stop_reason = "TAR_END_MARKERS"
                break
            continue
        zero_blocks = 0
        try:
            name = decode_tar_name(block)
            size = parse_octal(block[124:136])
            stored_checksum, computed_checksum = tar_checksum(block)
        except Exception as exc:
            stop_reason = f"INVALID_HEADER_AT_{offset}:{type(exc).__name__}:{exc}"
            break
        checksum_pass = stored_checksum == computed_checksum
        if not checksum_pass or not safe_relative(name):
            stop_reason = f"HEADER_REJECTED_AT_{offset}"
            members.append(
                {
                    "offset": offset,
                    "name": name,
                    "size": size,
                    "stored_checksum": stored_checksum,
                    "computed_checksum": computed_checksum,
                    "checksum_pass": checksum_pass,
                    "safe_name": safe_relative(name),
                    "complete": False,
                }
            )
            break
        data_start = offset + 512
        data_end = data_start + size
        complete = data_end <= len(payload)
        typeflag = block[156:157].decode("ascii", errors="replace") or "0"
        record: dict[str, object] = {
            "offset": offset,
            "name": name,
            "size": size,
            "typeflag": typeflag,
            "stored_checksum": stored_checksum,
            "computed_checksum": computed_checksum,
            "checksum_pass": True,
            "safe_name": True,
            "complete": complete,
        }
        if complete and typeflag in {"0", "\x00", "7"}:
            data = payload[data_start:data_end]
            record["sha256"] = sha256(data)
            record["bytes"] = len(data)
            if PurePosixPath(name).name in TARGET_BASENAMES:
                destination = output / "recovered" / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                recovered.append(
                    {
                        "name": name,
                        "bytes": len(data),
                        "sha256": sha256(data),
                        "output_path": destination.relative_to(output).as_posix(),
                    }
                )
        members.append(record)
        if not complete:
            stop_reason = f"INCOMPLETE_MEMBER_AT_{offset}:{name}"
            break
        offset = data_start + ((size + 511) // 512) * 512

    return {
        "payload_bytes": len(payload),
        "payload_sha256": sha256(payload),
        "scanned_through_offset": offset,
        "member_count": len(members),
        "complete_member_count": sum(1 for item in members if item.get("complete")),
        "all_complete_headers_checksum_pass": all(bool(item.get("checksum_pass")) for item in members),
        "members": members,
        "target_recovered_count": len(recovered),
        "targets_recovered": recovered,
        "stop_reason": stop_reason,
    }


def inspect_candidate(label: str, compressed: bytes, output: Path) -> dict[str, object]:
    result: dict[str, object] = {
        "label": label,
        "compressed_bytes": len(compressed),
        "compressed_sha256": sha256(compressed),
        "prefix_hex": compressed[:32].hex(),
        "suffix_hex": compressed[-32:].hex(),
        "gzip_magic_offsets": [index for index in range(max(0, len(compressed) - 2)) if compressed[index:index+3] == b"\x1f\x8b\x08"][:100],
        "zip_magic_offsets": [index for index in range(max(0, len(compressed) - 3)) if compressed[index:index+4] == b"PK\x03\x04"][:100],
    }
    try:
        header_end = parse_gzip_header_end(compressed)
        result["gzip_header_end"] = header_end
        inflater = zlib.decompressobj(wbits=-zlib.MAX_WBITS)
        payload = inflater.decompress(compressed[header_end:]) + inflater.flush()
        consumed = len(compressed[header_end:]) - len(inflater.unused_data)
        result.update(
            {
                "deflate_eof": inflater.eof,
                "deflate_consumed_bytes": consumed,
                "unused_bytes": len(inflater.unused_data),
                "unconsumed_tail_bytes": len(inflater.unconsumed_tail),
                "partial_payload_bytes": len(payload),
                "partial_payload_sha256": sha256(payload),
                "partial_payload_prefix_hex": payload[:64].hex(),
                "partial_payload_suffix_hex": payload[-64:].hex(),
                "partial_payload_contains_ustar": b"ustar" in payload,
                "partial_payload_contains_null_runtime": b"null_runtime.py" in payload,
                "partial_payload_contains_test_null_runtime": b"test_null_runtime.py" in payload,
                "partial_payload_contains_freeze_compiler": b"freeze_null_perturbation_runtime.py" in payload,
            }
        )
        candidate_output = output / label
        candidate_output.mkdir(parents=True, exist_ok=True)
        (candidate_output / "PARTIAL_DECOMPRESSED_PREFIX.bin").write_bytes(payload)
        result["tar_scan"] = scan_partial_tar(payload, candidate_output)
        unused = inflater.unused_data
        (candidate_output / "UNUSED_COMPRESSED_SUFFIX.bin").write_bytes(unused)
        result["unused_prefix_hex"] = unused[:128].hex()
        result["unused_suffix_hex"] = unused[-128:].hex()
        result["unused_gzip_offsets"] = [index for index in range(max(0, len(unused) - 2)) if unused[index:index+3] == b"\x1f\x8b\x08"][:100]
        result["unused_zip_offsets"] = [index for index in range(max(0, len(unused) - 3)) if unused[index:index+4] == b"PK\x03\x04"][:100]
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo_root.resolve()
    output = args.output.resolve()
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    git(repo, "cat-file", "-e", f"{COMMIT}^{{commit}}")

    raw_chunks: list[bytes] = []
    chunk_receipts: list[dict[str, object]] = []
    decoded_chunks: list[bytes] = []
    for path, expected_blob in CHUNKS:
        observed_blob = git(repo, "rev-parse", f"{COMMIT}:{path}").decode().strip()
        if observed_blob != expected_blob:
            raise RuntimeError(f"blob mismatch for {path}: {observed_blob}")
        raw = git(repo, "show", f"{COMMIT}:{path}")
        compact = b"".join(raw.split())
        raw_chunks.append(raw)
        decoded = base64.b64decode(compact, validate=True)
        decoded_chunks.append(decoded)
        chunk_receipts.append(
            {
                "path": path,
                "git_blob_sha1": observed_blob,
                "raw_bytes": len(raw),
                "raw_sha256": sha256(raw),
                "compact_base64_bytes": len(compact),
                "compact_base64_mod4": len(compact) % 4,
                "compact_base64_sha256": sha256(compact),
                "base64_prefix": compact[:32].decode("ascii"),
                "base64_suffix": compact[-32:].decode("ascii"),
                "individually_decoded_bytes": len(decoded),
                "individually_decoded_sha256": sha256(decoded),
                "individually_decoded_prefix_hex": decoded[:32].hex(),
                "individually_decoded_suffix_hex": decoded[-32:].hex(),
            }
        )

    raw_join = b"".join(raw_chunks)
    compact_join = b"".join(raw_join.split())
    candidates = {
        "CONCAT_BASE64_THEN_DECODE": base64.b64decode(compact_join, validate=True),
        "DECODE_EACH_THEN_CONCAT": b"".join(decoded_chunks),
    }
    diagnostics = [inspect_candidate(label, data, output) for label, data in candidates.items()]

    body: dict[str, object] = {
        "format": "KCH_HELICAL_V0_13_2_V084_SOURCE_TRANSPORT_FORENSIC_RECEIPT",
        "source_commit": COMMIT,
        "chunks": chunk_receipts,
        "concatenated_raw_bytes": len(raw_join),
        "concatenated_raw_sha256": sha256(raw_join),
        "concatenated_compact_base64_bytes": len(compact_join),
        "concatenated_compact_base64_mod4": len(compact_join) % 4,
        "concatenated_compact_base64_sha256": sha256(compact_join),
        "candidate_diagnostics": diagnostics,
        "scientific_execution_performed": False,
        "calibration_data_accessed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "authority_ceiling": "SOURCE_RECONSTRUCTION_AND_SOFTWARE_INSPECTION_ONLY",
    }
    body["receipt_id"] = "h132transportforensic:" + sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    )
    (output / "V084_SOURCE_TRANSPORT_FORENSIC_RECEIPT.json").write_text(
        json.dumps(body, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    print(json.dumps({"receipt_id": body["receipt_id"], "diagnostic_count": len(diagnostics)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
