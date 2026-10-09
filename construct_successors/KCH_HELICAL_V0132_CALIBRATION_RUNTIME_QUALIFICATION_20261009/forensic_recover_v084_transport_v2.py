from __future__ import annotations

import argparse
import base64
import json
import shutil
from pathlib import Path

from forensic_recover_v084_transport import (
    CHUNKS,
    COMMIT,
    git,
    inspect_candidate,
    sha256,
)


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
    compact_chunks: list[bytes] = []
    chunk_receipts: list[dict[str, object]] = []
    independently_decoded: list[bytes] = []
    all_individually_decodable = True

    for path, expected_blob in CHUNKS:
        observed_blob = git(repo, "rev-parse", f"{COMMIT}:{path}").decode().strip()
        if observed_blob != expected_blob:
            raise RuntimeError(f"blob mismatch for {path}: {observed_blob}")
        raw = git(repo, "show", f"{COMMIT}:{path}")
        compact = b"".join(raw.split())
        raw_chunks.append(raw)
        compact_chunks.append(compact)
        receipt: dict[str, object] = {
            "path": path,
            "git_blob_sha1": observed_blob,
            "raw_bytes": len(raw),
            "raw_sha256": sha256(raw),
            "compact_base64_bytes": len(compact),
            "compact_base64_mod4": len(compact) % 4,
            "compact_base64_sha256": sha256(compact),
            "base64_prefix": compact[:32].decode("ascii"),
            "base64_suffix": compact[-32:].decode("ascii"),
        }
        try:
            decoded = base64.b64decode(compact, validate=True)
            independently_decoded.append(decoded)
            receipt.update(
                {
                    "individually_decodable": True,
                    "individually_decoded_bytes": len(decoded),
                    "individually_decoded_sha256": sha256(decoded),
                    "individually_decoded_prefix_hex": decoded[:32].hex(),
                    "individually_decoded_suffix_hex": decoded[-32:].hex(),
                }
            )
        except Exception as exc:
            all_individually_decodable = False
            receipt.update(
                {
                    "individually_decodable": False,
                    "individual_decode_error": f"{type(exc).__name__}: {exc}",
                }
            )
        chunk_receipts.append(receipt)

    raw_join = b"".join(raw_chunks)
    compact_join = b"".join(compact_chunks)
    global_decoded = base64.b64decode(compact_join, validate=True)
    candidates: dict[str, bytes] = {"CONCAT_COMPACT_BASE64_THEN_DECODE": global_decoded}
    if all_individually_decodable:
        candidates["DECODE_EACH_THEN_CONCAT"] = b"".join(independently_decoded)
    diagnostics = [inspect_candidate(label, data, output) for label, data in candidates.items()]

    cumulative_boundaries: list[dict[str, object]] = []
    cursor = 0
    for index, compact in enumerate(compact_chunks):
        cursor += len(compact)
        cumulative_boundaries.append(
            {
                "after_chunk_index": index,
                "cumulative_base64_characters": cursor,
                "cumulative_mod4": cursor % 4,
                "corresponding_complete_decoded_bytes": (cursor // 4) * 3,
            }
        )

    body: dict[str, object] = {
        "format": "KCH_HELICAL_V0_13_2_V084_SOURCE_TRANSPORT_FORENSIC_RECEIPT_V2",
        "source_commit": COMMIT,
        "chunks": chunk_receipts,
        "chunks_are_individually_decodable": all_individually_decodable,
        "cumulative_chunk_boundaries": cumulative_boundaries,
        "concatenated_raw_bytes": len(raw_join),
        "concatenated_raw_sha256": sha256(raw_join),
        "concatenated_compact_base64_bytes": len(compact_join),
        "concatenated_compact_base64_mod4": len(compact_join) % 4,
        "concatenated_compact_base64_sha256": sha256(compact_join),
        "global_decoded_bytes": len(global_decoded),
        "global_decoded_sha256": sha256(global_decoded),
        "candidate_diagnostics": diagnostics,
        "scientific_execution_performed": False,
        "calibration_data_accessed": False,
        "sealed_test_accessed": False,
        "scientific_result": None,
        "authority_ceiling": "SOURCE_RECONSTRUCTION_AND_SOFTWARE_INSPECTION_ONLY",
    }
    body["receipt_id"] = "h132transportforensicv2:" + sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    )
    (output / "V084_SOURCE_TRANSPORT_FORENSIC_RECEIPT_V2.json").write_text(
        json.dumps(body, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    print(json.dumps({"receipt_id": body["receipt_id"], "diagnostic_count": len(diagnostics)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
