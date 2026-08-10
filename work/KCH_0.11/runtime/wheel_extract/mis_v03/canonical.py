from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any


class CanonicalizationError(ValueError):
    """Raised when a value has no admitted canonical representation."""


def exact_fraction(value: object, *, field: str = "value") -> Fraction:
    """Coerce only integers and Fractions; never hide binary-float or bool inputs."""

    if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
        raise TypeError(f"{field} must be an int or Fraction, not {type(value).__name__}")
    return Fraction(value)


def validate_identifier_tuple(
    values: object,
    *,
    field: str,
    require_sorted: bool = False,
) -> tuple[str, ...]:
    """Validate a finite native qualitative axis without coercing identities."""

    if not isinstance(values, tuple):
        raise TypeError(f"{field} must be a tuple")
    if not values:
        raise ValueError(f"{field} cannot be empty")
    for value in values:
        if not isinstance(value, str):
            raise TypeError(f"{field} identifiers must be strings")
        if not value.strip():
            raise ValueError(f"{field} identifiers cannot be empty or blank")
    if len(set(values)) != len(values):
        raise ValueError(f"{field} identifiers must be unique")
    if require_sorted and values != tuple(sorted(values)):
        raise ValueError(f"{field} identifiers must be in canonical sorted order")
    return values


def fraction_text(value: Fraction | int) -> str:
    value = exact_fraction(value, field="fraction")
    return f"{value.numerator}/{value.denominator}"


def parse_fraction(value: str) -> Fraction:
    if not isinstance(value, str) or "/" not in value:
        raise CanonicalizationError("fractions must be canonical 'numerator/denominator' strings")
    numerator, denominator = value.split("/", 1)
    parsed = Fraction(int(numerator), int(denominator))
    if fraction_text(parsed) != value:
        raise CanonicalizationError(f"non-canonical fraction: {value!r}")
    return parsed


def canonical_value(value: Any) -> Any:
    if isinstance(value, Fraction):
        return {"$fraction": fraction_text(value)}
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return canonical_value(asdict(value))
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise CanonicalizationError("canonical mappings require string keys")
        return {key: canonical_value(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [canonical_value(item) for item in value]
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        raise CanonicalizationError("binary floats are forbidden in the exact MIS core")
    raise CanonicalizationError(f"unsupported canonical value: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        canonical_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_payload(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
