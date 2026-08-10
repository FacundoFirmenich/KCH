from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from .canonical import exact_fraction, fraction_text, parse_fraction, sha256_payload
from .exact import ExactDistribution, dirichlet_predictive


@dataclass(frozen=True, slots=True)
class FrozenRound:
    stream_id: str
    sequence: int
    jurisdiction: str
    available_evidence_through: int
    prior: ExactDistribution
    policy_hash: str
    parent_freeze_hash: str | None
    source_receipt_hashes: tuple[str, ...]
    frozen_at: str
    freeze_hash: str

    @classmethod
    def create(
        cls,
        *,
        stream_id: str,
        sequence: int,
        jurisdiction: str,
        available_evidence_through: int,
        prior: ExactDistribution,
        policy_hash: str,
        parent_freeze_hash: str | None,
        source_receipt_hashes: tuple[str, ...],
        frozen_at: str,
    ) -> "FrozenRound":
        core = {
            "schema": "MIS_FROZEN_ROUND_v0.3",
            "stream_id": stream_id,
            "sequence": sequence,
            "jurisdiction": jurisdiction,
            "available_evidence_through": available_evidence_through,
            "prior": prior.to_payload(),
            "policy_hash": policy_hash,
            "parent_freeze_hash": parent_freeze_hash,
            "source_receipt_hashes": list(source_receipt_hashes),
            "frozen_at": frozen_at,
        }
        return cls(
            stream_id,
            sequence,
            jurisdiction,
            available_evidence_through,
            prior,
            policy_hash,
            parent_freeze_hash,
            source_receipt_hashes,
            frozen_at,
            sha256_payload(core),
        )


    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "FrozenRound":
        expected = {
            "schema", "stream_id", "sequence", "jurisdiction",
            "available_evidence_through", "prior", "policy_hash",
            "parent_freeze_hash", "source_receipt_hashes", "frozen_at", "freeze_hash",
        }
        if set(payload) != expected or payload.get("schema") != "MIS_FROZEN_ROUND_v0.3":
            raise ValueError("invalid frozen-round payload")
        sequence = payload["sequence"]
        available = payload["available_evidence_through"]
        if (
            not isinstance(sequence, int)
            or isinstance(sequence, bool)
            or not isinstance(available, int)
            or isinstance(available, bool)
        ):
            raise ValueError("frozen-round sequence fields must be integers")
        string_fields = ("stream_id", "jurisdiction", "policy_hash", "frozen_at", "freeze_hash")
        if any(not isinstance(payload[field], str) or not payload[field] for field in string_fields):
            raise ValueError("frozen-round string fields must be non-empty strings")
        parent = payload["parent_freeze_hash"]
        if parent is not None and (not isinstance(parent, str) or not parent):
            raise ValueError("invalid parent freeze hash")
        receipt_hashes = payload["source_receipt_hashes"]
        if not isinstance(receipt_hashes, list) or not all(
            isinstance(item, str) and item for item in receipt_hashes
        ):
            raise ValueError("invalid source receipt hashes")
        prior_payload = payload["prior"]
        if not isinstance(prior_payload, dict):
            raise ValueError("invalid frozen prior payload")
        frozen = cls(
            stream_id=payload["stream_id"],
            sequence=sequence,
            jurisdiction=payload["jurisdiction"],
            available_evidence_through=available,
            prior=ExactDistribution.from_payload(prior_payload),
            policy_hash=payload["policy_hash"],
            parent_freeze_hash=parent,
            source_receipt_hashes=tuple(receipt_hashes),
            frozen_at=payload["frozen_at"],
            freeze_hash=payload["freeze_hash"],
        )
        if not frozen.verify():
            raise ValueError("frozen-round payload failed independent verification")
        return frozen

    def core_payload(self) -> dict[str, object]:
        return {
            "schema": "MIS_FROZEN_ROUND_v0.3",
            "stream_id": self.stream_id,
            "sequence": self.sequence,
            "jurisdiction": self.jurisdiction,
            "available_evidence_through": self.available_evidence_through,
            "prior": self.prior.to_payload(),
            "policy_hash": self.policy_hash,
            "parent_freeze_hash": self.parent_freeze_hash,
            "source_receipt_hashes": list(self.source_receipt_hashes),
            "frozen_at": self.frozen_at,
        }

    def to_payload(self) -> dict[str, object]:
        return {**self.core_payload(), "freeze_hash": self.freeze_hash}

    def verify(self) -> bool:
        try:
            if (
                not isinstance(self.sequence, int)
                or isinstance(self.sequence, bool)
                or self.sequence < 1
                or self.available_evidence_through != self.sequence - 1
                or len(self.source_receipt_hashes) != self.sequence - 1
            ):
                return False
            if self.sequence == 1 and self.parent_freeze_hash is not None:
                return False
            if self.sequence > 1 and not self.parent_freeze_hash:
                return False
            return sha256_payload(self.core_payload()) == self.freeze_hash
        except (TypeError, ValueError):
            return False


@dataclass(frozen=True, slots=True)
class OutcomeReceipt:
    stream_id: str
    sequence: int
    freeze_hash: str
    observed_state: str
    source_unit_hash: str
    observed_at: str
    receipt_hash: str

    @classmethod
    def create(
        cls,
        *,
        stream_id: str,
        sequence: int,
        freeze_hash: str,
        observed_state: str,
        source_unit_hash: str,
        observed_at: str,
    ) -> "OutcomeReceipt":
        core = {
            "schema": "MIS_OUTCOME_RECEIPT_v0.3",
            "stream_id": stream_id,
            "sequence": sequence,
            "freeze_hash": freeze_hash,
            "observed_state": observed_state,
            "source_unit_hash": source_unit_hash,
            "observed_at": observed_at,
        }
        return cls(
            stream_id,
            sequence,
            freeze_hash,
            observed_state,
            source_unit_hash,
            observed_at,
            sha256_payload(core),
        )


    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "OutcomeReceipt":
        expected = {
            "schema", "stream_id", "sequence", "freeze_hash", "observed_state",
            "source_unit_hash", "observed_at", "receipt_hash",
        }
        if set(payload) != expected or payload.get("schema") != "MIS_OUTCOME_RECEIPT_v0.3":
            raise ValueError("invalid outcome-receipt payload")
        sequence = payload["sequence"]
        if not isinstance(sequence, int) or isinstance(sequence, bool):
            raise ValueError("outcome sequence must be an integer")
        string_fields = (
            "stream_id", "freeze_hash", "observed_state",
            "source_unit_hash", "observed_at", "receipt_hash",
        )
        if any(not isinstance(payload[field], str) or not payload[field] for field in string_fields):
            raise ValueError("outcome-receipt fields must be non-empty strings")
        receipt = cls(
            stream_id=payload["stream_id"],
            sequence=sequence,
            freeze_hash=payload["freeze_hash"],
            observed_state=payload["observed_state"],
            source_unit_hash=payload["source_unit_hash"],
            observed_at=payload["observed_at"],
            receipt_hash=payload["receipt_hash"],
        )
        if not receipt.verify():
            raise ValueError("outcome-receipt payload failed independent verification")
        return receipt

    def core_payload(self) -> dict[str, object]:
        return {
            "schema": "MIS_OUTCOME_RECEIPT_v0.3",
            "stream_id": self.stream_id,
            "sequence": self.sequence,
            "freeze_hash": self.freeze_hash,
            "observed_state": self.observed_state,
            "source_unit_hash": self.source_unit_hash,
            "observed_at": self.observed_at,
        }

    def to_payload(self) -> dict[str, object]:
        return {**self.core_payload(), "receipt_hash": self.receipt_hash}

    def verify(self) -> bool:
        try:
            return (
                isinstance(self.sequence, int)
                and not isinstance(self.sequence, bool)
                and self.sequence >= 1
                and sha256_payload(self.core_payload()) == self.receipt_hash
            )
        except (TypeError, ValueError):
            return False


class FutureOnlyLedger:
    """Append-only categorical learner: outcome k may affect priors only for k+1 onward."""

    def __init__(
        self,
        *,
        stream_id: str,
        states: tuple[str, ...],
        alpha: Mapping[str, Fraction],
        jurisdiction: str,
        policy_hash: str,
    ) -> None:
        if not stream_id or not jurisdiction or not policy_hash:
            raise ValueError("stream, jurisdiction and policy hash must be non-empty")
        if not states or len(set(states)) != len(states) or not all(
            isinstance(state, str) and state for state in states
        ):
            raise ValueError("states must be unique non-empty strings")
        self.stream_id = stream_id
        self.states = tuple(sorted(states))
        self.alpha = {
            state: exact_fraction(alpha[state], field=f"alpha[{state}]")
            for state in self.states
        }
        if set(alpha) != set(self.states) or any(value <= 0 for value in self.alpha.values()):
            raise ValueError("alpha must be positive and cover the exact state space")
        self.jurisdiction = jurisdiction
        self.policy_hash = policy_hash
        self._freezes: list[FrozenRound] = []
        self._outcomes: list[OutcomeReceipt] = []

    @property
    def freezes(self) -> tuple[FrozenRound, ...]:
        return tuple(self._freezes)

    @property
    def outcomes(self) -> tuple[OutcomeReceipt, ...]:
        return tuple(self._outcomes)

    def counts_before(self, sequence: int) -> dict[str, int]:
        counts = {state: 0 for state in self.states}
        for receipt in self._outcomes:
            if receipt.sequence < sequence:
                counts[receipt.observed_state] += 1
        return counts

    def prior_for(self, sequence: int) -> ExactDistribution:
        return dirichlet_predictive(self.states, self.alpha, self.counts_before(sequence))

    def freeze(self, *, sequence: int, frozen_at: str) -> FrozenRound:
        expected = len(self._freezes) + 1
        if sequence != expected:
            raise ValueError(f"freeze sequence must be contiguous; expected {expected}")
        if len(self._outcomes) != sequence - 1:
            raise ValueError("previous round needs an outcome before the next freeze")
        prior = self.prior_for(sequence)
        parent = self._freezes[-1].freeze_hash if self._freezes else None
        receipt_hashes = tuple(receipt.receipt_hash for receipt in self._outcomes)
        frozen = FrozenRound.create(
            stream_id=self.stream_id,
            sequence=sequence,
            jurisdiction=self.jurisdiction,
            available_evidence_through=sequence - 1,
            prior=prior,
            policy_hash=self.policy_hash,
            parent_freeze_hash=parent,
            source_receipt_hashes=receipt_hashes,
            frozen_at=frozen_at,
        )
        self._freezes.append(frozen)
        return frozen

    def observe(
        self,
        *,
        sequence: int,
        observed_state: str,
        source_unit_hash: str,
        observed_at: str,
    ) -> OutcomeReceipt:
        if observed_state not in self.states:
            raise ValueError("outcome is outside the frozen state space")
        if not self._freezes or self._freezes[-1].sequence != sequence:
            raise ValueError("outcome requires its matching frozen round")
        if len(self._outcomes) != sequence - 1:
            raise ValueError("outcome sequence must be contiguous and unique")
        receipt = OutcomeReceipt.create(
            stream_id=self.stream_id,
            sequence=sequence,
            freeze_hash=self._freezes[-1].freeze_hash,
            observed_state=observed_state,
            source_unit_hash=source_unit_hash,
            observed_at=observed_at,
        )
        self._outcomes.append(receipt)
        return receipt

    def verify(self) -> bool:
        if len(self._outcomes) > len(self._freezes):
            return False
        if len(self._freezes) - len(self._outcomes) not in (0, 1):
            return False
        try:
            for index, receipt in enumerate(self._outcomes, start=1):
                if (
                    not receipt.verify()
                    or receipt.sequence != index
                    or receipt.stream_id != self.stream_id
                    or receipt.observed_state not in self.states
                    or receipt.freeze_hash != self._freezes[index - 1].freeze_hash
                ):
                    return False
            for index, frozen in enumerate(self._freezes, start=1):
                if (
                    not frozen.verify()
                    or frozen.sequence != index
                    or frozen.stream_id != self.stream_id
                    or frozen.jurisdiction != self.jurisdiction
                    or frozen.policy_hash != self.policy_hash
                ):
                    return False
                prior_receipts = self._outcomes[: index - 1]
                counts = {state: 0 for state in self.states}
                for receipt in prior_receipts:
                    counts[receipt.observed_state] += 1
                if frozen.prior != dirichlet_predictive(self.states, self.alpha, counts):
                    return False
                expected_parent = self._freezes[index - 2].freeze_hash if index > 1 else None
                if frozen.parent_freeze_hash != expected_parent:
                    return False
                expected_receipts = tuple(receipt.receipt_hash for receipt in prior_receipts)
                if frozen.source_receipt_hashes != expected_receipts:
                    return False
        except (IndexError, KeyError, TypeError, ValueError):
            return False
        return True

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "MIS_FUTURE_ONLY_LEDGER_v0.3",
            "stream_id": self.stream_id,
            "states": list(self.states),
            "alpha": {state: fraction_text(self.alpha[state]) for state in self.states},
            "jurisdiction": self.jurisdiction,
            "policy_hash": self.policy_hash,
            "freezes": [item.to_payload() for item in self._freezes],
            "outcomes": [item.to_payload() for item in self._outcomes],
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "FutureOnlyLedger":
        expected = {
            "schema", "stream_id", "states", "alpha", "jurisdiction",
            "policy_hash", "freezes", "outcomes",
        }
        if set(payload) != expected or payload.get("schema") != "MIS_FUTURE_ONLY_LEDGER_v0.3":
            raise ValueError("invalid future-only ledger payload")
        states = payload["states"]
        if (
            not isinstance(states, list)
            or not states
            or not all(isinstance(state, str) and state for state in states)
            or states != sorted(set(states))
        ):
            raise ValueError("ledger states must be sorted unique strings")
        alpha_payload = payload["alpha"]
        if not isinstance(alpha_payload, dict) or set(alpha_payload) != set(states) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in alpha_payload.items()
        ):
            raise ValueError("invalid ledger alpha mapping")
        freezes_payload = payload["freezes"]
        outcomes_payload = payload["outcomes"]
        if not isinstance(freezes_payload, list) or not all(
            isinstance(item, dict) for item in freezes_payload
        ):
            raise ValueError("invalid ledger freezes")
        if not isinstance(outcomes_payload, list) or not all(
            isinstance(item, dict) for item in outcomes_payload
        ):
            raise ValueError("invalid ledger outcomes")
        string_fields = ("stream_id", "jurisdiction", "policy_hash")
        if any(not isinstance(payload[field], str) or not payload[field] for field in string_fields):
            raise ValueError("ledger identity fields must be non-empty strings")
        ledger = cls(
            stream_id=payload["stream_id"],
            states=tuple(states),
            alpha={state: parse_fraction(alpha_payload[state]) for state in states},
            jurisdiction=payload["jurisdiction"],
            policy_hash=payload["policy_hash"],
        )
        ledger._freezes = [FrozenRound.from_payload(item) for item in freezes_payload]
        ledger._outcomes = [OutcomeReceipt.from_payload(item) for item in outcomes_payload]
        if not ledger.verify():
            raise ValueError("future-only ledger payload failed independent chain verification")
        if ledger.to_payload() != payload:
            raise ValueError("future-only ledger payload is not canonical")
        return ledger
