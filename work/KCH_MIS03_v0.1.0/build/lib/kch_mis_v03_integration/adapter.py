from __future__ import annotations

import importlib
import json
from typing import Any

from .adapter_base import (
    ADAPTER_VERSION,
    EXPECTED,
    MIS_VERSION,
    AdapterContractError,
    MISV03Adapter as _BaseMISV03Adapter,
    _certificate,
    canonical_json,
    sha256_file,
    sha256_json,
    verify_exact_decision_certificate,
    verify_historical_certificate,
)


class MISV03Adapter(_BaseMISV03Adapter):
    """Adapter with explicit normalization of one null transport field."""

    def audit_historical_khc(self) -> dict[str, Any]:
        khc = importlib.import_module("mis_v03.khc")
        experiments = importlib.import_module("mis_v03.experiments")
        freeze = importlib.import_module("mis_v03.freeze")

        report = json.loads(self.paths.report.read_text(encoding="utf-8-sig"))
        persisted = json.loads(self.paths.ledgers.read_text(encoding="utf-8-sig"))
        manifest = json.loads(self.paths.manifest.read_text(encoding="utf-8-sig"))
        if manifest.get("schema") != "MIS_RELEASE_MANIFEST_v0.3.1" or manifest.get("file_count") != 32:
            raise AdapterContractError("MIS release manifest contract mismatch")

        corpus = khc.load_khc_corpus(self.paths.corpus)
        units = khc.constitute_units(corpus)
        audit = khc.integration_audit(corpus)
        replay_runtime = experiments.khc_future_only_replay(self.paths.corpus, include_ledgers=False)
        # The runtime returns ``ledgers: None`` in its non-embedded transport
        # form, whereas the qualified report omits that null transport field.
        replay = {
            key: value
            for key, value in replay_runtime.items()
            if not (key == "ledgers" and value is None)
        }
        if audit != report.get("khc_integration"):
            raise AdapterContractError("live integration audit differs from frozen v0.3.1 report")
        if replay != report.get("khc_future_only_replay"):
            raise AdapterContractError("live future-only replay differs from frozen v0.3.1 report")

        ledger_rows = persisted.get("ledgers")
        if not isinstance(ledger_rows, list) or len(ledger_rows) != 60:
            raise AdapterContractError("persisted MIS ledger cardinality mismatch")
        verified_ledgers: list[dict[str, str]] = []
        for row in ledger_rows:
            rebuilt = freeze.FutureOnlyLedger.from_payload(row)
            if not rebuilt.verify():
                raise AdapterContractError(f"MIS ledger verification failed: {rebuilt.stream_id}")
            verified_ledgers.append({"stream_id": rebuilt.stream_id, "payload_sha256": sha256_json(row)})
        verified_ledgers.sort(key=lambda item: item["stream_id"])

        core = {
            "schema": "kch.mis.v03.historical-certificate.v0.1.0",
            "adapter_version": ADAPTER_VERSION,
            "mis_version": MIS_VERSION,
            "custody": dict(EXPECTED),
            "source_schema": audit["source_schema"],
            "records": audit["records"],
            "coordinates_unique": audit["coordinates_unique"],
            "units_unique": audit["units_unique"],
            "unit_hash_sequence_sha256": sha256_json([unit.unit_hash for unit in units]),
            "streams": replay["streams"],
            "freezes": replay["freezes"],
            "outcomes": replay["outcomes"],
            "persisted_ledgers_verified": len(verified_ledgers),
            "persisted_ledger_set_sha256": sha256_json(verified_ledgers),
            "policy_hash": replay["policy_hash"],
            "live_audit_sha256": sha256_json(audit),
            "live_replay_sha256": sha256_json(replay),
            "frozen_report_exact_match": True,
            "future_only_chronology_verified": True,
            "authority_created": False,
            "execution_authorized": False,
            "automatic_promotion": False,
            "claim_ceiling": "STRUCTURAL_LOSSLESS_REPRESENTATION_EXACT_REPLAY_AND_FUTURE_ONLY_INTEGRITY_ONLY",
            "not_demonstrated": [
                "CAUSAL_KCH_IMPROVEMENT",
                "PROSPECTIVE_PREDICTIVE_SUPERIORITY",
                "HUMAN_UTILITY",
                "OPEN_DOMAIN_SCALABILITY",
                "GLOBAL_WINNER",
            ],
        }
        return _certificate(core)


__all__ = [
    "ADAPTER_VERSION",
    "EXPECTED",
    "MIS_VERSION",
    "AdapterContractError",
    "MISV03Adapter",
    "canonical_json",
    "sha256_file",
    "sha256_json",
    "verify_exact_decision_certificate",
    "verify_historical_certificate",
]

