"""Fail-closed authority logic for the RDSS temporal SHADOW gate.

This module is deliberately model-agnostic.  The GPU adapter supplies temporal
observations and frozen value estimates; this module decides whether authority
may leave the default TALON mass-right branch.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable, Mapping, Sequence


KEEP_DEFAULT = "KEEP_DEFAULT"
SWITCH_RESCUE = "SWITCH_RESCUE"
ABSTAIN = "ABSTAIN"
ASK = "ASK"


@dataclass(frozen=True)
class CandidateEstimate:
    action: str
    expected_gain: float
    gain_lcb95: float
    harm_probability_ucb95: float
    probe_cost: float
    observations: int

    def value_lcb_after_cost(self, risk_penalty: float = 1.0) -> float:
        return (
            float(self.gain_lcb95)
            - float(self.probe_cost)
            - risk_penalty * float(self.harm_probability_ucb95)
        )


@dataclass(frozen=True)
class GateConfig:
    default_action: str = "talon_mass_right"
    rescue_ladder: tuple[str, ...] = (
        "talon_mass_left",
        "talm_mass_right_soft",
        "baseline",
    )
    headroom_probability_threshold: float = 0.20
    minimum_observations: int = 2
    minimum_lcb_after_cost: float = 0.0
    harm_ucb95_delta: float = 0.025
    risk_penalty: float = 1.0
    fail_closed: bool = True


@dataclass(frozen=True)
class GateDecision:
    outcome: str
    generation_action: str
    probe_action: str | None
    reason: str
    headroom_probability: float
    selected_estimate: Mapping[str, object] | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class TemporalShadowGate:
    """Authority gate with a strict default branch and frozen-policy boundary."""

    def __init__(self, config: GateConfig | None = None, *, policy_frozen: bool = False):
        self.config = config or GateConfig()
        self.policy_frozen = bool(policy_frozen)

    def screen(self, headroom_probability: float, observations: int) -> bool:
        if observations < self.config.minimum_observations:
            return False
        return float(headroom_probability) >= self.config.headroom_probability_threshold

    def decide(
        self,
        *,
        headroom_probability: float,
        estimates: Sequence[CandidateEstimate] | Iterable[CandidateEstimate],
        observations: int,
        allow_ask: bool = False,
    ) -> GateDecision:
        cfg = self.config

        if not self.screen(headroom_probability, observations):
            return GateDecision(
                KEEP_DEFAULT,
                cfg.default_action,
                None,
                "cheap_screen_negative_or_immature",
                float(headroom_probability),
            )

        estimates = tuple(estimates)
        if not estimates:
            return GateDecision(
                ASK if allow_ask else ABSTAIN,
                cfg.default_action,
                None,
                "screen_positive_but_no_shadow_evidence",
                float(headroom_probability),
            )

        order = {name: index for index, name in enumerate(cfg.rescue_ladder)}
        admissible = [
            item
            for item in estimates
            if item.action in order
            and item.observations >= cfg.minimum_observations
            and item.harm_probability_ucb95 <= cfg.harm_ucb95_delta
            and item.value_lcb_after_cost(cfg.risk_penalty)
            > cfg.minimum_lcb_after_cost
        ]
        admissible.sort(
            key=lambda item: (
                -item.value_lcb_after_cost(cfg.risk_penalty),
                order[item.action],
            )
        )

        if not admissible:
            return GateDecision(
                KEEP_DEFAULT,
                cfg.default_action,
                None,
                "no_rescue_clears_value_and_harm_bounds",
                float(headroom_probability),
            )

        best = admissible[0]
        if not self.policy_frozen:
            return GateDecision(
                KEEP_DEFAULT,
                cfg.default_action,
                best.action,
                "shadow_only_policy_not_frozen",
                float(headroom_probability),
                asdict(best),
            )

        return GateDecision(
            SWITCH_RESCUE,
            best.action,
            best.action,
            "frozen_policy_rescue_clears_all_bounds",
            float(headroom_probability),
            asdict(best),
        )
