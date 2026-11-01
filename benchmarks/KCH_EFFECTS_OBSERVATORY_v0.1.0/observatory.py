#!/usr/bin/env python3
"""KCH Contrastive Effects Observatory.

Compiles the historical KCH prepilots without rewriting adverse evidence and
emits fail-closed, user-controlled activation receipts.  Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any, Iterable


SCHEMA = "kch.effects-observatory.v0.1.0"
ACTIVATION_SCHEMA = "kch.effects-observatory.activation-receipt.v0.1.0"


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """Numerical Recipes continued fraction used by UnlikelyLOOP paired Bayes."""
    maximum_iterations, epsilon, fp_minimum = 300, 3.0e-14, 1.0e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = 1.0 / (fp_minimum if abs(d) < fp_minimum else d)
    result = d
    for iteration in range(1, maximum_iterations + 1):
        even = 2 * iteration
        coefficient = iteration * (b - iteration) * x / ((qam + even) * (a + even))
        d = 1.0 + coefficient * d
        d = fp_minimum if abs(d) < fp_minimum else d
        c = 1.0 + coefficient / c
        c = fp_minimum if abs(c) < fp_minimum else c
        d = 1.0 / d
        result *= d * c
        coefficient = -(a + iteration) * (qab + iteration) * x / ((a + even) * (qap + even))
        d = 1.0 + coefficient * d
        d = fp_minimum if abs(d) < fp_minimum else d
        c = 1.0 + coefficient / c
        c = fp_minimum if abs(c) < fp_minimum else c
        d = 1.0 / d
        delta = d * c
        result *= delta
        if abs(delta - 1.0) < epsilon:
            return result
    raise ArithmeticError("beta continued fraction did not converge")


def regularized_beta(x: float, a: float, b: float) -> float:
    if not 0.0 <= x <= 1.0 or a <= 0.0 or b <= 0.0:
        raise ValueError("invalid regularized-beta parameters")
    if x in (0.0, 1.0):
        return x
    logarithm = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    front = math.exp(logarithm)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_continued_fraction(a, b, x) / a
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x) / b


def beta_quantile(probability: float, a: float, b: float) -> float:
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability out of range")
    if probability in (0.0, 1.0):
        return probability
    lower, upper = 0.0, 1.0
    for _ in range(100):
        middle = (lower + upper) / 2.0
        if regularized_beta(middle, a, b) < probability:
            lower = middle
        else:
            upper = middle
    return (lower + upper) / 2.0


@dataclass(frozen=True)
class PairEvidence:
    case_id: str
    baseline_arm: str
    candidate_arm: str
    baseline_score: float | None
    candidate_score: float | None
    maximum: float | None
    normalized_delta_points: float | None
    baseline_receipt_bytes: int | None
    candidate_receipt_bytes: int | None
    receipt_size_ratio: float | None
    condition_gate: str
    admissible: bool
    descriptive_outcome: str
    causal_effect: str
    invalid_reason: str | None
    source_sha256: str


def _quality(result: dict[str, Any]) -> dict[str, Any]:
    return result.get("quality") or result.get("evaluation") or {}


def _condition_gate(document: dict[str, Any]) -> str:
    gate = document.get("comparative_condition_gate") or document.get("comparative_efficacy_gate")
    if gate:
        return str(gate)
    integrity = document.get("condition_integrity") or {}
    return str(integrity.get("comparative_efficacy_gate", "NOT_RECORDED"))


def parse_pair(document: dict[str, Any]) -> PairEvidence:
    results = document.get("results") or {}
    if len(results) != 2:
        raise ValueError(f"{document.get('case_id')}: expected exactly two arms")
    baseline_name = next((name for name in results if "BASELINE" in name.upper()), None)
    if baseline_name is None:
        raise ValueError(f"{document.get('case_id')}: no baseline arm")
    candidate_name = next(name for name in results if name != baseline_name)
    baseline, candidate = results[baseline_name], results[candidate_name]
    bq, cq = _quality(baseline), _quality(candidate)
    bs, cs = bq.get("score"), cq.get("score")
    bm, cm = bq.get("maximum"), cq.get("maximum")
    maximum = float(bm) if bm is not None and cm == bm else None
    delta = None
    if bs is not None and cs is not None and maximum:
        delta = 100.0 * (float(cs) - float(bs)) / maximum
    gate = _condition_gate(document)
    admissible = gate.startswith("PASS_") or gate == "PASS"
    if delta is None:
        outcome = str(document.get("descriptive_outcome", "NOT_ESTIMABLE"))
    elif abs(delta) < 1e-12:
        outcome = "TIE"
    else:
        outcome = "CANDIDATE_WIN" if delta > 0 else "BASELINE_WIN"
    br, cr = baseline.get("bytes"), candidate.get("bytes")
    ratio = float(cr) / float(br) if isinstance(br, int) and isinstance(cr, int) and br > 0 else None
    invalid_reason = None if admissible else gate
    return PairEvidence(
        case_id=str(document.get("case_id", "UNKNOWN")),
        baseline_arm=baseline_name,
        candidate_arm=candidate_name,
        baseline_score=float(bs) if bs is not None else None,
        candidate_score=float(cs) if cs is not None else None,
        maximum=maximum,
        normalized_delta_points=delta,
        baseline_receipt_bytes=br if isinstance(br, int) else None,
        candidate_receipt_bytes=cr if isinstance(cr, int) else None,
        receipt_size_ratio=ratio,
        condition_gate=gate,
        admissible=admissible,
        descriptive_outcome=outcome,
        causal_effect=str(document.get("causal_effect", "NOT_ESTIMABLE")),
        invalid_reason=invalid_reason,
        source_sha256=hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest(),
    )


def compile_effects(documents: Iterable[dict[str, Any]]) -> dict[str, Any]:
    pairs = [parse_pair(document) for document in documents]
    valid = [pair for pair in pairs if pair.admissible]
    deltas = [pair.normalized_delta_points for pair in valid if pair.normalized_delta_points is not None]
    wins = sum(pair.descriptive_outcome == "CANDIDATE_WIN" for pair in valid)
    losses = sum(pair.descriptive_outcome == "BASELINE_WIN" for pair in valid)
    ties = sum(pair.descriptive_outcome == "TIE" for pair in valid)
    alpha, beta = 1.0 + wins, 1.0 + losses
    posterior = {
        "model": "BETA_BINOMIAL_DIRECTIONAL_ON_ADMISSIBLE_CASE_WINS_EXCLUDING_TIES",
        "prior": {"alpha": 1.0, "beta": 1.0},
        "posterior_alpha": alpha,
        "posterior_beta": beta,
        "discordant_cases": wins + losses,
        "probability_candidate_better": 1.0 - regularized_beta(0.5, alpha, beta),
        "probability_practical_equivalence_rope_theta_0_45_0_55": regularized_beta(0.55, alpha, beta) - regularized_beta(0.45, alpha, beta),
        "conditional_advantage_mean": 2.0 * alpha / (alpha + beta) - 1.0,
        "conditional_advantage_credible95": [2.0 * beta_quantile(0.025, alpha, beta) - 1.0, 2.0 * beta_quantile(0.975, alpha, beta) - 1.0],
        "interpretation": "No discordant admissible case means the directional posterior is unchanged from the prior." if wins + losses == 0 else "Directional evidence exists but does not establish causal benefit without randomized replicated cases.",
    }
    missing_metrics = ["wall_clock_latency", "provider_input_tokens", "provider_output_tokens", "provider_reasoning_tokens", "provider_cost", "user_corrections", "task_resolution", "human_utility", "errors_avoided"]
    automatic_gate = {
        "minimum_admissible_pairs": 20,
        "minimum_discordant_pairs": 5,
        "minimum_probability_candidate_better": 0.95,
        "credible_interval_lower_must_exceed": 0.0,
        "requires_complete_cost_and_latency": True,
    }
    eligible = (
        len(valid) >= automatic_gate["minimum_admissible_pairs"]
        and wins + losses >= automatic_gate["minimum_discordant_pairs"]
        and posterior["probability_candidate_better"] >= automatic_gate["minimum_probability_candidate_better"]
        and posterior["conditional_advantage_credible95"][0] > 0.0
        and not missing_metrics
    )
    core = {
        "schema": SCHEMA,
        "source": "FacundoFirmenich/KCH@main/benchmarks/KCH_PREPILOT_001..003/evaluation.json",
        "pairs": [asdict(pair) for pair in pairs],
        "aggregate": {
            "total_pairs": len(pairs),
            "admissible_pairs": len(valid),
            "invalid_pairs": len(pairs) - len(valid),
            "candidate_wins": wins,
            "baseline_wins": losses,
            "ties": ties,
            "median_normalized_delta_points": median(deltas) if deltas else None,
            "pooled_causal_effect": "NOT_ESTIMABLE",
            "industrial_validation": False,
            "heterogeneous_case_pooling_performed": False,
        },
        "paired_bayes": posterior,
        "measurement_completeness": {"missing_metrics": missing_metrics, "complete_for_quality_superiority": False, "complete_for_cost_optimization": False},
        "automatic_activation_gate": {**automatic_gate, "eligible": eligible, "current_state": "BLOCKED_INSUFFICIENT_EVIDENCE" if not eligible else "ELIGIBLE_UNDER_EXPLICIT_POLICY"},
        "claim_ceiling": "Dos empates descriptivos válidos y un par inválido. No hay mejora de calidad medida, efecto causal, ventaja de coste o tiempo, utilidad humana ni validación industrial.",
    }
    return {**core, "evidence_sha256": sha256_json(core)}


def activation_receipt(evidence: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    required = ("risk", "coupling", "provenance_need", "authority_sensitivity", "recovery_need", "budget_remaining_ratio")
    for field in required:
        value = profile.get(field)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"{field} must lie in [0,1]")
    policy = str(profile.get("policy", "ASK")).upper()
    if policy not in {"NEVER", "ASK", "AUTO_BOUNDED"}:
        raise ValueError("policy must be NEVER, ASK or AUTO_BOUNDED")
    explicit = bool(profile.get("explicit_user_request", False))
    reserve = float(profile.get("reserve_ratio", 0.15))
    score = round(0.24 * profile["risk"] + 0.20 * profile["coupling"] + 0.20 * profile["provenance_need"] + 0.20 * profile["authority_sensitivity"] + 0.16 * profile["recovery_need"], 6)
    evidence_eligible = bool(evidence.get("automatic_activation_gate", {}).get("eligible", False))
    reasons: list[str] = []
    if policy == "NEVER":
        decision, authorized = "OFF_USER_POLICY", False
        reasons.append("policy_never")
    elif explicit:
        decision, authorized = "ACTIVE_EXPLICIT_ONE_RUN", True
        reasons.append("explicit_user_request")
    elif profile["budget_remaining_ratio"] <= reserve:
        decision, authorized = "OFF_BUDGET_RESERVE", False
        reasons.append("budget_at_or_below_reserve")
    elif policy == "AUTO_BOUNDED" and evidence_eligible and score >= 0.65:
        decision, authorized = "ACTIVE_AUTO_BOUNDED", True
        reasons.extend(["explicit_auto_bounded_policy", "evidence_gate_pass", "need_score_threshold"])
    elif score >= 0.65:
        decision, authorized = "ASK_USER_BEFORE_USE", False
        reasons.extend(["need_score_threshold", "automatic_evidence_gate_blocked" if not evidence_eligible else "policy_requires_confirmation"])
    else:
        decision, authorized = "OFF_NO_MATERIAL_NEED", False
        reasons.append("need_score_below_threshold")
    core = {
        "schema": ACTIVATION_SCHEMA,
        "decision": decision,
        "execution_authorized": authorized,
        "authority_source": "explicit_user_request" if explicit and policy != "NEVER" else ("explicit_auto_bounded_policy" if authorized else "none"),
        "need_score": score,
        "trigger_reasons": reasons,
        "profile": profile,
        "evidence_sha256": evidence.get("evidence_sha256"),
        "automatic_evidence_gate": evidence.get("automatic_activation_gate"),
        "cost_claim": "NOT_ESTIMABLE_WITHOUT_PROVIDER_USAGE_RECEIPTS",
        "traceability": {"pre_execution_receipt_required": True, "post_execution_usage_receipt_required": True, "silent_activation_allowed": False},
        "recommendation_is_authority": False,
    }
    return {**core, "receipt_sha256": sha256_json(core), "created_at": utc_now()}


def render_markdown(report: dict[str, Any]) -> str:
    rows = []
    for pair in report["pairs"]:
        delta = "NA" if pair["normalized_delta_points"] is None else f"{pair['normalized_delta_points']:+.1f}"
        ratio = "NA" if pair["receipt_size_ratio"] is None else f"{pair['receipt_size_ratio']:.3f}×"
        rows.append(f"| {pair['case_id']} | {'sí' if pair['admissible'] else 'no'} | {pair['baseline_score']}/{pair['maximum']} | {pair['candidate_score']}/{pair['maximum']} | {delta} | {ratio} | {pair['condition_gate']} |")
    agg, bayes = report["aggregate"], report["paired_bayes"]
    return "\n".join([
        "# KCH Contrastive Effects Observatory — resultado histórico",
        "",
        "| Caso | Par admisible | Baseline | KCH | Δ puntos normalizados | Ratio bytes recibo | Gate |",
        "|---|---:|---:|---:|---:|---:|---|",
        *rows,
        "",
        f"Pares: {agg['total_pairs']}; admisibles: {agg['admissible_pairs']}; inválidos: {agg['invalid_pairs']}; victorias KCH: {agg['candidate_wins']}; derrotas: {agg['baseline_wins']}; empates: {agg['ties']}.",
        "",
        f"Posterior direccional P(KCH mejor) = {bayes['probability_candidate_better']:.3f}; intervalo creíble 95% de ventaja condicional = [{bayes['conditional_advantage_credible95'][0]:.3f}, {bayes['conditional_advantage_credible95'][1]:.3f}]. Al no haber pares discordantes, este posterior no aprendió nada respecto del prior.",
        "",
        "**Techo de afirmación:** " + report["claim_ceiling"],
        "",
        "**Activación automática:** " + report["automatic_activation_gate"]["current_state"] + ".",
        "",
        "Métricas ausentes: " + ", ".join(report["measurement_completeness"]["missing_metrics"]) + ".",
        "",
        f"SHA-256 lógico de evidencia compilada: `{report['evidence_sha256']}`",
        "",
    ])


def _load(paths: list[Path]) -> list[dict[str, Any]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    analyze = sub.add_parser("analyze")
    analyze.add_argument("inputs", nargs="+", type=Path)
    analyze.add_argument("--json", type=Path, required=True)
    analyze.add_argument("--markdown", type=Path, required=True)
    decide = sub.add_parser("decide")
    decide.add_argument("--evidence", type=Path, required=True)
    decide.add_argument("--profile", type=Path, required=True)
    decide.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "analyze":
        report = compile_effects(_load(args.inputs))
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.markdown.write_text(render_markdown(report), encoding="utf-8")
    else:
        evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
        profile = json.loads(args.profile.read_text(encoding="utf-8"))
        receipt = activation_receipt(evidence, profile)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
