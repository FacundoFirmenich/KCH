from __future__ import annotations

import argparse
import itertools
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

from .canonical import fraction_text, sha256_payload
from .decision import LossTable, bayes_decide
from .exact import ExactDistribution, ZeroEvidenceError, categorical_brier
from .freeze import FutureOnlyLedger
from .khc import (
    KHC_SCHEMA,
    constitute_units,
    integration_audit,
    khc_action_registry,
    load_khc_corpus,
    records_by_stream,
)


class ExperimentInvariantError(RuntimeError):
    """Raised when an executed experimental gate contradicts its frozen invariant."""


def exact_structural_exhaustion() -> dict[str, object]:
    states = (
        "mis.state.out_of_scope.v1",
        "mis.state.supported.v1",
        "mis.state.unsupported.v1",
    )
    action_for_state = {
        "mis.state.out_of_scope.v1": "mis.action.withhold.v1",
        "mis.state.supported.v1": "mis.action.apply.v1",
        "mis.state.unsupported.v1": "mis.action.abstain.v1",
    }
    actions = tuple(sorted(action_for_state.values()))
    losses = {
        (action, state): Fraction(0 if action == action_for_state[state] else 1)
        for action in actions
        for state in states
    }
    table = LossTable(actions, states, losses)
    priors: list[ExactDistribution] = []
    for a in range(5):
        for b in range(5 - a):
            c = 4 - a - b
            priors.append(
                ExactDistribution.from_mapping(
                    {states[0]: Fraction(a, 4), states[1]: Fraction(b, 4), states[2]: Fraction(c, 4)}
                )
            )
    likelihood_values = (Fraction(0), Fraction(1, 2), Fraction(1))
    attempted = 0
    admissible = 0
    zero_evidence = 0
    unique_decisions = 0
    ties = 0
    for prior in priors:
        for vector in itertools.product(likelihood_values, repeat=3):
            attempted += 1
            likelihood = dict(zip(states, vector, strict=True))
            try:
                posterior = prior.update(likelihood)
            except ZeroEvidenceError:
                zero_evidence += 1
                continue
            admissible += 1
            if sum(posterior.masses, Fraction(0)) != 1:
                raise ExperimentInvariantError("posterior failed exact normalization")
            decision = bayes_decide(posterior, table)
            expected_states = {
                state
                for state in states
                if posterior.probability(state) == max(posterior.masses)
            }
            expected_actions = tuple(sorted(action_for_state[state] for state in expected_states))
            if decision.minimizers != expected_actions:
                raise ExperimentInvariantError(
                    "Bayes minimizers differ from the exact expected set"
                )
            if decision.minimum_risk != 1 - max(posterior.masses):
                raise ExperimentInvariantError(
                    "minimum risk differs from the exact 0-1-loss result"
                )
            if len(decision.minimizers) == 1:
                unique_decisions += 1
            else:
                ties += 1
    return {
        "schema": "MIS_EXACT_STRUCTURAL_EXHAUSTION_v0.3",
        "prior_lattice": "three-state simplex on denominator 4, including boundary points",
        "likelihood_lattice": "{0, 1/2, 1}^3",
        "priors": len(priors),
        "attempted_updates": attempted,
        "admissible_updates": admissible,
        "zero_evidence_rejections": zero_evidence,
        "unique_bayes_decisions": unique_decisions,
        "tie_preserving_decisions": ties,
        "failures": 0,
        "claim_boundary": (
            "Exhaustive only over the explicitly declared finite rational lattice; it is not an "
            "exhaustion of all Bayesian models or all loss functions."
        ),
    }


def exact_loss_example() -> dict[str, object]:
    safe = "mis.state.safe.v1"
    risk = "mis.state.risk.v1"
    act = "mis.action.apply.v1"
    hold = "mis.action.withhold.v1"
    prior = ExactDistribution.from_mapping({safe: Fraction(1, 2), risk: Fraction(1, 2)})
    posterior = prior.update({safe: Fraction(1, 4), risk: Fraction(3, 4)})
    loss = LossTable(
        (act, hold),
        (safe, risk),
        {
            (act, safe): Fraction(0),
            (act, risk): Fraction(10),
            (hold, safe): Fraction(1),
            (hold, risk): Fraction(0),
        },
    )
    decision = bayes_decide(posterior, loss)
    return {
        "schema": "MIS_EXACT_LOSS_EXAMPLE_v0.3",
        "role": "formal validation example; parameters are not empirical estimates",
        "prior": prior.to_payload(),
        "likelihood": {safe: "1/4", risk: "3/4"},
        "posterior": posterior.to_payload(),
        "loss": loss.to_payload(),
        "decision": decision.to_payload(),
    }


def khc_future_only_replay(khc_path: str | Path, *, include_ledgers: bool = True) -> dict[str, object]:
    corpus = load_khc_corpus(khc_path)
    units = constitute_units(corpus)
    unit_by_coordinate = {unit.coordinate: unit for unit in units}
    registry = khc_action_registry()
    states = registry.atom_ids("bayes_action")
    alpha = {state: Fraction(1) for state in states}
    policy = {
        "schema": "MIS_KHC_PREQUENTIAL_POLICY_v0.3",
        "states": list(states),
        "alpha": {state: "1/1" for state in states},
        "score": "categorical Brier, exact rational",
        "update_rule": "Dirichlet categorical posterior predictive",
        "jurisdiction": "one KHC model/task stream; next observed action only",
        "mode": "historical future-only replay; not prospective causal validation",
    }
    policy_hash = sha256_payload(policy)
    total_brier = Fraction(0)
    round_brier: Counter[int] = Counter()
    round_counts: Counter[int] = Counter()
    freeze_count = 0
    outcome_count = 0
    unchanged_hash_checks = 0
    rehydrated_ledgers_verified = 0
    ledgers: list[dict[str, object]] = []
    for stream_id, records in records_by_stream(corpus.records).items():
        ledger = FutureOnlyLedger(
            stream_id=stream_id,
            states=states,
            alpha=alpha,
            jurisdiction=f"KHC/B/{stream_id}/observed-action-stream",
            policy_hash=policy_hash,
        )
        original_freeze_hashes: list[str] = []
        for record in records:
            frozen = ledger.freeze(
                sequence=record.round_index,
                frozen_at=f"KHC_v2.0.7_REPLAY_PRE_R{record.round_index}",
            )
            freeze_count += 1
            original_freeze_hashes.append(frozen.freeze_hash)
            action_atom = registry.parse(record.action, "khc").atom_id
            score = categorical_brier(frozen.prior, action_atom)
            total_brier += score
            round_brier[record.round_index] += score
            round_counts[record.round_index] += 1
            unit = unit_by_coordinate[record.coordinate()]
            ledger.observe(
                sequence=record.round_index,
                observed_state=action_atom,
                source_unit_hash=unit.unit_hash,
                observed_at=f"KHC_v2.0.7_REPLAY_POST_R{record.round_index}",
            )
            outcome_count += 1
            if frozen.freeze_hash != original_freeze_hashes[-1] or not frozen.verify():
                raise ExperimentInvariantError(
                    f"freeze changed or failed verification for {stream_id} "
                    f"round {record.round_index}"
                )
            unchanged_hash_checks += 1
        if not ledger.verify():
            raise ExperimentInvariantError(
                f"future-only ledger failed verification for {stream_id}"
            )
        if tuple(item.freeze_hash for item in ledger.freezes) != tuple(original_freeze_hashes):
            raise ExperimentInvariantError(
                f"historical freeze hashes changed for {stream_id}"
            )
        rehydrated = FutureOnlyLedger.from_payload(
            json.loads(json.dumps(ledger.to_payload(), ensure_ascii=False))
        )
        if rehydrated.to_payload() != ledger.to_payload() or not rehydrated.verify():
            raise ExperimentInvariantError(
                f"rehydrated ledger differs for {stream_id}"
            )
        rehydrated_ledgers_verified += 1
        if include_ledgers:
            ledgers.append(ledger.to_payload())
    return {
        "schema": "MIS_KHC_FUTURE_ONLY_REPLAY_v0.3",
        "source_schema": KHC_SCHEMA,
        "source_sha256": corpus.source_sha256,
        "policy": policy,
        "policy_hash": policy_hash,
        "streams": 60,
        "freezes": freeze_count,
        "outcomes": outcome_count,
        "freeze_hash_unchanged_checks": unchanged_hash_checks,
        "ledgers_verified": 60,
        "rehydrated_ledgers_verified": rehydrated_ledgers_verified,
        "total_brier": fraction_text(total_brier),
        "mean_brier": fraction_text(total_brier / outcome_count),
        "round_mean_brier": {
            str(index): fraction_text(round_brier[index] / round_counts[index])
            for index in sorted(round_counts)
        },
        "ledgers": ledgers if include_ledgers else None,
        "claim_boundary": (
            "This is a hindsight-limited replay of the already observed KHC action stream. It proves "
            "exact freeze/outcome separation and future-only state transition. It does not prove that "
            "MIS improves KHC decisions, because model actions are observations here, not adjudicated "
            "ground-truth outcomes, and the replay is not a new prospective holdout."
        ),
    }


def run_all(khc_path: str | Path, output_dir: str | Path) -> dict[str, object]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    corpus = load_khc_corpus(khc_path)
    audit = integration_audit(corpus)
    replay = khc_future_only_replay(khc_path, include_ledgers=True)
    report = {
        "schema": "MIS_v0.3.1_EXPERIMENT_REPORT",
        "version": "0.3.1",
        "structural_exhaustion": exact_structural_exhaustion(),
        "loss_decision_example": exact_loss_example(),
        "khc_integration": audit,
        "khc_future_only_replay": {key: value for key, value in replay.items() if key != "ledgers"},
        "global_claim_boundary": (
            "Executable structural validation and historical replay only. Human utility, causal KHC "
            "improvement, open-domain scalability and prospective predictive superiority remain pending."
        ),
    }
    (output / "MIS_v0_3_EXPERIMENT_REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "MIS_v0_3_KHC_FUTURE_ONLY_LEDGERS.json").write_text(
        json.dumps(
            {
                "schema": replay["schema"],
                "source_sha256": replay["source_sha256"],
                "policy_hash": replay["policy_hash"],
                "ledgers": replay["ledgers"],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the reproducible MIS v0.3 validation campaign")
    parser.add_argument("--khc", required=True, help="Path to KHC_TWO_BATTERY_MASTER_RESULTS_v2.0.7.json")
    parser.add_argument("--output", required=True, help="Directory for result artifacts")
    args = parser.parse_args()
    report = run_all(args.khc, args.output)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
