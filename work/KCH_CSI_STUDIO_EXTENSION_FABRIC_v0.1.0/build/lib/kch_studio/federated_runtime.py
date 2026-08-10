from __future__ import annotations

import importlib
import sqlite3
import sys
import uuid
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .contracts import canonical_json, sha256_json, sqlite_connection
from .installation import ConsentDecision, ConsentPolicy


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _enable_bundled_vendor_imports() -> None:
    """Make the frozen pure-Python component wheels importable in source checkouts.

    Portable installations install these wheels normally.  A source checkout keeps
    them in the frozen KCH 0.11 vendor directory; zipimport can load them without
    extracting or rewriting the historical bytes.
    """

    candidate = Path(__file__).resolve().parents[3] / "KCH_0.11_REEXTRACT_FINAL" / "vendor"
    if not candidate.is_dir():
        return
    for wheel in sorted(candidate.glob("*.whl")):
        value = str(wheel)
        if value not in sys.path:
            sys.path.append(value)


def _import(name: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError:
        _enable_bundled_vendor_imports()
        return importlib.import_module(name)


class RigorRuntime:
    """Operational adapter for the packaged Rigor Gradient Governor (RGG)."""

    def __init__(self) -> None:
        self.module = _import("kch_rigor_governor")

    def status(self) -> dict[str, Any]:
        return {
            "schema": "kch.rgg-runtime-status.v0.2.0",
            "state": "AVAILABLE_OPERATIONAL",
            "profiles": self.module.PROFILES,
            "operations": [
                "resolve_profile",
                "adjudicate_action",
                "audit_review",
                "transition_plan",
            ],
            "mode": "SHADOW_ONLY",
            "authority_created": False,
        }

    def resolve_profile(self, value: dict[str, Any]) -> dict[str, Any]:
        return self.module.resolve_profile(value)

    def adjudicate_action(self, value: dict[str, Any]) -> dict[str, Any]:
        return self.module.adjudicate_action(value)

    def audit_review(self, value: dict[str, Any]) -> dict[str, Any]:
        return self.module.audit_review(value)

    def transition_plan(self, value: dict[str, Any]) -> dict[str, Any]:
        return self.module.transition_plan(value)


class KwanPromptsRuntime:
    """Stateful adapter for the packaged KwanPrompts message-governance service."""

    def __init__(self, root: str | Path) -> None:
        root = Path(root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        ledger_module = _import("kwanprompts.ledger_final")
        service_module = _import("kwanprompts.service_final")
        self.service = service_module.KwanPromptsService(
            ledger_module.KwanPromptsLedger(root / "kwanprompts.sqlite3")
        )

    def status(self) -> dict[str, Any]:
        return self.service.status()

    def ingest(self, value: dict[str, Any]) -> dict[str, Any]:
        return self.service.ingest(value)

    def inspect(self, message_id: str) -> dict[str, Any]:
        return self.service.inspect(message_id)

    def adjudicate(self, value: dict[str, Any]) -> dict[str, Any]:
        return self.service.adjudicate(value)

    def kwandocs_envelope(self, thread_id: str) -> dict[str, Any]:
        return self.service.kwandocs_envelope(thread_id)

    def verify(self) -> dict[str, Any]:
        return self.service.ledger.verify()


class SCORuntime:
    """Operational adapter for the sovereign SuperChats Orchestrators ledger."""

    def __init__(self, root: str | Path) -> None:
        root = Path(root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        module = _import("kch_sco")
        self.service = module.SCOService(root / "sco.sqlite3")

    def status(self, sco_id: str | None = None) -> dict[str, Any]:
        return {
            "schema": "kch.sco-runtime-status.v0.2.0",
            "projection": self.service.projection(sco_id),
            "integrity": self.service.verify(),
            "live_cross_provider_dispatch": False,
            "host_bridge_required": True,
            "context_fusion": False,
            "member_independence_preserved": True,
            "authority_created": False,
        }

    @staticmethod
    def _write_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "actor": str(arguments["actor"]),
            "command_id": str(arguments["command_id"]),
            "expected_head_hash": str(arguments["expected_head_hash"]),
        }

    def create(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.service.create_superchat(
            dict(arguments["record"]), **self._write_arguments(arguments)
        )

    def add_node(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.service.add_node(dict(arguments["record"]), **self._write_arguments(arguments))

    def retire_node(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.service.retire_node(
            str(arguments["sco_id"]),
            str(arguments["node_id"]),
            **self._write_arguments(arguments),
        )

    def add_edge(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.service.add_edge(dict(arguments["record"]), **self._write_arguments(arguments))

    def issue_work_order(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.service.issue_work_order(
            dict(arguments["record"]), **self._write_arguments(arguments)
        )

    def ingest_receipt(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.service.ingest_receipt(
            dict(arguments["record"]), **self._write_arguments(arguments)
        )

    def declare_conflict(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.service.declare_conflict(
            dict(arguments["record"]), **self._write_arguments(arguments)
        )

    def schedule(self, sco_id: str) -> dict[str, Any]:
        return self.service.schedule(sco_id)

    def graph_diagnostics(self, sco_id: str) -> dict[str, Any]:
        return self.service.graph_diagnostics(sco_id)

    def export_bundle(self, sco_id: str) -> dict[str, Any]:
        return self.service.export_bundle(sco_id)

    def dispatch_envelopes(self, sco_id: str) -> list[dict[str, Any]]:
        return self.service.dispatch_envelopes(sco_id)


PHL_LINK_DDL = """
CREATE TABLE IF NOT EXISTS session_links (
    public_session_id TEXT PRIMARY KEY,
    effective_session_id TEXT NOT NULL UNIQUE,
    learning_session_id TEXT NOT NULL UNIQUE,
    trigger TEXT NOT NULL,
    consent TEXT NOT NULL,
    state TEXT NOT NULL,
    started_at TEXT NOT NULL,
    closed_at TEXT,
    feedback_count INTEGER NOT NULL DEFAULT 0,
    packet_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT
);
"""


class PHLRuntime:
    """Effective, user-governed PHL bridge with an exclusive ordinary-work lock.

    The packaged effective-integration service owns the mutation gate.  The
    packaged learning workbench owns decisions, scores and future-only training
    packets.  This bridge links their otherwise independent session identifiers
    and makes split state explicit instead of silently treating either ledger as
    sufficient on its own.
    """

    SERVICE_ID = "KCH_SUPER_MCP_INTEGRATED"
    CONTROL_TOOLS = {
        "phl_status",
        "phl_decisions_list",
        "phl_session_start",
        "phl_score",
        "phl_packet_compile",
        "phl_session_close",
        "phl_decision_register",
        "mis_decision_register_phl",
    }

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        integration_module = _import("kch_phl_integration")
        learning_ledger = _import("kch_learning.ledger_release")
        learning_service = _import("kch_learning.service_release")
        self.integration = integration_module.EffectiveIntegrationService(
            self.root / "effective-integration.sqlite3"
        )
        self.learning_ledger = learning_ledger.LearningLedger(self.root / "learning.sqlite3")
        self.learning = learning_service.LearningService(self.learning_ledger)
        self.links_path = self.root / "phl-runtime.sqlite3"
        self.consent = ConsentPolicy()
        self.client = {
            "client_id": "KCH_USER_GOVERNED_PHL",
            "client_instance_id": sha256_json(str(self.root))[:32],
        }
        with closing(self.connect()) as connection:
            connection.executescript(PHL_LINK_DDL)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite_connection(self.links_path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def register_capabilities(self, tools: list[dict[str, Any]]) -> dict[str, Any]:
        registered = 0
        for descriptor in sorted(tools, key=lambda item: item["name"]):
            name = str(descriptor["name"])
            if name in self.CONTROL_TOOLS:
                continue
            record = {
                "service_id": self.SERVICE_ID,
                "method": name,
                "classification": "READ_ONLY" if descriptor["readOnly"] else "MUTATING",
                "evidence_ref": f"KCH_CSI_STUDIO_TOOL_DESCRIPTOR:{name}",
            }
            request_id = "PHL-CATALOG-" + sha256_json(record)[:32]
            self.integration.register_mutability(
                record,
                client=self.client,
                request_id=request_id,
                expected_head_hash=self.integration.head(),
            )
            registered += 1
        return {
            "registered_or_replayed": registered,
            "effective_catalog_size": self.integration.projection()["mutability_methods"],
        }

    def dispatch(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        handler: Callable[[dict[str, Any]], Any],
    ) -> Any:
        if tool_name in self.CONTROL_TOOLS:
            return handler(arguments)
        receipt = self.integration.dispatch(
            self.SERVICE_ID,
            tool_name,
            arguments,
            lambda: handler(arguments),
            client=self.client,
            request_id=f"PHL-DISPATCH-{uuid.uuid4()}",
            expected_head_hash=self.integration.head(),
        )
        result = receipt["result"]
        if not result["allowed"]:
            raise PermissionError(
                canonical_json(
                    {
                        "state": "BLOCKED_BY_PHL_EXCLUSIVE_LOCK",
                        "tool": tool_name,
                        "reason": result["reason"],
                        "active_phl_session_id": self.integration.projection()[
                            "active_phl_session_id"
                        ],
                    }
                )
            )
        return result["executor_result"]

    def register_decision(self, record: dict[str, Any]) -> dict[str, Any]:
        if self.integration.projection()["active_phl_session_id"] is not None:
            raise PermissionError("reviewable-decision inventory is frozen during active PHL")
        validated = _import("kch_phl_integration.contracts").validate_reviewable_decision(record)
        component_id = str(record["component_id"])
        emitter = {
            "component_id": component_id,
            "registry_name": component_id,
            "inventory_state": "DECISION_EMITTER",
            "evidence_ref": str(record["source_uri"]),
        }
        emitter_receipt = self.integration.register_emitter(
            emitter,
            client=self.client,
            request_id="PHL-EMITTER-" + sha256_json(emitter)[:32],
            expected_head_hash=self.integration.head(),
        )
        effective_receipt = self.integration.register_decision(
            validated["record"],
            client=self.client,
            request_id="PHL-DECISION-" + validated["record_sha256"][:32],
            expected_head_hash=self.integration.head(),
        )
        learning_record = {
            **record,
            "component": component_id,
            "alternatives": list(record["alternatives_considered"]),
            "evidence": list(record["evidence_ids"]),
            "uncertainty": record["confidence_representation"],
            "policy_version": list(record["active_rule_ids"]),
            "claim_scope": record["claim_ceiling"],
        }
        learning_receipt = self.learning.register_decision(learning_record)
        return {
            "decision_id": record["decision_id"],
            "record_sha256": validated["record_sha256"],
            "contract_state": validated["contract_state"],
            "emitter": emitter_receipt,
            "effective": effective_receipt,
            "learning": learning_receipt,
            "reviewable_for_phl": True,
            "decision_authority_created": False,
            "historical_decision_mutated": False,
            "training_executed": False,
        }

    def list_decisions(
        self, component: str | None = None, reviewed: bool | None = None
    ) -> list[dict[str, Any]]:
        return self.learning_ledger.list_decisions(component=component, reviewed=reviewed)

    def _active_link(self, public_session_id: str) -> dict[str, Any]:
        with closing(self.connect()) as connection:
            row = connection.execute(
                "SELECT * FROM session_links WHERE public_session_id=?",
                (public_session_id,),
            ).fetchone()
        if row is None:
            raise KeyError(public_session_id)
        value = dict(row)
        if value["state"] != "ACTIVE":
            raise ValueError("PHL session is not active")
        return value

    def start(self, *, trigger: str, consent: str) -> dict[str, Any]:
        decision = ConsentDecision(consent)
        if not self.consent.adjudicate(decision):
            return {
                "state": "DECLINED_NO_PHL_SESSION_STARTED",
                "consent": decision.value,
                "session_policy": self.consent.state(),
                "phl_authorized": True,
                "training_executed": False,
            }
        current = self.status()
        if current["effective"]["active_phl_session_id"] is not None:
            raise RuntimeError("PHL session already active")
        effective_receipt = self.integration.start_phl(
            client=self.client,
            request_id=f"PHL-START-{uuid.uuid4()}",
            expected_head_hash=self.integration.head(),
            trigger=trigger,
        )
        effective_session_id = str(effective_receipt["result"]["session_id"])
        try:
            learning_receipt = self.learning.start_phl(trigger)
        except Exception:
            self.integration.close_phl(
                effective_session_id,
                client=self.client,
                request_id=f"PHL-COMPENSATE-{uuid.uuid4()}",
                expected_head_hash=self.integration.head(),
            )
            raise
        public_session_id = f"PHL-{uuid.uuid4()}"
        with closing(self.connect()) as connection:
            connection.execute(
                "INSERT INTO session_links VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (
                    public_session_id,
                    effective_session_id,
                    str(learning_receipt["session_id"]),
                    trigger,
                    decision.value,
                    "ACTIVE",
                    utc_now(),
                    None,
                    0,
                    0,
                    None,
                ),
            )
            connection.commit()
        return {
            "schema": "kch.phl-linked-session.v0.2.0",
            "state": "ACTIVE",
            "public_session_id": public_session_id,
            "effective_session_id": effective_session_id,
            "learning_session_id": learning_receipt["session_id"],
            "exclusive": True,
            "ordinary_kch_mutating_work_allowed": False,
            "phl_authorized": True,
            "training_executed": False,
            "consent": decision.value,
            "consent_attestation": "DECLARED_BY_CALLER_NOT_CRYPTOGRAPHIC_HOST_IDENTITY",
        }

    def score(
        self,
        *,
        public_session_id: str,
        decision_id: str,
        score_display: str,
        contextual_text: str,
        correction_text: str,
        user_authored: bool,
        consent: str,
    ) -> dict[str, Any]:
        if user_authored is not True:
            raise PermissionError("PHL score authorship is reserved to the user")
        decision = ConsentDecision(consent)
        if not self.consent.adjudicate(decision):
            return {
                "state": "DECLINED_NO_FEEDBACK_RECORDED",
                "public_session_id": public_session_id,
                "consent": decision.value,
            }
        link = self._active_link(public_session_id)
        receipt = self.learning.score_phl(
            str(link["learning_session_id"]),
            decision_id,
            score_display,
            contextual_text,
            correction_text,
        )
        with closing(self.connect()) as connection:
            connection.execute(
                "UPDATE session_links SET feedback_count=feedback_count+1 WHERE public_session_id=?",
                (public_session_id,),
            )
            connection.commit()
        return {
            **receipt,
            "public_session_id": public_session_id,
            "phl_authorized": True,
            "training_executed": True,
            "historical_decision_mutated": False,
            "future_only": True,
            "consent_attestation": "DECLARED_BY_CALLER_NOT_CRYPTOGRAPHIC_HOST_IDENTITY",
        }

    def compile_packet(self, public_session_id: str) -> dict[str, Any]:
        link = self._active_link(public_session_id)
        receipt = self.learning.compile_training_packet(str(link["learning_session_id"]))
        with closing(self.connect()) as connection:
            connection.execute(
                "UPDATE session_links SET packet_count=packet_count+1 WHERE public_session_id=?",
                (public_session_id,),
            )
            connection.commit()
        return {
            **receipt,
            "public_session_id": public_session_id,
            "activation_authorized": False,
            "automatic_promotion": False,
        }

    def close_session(self, public_session_id: str) -> dict[str, Any]:
        link = self._active_link(public_session_id)
        learning_receipt = self.learning.close_session(str(link["learning_session_id"]))
        try:
            effective_receipt = self.integration.close_phl(
                str(link["effective_session_id"]),
                client=self.client,
                request_id=f"PHL-CLOSE-{uuid.uuid4()}",
                expected_head_hash=self.integration.head(),
            )
        except Exception as exc:
            with closing(self.connect()) as connection:
                connection.execute(
                    "UPDATE session_links SET state='DEGRADED_EFFECTIVE_LOCK_REMAINS',last_error=? WHERE public_session_id=?",
                    (f"{type(exc).__name__}: {exc}", public_session_id),
                )
                connection.commit()
            raise
        with closing(self.connect()) as connection:
            connection.execute(
                "UPDATE session_links SET state='CLOSED',closed_at=? WHERE public_session_id=?",
                (utc_now(), public_session_id),
            )
            connection.commit()
        return {
            "state": "CLOSED",
            "public_session_id": public_session_id,
            "learning": learning_receipt,
            "effective": effective_receipt,
            "ordinary_kch_mutating_work_allowed": True,
        }

    def status(self) -> dict[str, Any]:
        effective = self.integration.projection()
        effective_integrity = self.integration.verify()
        learning_integrity = self.learning_ledger.verify()
        with closing(self.learning_ledger._connect()) as connection:
            feedback = int(
                connection.execute("SELECT COUNT(*) FROM feedback WHERE channel='PHL'").fetchone()[
                    0
                ]
            )
            decisions = int(connection.execute("SELECT COUNT(*) FROM decisions").fetchone()[0])
            packets = int(connection.execute("SELECT COUNT(*) FROM training_packets").fetchone()[0])
            active_learning = self.learning_ledger.active_phl_session()
        with closing(self.connect()) as connection:
            links = [
                dict(row)
                for row in connection.execute("SELECT * FROM session_links ORDER BY started_at")
            ]
        active_links = [item for item in links if item["state"] == "ACTIVE"]
        consistency_errors: list[str] = []
        if bool(effective["active_phl_session_id"]) != bool(active_learning):
            consistency_errors.append("EFFECTIVE_AND_LEARNING_LOCK_DIVERGENCE")
        if bool(active_links) != bool(active_learning):
            consistency_errors.append("LINK_AND_LEARNING_LOCK_DIVERGENCE")
        if active_links and (
            active_links[0]["effective_session_id"] != effective["active_phl_session_id"]
            or active_links[0]["learning_session_id"] != active_learning
        ):
            consistency_errors.append("ACTIVE_SESSION_IDENTIFIER_DIVERGENCE")
        return {
            "schema": "kch.phl-runtime-status.v0.2.0",
            "phl_authorized": True,
            "authorization_scope": "KCH_LOCAL_USER_GOVERNED_CAPABILITY",
            "capability_available": True,
            "training_executed": feedback > 0,
            "training_feedback_count": feedback,
            "reviewable_decisions": decisions,
            "training_packets": packets,
            "active_public_session_id": active_links[0]["public_session_id"]
            if active_links
            else None,
            "active_learning_session_id": active_learning,
            "effective": effective,
            "effective_integrity": effective_integrity,
            "learning_integrity": learning_integrity,
            "bridge_consistent": not consistency_errors,
            "bridge_errors": consistency_errors,
            "automatic_promotion": False,
            "packet_activation_authorized": False,
            "historical_decisions_mutated": False,
            "session_policy": self.consent.state(),
        }
