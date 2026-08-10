from __future__ import annotations

from copy import deepcopy
from typing import Any

from .canonical import sha256_json, sha256_text
from .classifier import FirstSeparator
from .ledger import KwanPromptsError, KwanPromptsLedger


class KwanPromptsService:
    ROLES = {"system", "developer", "user", "assistant", "tool"}
    ADJUDICATIONS = {"PROMOTE_STRATEGIC", "KEEP_INTERMEDIATE", "MARK_REVIEW"}

    def __init__(self, ledger: KwanPromptsLedger):
        self.ledger = ledger
        self.separator = FirstSeparator()

    def ingest(self, value: dict[str, Any]) -> dict[str, Any]:
        message_id = str(value.get("message_id", "")).strip()
        thread_id = str(value.get("thread_id", "")).strip()
        role = str(value.get("role", "")).strip().lower()
        raw_text = value.get("raw_text")
        if not message_id or not thread_id or role not in self.ROLES or not isinstance(raw_text, str) or not raw_text:
            raise KwanPromptsError("message_id, thread_id, valid role and non-empty raw_text are required")
        ordinal = value.get("ordinal")
        if ordinal is not None and (not isinstance(ordinal, int) or ordinal < 0):
            raise KwanPromptsError("ordinal must be a non-negative integer or null")
        structure = self.separator.classify_message(raw_text)
        record = {
            "schema": "kwanprompts.message-record.v0.1.0",
            "message_id": message_id,
            "thread_id": thread_id,
            "role": role,
            "ordinal": ordinal,
            "timestamp": value.get("timestamp"),
            "source_uri": value.get("source_uri"),
            "parent_message_id": value.get("parent_message_id"),
            "raw_text": raw_text,
            "raw_sha256": sha256_text(raw_text),
            "structure": structure,
            "canonical_status": "UNPROMOTED",
            "kwandocs_status": "NOT_INGESTED",
            "authority_created": False,
        }
        stored = self.ledger.put_message(record)
        return {
            "schema": "kwanprompts.ingest-receipt.v0.1.0",
            "message_id": message_id,
            "raw_sha256": record["raw_sha256"],
            "branch": structure["branch"],
            "disposition": structure["disposition"],
            "segment_count": len(structure["segments"]),
            "event_hash": stored["event_hash"],
            "idempotent": stored["idempotent"],
            "raw_preserved": True,
            "canonical_promotion": "NOT_REQUESTED",
            "authority_created": False,
            "csi_projection": self.csi_projection(record),
        }

    def inspect(self, message_id: str) -> dict[str, Any]:
        return self.ledger.get_message(message_id)

    def adjudicate(self, value: dict[str, Any]) -> dict[str, Any]:
        message_id = str(value.get("message_id", "")).strip()
        decision = str(value.get("decision", "")).strip()
        actor = str(value.get("actor", "")).strip()
        reason = str(value.get("reason", "")).strip()
        if not message_id or decision not in self.ADJUDICATIONS or not actor or not reason:
            raise KwanPromptsError("message_id, allowed decision, actor and reason are required")
        source = self.ledger.get_message(message_id)
        record = {
            "schema": "kwanprompts.review-adjudication.v0.1.0",
            "adjudication_id": "adj-" + sha256_json([message_id, decision, actor, reason])[:32],
            "message_id": message_id,
            "source_raw_sha256": source["raw_sha256"],
            "decision": decision,
            "actor": actor,
            "reason": reason,
            "raw_mutated": False,
            "canonical_promotion": False,
            "authority_created": False,
        }
        stored = self.ledger.add_adjudication(record)
        return {**record, **stored}

    def kwandocs_envelope(self, thread_id: str) -> dict[str, Any]:
        messages = [item for item in self.ledger.list_messages() if item["thread_id"] == thread_id]
        if not messages:
            raise KwanPromptsError("no messages for thread_id")
        message_hashes = [item["raw_sha256"] for item in messages]
        edges = [
            {"parent": item["parent_message_id"], "child": item["message_id"]}
            for item in messages
            if item.get("parent_message_id")
        ]
        body = {
            "schema": "kwanprompts.kwandocs-envelope.v0.1.0",
            "thread_id": thread_id,
            "population_scope": "single_llm_session_message_graph",
            "message_count": len(messages),
            "message_hashes": message_hashes,
            "edges": edges,
            "messages": messages,
            "raw_preserved": True,
            "kwandocs_ingestion_executed": False,
            "canonical_promotion": "REQUIRES_EXPLICIT_APPROVAL",
        }
        return {**body, "envelope_sha256": sha256_json(body)}

    @staticmethod
    def csi_projection(record: dict[str, Any]) -> dict[str, Any]:
        segments = record["structure"]["segments"]
        return {
            "schema": "kwanprompts.csi-projection.v0.1.0",
            "root_csi": {
                "uid_seed": record["raw_sha256"],
                "label": f"message:{record['message_id']}",
                "identitas": {
                    "statements": [
                        f"source_message_id={record['message_id']}",
                        f"raw_sha256={record['raw_sha256']}",
                        "raw content is immutable",
                    ],
                    "strata": [["RAW_MESSAGE"], ["NO_CANONICAL_PROMOTION_BY_CLASSIFICATION"]],
                    "explicitly_extensible": False,
                },
                "modi": ["RAW_CAPTURE", "FIRST_SEPARATOR", "REVIEW"],
                "active_modus": "FIRST_SEPARATOR",
                "domain": {"selector": record["thread_id"], "activation": "MESSAGE_RECEIVED"},
            },
            "segment_csis": [
                {
                    "segment_id": item["segment_id"],
                    "raw_sha256": item["raw_sha256"],
                    "relation": "NESTING",
                    "branch": item["classification"]["branch"],
                    "disposition": item["classification"]["disposition"],
                }
                for item in segments
            ],
            "message_level": {
                "branch": record["structure"]["branch"],
                "disposition": record["structure"]["disposition"],
                "canonical_status": "UNPROMOTED",
            },
            "authority_created": False,
        }

    def status(self) -> dict[str, Any]:
        verification = self.ledger.verify()
        return {
            "schema": "kwanprompts.status.v0.1.0",
            "canonical_name": "KwanPrompts",
            "kch_role": "CSI_PRESET_AND_MESSAGE_STRUCTURING_SUBSYSTEM",
            "first_separator": ["STRATEGIC_OR_INFORMATIVE", "INTERMEDIATE_OR_IRRELEVANT"],
            "unresolved_gate": "REVIEW_REQUIRED",
            "raw_preservation": True,
            "kwandocs_boundary": "EXPORT_ENVELOPE_ONLY__DURABLE_INGESTION_SEPARATE",
            "ledger": verification,
            "authority_created": False,
        }

