#!/usr/bin/env python3
"""TUF 7 successor for the v0.12 external-conformance gate.

The predecessor reached every external subsystem but used the pre-TUF-7
TrustedMetadataSet constructor. This successor changes only that adjudicated
boundary and then delegates the rest of the gate unchanged.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import kwan_external_conformance_v2 as predecessor


def tuf_rollback_check_v7() -> dict[str, Any]:
    try:
        from securesystemslib.signer import CryptoSigner
        from tuf.api.exceptions import BadVersionNumberError
        from tuf.api.metadata import MetaFile, Metadata, Root, Timestamp
        from tuf.ngclient._internal.trusted_metadata_set import TrustedMetadataSet
        from tuf.ngclient.config import EnvelopeType
    except Exception as exc:
        return {"passed": False, "error": f"import failed: {exc}"}

    now = dt.datetime.now(dt.timezone.utc)
    signer = CryptoSigner.generate_ed25519()
    root = Metadata(Root(expires=now + dt.timedelta(days=30), version=1))
    for role in ("root", "timestamp", "snapshot", "targets"):
        root.signed.add_key(signer.public_key, role)
    root.sign(signer)

    def timestamp(version: int) -> bytes:
        metadata = Metadata(
            Timestamp(
                expires=now + dt.timedelta(days=7),
                version=version,
                snapshot_meta=MetaFile(version=1),
            )
        )
        metadata.sign(signer)
        return metadata.to_bytes()

    trusted = TrustedMetadataSet(root.to_bytes(), EnvelopeType.METADATA)
    trusted.update_timestamp(timestamp(2))
    rejected = False
    error_type = None
    try:
        trusted.update_timestamp(timestamp(1))
    except BadVersionNumberError as exc:
        rejected = True
        error_type = type(exc).__name__
    return {
        "passed": rejected,
        "trusted_timestamp_version": 2,
        "rollback_candidate_version": 1,
        "rollback_rejected": rejected,
        "error_type": error_type,
        "envelope_type": "METADATA",
    }


def main() -> int:
    predecessor.base.tuf_rollback_check = tuf_rollback_check_v7
    return predecessor.main()


if __name__ == "__main__":
    raise SystemExit(main())
