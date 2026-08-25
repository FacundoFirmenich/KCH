from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import attach_hash, sha256_bytes
from .graph import rgg_historical_summary
from .mis_adapter import MISExactAdapter
from .temporal import TemporalMemory


THREE_LAYER_BYTE_SHA256 = "9248f97ccbe0f45804e372ce51f2a36be61fc39e60d3b354bf2a7525a91338c9"


def onboard_historical_three_layer_byte(path: str | Path, *, mis: MISExactAdapter | None = None) -> dict[str, Any]:
    source = Path(path).resolve(strict=True)
    raw = source.read_bytes()
    digest = sha256_bytes(raw)
    if digest != THREE_LAYER_BYTE_SHA256:
        raise ValueError(f"historical byte custody mismatch: {digest}")
    value = json.loads(raw.decode("utf-8-sig"))
    required = {"protocol_id", "status", "seeds", "source_raw_sha256", "coordinates", "evidence_boundary", "layers",
                "C2_IDEOCRYPTIC_BYTE_QE_VIEW_PRIMARY", "C3_forward_reverse", "all_three_layers"}
    missing = required - set(value)
    if missing:
        raise ValueError(f"historical byte missing keys: {sorted(missing)}")
    if value["protocol_id"] != "MU_EQ_QE_THREE_LAYER_BYTE_COMPLETION_V0_1_20260810":
        raise ValueError("unexpected historical protocol")
    if value["seeds"] != list(range(20001, 20009)):
        raise ValueError("historical seeds changed")
    c2 = value["C2_IDEOCRYPTIC_BYTE_QE_VIEW_PRIMARY"]["joint_metrics"]
    extracted = {
        "protocol_id": value["protocol_id"],
        "historical_status": value["status"],
        "seeds": value["seeds"],
        "seed_role": "REPLICA_ONLY",
        "coordinates": value["coordinates"],
        "evidence_boundary": value["evidence_boundary"],
        "c2_between_pair_binding_bits_mean": c2["between_pair_binding_bits"]["mean"],
        "c2_between_pair_binding_permutation_upper_tail_p": value["C2_IDEOCRYPTIC_BYTE_QE_VIEW_PRIMARY"]["between_pair_binding_permutation"]["upper_tail_p"],
        "c2_total_correlation_bits_mean": c2["total_correlation_bits"]["mean"],
        "c2_o_information_bits_mean": c2["o_information_bits"]["mean"],
        "c2_effective_byte_states_mean": c2["effective_byte_states"]["mean"],
        "source_raw_receipts": value["source_raw_sha256"],
    }
    memory = TemporalMemory()
    memory.append("mu_three_layer_byte", extracted, status="OBSOLETE", valid_from="2026-08-10",
                  observed_at="2026-08-13", authority="HISTORICAL_EVIDENCE",
                  reason="Onboarding preserves the original exploratory result without retrospective promotion",
                  source_receipts=(digest,))
    memory.append("mu_three_layer_byte", extracted, status="RESIDUAL", valid_from="2026-08-10",
                  observed_at="2026-08-13", authority="NONE",
                  reason="Residual structure is retained for future confirmatory successors",
                  source_receipts=(memory.entries[-1].receipt_sha256,))
    graph = rgg_historical_summary(digest, value["coordinates"])
    mis_certificate = None if mis is None else mis.certify_payload(extracted)
    gates = {
        "source_sha256_exact": True,
        "all_required_sections_present": True,
        "seed_role_replica_only": True,
        "temporal_chain_valid": memory.verify(),
        "rgg_no_authority_created": graph["authority_created"] is False,
        "mis_exact_hash_agreement": None if mis_certificate is None else mis_certificate["exact_hash_agreement"],
        "adverse_and_exploratory_boundary_preserved": True,
    }
    return attach_hash({
        "schema": "kch.mu-transmuter.onboarding-three-layer-byte.v0.1.0",
        "gate": "PASS_HISTORICAL_ONBOARDING" if all(item is not False for item in gates.values()) else "FAIL",
        "source_path": str(source),
        "source_sha256": digest,
        "source_bytes": len(raw),
        "extracted": extracted,
        "temporal_memory": [entry.core() | {"receipt_sha256": entry.receipt_sha256} for entry in memory.entries],
        "rgg": graph,
        "mis_certificate": mis_certificate,
        "gates": gates,
        "scientific_claim_update": "NONE_REPLAY_ONLY",
        "global_winner": None,
        "router_authorized": False,
        "phl_training_executed": False,
        "claim_boundary": "First KCH onboarding of an immutable exploratory historical result. It proves governed ingestion and preservation, not a new causal replication, Transmuter or mu superiority, universal antisymmetry, or full end-to-end host deployment.",
    })
