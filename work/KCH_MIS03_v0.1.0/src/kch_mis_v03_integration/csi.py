from __future__ import annotations

from typing import Any, Mapping

from .adapter import ADAPTER_VERSION, MIS_VERSION, sha256_json


def lower_to_csi(certificate: Mapping[str, Any], gate_result_sha256: str) -> dict[str, Any]:
    certificate_sha = str(certificate["certificate_sha256"])
    session_id = f"csi:mis-v03:{certificate_sha[:24]}"
    raw = [
        {
            "kind": "OPEN_SESSION",
            "session_id": session_id,
            "params": {"label": "kch.preset.mis.v03.exact-decision-support", "epoch": 0},
        },
        {
            "kind": "SEAL_IDENTITAS",
            "session_id": session_id,
            "params": {
                "statements": [
                    "MIS supplies exact semantic state, posterior, loss, decision and certificate calculations",
                    "KCH alone governs authority, routing, commit and promotion",
                    "Preserve evidence provenance, purpose, jurisdiction and future-only chronology",
                    "Historical replay cannot establish causal improvement, prospective superiority or a global winner",
                    "A MIS decision certificate never authorizes execution by itself",
                ],
                "strata": [
                    ["MIS_V0_3_1", "EXACT_QUALITATIVE_BAYES"],
                    ["KCH", "AUTHORITY_AND_COMMIT"],
                    ["CSI", "COMPOSITIONAL_LOWERING"],
                ],
                "explicitly_extensible": True,
            },
        },
        {
            "kind": "ADD_DATUM",
            "session_id": session_id,
            "params": {
                "datum": {
                    "datum_id": "mis-v03-custody-and-boundary",
                    "role": "CONSTRAINT",
                    "payload": {
                        "mis_version": MIS_VERSION,
                        "adapter_version": ADAPTER_VERSION,
                        "historical_certificate_sha256": certificate_sha,
                        "gate_result_sha256": gate_result_sha256,
                        "records": certificate["records"],
                        "streams": certificate["streams"],
                        "authority_created": False,
                        "execution_authorized": False,
                        "automatic_promotion": False,
                        "claim_ceiling": certificate["claim_ceiling"],
                        "not_demonstrated": certificate["not_demonstrated"],
                    },
                    "priority": 2,
                    "source": "kch-mis-v03-integration/0.1.0",
                }
            },
        },
        {
            "kind": "MODE_ON",
            "session_id": session_id,
            "params": {
                "modus": {
                    "modus_id": "EXACT_QUALITATIVE_DECISION_SUPPORT",
                    "description": "Exact MIS calculation with KCH authority separation",
                    "preserves_identitas": True,
                    "parameters": {
                        "calculation": "EXACT_RATIONAL",
                        "ties": "PRESERVED_UNLESS_RULE_DECLARED",
                        "chronology": "FUTURE_ONLY",
                        "authority": "KCH_ONLY",
                        "promotion": "EXPLICIT_GATE_REQUIRED",
                    },
                }
            },
        },
    ]
    return {
        "schema": "kch.mis.v03.csi-lowering.v0.1.0",
        "preset_id": "kch.preset.mis.v03.exact-decision-support",
        "topological_address": ["KCH", "FEDERATED_MATHEMATICAL_SERVICES", "MIS", "v0.3.1"],
        "source_certificate_sha256": certificate_sha,
        "gate_result_sha256": gate_result_sha256,
        "raw_csi_program": raw,
        "raw_csi_program_sha256": sha256_json(raw),
        "authority_created": False,
        "execution_authorized": False,
        "automatic_promotion": False,
    }

