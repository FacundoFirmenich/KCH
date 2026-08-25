from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, is_dataclass
from typing import Any


def canonical_value(value: Any) -> Any:
    if is_dataclass(value):
        return canonical_value(asdict(value))
    if isinstance(value, dict):
        return {str(key): canonical_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [canonical_value(item) for item in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite values are forbidden in canonical receipts")
        return value
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError(f"unsupported canonical value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(canonical_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_json(value).encode("utf-8"))


def attach_hash(payload: dict[str, Any], field: str = "receipt_sha256") -> dict[str, Any]:
    if field in payload:
        raise ValueError(f"hash field already present: {field}")
    core = canonical_value(payload)
    return {**core, field: sha256_json(core)}


def verify_attached_hash(payload: dict[str, Any], field: str = "receipt_sha256") -> bool:
    if field not in payload:
        return False
    core = {key: value for key, value in payload.items() if key != field}
    return payload[field] == sha256_json(core)

