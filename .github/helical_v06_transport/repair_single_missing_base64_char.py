from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

EXPECTED_SHA256 = "361626dd19369a518a8ea1d3754ad33bebd35689442607cb2996e4f95f10f593"
EXPECTED_BYTES = 18000
BASE64_ALPHABET = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()

    observed = args.input.read_bytes()
    observed_sha = sha256(observed)
    receipt: dict[str, object] = {
        "format": "KCH_SINGLE_MISSING_BASE64_CHAR_TRANSPORT_REPAIR_RECEIPT_V1",
        "input_path": args.input.as_posix(),
        "observed_bytes_before": len(observed),
        "observed_sha256_before": observed_sha,
        "expected_bytes": EXPECTED_BYTES,
        "expected_sha256": EXPECTED_SHA256,
        "scientific_runtime_changed": False,
        "protocol_changed": False,
        "thresholds_changed": False,
        "data_acquired_before_repair": False,
        "repaired_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    if observed_sha == EXPECTED_SHA256 and len(observed) == EXPECTED_BYTES:
        receipt.update(
            status="ALREADY_EXACT",
            insertion_performed=False,
            recovered_position=None,
            recovered_character=None,
        )
    else:
        if len(observed) != EXPECTED_BYTES - 1:
            raise SystemExit(
                f"refusing non-single-character repair: observed bytes={len(observed)}, expected={EXPECTED_BYTES}"
            )

        match: tuple[int, int, bytes] | None = None
        for position in range(len(observed) + 1):
            prefix = observed[:position]
            suffix = observed[position:]
            for character in BASE64_ALPHABET:
                candidate = prefix + bytes((character,)) + suffix
                if sha256(candidate) == EXPECTED_SHA256:
                    if match is not None:
                        raise SystemExit("ambiguous repair: more than one insertion matches the locked SHA-256")
                    match = (position, character, candidate)

        if match is None:
            raise SystemExit("no single base64-character insertion recovers the locked SHA-256")

        position, character, candidate = match
        args.input.write_bytes(candidate)
        receipt.update(
            status="RECOVERED_EXACT_LOCKED_CHUNK",
            insertion_performed=True,
            recovered_position=position,
            recovered_character=chr(character),
            observed_bytes_after=len(candidate),
            observed_sha256_after=sha256(candidate),
        )

    final = args.input.read_bytes()
    if len(final) != EXPECTED_BYTES or sha256(final) != EXPECTED_SHA256:
        raise SystemExit("post-repair verification failed")

    canonical = json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt["receipt_id"] = "h6t:" + sha256(canonical)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
