from __future__ import annotations

from typing import Any

from .models import sha256_json


def lower_superchat(bundle: dict[str, Any]) -> dict[str, Any]:
    if bundle.get("schema") != "kch.sco.portable-orchestration-bundle.v0.1.0":
        raise ValueError("unsupported SCO bundle")
    if bundle.get("native_chat_content_included") or bundle.get("native_memory_included"):
        raise ValueError("SCO lowering refuses merged native content or memory")
    sco = bundle["superchat"]
    seed = [sco["sco_id"], bundle["bundle_sha256"], bundle["ledger_head_hash"]]
    session_id = "csi:sco:" + sha256_json(seed)[:24]
    identitas = {
        "statements": [
            "Orchestrate selected sovereign chats without fusing them",
            "Preserve every node's native context, memory, capabilities and lifecycle",
            "Exchange only scoped references through explicit work orders and receipts",
            "Preserve adverse results, abstentions and unresolved conflicts",
            "Never create authority through orchestration",
        ],
        "strata": [
            ["SCO", "SUPERCHATS_ORCHESTRATORS"],
            ["SOVEREIGN_NODES", "NO_CONTEXT_FUSION"],
            ["GRAPH_ORCHESTRATION", "EVIDENCE_LINKED_RECEIPTS"],
        ],
        "explicitly_extensible": True,
    }

    def operation(kind: str, params: dict[str, Any]) -> dict[str, Any]:
        return {"kind": kind, "session_id": session_id, "params": params}

    raw_program = [
        operation("OPEN_SESSION", {"label": "kch.preset.sco.orchestration", "epoch": 0}),
        operation("SEAL_IDENTITAS", identitas),
        operation(
            "ADD_DATUM",
            {
                "datum": {
                    "datum_id": "sco-contract",
                    "role": "CONSTRAINT",
                    "payload": {
                        "sco_id": sco["sco_id"],
                        "objective": sco["objective"],
                        "non_goals": sco["non_goals"],
                        "jurisdiction": sco["jurisdiction"],
                        "claim_ceiling": sco["claim_ceiling"],
                        "native_contexts_merged": False,
                        "native_memories_replaced": False,
                    },
                    "priority": 2,
                    "source": "kch-sco/0.1.0",
                }
            },
        ),
        operation(
            "MODE_ON",
            {
                "modus": {
                    "modus_id": "SOVEREIGN_CHAT_ORCHESTRATION",
                    "description": "Graph orchestration of sovereign heterogeneous chat nodes",
                    "preserves_identitas": True,
                    "parameters": {
                        "routing": "EXPLICIT_GRAPH",
                        "disclosure": "SCOPED_REFERENCES_ONLY",
                        "memory": "NATIVE_MEMORY_PRESERVED",
                        "conflicts": "PRESERVED_UNTIL_ADJUDICATED",
                    },
                }
            },
        ),
    ]
    for node in bundle["nodes"]:
        raw_program.append(
            operation(
                "ADD_DATUM",
                {
                    "datum": {
                        "datum_id": f"node:{node['node_id']}",
                        "role": "CONSTRAINT",
                        "payload": {
                            "node_id": node["node_id"],
                            "provider": node["provider"],
                            "native_uri": node["native_uri"],
                            "role": node["role"],
                            "autonomy_level": node["autonomy_level"],
                            "authority_granted": node["authority_granted"],
                            "connector_state": node["connector_state"],
                        },
                        "priority": 2,
                        "source": "kch-sco-node-registry",
                    }
                },
            )
        )
    for edge in bundle["edges"]:
        raw_program.append(
            operation(
                "ADD_DATUM",
                {
                    "datum": {
                        "datum_id": f"edge:{edge['edge_id']}",
                        "role": "CONSTRAINT",
                        "payload": {
                            "source_node_id": edge["source_node_id"],
                            "target_node_id": edge["target_node_id"],
                            "relation": edge["relation"],
                            "disclosure_contract": edge["disclosure_contract"],
                            "activation_condition": edge["activation_condition"],
                            "gate_id": edge["gate_id"],
                        },
                        "priority": 2,
                        "source": "kch-sco-edge-registry",
                    }
                },
            )
        )
    result = {
        "schema": "kch.sco.csi-lowering.v0.1.0",
        "preset_id": "kch.preset.sco.orchestration",
        "topological_address": ["KCH", "ORCHESTRATION", "SCO", sco["sco_id"]],
        "identitas_sha256": sha256_json(identitas),
        "source_bundle_sha256": bundle["bundle_sha256"],
        "raw_csi_program": raw_program,
        "raw_csi_program_sha256": sha256_json(raw_program),
        "authority_created": False,
        "native_contexts_merged": False,
        "native_memories_replaced": False,
        "execution_authorized": False,
    }
    return result
