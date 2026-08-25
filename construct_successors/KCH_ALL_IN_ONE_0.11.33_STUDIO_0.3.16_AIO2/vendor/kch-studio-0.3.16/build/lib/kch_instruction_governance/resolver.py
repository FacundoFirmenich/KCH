from __future__ import annotations

from itertools import combinations
from typing import Any, Callable

from .credal import ConditionedCredalSet, StateSpace
from .models import (
    DecisionState,
    GovernanceContext,
    GovernanceLayer,
    Instruction,
    effects_conflict,
)
from .store import canonical_json, sha256_json


class InstructionResolver:
    """Hard-precedence resolver with a bounded credal lane.

    Hard authority, lifecycle, explicit supersession and applicability run
    before credal comparisons.  Credal mandate strength can break a tie only
    inside the same attested governance layer.
    """

    SCHEMA = "kch.ige.resolution.v0.3.0"

    def __init__(
        self,
        instruction_loader: Callable[[], list[Instruction]],
        profile_loader: Callable[[str], ConditionedCredalSet],
        *,
        state_space: StateSpace | None = None,
    ):
        self.instruction_loader = instruction_loader
        self.profile_loader = profile_loader
        self.state_space = state_space or StateSpace()

    def _profile(self, instruction: Instruction) -> ConditionedCredalSet | None:
        if instruction.credal_profile_id is None:
            return None
        try:
            profile = self.profile_loader(instruction.credal_profile_id)
        except KeyError:
            return None
        if profile.size != self.state_space.size:
            raise ValueError(
                f"credal profile {instruction.credal_profile_id} has an incompatible state space"
            )
        return profile

    def _credal_summary(self, instruction: Instruction) -> dict[str, Any]:
        profile = self._profile(instruction)
        if profile is None:
            return {
                "profile_id": instruction.credal_profile_id,
                "state": DecisionState.NOT_ESTIMABLE.value,
                "mandate_strength": None,
                "scope_breadth": None,
                "high_risk_probability": None,
            }
        mandate = self.state_space.mandate()
        scope = self.state_space.scope()
        high_risk = self.state_space.high_risk()
        return {
            "profile_id": instruction.credal_profile_id,
            "state": "ESTIMATED_FROM_DECLARED_CREDAL_PROFILE",
            "mandate_strength": {
                "lower": profile.lower_expectation(mandate),
                "upper": profile.upper_expectation(mandate),
            },
            "scope_breadth": {
                "lower": profile.lower_expectation(scope),
                "upper": profile.upper_expectation(scope),
            },
            "high_risk_probability": {
                "lower": profile.lower_expectation(high_risk),
                "upper": profile.upper_expectation(high_risk),
            },
        }

    def resolve(
        self,
        context: GovernanceContext,
        *,
        instruction_ids: list[str] | None = None,
        high_risk_threshold: float = 0.5,
    ) -> dict[str, Any]:
        if not 0 <= high_risk_threshold <= 1:
            raise ValueError("high_risk_threshold must lie in [0,1]")
        all_instructions = {item.instruction_id: item for item in self.instruction_loader()}
        requested = set(instruction_ids or all_instructions)
        unknown = sorted(requested - set(all_instructions))
        selected = [all_instructions[item_id] for item_id in sorted(requested & set(all_instructions))]
        unattested = sorted(
            item.instruction_id for item in selected if item.active and not item.authority_attested
        )
        applicable = [item for item in selected if item.applies_to(context)]
        by_id = {item.instruction_id: item for item in applicable}
        missing_dependencies = {
            item.instruction_id: sorted(set(item.depends_on) - set(by_id))
            for item in applicable
            if set(item.depends_on) - set(by_id)
        }

        if unknown or unattested or missing_dependencies:
            core = {
                "schema": self.SCHEMA,
                "decision": DecisionState.ABSTAIN.value,
                "context": context.to_dict(),
                "effective_instruction_ids": [],
                "defeated_instruction_ids": [],
                "unknown_instruction_ids": unknown,
                "unattested_instruction_ids": unattested,
                "missing_dependencies": missing_dependencies,
                "conflicts": [],
                "reason": "AUTHORITY_OR_DEPENDENCY_EVIDENCE_INCOMPLETE",
                "authority_created": False,
            }
            return {**core, "receipt_sha256": sha256_json(core)}

        if not applicable:
            core = {
                "schema": self.SCHEMA,
                "decision": DecisionState.NOT_APPLICABLE.value,
                "context": context.to_dict(),
                "effective_instruction_ids": [],
                "defeated_instruction_ids": [],
                "unknown_instruction_ids": unknown,
                "unattested_instruction_ids": unattested,
                "missing_dependencies": {},
                "conflicts": [],
                "reason": "NO_ACTIVE_ATTESTED_INSTRUCTION_APPLIES",
                "authority_created": False,
            }
            return {**core, "receipt_sha256": sha256_json(core)}

        summaries = {item.instruction_id: self._credal_summary(item) for item in applicable}
        defeated: set[str] = set()
        dominance: list[dict[str, Any]] = []
        unauthorized_supersession: list[dict[str, str]] = []

        # Explicit supersession is hard metadata and can only flow from an equal
        # or stronger layer (smaller numeric rank) to a weaker one.
        for item in applicable:
            for target_id in item.supersedes:
                target = by_id.get(target_id)
                if target is None:
                    continue
                if item.layer <= target.layer:
                    defeated.add(target_id)
                    dominance.append(
                        {
                            "winner": item.instruction_id,
                            "loser": target_id,
                            "basis": "EXPLICIT_AUTHORIZED_SUPERSESSION",
                        }
                    )
                else:
                    unauthorized_supersession.append(
                        {
                            "instruction_id": item.instruction_id,
                            "target_id": target_id,
                            "reason": "WEAKER_LAYER_CANNOT_SUPERSEDE_STRONGER_LAYER",
                        }
                    )

        unresolved: list[dict[str, Any]] = []
        for left, right in combinations(applicable, 2):
            if left.instruction_id in defeated or right.instruction_id in defeated:
                continue
            if not effects_conflict(left.effect, right.effect):
                continue
            if left.layer != right.layer:
                winner, loser = (left, right) if left.layer < right.layer else (right, left)
                defeated.add(loser.instruction_id)
                dominance.append(
                    {
                        "winner": winner.instruction_id,
                        "loser": loser.instruction_id,
                        "basis": "HARD_GOVERNANCE_LAYER_PRECEDENCE",
                    }
                )
                continue

            left_strength = summaries[left.instruction_id]["mandate_strength"]
            right_strength = summaries[right.instruction_id]["mandate_strength"]
            if left_strength is not None and right_strength is not None:
                if float(left_strength["lower"]) > float(right_strength["upper"]) + 1e-12:
                    defeated.add(right.instruction_id)
                    dominance.append(
                        {
                            "winner": left.instruction_id,
                            "loser": right.instruction_id,
                            "basis": "ROBUST_CREDAL_MANDATE_DOMINANCE_SAME_LAYER",
                        }
                    )
                    continue
                if float(right_strength["lower"]) > float(left_strength["upper"]) + 1e-12:
                    defeated.add(left.instruction_id)
                    dominance.append(
                        {
                            "winner": right.instruction_id,
                            "loser": left.instruction_id,
                            "basis": "ROBUST_CREDAL_MANDATE_DOMINANCE_SAME_LAYER",
                        }
                    )
                    continue
            unresolved.append(
                {
                    "instruction_ids": sorted([left.instruction_id, right.instruction_id]),
                    "layer": left.layer.name,
                    "effects": sorted([left.effect.value, right.effect.value]),
                    "basis": "NO_ROBUST_DOMINANCE",
                    "credal": {
                        left.instruction_id: summaries[left.instruction_id],
                        right.instruction_id: summaries[right.instruction_id],
                    },
                }
            )

        effective = sorted(
            (item for item in applicable if item.instruction_id not in defeated),
            key=lambda item: (int(item.layer), item.instruction_id),
        )
        if unauthorized_supersession:
            decision = DecisionState.BLOCK
            reason = "UNAUTHORIZED_PRECEDENCE_ESCALATION"
        elif unresolved:
            risk_upper = [
                float(summary["high_risk_probability"]["upper"])
                for conflict in unresolved
                for summary in conflict["credal"].values()
                if summary["high_risk_probability"] is not None
            ]
            hard_effect_conflict = any(
                GovernanceLayer[conflict["layer"]] <= GovernanceLayer.RULES
                for conflict in unresolved
            )
            if any(value >= high_risk_threshold for value in risk_upper) or not risk_upper or hard_effect_conflict:
                decision = DecisionState.ASK_USER
                reason = "UNRESOLVED_CONFLICT_REQUIRES_EXPLICIT_USER_CLARIFICATION"
            else:
                decision = DecisionState.CONFLICT_SET
                reason = "LOW_RISK_CONFLICT_PRESERVED_WITHOUT_ARBITRARY_TIE_BREAK"
        else:
            decision = DecisionState.APPLY
            reason = "HARD_PRECEDENCE_AND_ROBUST_COMPARISONS_CLOSED"

        core = {
            "schema": self.SCHEMA,
            "decision": decision.value,
            "context": context.to_dict(),
            "effective_instruction_ids": [item.instruction_id for item in effective],
            "defeated_instruction_ids": sorted(defeated),
            "dominance": dominance,
            "conflicts": unresolved,
            "unauthorized_supersession": unauthorized_supersession,
            "credal_summaries": summaries,
            "reason": reason,
            "authority_created": False,
            "hard_precedence_computed_credally": False,
            "lexicographic_semantic_winner_used": False,
        }
        return {**core, "receipt_sha256": sha256_json(core)}

    def compile_context(
        self,
        context: GovernanceContext,
        *,
        instruction_ids: list[str] | None = None,
        high_risk_threshold: float = 0.5,
    ) -> dict[str, Any]:
        resolution = self.resolve(
            context,
            instruction_ids=instruction_ids,
            high_risk_threshold=high_risk_threshold,
        )
        if resolution["decision"] != DecisionState.APPLY.value:
            return {
                "schema": "kch.ige.compiled-context.v0.3.0",
                "state": "NOT_COMPILED",
                "resolution": resolution,
                "instructions": [],
                "transport_json": None,
                "prompt_injection_immunity_established": False,
            }
        by_id = {item.instruction_id: item for item in self.instruction_loader()}
        records = [by_id[item_id].to_dict() for item_id in resolution["effective_instruction_ids"]]
        transport = {
            "schema": "kch.ige.instruction-data-envelope.v0.3.0",
            "notice": "DATA_RECORDS_NOT_A_NEW_AUTHORITY_CHANNEL",
            "resolution_receipt_sha256": resolution["receipt_sha256"],
            "instructions": records,
        }
        core = {
            "schema": "kch.ige.compiled-context.v0.3.0",
            "state": "COMPILED_STRUCTURED_DATA",
            "resolution": resolution,
            "instructions": records,
            "transport_json": canonical_json(transport),
            "prompt_injection_immunity_established": False,
            "host_must_preserve_attested_channel_boundary": True,
        }
        return {**core, "compiled_sha256": sha256_json(core)}
