"""Typed System One observations for RDSS; never execution authority.

Compatible with the real ``system_one(state, questions)`` interfaces used by
the LSD Jev/RDSS branch, Laya and OpenDecider. It imports their receipts without
running an experiment or selecting a production action. TypeSafe clients can
bind their explicit model using ``functools.partial(client.system_one, model=...)``.
No inference provider, endpoint, credential, or threshold is silently selected.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import time
from typing import Any, Callable, Mapping


class SensorContractError(ValueError):
    """Invalid or incompatible typed sensor data."""


def _canonical(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise SensorContractError("non_json_or_nonfinite_data") from exc


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _questions_digest(value: Any) -> str:
    # Criteria order affects some backends and is tested by the existing RDSS gate.
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return sha256(raw.encode("utf-8")).hexdigest()


def _number(value: Any, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SensorContractError(name + ":expected_number")
    value = float(value)
    if not math.isfinite(value) or not low <= value <= high:
        raise SensorContractError(name + ":out_of_range")
    return value


def validate_questions(questions: Mapping[str, Any]) -> dict[str, Any]:
    """Copy questions, preserving their criteria order in the backend request."""
    if not isinstance(questions, Mapping) or not questions:
        raise SensorContractError("questions_must_be_nonempty_mapping")
    # Do not sort the live request: option ordering is an experimental variable.
    q = json.loads(json.dumps(dict(questions), ensure_ascii=False, allow_nan=False))
    for key, question in q.items():
        if not isinstance(key, str) or not key or not isinstance(question, dict):
            raise SensorContractError("invalid_question")
        kind = question.get("type")
        criteria = question.get("criteria")
        if kind == "choice":
            if not isinstance(criteria, dict) or len(criteria) < 2:
                raise SensorContractError(key + ":choice_requires_options")
        elif kind == "score":
            if not isinstance(criteria, list) or len(criteria) < 2:
                raise SensorContractError(key + ":score_requires_ordered_levels")
        elif kind != "noul":
            raise SensorContractError(key + ":unsupported_primitive")
    return q


@dataclass(frozen=True)
class TypedSignal:
    question_id: str
    primitive: str
    value: str | float
    probabilities: tuple[tuple[str, float], ...] = ()
    confidence: float | None = None
    abstained: bool = False
    reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"question_id": self.question_id, "primitive": self.primitive,
                "value": self.value, "probabilities": dict(self.probabilities),
                "confidence": self.confidence, "abstained": self.abstained,
                "reason": self.reason}


@dataclass(frozen=True)
class SensorObservation:
    provider: str
    model_revision: str
    source_ref: str
    status: str
    signals: tuple[TypedSignal, ...]
    raw_json: str
    questions_sha256: str
    state_sha256: str | None
    response_sha256: str
    reasons: tuple[str, ...] = ()
    historical: bool = False
    development_only: bool = True
    state_truncated: bool = False
    wall_seconds: float | None = None

    @property
    def mode(self) -> str:
        return "SENSOR_ONLY"

    @property
    def authority(self) -> str:
        return "NONE"

    @property
    def promotion_allowed(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "KCH_TYPED_SENSOR_OBSERVATION_0.1", "provider": self.provider,
                "model_revision": self.model_revision, "source_ref": self.source_ref,
                "revision_basis": "caller_supplied_not_runtime_attested",
                "status": self.status, "signals": [s.to_dict() for s in self.signals],
                "raw": json.loads(self.raw_json), "questions_sha256": self.questions_sha256,
                "state_sha256": self.state_sha256, "response_sha256": self.response_sha256,
                "reasons": list(self.reasons), "historical": self.historical,
                "development_only": self.development_only, "state_truncated": self.state_truncated,
                "wall_seconds": self.wall_seconds, "mode": self.mode,
                "authority": self.authority, "promotion_allowed": self.promotion_allowed}


def _distribution(answer: dict[str, Any], key: str) -> dict[str, float]:
    values = answer.get("probabilities")
    if not isinstance(values, dict) or not values:
        raise SensorContractError(key + ":missing_distribution")
    dist = {str(k): _number(v, key + ":probability", 0, 1) for k, v in values.items()}
    if len(dist) != len(values):
        raise SensorContractError(key + ":duplicate_probability_keys")
    # Accept rounding in native receipts; never renormalize the observation.
    if abs(sum(dist.values()) - 1.0) > 0.001:
        raise SensorContractError(key + ":distribution_not_normalized")
    return dist


def _signal(key: str, question: dict[str, Any], answer: Any) -> TypedSignal:
    if isinstance(answer, dict) and isinstance(answer.get("root"), dict):
        answer = answer["root"]
    if not isinstance(answer, dict):
        raise SensorContractError(key + ":missing_answer")
    kind = question["type"]
    if answer.get("type", kind) != kind:
        raise SensorContractError(key + ":primitive_mismatch")
    confidence = answer.get("confidence")
    if confidence is not None:
        confidence = _number(confidence, key + ":confidence", 0, 1)
    if kind == "noul":
        # Do not invent a confidence value: Jev's Noul has none.
        return TypedSignal(key, kind, _number(answer.get("noul"), key + ":noul", 0, 1),
                           confidence=confidence)
    dist = _distribution(answer, key)
    if kind == "choice":
        choice = answer.get("choice")
        if set(dist) != set(question["criteria"]) or choice not in dist:
            raise SensorContractError(key + ":choice_catalogue_mismatch")
        if dist[choice] < max(dist.values()):
            raise SensorContractError(key + ":choice_not_distribution_maximum")
        abstain = choice in {"ABSTAIN", "OTHER"}
        return TypedSignal(key, kind, choice, tuple(dist.items()), confidence, abstain,
                           "model_abstained" if choice == "ABSTAIN" else
                           "outside_catalogue" if choice == "OTHER" else None)
    n = len(question["criteria"])
    numeric_keys = {str(i) for i in range(n)}
    mini_keys = {"L" + str(i) for i in range(n)}
    if set(dist) not in (numeric_keys, mini_keys):
        raise SensorContractError(key + ":score_levels_mismatch")
    score = _number(answer.get("score"), key + ":score", 0, n - 1)
    return TypedSignal(key, kind, score, tuple(dist.items()), confidence)


def observe_response(response: Any, questions: Mapping[str, Any], *, provider: str,
                     model_revision: str, source_ref: str, state: Any = None,
                     historical: bool = False, development_only: bool = True,
                     wall_seconds: float | None = None) -> SensorObservation:
    """Validate an actual response without deriving permissions or model scores."""
    if not provider or not model_revision or not source_ref:
        raise SensorContractError("provider_revision_and_source_required")
    q = validate_questions(questions)
    if hasattr(response, "model_dump"):
        response = response.model_dump(mode="json")
    if not isinstance(response, dict):
        raise SensorContractError("response_must_be_mapping")
    raw = _canonical(response)
    reasons: list[str] = []
    signals: list[TypedSignal] = []
    if response.get("error") is not None or response.get("http_status", 200) != 200:
        reasons.append("provider_error")
    answers = response.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(q):
        reasons.append("answer_set_mismatch")
    if not reasons:
        try:
            signals = [_signal(key, question, answers[key]) for key, question in q.items()]
        except SensorContractError as exc:
            reasons.append(str(exc))
    truncated = response.get("state_truncated", False)
    if not isinstance(truncated, bool):
        raise SensorContractError("state_truncated_must_be_boolean")
    if truncated:
        reasons.append("state_truncated")
    if response.get("control") == "closed_set_stress":
        reasons.append("closed_set_stress_not_deployment_candidate")
    if reasons:
        # Do not emit a partial decision when any required signal is invalid.
        signals = []
    return SensorObservation(provider, model_revision, source_ref,
                             "ABSTAIN" if reasons else "OBSERVED", tuple(signals), raw,
                             _questions_digest(q), _digest(state) if state is not None else None,
                             sha256(raw.encode("utf-8")).hexdigest(), tuple(reasons), historical,
                             development_only, truncated, wall_seconds)


def import_rdss_receipt(receipt: Mapping[str, Any], questions: Mapping[str, Any], *,
                        provider: str, model_revision: str, source_ref: str) -> SensorObservation:
    """Admit historical Jev/Laya/OpenDecider/MiniSystemOne receipts as observations.

    The original runner's ``authority_choice`` is an ordinary question ID here.
    Its name cannot confer authority, and historical data never replay an action.
    """
    schema = receipt.get("schema", "")
    if not isinstance(schema, str) or not schema.startswith(("JEV_RDSS_RECEIPT_",
            "LAYA_RDSS_RECEIPT_", "OPENDECIDER_RDSS_RECEIPT_", "MINISYSTEMONE_RDSS_RECEIPT_")):
        raise SensorContractError("unrecognized_rdss_receipt_schema")
    declared_revision = receipt.get("resolved_revision") or receipt.get("resolved_model")
    if declared_revision and declared_revision != model_revision:
        raise SensorContractError("receipt_revision_mismatch")
    return observe_response(dict(receipt), questions, provider=provider,
                            model_revision=model_revision, source_ref=source_ref,
                            historical=True, development_only=True,
                            wall_seconds=receipt.get("wall_seconds"))


class SystemOneSensor:
    """Calls a user-selected compatible model and returns only typed evidence.

    The caller owns network authorization and backend timeouts. Nothing in this
    adapter can invoke a tool, grant a lease, or promote a model to production.
    """
    def __init__(self, system_one: Callable[..., Any], *, provider: str,
                 model_revision: str, source_ref: str):
        if not callable(system_one):
            raise SensorContractError("backend_must_be_callable")
        if not provider or not model_revision or not source_ref:
            raise SensorContractError("provider_revision_and_source_required")
        self._call = system_one
        self.provider, self.model_revision, self.source_ref = provider, model_revision, source_ref

    def evaluate(self, state: Any, questions: Mapping[str, Any]) -> SensorObservation:
        q = validate_questions(questions)
        _canonical(state)  # Validate before sending data to an external provider.
        start = time.perf_counter()
        try:
            response = self._call(state=state, questions=q)
        except Exception as exc:
            # Exception messages may contain credentials or submitted private data.
            response = {"error": {"class": type(exc).__name__}, "answers": {}}
        return observe_response(response, q, provider=self.provider,
                                model_revision=self.model_revision, source_ref=self.source_ref,
                                state=state, wall_seconds=time.perf_counter() - start)
