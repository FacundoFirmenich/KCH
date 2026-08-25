from __future__ import annotations

from fractions import Fraction
from typing import Any, Protocol

from .canonical import attach_hash, sha256_json


class MISBridgeProtocol(Protocol):
    def dispatch(self, operation: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]: ...


class MISExactAdapter:
    """Uses MIS exact operations as certificates, never as scientific authority."""

    def __init__(self, bridge: MISBridgeProtocol) -> None:
        self.bridge = bridge

    @classmethod
    def _exact_projection(cls, value: Any) -> Any:
        if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
            return value
        if isinstance(value, float):
            numerator, denominator = value.as_integer_ratio()
            return {"$fraction": str(Fraction(numerator, denominator))}
        if isinstance(value, dict):
            return {str(key): cls._exact_projection(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._exact_projection(item) for item in value]
        raise TypeError(f"MIS exact projection does not support {type(value).__name__}")

    def certify_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        exact_payload = self._exact_projection(payload)
        result = self.bridge.dispatch("mis_canonical_sha256_payload", {"value": exact_payload})
        mis_hash = result["result"]
        local_hash = sha256_json(exact_payload)
        return attach_hash({
            "schema": "kch.mu-transmuter.mis-certificate.v0.1.0",
            "operation": result["operation"],
            "mis_version": result["mis_version"],
            "mis_wheel_sha256": result["wheel_sha256"],
            "mis_sha256": mis_hash,
            "local_sha256": local_hash,
            "exact_hash_agreement": mis_hash == local_hash,
            "float_policy": "IEEE754_VALUES_PROJECTED_TO_EXACT_RATIONALS_BEFORE_MIS",
            "authority_created": False,
            "execution_authorized": False,
            "training_executed": False,
        })
