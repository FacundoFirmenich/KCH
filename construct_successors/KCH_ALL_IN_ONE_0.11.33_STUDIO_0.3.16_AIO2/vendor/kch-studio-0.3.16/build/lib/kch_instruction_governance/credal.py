from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any, Iterable

import numpy as np
from scipy.optimize import linprog


@dataclass(frozen=True, slots=True)
class StateSpace:
    """Finite interpretive state space inherited from IGE, with one correction.

    The first axis is mandate strength *inside an already attested hard authority
    layer*.  It is deliberately not an estimate of platform/user authority.
    """

    mandate_levels: int = 5
    scope_levels: int = 4
    risk_levels: int = 5

    @property
    def cells(self) -> tuple[tuple[int, int, int], ...]:
        return tuple(
            product(
                range(self.mandate_levels),
                range(self.scope_levels),
                range(self.risk_levels),
            )
        )

    @property
    def size(self) -> int:
        return self.mandate_levels * self.scope_levels * self.risk_levels

    def mandate(self) -> np.ndarray:
        return np.asarray([cell[0] for cell in self.cells], dtype=float)

    def scope(self) -> np.ndarray:
        return np.asarray([cell[1] for cell in self.cells], dtype=float)

    def risk(self) -> np.ndarray:
        return np.asarray([cell[2] for cell in self.cells], dtype=float)

    def high_risk(self, threshold: int = 3) -> np.ndarray:
        if threshold < 0 or threshold >= self.risk_levels:
            raise ValueError("risk threshold is outside the state space")
        return np.asarray([cell[2] >= threshold for cell in self.cells], dtype=float)


class CredalInfeasibleError(ValueError):
    pass


class LinearCredalSet:
    """Closed convex credal set over a finite state space.

    Bounds and any additional linear constraints are retained as one polytope.
    Posterior updates never collapse that polytope to independent cell bounds.
    """

    SCHEMA = "kch.ige.linear-credal-set.v0.3.0"

    def __init__(
        self,
        lower: Iterable[float],
        upper: Iterable[float],
        *,
        extra_a_ub: Iterable[Iterable[float]] = (),
        extra_b_ub: Iterable[float] = (),
        extra_a_eq: Iterable[Iterable[float]] = (),
        extra_b_eq: Iterable[float] = (),
    ):
        self.lower = np.asarray(tuple(lower), dtype=float)
        self.upper = np.asarray(tuple(upper), dtype=float)
        if self.lower.ndim != 1 or self.lower.size == 0 or self.upper.shape != self.lower.shape:
            raise ValueError("lower and upper must be non-empty vectors of equal length")
        if not np.all(np.isfinite(self.lower)) or not np.all(np.isfinite(self.upper)):
            raise ValueError("credal bounds must be finite")
        if np.any(self.lower < 0) or np.any(self.upper > 1) or np.any(self.lower > self.upper):
            raise ValueError("credal bounds must satisfy 0 <= lower <= upper <= 1")
        if float(self.lower.sum()) > 1 + 1e-12 or float(self.upper.sum()) < 1 - 1e-12:
            raise CredalInfeasibleError("probability normalization is incompatible with bounds")

        self.extra_a_ub = self._matrix(extra_a_ub, self.lower.size)
        self.extra_b_ub = self._vector(extra_b_ub, self.extra_a_ub.shape[0])
        self.extra_a_eq = self._matrix(extra_a_eq, self.lower.size)
        self.extra_b_eq = self._vector(extra_b_eq, self.extra_a_eq.shape[0])

        identity = np.eye(self.lower.size)
        self.a_ub = np.vstack((identity, -identity, self.extra_a_ub))
        self.b_ub = np.concatenate((self.upper, -self.lower, self.extra_b_ub))
        self.a_eq = np.vstack((np.ones((1, self.lower.size)), self.extra_a_eq))
        self.b_eq = np.concatenate((np.ones(1), self.extra_b_eq))
        self._assert_feasible()

    @staticmethod
    def _matrix(values: Iterable[Iterable[float]], width: int) -> np.ndarray:
        rows = tuple(tuple(row) for row in values)
        if not rows:
            return np.empty((0, width), dtype=float)
        matrix = np.asarray(rows, dtype=float)
        if matrix.ndim != 2 or matrix.shape[1] != width or not np.all(np.isfinite(matrix)):
            raise ValueError("linear-constraint matrix has an invalid shape or value")
        return matrix

    @staticmethod
    def _vector(values: Iterable[float], size: int) -> np.ndarray:
        vector = np.asarray(tuple(values), dtype=float)
        if vector.shape != (size,) or not np.all(np.isfinite(vector)):
            raise ValueError("linear-constraint vector has an invalid shape or value")
        return vector

    @classmethod
    def vacuous(cls, size: int) -> LinearCredalSet:
        if size < 1:
            raise ValueError("size must be positive")
        return cls(np.zeros(size), np.ones(size))

    @property
    def size(self) -> int:
        return int(self.lower.size)

    def _assert_feasible(self) -> None:
        result = linprog(
            np.zeros(self.size),
            A_ub=self.a_ub,
            b_ub=self.b_ub,
            A_eq=self.a_eq,
            b_eq=self.b_eq,
            bounds=[(0.0, 1.0)] * self.size,
            method="highs",
        )
        if not result.success:
            raise CredalInfeasibleError(f"credal polytope is infeasible: {result.message}")

    def expectation(self, functional: Iterable[float], *, maximize: bool = False) -> float:
        values = np.asarray(tuple(functional), dtype=float)
        if values.shape != (self.size,) or not np.all(np.isfinite(values)):
            raise ValueError("functional must be a finite vector matching the state space")
        result = linprog(
            -values if maximize else values,
            A_ub=self.a_ub,
            b_ub=self.b_ub,
            A_eq=self.a_eq,
            b_eq=self.b_eq,
            bounds=[(0.0, 1.0)] * self.size,
            method="highs",
        )
        if not result.success:
            raise CredalInfeasibleError(result.message)
        optimum = float(result.fun)
        return -optimum if maximize else optimum

    def lower_expectation(self, functional: Iterable[float]) -> float:
        return self.expectation(functional)

    def upper_expectation(self, functional: Iterable[float]) -> float:
        return self.expectation(functional, maximize=True)

    def conditioned(self) -> ConditionedCredalSet:
        return ConditionedCredalSet(self, np.ones(self.size))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "lower": self.lower.tolist(),
            "upper": self.upper.tolist(),
            "extra_a_ub": self.extra_a_ub.tolist(),
            "extra_b_ub": self.extra_b_ub.tolist(),
            "extra_a_eq": self.extra_a_eq.tolist(),
            "extra_b_eq": self.extra_b_eq.tolist(),
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> LinearCredalSet:
        if value.get("schema") != cls.SCHEMA:
            raise ValueError("unsupported credal-set schema")
        return cls(
            value["lower"],
            value["upper"],
            extra_a_ub=value.get("extra_a_ub", ()),
            extra_b_ub=value.get("extra_b_ub", ()),
            extra_a_eq=value.get("extra_a_eq", ()),
            extra_b_eq=value.get("extra_b_eq", ()),
        )


class ConditionedCredalSet:
    """Exact generalized-Bayes view of a base polytope after evidence.

    Sequential likelihoods are multiplied and optimized against the original
    polytope via Charnes-Cooper.  Marginal posterior bounds are projections for
    reporting only; they never replace the posterior set.
    """

    SCHEMA = "kch.ige.conditioned-credal-set.v0.3.0"

    def __init__(self, base: LinearCredalSet, evidence_weights: Iterable[float]):
        self.base = base
        weights = np.asarray(tuple(evidence_weights), dtype=float)
        if weights.shape != (base.size,) or not np.all(np.isfinite(weights)):
            raise ValueError("evidence weights must match the base state space")
        if np.any(weights < 0) or not np.any(weights > 0):
            raise ValueError("evidence weights must be non-negative and not identically zero")
        scale = float(weights.max())
        self.evidence_weights = weights / scale
        if self.base.upper_expectation(self.evidence_weights) <= 1e-15:
            raise CredalInfeasibleError("evidence has zero upper probability in the credal set")

    @property
    def size(self) -> int:
        return self.base.size

    def update(self, likelihood: Iterable[float]) -> ConditionedCredalSet:
        values = np.asarray(tuple(likelihood), dtype=float)
        if values.shape != (self.size,) or not np.all(np.isfinite(values)):
            raise ValueError("likelihood must be a finite vector matching the state space")
        if np.any(values < 0) or np.any(values > 1):
            raise ValueError("likelihood values must lie in [0,1]")
        return ConditionedCredalSet(self.base, self.evidence_weights * values)

    def expectation(self, functional: Iterable[float], *, maximize: bool = False) -> float:
        values = np.asarray(tuple(functional), dtype=float)
        if values.shape != (self.size,) or not np.all(np.isfinite(values)):
            raise ValueError("functional must be a finite vector matching the state space")

        # Charnes-Cooper: y = p/(p.w), t = 1/(p.w).
        a_ub = np.hstack((self.base.a_ub, -self.base.b_ub[:, None]))
        a_eq = np.hstack((self.base.a_eq, -self.base.b_eq[:, None]))
        evidence_eq = np.concatenate((self.evidence_weights, np.zeros(1)))[None, :]
        a_eq = np.vstack((a_eq, evidence_eq))
        b_eq = np.concatenate((np.zeros(self.base.b_eq.size), np.ones(1)))
        objective = np.concatenate((self.evidence_weights * values, np.zeros(1)))
        result = linprog(
            -objective if maximize else objective,
            A_ub=a_ub,
            b_ub=np.zeros(self.base.b_ub.size),
            A_eq=a_eq,
            b_eq=b_eq,
            bounds=[(0.0, None)] * (self.size + 1),
            method="highs",
        )
        if not result.success:
            raise CredalInfeasibleError(f"posterior optimization failed: {result.message}")
        optimum = float(result.fun)
        return -optimum if maximize else optimum

    def lower_expectation(self, functional: Iterable[float]) -> float:
        return self.expectation(functional)

    def upper_expectation(self, functional: Iterable[float]) -> float:
        return self.expectation(functional, maximize=True)

    def probability_bounds(self, event: Iterable[float]) -> tuple[float, float]:
        values = np.asarray(tuple(event), dtype=float)
        if np.any(values < 0) or np.any(values > 1):
            raise ValueError("event indicators/weights must lie in [0,1]")
        return self.lower_expectation(values), self.upper_expectation(values)

    def cell_probability_bounds(self) -> list[dict[str, float | int]]:
        rows: list[dict[str, float | int]] = []
        for index in range(self.size):
            indicator = np.zeros(self.size)
            indicator[index] = 1.0
            lower, upper = self.probability_bounds(indicator)
            rows.append({"index": index, "lower": lower, "upper": upper})
        return rows

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "base": self.base.to_dict(),
            "evidence_weights": self.evidence_weights.tolist(),
            "posterior_representation": "EXACT_LINEAR_FRACTIONAL_VIEW_NOT_INTERVAL_HULL",
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ConditionedCredalSet:
        if value.get("schema") != cls.SCHEMA:
            raise ValueError("unsupported conditioned credal-set schema")
        return cls(LinearCredalSet.from_dict(value["base"]), value["evidence_weights"])
