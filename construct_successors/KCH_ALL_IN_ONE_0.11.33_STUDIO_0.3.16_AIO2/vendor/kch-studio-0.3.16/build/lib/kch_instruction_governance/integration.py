from __future__ import annotations

from pathlib import Path
from typing import Any

from .credal import ConditionedCredalSet, StateSpace
from .elicitation import ClarificationQuestion, rank_questions
from .models import GovernanceContext
from .resolver import InstructionResolver
from .store import InstructionEventStore


class KCHInstructionGovernance:
    """Complete local candidate kernel with native-first host bindings.

    The class exposes handlers and tool descriptors but does not start a server,
    mutate the stable KCH tree, or claim that the host has interposed the tools.
    """

    def __init__(self, root: str | Path, *, state_space: StateSpace | None = None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_space = state_space or StateSpace()
        self.store = InstructionEventStore(self.root / "instruction_governance.sqlite3")
        self.resolver = InstructionResolver(
            lambda: self.store.current_instructions(),
            self.store.get_profile,
            state_space=self.state_space,
        )

    def instruction_commit(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.store.commit_instruction(
            str(arguments["command_id"]), dict(arguments["instruction"])
        )

    def instruction_revoke(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.store.revoke_instruction(
            str(arguments["command_id"]),
            str(arguments["instruction_id"]),
            reason=str(arguments["reason"]),
            authority_receipt_sha256=str(arguments["authority_receipt_sha256"]),
        )

    def credal_profile_commit(self, arguments: dict[str, Any]) -> dict[str, Any]:
        profile = ConditionedCredalSet.from_dict(dict(arguments["profile"]))
        if profile.size != self.state_space.size:
            raise ValueError("profile has an incompatible state space")
        return self.store.commit_profile(
            str(arguments["command_id"]),
            str(arguments["profile_id"]),
            profile,
            [str(item) for item in arguments["evidence_refs"]],
        )

    def resolve(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.resolver.resolve(
            GovernanceContext.from_dict(dict(arguments["context"])),
            instruction_ids=[str(item) for item in arguments.get("instruction_ids", [])]
            or None,
            high_risk_threshold=float(arguments.get("high_risk_threshold", 0.5)),
        )

    def compile_context(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.resolver.compile_context(
            GovernanceContext.from_dict(dict(arguments["context"])),
            instruction_ids=[str(item) for item in arguments.get("instruction_ids", [])]
            or None,
            high_risk_threshold=float(arguments.get("high_risk_threshold", 0.5)),
        )

    def clarification_rank(self, arguments: dict[str, Any]) -> dict[str, Any]:
        profile = self.store.get_profile(str(arguments["profile_id"]))
        questions = [
            ClarificationQuestion.from_dict(dict(item)) for item in arguments["questions"]
        ]
        return rank_questions(profile, questions, state_space=self.state_space)

    def status(self) -> dict[str, Any]:
        snapshot = self.store.snapshot()
        return {
            "schema": "kch.ige.status.v0.3.0",
            "state_space_cells": self.state_space.size,
            "store": snapshot["integrity"],
            "instruction_count": len(snapshot["instructions"]),
            "credal_profile_count": len(snapshot["credal_profiles"]),
            "hard_precedence": "EXTERNAL_PLATFORM > HARNESS > AGENTS > RULES > SESSION_POLICY",
            "credal_authority_inference_prohibited": True,
            "concurrency_model": "SQLITE_WAL_BEGIN_IMMEDIATE_SERIALIZED_LOCAL_WRITES",
            "distributed_linearizability_established": False,
            "multi_user_security_established": False,
            "physical_append_only_established": False,
            "mutating_execution_authorized": False,
            "stable_kch_modified": False,
            "native_host_interposition_established": False,
            "mcp_required": False,
            "api_exposed": False,
            "phl_training_executed": False,
            "claim_ceiling": "LOCAL_EXECUTABLE_CSI_SUCCESSOR_CANDIDATE_NOT_PROMOTED_NOT_HOST_VALIDATED",
        }

    def handlers(self) -> dict[str, Any]:
        return {
            "instruction_governance_status": lambda _a: self.status(),
            "instruction_governance_resolve": self.resolve,
            "instruction_governance_compile_context": self.compile_context,
            "instruction_governance_clarification_rank": self.clarification_rank,
            "instruction_governance_commit": self.instruction_commit,
            "instruction_governance_revoke": self.instruction_revoke,
            "instruction_governance_credal_profile_commit": self.credal_profile_commit,
        }

    @staticmethod
    def tool_descriptors() -> list[dict[str, Any]]:
        def descriptor(name: str, description: str, *, read_only: bool) -> dict[str, Any]:
            return {
                "name": name,
                "title": name.replace("_", " ").title(),
                "description": description,
                "inputSchema": {
                    "type": "object",
                    "additionalProperties": True,
                },
                "readOnly": read_only,
            }

        return [
            descriptor(
                "instruction_governance_status",
                "Inspect the bounded KCH instruction-governance candidate without creating authority.",
                read_only=True,
            ),
            descriptor(
                "instruction_governance_resolve",
                "Resolve applicable instructions under hard KCH precedence and bounded credal ties.",
                read_only=True,
            ),
            descriptor(
                "instruction_governance_compile_context",
                "Compile only a closed APPLY resolution as structured data, not a new authority channel.",
                read_only=True,
            ),
            descriptor(
                "instruction_governance_clarification_rank",
                "Rank calibrated clarification questions by robust decisional-imprecision contraction.",
                read_only=True,
            ),
            descriptor(
                "instruction_governance_commit",
                "Commit an attested, versioned instruction and custody event atomically.",
                read_only=False,
            ),
            descriptor(
                "instruction_governance_revoke",
                "Append an authority-bound revocation as a new instruction version.",
                read_only=False,
            ),
            descriptor(
                "instruction_governance_credal_profile_commit",
                "Commit an evidence-referenced credal profile atomically.",
                read_only=False,
            ),
        ]

    def native_hook_contract(self) -> dict[str, Any]:
        return {
            "schema": "kch.ige.native-hook-contract.v0.3.0",
            "SessionStart": ["load integrity-verified instruction snapshot"],
            "UserPromptSubmit": [
                "register candidates only when an authority compiler attests the source",
                "resolve semantic ambiguity and request explicit clarification when unresolved",
            ],
            "PreToolUse": [
                "enforce deterministic constitutional layers before credal resolution",
                "classify read-only inspection separately from mutation",
                "never bypass KCH constitutional locks",
            ],
            "PostToolUse": ["append outcome evidence through the host's transactional bridge"],
            "PreCompact": ["persist snapshot hash and unresolved conflict set"],
            "Stop": ["preserve explicit stop semantics and governing mission terminal state"],
            "SessionEnd": ["close finite leases and persist final projection"],
            "automatic_host_interposition_established": False,
            "requires_stable_patch_after_gate": True,
            "mcp_fallback_needed": False,
        }
