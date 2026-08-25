from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from .credal import ConditionedCredalSet, CredalInfeasibleError, StateSpace


@dataclass(frozen=True, slots=True)
class ClarificationQuestion:
    question_id: str
    prompt: str
    cost: float
    outcome_likelihoods: dict[str, tuple[float, ...]]
    calibration_receipt_sha256: str | None

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ClarificationQuestion:
        return cls(
            question_id=str(value["question_id"]),
            prompt=str(value["prompt"]),
            cost=float(value["cost"]),
            outcome_likelihoods={
                str(key): tuple(float(item) for item in items)
                for key, items in dict(value["outcome_likelihoods"]).items()
            },
            calibration_receipt_sha256=value.get("calibration_receipt_sha256"),
        )

    def validate(self, size: int) -> None:
        if not self.question_id.strip() or not self.prompt.strip() or self.cost <= 0:
            raise ValueError("question id, prompt and positive cost are required")
        if len(self.outcome_likelihoods) < 2:
            raise ValueError("a clarification question requires at least two outcomes")
        likelihood_rows = []
        for likelihood in self.outcome_likelihoods.values():
            values = np.asarray(likelihood)
            if values.shape != (size,) or np.any(values < 0) or np.any(values > 1):
                raise ValueError("outcome likelihoods must match the state space and lie in [0,1]")
            likelihood_rows.append(values)
        if not np.allclose(np.sum(likelihood_rows, axis=0), np.ones(size), atol=1e-12):
            raise ValueError("outcome likelihoods must define a normalized answer model per state")


def decisional_imprecision(profile: ConditionedCredalSet, state_space: StateSpace) -> float:
    functionals = (state_space.mandate(), state_space.scope(), state_space.high_risk())
    return max(
        profile.upper_expectation(functional) - profile.lower_expectation(functional)
        for functional in functionals
    )


def score_question(
    profile: ConditionedCredalSet,
    question: ClarificationQuestion,
    *,
    state_space: StateSpace | None = None,
) -> dict[str, Any]:
    space = state_space or StateSpace()
    if profile.size != space.size:
        raise ValueError("profile and state space are incompatible")
    question.validate(profile.size)
    receipt = question.calibration_receipt_sha256 or ""
    if len(receipt) != 64 or any(char not in "0123456789abcdef" for char in receipt):
        return {
            "question_id": question.question_id,
            "state": "NOT_ESTIMABLE_UNCALIBRATED_LIKELIHOODS",
            "score": None,
            "expected_information_gain_claimed": False,
            "invented_answer_fidelity_used": False,
        }

    current = decisional_imprecision(profile, space)
    residuals: dict[str, float | None] = {}
    for outcome, likelihood in question.outcome_likelihoods.items():
        try:
            posterior = profile.update(likelihood)
        except CredalInfeasibleError:
            residuals[outcome] = None
            continue
        residuals[outcome] = decisional_imprecision(posterior, space)
    feasible = [float(value) for value in residuals.values() if value is not None]
    if not feasible:
        return {
            "question_id": question.question_id,
            "state": "NOT_ESTIMABLE_NO_CREDALLY_POSSIBLE_OUTCOME",
            "score": None,
            "residual_imprecision": residuals,
            "expected_information_gain_claimed": False,
            "invented_answer_fidelity_used": False,
        }
    worst_residual = max(feasible)
    contraction = current - worst_residual
    return {
        "question_id": question.question_id,
        "state": "ESTIMATED_ROBUST_MINIMAX_CONTRACTION",
        "score": contraction / question.cost,
        "current_imprecision": current,
        "worst_case_residual_imprecision": worst_residual,
        "residual_imprecision": residuals,
        "cost": question.cost,
        "calibration_receipt_sha256": receipt,
        "expected_information_gain_claimed": False,
        "predictive_midpoint_used": False,
        "invented_answer_fidelity_used": False,
    }


def rank_questions(
    profile: ConditionedCredalSet,
    questions: list[ClarificationQuestion],
    *,
    state_space: StateSpace | None = None,
) -> dict[str, Any]:
    rows = [score_question(profile, question, state_space=state_space) for question in questions]
    estimable = sorted(
        (row for row in rows if row["score"] is not None),
        key=lambda row: (-float(row["score"]), str(row["question_id"])),
    )
    beneficial = [row for row in estimable if float(row["score"]) > 1e-12]
    not_estimable = sorted(
        (row for row in rows if row["score"] is None), key=lambda row: str(row["question_id"])
    )
    if beneficial:
        recommended_action = "ASK_USER"
        stop_reason = None
    elif estimable:
        recommended_action = "STOP_ELICITATION"
        stop_reason = "NO_POSITIVE_ROBUST_CONTRACTION"
    else:
        recommended_action = "STOP_ELICITATION"
        stop_reason = "QUESTION_VALUE_NOT_ESTIMABLE"
    return {
        "schema": "kch.ige.clarification-ranking.v0.3.0",
        "ranking": [*estimable, *not_estimable],
        "best_question_id": beneficial[0]["question_id"] if beneficial else None,
        "state": (
            "RANKED"
            if beneficial
            else "NO_POSITIVE_ROBUST_CONTRACTION"
            if estimable
            else "NOT_ESTIMABLE"
        ),
        "criterion": "ROBUST_WORST_CASE_DECISIONAL_IMPRECISION_CONTRACTION_PER_COST",
        "recommended_action": recommended_action,
        "stop_reason": stop_reason,
        "user_consultation_required": recommended_action == "ASK_USER",
        "automatic_execution_authorized": False,
        "standard_expected_information_gain_claimed": False,
    }
