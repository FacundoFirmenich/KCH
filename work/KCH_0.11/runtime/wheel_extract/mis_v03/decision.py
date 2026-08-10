from __future__ import annotations

from collections.abc import Mapping as MappingABC
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType
from typing import Mapping

from .canonical import exact_fraction, fraction_text, validate_identifier_tuple
from .exact import ExactDistribution


@dataclass(frozen=True, slots=True)
class LossTable:
    actions: tuple[str, ...]
    states: tuple[str, ...]
    losses: Mapping[tuple[str, str], Fraction]

    def __post_init__(self) -> None:
        validate_identifier_tuple(self.actions, field="actions")
        validate_identifier_tuple(self.states, field="states")
        if not isinstance(self.losses, MappingABC):
            raise TypeError("losses must be a mapping")
        actions = tuple(sorted(self.actions))
        states = tuple(sorted(self.states))
        expected = {(action, state) for action in actions for state in states}
        if set(self.losses) != expected:
            raise ValueError("loss table must cover the full action-state product")
        normalized = {
            key: exact_fraction(value, field=f"loss[{key[0]},{key[1]}]")
            for key, value in self.losses.items()
        }
        if any(value < 0 for value in normalized.values()):
            raise ValueError("losses cannot be negative")
        object.__setattr__(self, "actions", actions)
        object.__setattr__(self, "states", states)
        object.__setattr__(self, "losses", MappingProxyType(normalized))

    def risk(self, action: str, posterior: ExactDistribution) -> Fraction:
        if posterior.states != self.states:
            raise ValueError("posterior support and loss-table states differ")
        return sum(
            posterior.probability(state) * self.losses[(action, state)]
            for state in self.states
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "MIS_LOSS_TABLE_v0.3.1",
            "actions": list(self.actions),
            "states": list(self.states),
            "losses": {
                action: {state: fraction_text(self.losses[(action, state)]) for state in self.states}
                for action in self.actions
            },
        }


@dataclass(frozen=True, slots=True)
class BayesDecision:
    minimizers: tuple[str, ...]
    risks: Mapping[str, Fraction]
    minimum_risk: Fraction
    resolved_action: str | None
    tie_resolution: str

    def __post_init__(self) -> None:
        validate_identifier_tuple(self.minimizers, field="minimizers", require_sorted=True)
        if not isinstance(self.risks, MappingABC):
            raise TypeError("risks must be a mapping")
        risk_actions = validate_identifier_tuple(tuple(self.risks), field="risk actions")
        normalized_risks = {
            action: exact_fraction(self.risks[action], field=f"risk[{action}]")
            for action in sorted(risk_actions)
        }
        if any(risk < 0 for risk in normalized_risks.values()):
            raise ValueError("risks cannot be negative")
        minimum_risk = exact_fraction(self.minimum_risk, field="minimum_risk")
        actual_minimum = min(normalized_risks.values())
        if minimum_risk != actual_minimum:
            raise ValueError("minimum_risk does not equal the minimum declared risk")
        expected_minimizers = tuple(
            action for action in sorted(normalized_risks) if normalized_risks[action] == actual_minimum
        )
        if self.minimizers != expected_minimizers:
            raise ValueError("minimizers do not equal the complete risk argmin")
        if self.resolved_action is not None:
            if not isinstance(self.resolved_action, str):
                raise TypeError("resolved_action must be a string or None")
            if not self.resolved_action.strip():
                raise ValueError("resolved_action cannot be empty or blank")
        valid_resolutions = {"UNIQUE_MINIMUM", "EXPLICIT_TIE_ACTION", "UNRESOLVED_TIE"}
        if self.tie_resolution not in valid_resolutions:
            raise ValueError("unknown tie_resolution")
        if self.tie_resolution == "UNIQUE_MINIMUM":
            if len(self.minimizers) != 1 or self.resolved_action != self.minimizers[0]:
                raise ValueError("UNIQUE_MINIMUM requires its sole minimizer as resolved_action")
        elif self.tie_resolution == "EXPLICIT_TIE_ACTION":
            if len(self.minimizers) < 2 or self.resolved_action is None:
                raise ValueError("EXPLICIT_TIE_ACTION requires a tie and an explicit action")
        elif len(self.minimizers) < 2 or self.resolved_action is not None:
            raise ValueError("UNRESOLVED_TIE requires multiple minimizers and no resolved action")
        object.__setattr__(self, "risks", MappingProxyType(normalized_risks))
        object.__setattr__(self, "minimum_risk", minimum_risk)

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "MIS_BAYES_DECISION_v0.3.1",
            "minimizers": list(self.minimizers),
            "risks": {action: fraction_text(self.risks[action]) for action in sorted(self.risks)},
            "minimum_risk": fraction_text(self.minimum_risk),
            "resolved_action": self.resolved_action,
            "tie_resolution": self.tie_resolution,
        }


def bayes_decide(
    posterior: ExactDistribution,
    loss_table: LossTable,
    *,
    tie_action: str | None = None,
) -> BayesDecision:
    risks = {action: loss_table.risk(action, posterior) for action in loss_table.actions}
    minimum = min(risks.values())
    if tie_action is not None:
        if not isinstance(tie_action, str):
            raise TypeError("tie_action must be a string or None")
        if not tie_action.strip():
            raise ValueError("tie_action cannot be empty or blank")
    minimizers = tuple(sorted(action for action, risk in risks.items() if risk == minimum))
    if len(minimizers) == 1:
        resolved = minimizers[0]
        tie_resolution = "UNIQUE_MINIMUM"
    elif tie_action is not None:
        resolved = tie_action
        tie_resolution = "EXPLICIT_TIE_ACTION"
    else:
        resolved = None
        tie_resolution = "UNRESOLVED_TIE"
    return BayesDecision(minimizers, risks, minimum, resolved, tie_resolution)
