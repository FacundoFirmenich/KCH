from __future__ import annotations

import numpy as np
import pytest

from kch_instruction_governance.credal import (
    ConditionedCredalSet,
    LinearCredalSet,
    StateSpace,
)
from kch_instruction_governance.elicitation import (
    ClarificationQuestion,
    rank_questions,
)


def test_exact_sequential_conditioning_preserves_base_polytope() -> None:
    base = LinearCredalSet([0.1, 0.2, 0.0], [0.7, 0.8, 0.7])
    first = base.conditioned().update([0.8, 0.4, 0.2])
    sequential = first.update([0.5, 0.75, 0.25])
    direct = base.conditioned().update([0.4, 0.3, 0.05])
    for functional in ([1, 0, 0], [0, 1, 0], [0.2, 0.5, 1]):
        assert sequential.lower_expectation(functional) == pytest.approx(
            direct.lower_expectation(functional)
        )
        assert sequential.upper_expectation(functional) == pytest.approx(
            direct.upper_expectation(functional)
        )


def test_reporting_cell_bounds_does_not_replace_posterior_representation() -> None:
    base = LinearCredalSet([0.0, 0.0], [1.0, 1.0], extra_a_ub=[[1.0, -1.0]], extra_b_ub=[0.2])
    profile = base.conditioned().update([0.9, 0.3])
    rows = profile.cell_probability_bounds()
    assert len(rows) == 2
    assert profile.to_dict()["posterior_representation"].endswith("NOT_INTERVAL_HULL")


def test_uncalibrated_question_is_not_estimable() -> None:
    space = StateSpace()
    profile = LinearCredalSet.vacuous(space.size).conditioned()
    question = ClarificationQuestion(
        question_id="Q1",
        prompt="¿Qué alcance quiso declarar?",
        cost=1.0,
        outcome_likelihoods={
            "LOCAL": tuple(np.where(space.scope() <= 1, 0.8, 0.2)),
            "GLOBAL": tuple(np.where(space.scope() >= 2, 0.8, 0.2)),
        },
        calibration_receipt_sha256=None,
    )
    result = rank_questions(profile, [question], state_space=space)
    assert result["state"] == "NOT_ESTIMABLE"
    assert result["recommended_action"] == "STOP_ELICITATION"
    assert result["stop_reason"] == "QUESTION_VALUE_NOT_ESTIMABLE"
    assert result["user_consultation_required"] is False
    assert result["automatic_execution_authorized"] is False
    assert result["ranking"][0]["invented_answer_fidelity_used"] is False


def test_calibrated_question_uses_robust_minimax_not_midpoint_prediction() -> None:
    space = StateSpace()
    lower = np.full(space.size, 1 / space.size)
    profile = LinearCredalSet(lower, lower).conditioned()
    question = ClarificationQuestion(
        question_id="Q-CAL",
        prompt="¿La instrucción se limita al documento actual?",
        cost=2.0,
        outcome_likelihoods={
            "SI": tuple(np.where(space.scope() <= 1, 0.95, 0.05)),
            "NO": tuple(np.where(space.scope() >= 2, 0.95, 0.05)),
        },
        calibration_receipt_sha256="a" * 64,
    )
    result = rank_questions(profile, [question], state_space=space)
    row = result["ranking"][0]
    assert result["criterion"].startswith("ROBUST_WORST_CASE")
    assert row["predictive_midpoint_used"] is False
    assert row["expected_information_gain_claimed"] is False
    assert result["recommended_action"] == "STOP_ELICITATION"
    assert result["stop_reason"] == "NO_POSITIVE_ROBUST_CONTRACTION"
    assert result["user_consultation_required"] is False
    assert result["automatic_execution_authorized"] is False


def test_calibrated_question_is_asked_only_with_positive_robust_contraction() -> None:
    space = StateSpace()
    profile = LinearCredalSet.vacuous(space.size).conditioned()
    outcomes: dict[str, tuple[float, ...]] = {}
    for mandate_name, mandate_mask in (
        ("MANDATE_LOW", space.mandate() <= 2),
        ("MANDATE_HIGH", space.mandate() >= 3),
    ):
        for scope_name, scope_mask in (
            ("SCOPE_LOCAL", space.scope() <= 1),
            ("SCOPE_WIDE", space.scope() >= 2),
        ):
            for risk_name, risk_mask in (
                ("RISK_LOW", space.risk() <= 2),
                ("RISK_HIGH", space.risk() >= 3),
            ):
                outcomes[f"{mandate_name}:{scope_name}:{risk_name}"] = tuple(
                    (mandate_mask & scope_mask & risk_mask).astype(float)
                )
    question = ClarificationQuestion(
        question_id="Q-ROBUSTLY-BENEFICIAL",
        prompt="¿Cuál de estas ocho interpretaciones atestadas corresponde?",
        cost=1.0,
        outcome_likelihoods=outcomes,
        calibration_receipt_sha256="b" * 64,
    )
    result = rank_questions(profile, [question], state_space=space)
    assert result["state"] == "RANKED"
    assert result["recommended_action"] == "ASK_USER"
    assert result["stop_reason"] is None
    assert result["user_consultation_required"] is True
    assert result["automatic_execution_authorized"] is False


def test_profile_round_trip() -> None:
    profile = LinearCredalSet([0.2, 0.1], [0.9, 0.8]).conditioned().update([0.3, 0.7])
    restored = ConditionedCredalSet.from_dict(profile.to_dict())
    assert restored.lower_expectation([1, 0]) == pytest.approx(
        profile.lower_expectation([1, 0])
    )
