from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping

from .canonical import exact_fraction, fraction_text, parse_fraction, validate_identifier_tuple


class ZeroEvidenceError(ValueError):
    """Raised when the supplied observation has zero prior-predictive mass."""


@dataclass(frozen=True, slots=True)
class ExactDistribution:
    states: tuple[str, ...]
    masses: tuple[Fraction, ...]

    def __post_init__(self) -> None:
        validate_identifier_tuple(self.states, field="states", require_sorted=True)
        if not isinstance(self.masses, tuple):
            raise TypeError("masses must be a tuple")
        if len(self.states) != len(self.masses):
            raise ValueError("states and masses must have the same non-zero length")
        masses = tuple(
            exact_fraction(value, field=f"probability mass[{state}]")
            for state, value in zip(self.states, self.masses, strict=True)
        )
        if any(value < 0 for value in masses):
            raise ValueError("probability masses cannot be negative")
        if sum(masses, Fraction(0)) != 1:
            raise ValueError("probability masses must sum exactly to one")
        object.__setattr__(self, "masses", masses)

    @classmethod
    def from_mapping(cls, masses: Mapping[str, Fraction]) -> "ExactDistribution":
        source_states = validate_identifier_tuple(tuple(masses), field="mass keys")
        states = tuple(sorted(source_states))
        return cls(
            states,
            tuple(exact_fraction(masses[state], field=f"probability mass[{state}]") for state in states),
        )

    @classmethod
    def uniform(cls, states: tuple[str, ...]) -> "ExactDistribution":
        validate_identifier_tuple(states, field="states")
        canonical_states = tuple(sorted(states))
        mass = Fraction(1, len(states))
        return cls(canonical_states, tuple(mass for _ in canonical_states))

    def as_mapping(self) -> dict[str, Fraction]:
        return dict(zip(self.states, self.masses, strict=True))

    def probability(self, state: str) -> Fraction:
        return self.as_mapping()[state]

    def update(self, likelihood: Mapping[str, Fraction]) -> "ExactDistribution":
        if set(likelihood) != set(self.states):
            raise ValueError("likelihood must cover exactly the distribution states")
        weighted: dict[str, Fraction] = {}
        for state, prior in self.as_mapping().items():
            value = exact_fraction(likelihood[state], field=f"likelihood[{state}]")
            if value < 0 or value > 1:
                raise ValueError("likelihood values must lie in [0, 1]")
            weighted[state] = prior * value
        evidence_mass = sum(weighted.values(), Fraction(0))
        if evidence_mass == 0:
            raise ZeroEvidenceError("observation has zero prior-predictive mass")
        return ExactDistribution.from_mapping(
            {state: value / evidence_mass for state, value in weighted.items()}
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": "MIS_EXACT_DISTRIBUTION_v0.3.1",
            "masses": {state: fraction_text(mass) for state, mass in self.as_mapping().items()},
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "ExactDistribution":
        if (
            set(payload) != {"schema", "masses"}
            or payload["schema"] != "MIS_EXACT_DISTRIBUTION_v0.3.1"
        ):
            raise ValueError("invalid exact distribution payload")
        masses = payload["masses"]
        if not isinstance(masses, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in masses.items()):
            raise ValueError("invalid mass mapping")
        return cls.from_mapping({key: parse_fraction(value) for key, value in masses.items()})


def dirichlet_predictive(
    states: tuple[str, ...],
    alpha: Mapping[str, Fraction],
    counts: Mapping[str, int],
) -> ExactDistribution:
    validate_identifier_tuple(states, field="states", require_sorted=True)
    if set(alpha) != set(states) or set(counts) != set(states):
        raise ValueError("alpha and counts must cover exactly the state space")
    weights: dict[str, Fraction] = {}
    for state in states:
        alpha_value = exact_fraction(alpha[state], field=f"alpha[{state}]")
        count = counts[state]
        if isinstance(count, bool) or not isinstance(count, int):
            raise TypeError(f"count[{state}] must be an int, not {type(count).__name__}")
        if alpha_value <= 0 or count < 0:
            raise ValueError("Dirichlet alpha must be positive and counts non-negative")
        weights[state] = alpha_value + count
    total = sum(weights.values(), Fraction(0))
    return ExactDistribution.from_mapping({state: weight / total for state, weight in weights.items()})


def categorical_brier(distribution: ExactDistribution, observed_state: str) -> Fraction:
    if observed_state not in distribution.states:
        raise ValueError("observed state is outside the predictive support")
    return sum(
        (mass - (1 if state == observed_state else 0)) ** 2
        for state, mass in distribution.as_mapping().items()
    )
