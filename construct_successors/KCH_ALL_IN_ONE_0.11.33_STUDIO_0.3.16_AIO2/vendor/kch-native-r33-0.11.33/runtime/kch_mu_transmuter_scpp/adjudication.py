from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical import attach_hash


@dataclass(frozen=True, slots=True)
class DualAdjudicator:
    post_uncertainty_margin: float

    def __post_init__(self) -> None:
        if self.post_uncertainty_margin < 0:
            raise ValueError("post-uncertainty margin must be non-negative")

    def decide(
        self,
        *,
        jurisdiction_id: str,
        candidate: str,
        competitor: str,
        competitor_advantage: float,
        uncertainty: float,
        transparent_candidate: bool,
    ) -> dict[str, Any]:
        if uncertainty < 0:
            raise ValueError("uncertainty must be non-negative")
        d = float(competitor_advantage)
        u = float(uncertainty)
        k = float(self.post_uncertainty_margin)
        if d < -u:
            quantitative = f"WIN_{candidate}"
        elif d > u:
            quantitative = f"WIN_{competitor}"
        else:
            quantitative = "TIE_OR_UNCERTAIN"
        if d <= u and transparent_candidate:
            architectural = candidate
            rationale = "CANDIDATE_ADVANTAGE_OR_COMPETITOR_NOT_BEYOND_UNCERTAINTY"
        elif u < d <= u + k:
            architectural = "CONTEXTUAL"
            rationale = "POST_UNCERTAINTY_CONTEXTUAL_BAND"
        else:
            architectural = competitor
            rationale = "COMPETITOR_CLEAR_BEYOND_UNCERTAINTY_AND_MARGIN"
        return attach_hash({
            "schema": "kch.dual-local-adjudication.v0.1.0",
            "jurisdiction_id": jurisdiction_id,
            "candidate": candidate,
            "competitor": competitor,
            "competitor_advantage": d,
            "uncertainty": u,
            "post_uncertainty_margin": k,
            "quantitative_verdict": quantitative,
            "architectural_verdict": architectural,
            "architectural_rationale": rationale,
            "global_winner": None,
            "authority_scope": "LOCAL_ONLY",
            "numbers_reinterpreted": False,
        })

