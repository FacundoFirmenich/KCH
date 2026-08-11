from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable

from .permissions import PermissionGovernor

SOURCE_NATIVE_ORDER = "SOURCE_NATIVE_ORDER"
LEXICOGRAPHIC_ORDER = "LEXICOGRAPHIC_ORDER"
DEFAULT_MAX_RETURN_BYTES = 1_048_576
MAX_RETURN_BYTES = 5_242_880


def full_read_contract_status() -> dict[str, Any]:
    return {
        "schema": "kch.full-read-contract.v0.1.0",
        "complete_bytes_required": True,
        "fragment_substitution_forbidden": True,
        "default_inventory_order": SOURCE_NATIVE_ORDER,
        "alternate_order_requires_explicit_user_or_preregistered_contract": True,
        "order_semantics_must_be_declared": True,
        "independent_receipt_verification_required": True,
        "set_equality_does_not_rescue_order_mismatch": True,
        "executable_tool": "full_read_file",
        "single_transport_default_max_bytes": DEFAULT_MAX_RETURN_BYTES,
        "single_transport_hard_max_bytes": MAX_RETURN_BYTES,
        "oversize_complete_read_claim_allowed": False,
    }


class FullReadService:
    """Read a stable-root file completely and return content plus a two-read receipt.

    External paths remain governed by the explicit permission matrix.  A file that
    cannot fit in one bounded MCP response is still hashed, but it cannot receive a
    complete-reading claim because its content was not transported to the caller.
    """

    def __init__(self, stable_root: str | Path, permissions: PermissionGovernor):
        self.stable_root = Path(stable_root).resolve()
        self.permissions = permissions

    def _resolve(self, value: str) -> tuple[Path, bool]:
        candidate = Path(value)
        target = (
            candidate.resolve()
            if candidate.is_absolute()
            else (self.stable_root / candidate).resolve()
        )
        try:
            target.relative_to(self.stable_root)
            return target, True
        except ValueError:
            return target, False

    def read(
        self,
        path: str,
        *,
        max_return_bytes: int = DEFAULT_MAX_RETURN_BYTES,
        expected_sha256: str | None = None,
    ) -> dict[str, Any]:
        target, inside_stable_root = self._resolve(path)
        if not 1 <= int(max_return_bytes) <= MAX_RETURN_BYTES:
            raise ValueError(
                f"max_return_bytes must be between 1 and {MAX_RETURN_BYTES}"
            )
        if not inside_stable_root:
            permission = self.permissions.decide(
                actor="MODEL",
                resource="file://external/" + str(target),
                operation="READ",
            )
            if not permission["authorized"]:
                return {
                    "schema": "kch.full-read-file-receipt.v0.1.0",
                    "gate": "PERMISSION_REQUIRED",
                    "path": str(target),
                    "permission": permission,
                    "complete_read_claim_allowed": False,
                    "authority_created": False,
                }
        else:
            permission = {
                "authorized": True,
                "basis": "BOUNDED_STABLE_ROOT",
                "authority_created": False,
            }
        if not target.is_file():
            raise FileNotFoundError(str(target))

        first = target.read_bytes()
        second = target.read_bytes()
        first_sha256 = hashlib.sha256(first).hexdigest()
        second_sha256 = hashlib.sha256(second).hexdigest()
        stable_across_reads = first == second
        expected_match = expected_sha256 is None or first_sha256 == expected_sha256
        within_transport = len(first) <= int(max_return_bytes)
        try:
            text = first.decode("utf-8-sig")
            encoding = "utf-8-sig"
            binary = False
        except UnicodeDecodeError:
            text = None
            encoding = None
            binary = True

        transported = within_transport and not binary
        gate = "PASS"
        if not stable_across_reads:
            gate = "FAIL_SOURCE_CHANGED_BETWEEN_READS"
        elif not expected_match:
            gate = "FAIL_EXPECTED_SHA256_MISMATCH"
        elif binary:
            gate = "FAIL_TEXT_DECODING_REQUIRED"
        elif not within_transport:
            gate = "FAIL_SINGLE_TRANSPORT_LIMIT"
        line_breaks = None if text is None else len(text.splitlines())
        receipt: dict[str, Any] = {
            "schema": "kch.full-read-file-receipt.v0.1.0",
            "gate": gate,
            "path": str(target),
            "method": "TWO_INDEPENDENT_PATH_READ_BYTES",
            "byte_count": len(first),
            "physical_lines": line_breaks,
            "physical_line_method": "PYTHON_STR_SPLITLINES_UTF8_SIG",
            "sha256": first_sha256,
            "verification_sha256": second_sha256,
            "stable_across_independent_reads": stable_across_reads,
            "expected_sha256": expected_sha256,
            "expected_sha256_match": expected_match,
            "encoding": encoding,
            "binary": binary,
            "max_return_bytes": int(max_return_bytes),
            "complete_bytes_read_by_tool": True,
            "complete_content_transported": transported,
            "fragment_substitution_used": False,
            "permission": permission,
            "complete_read_claim_allowed": gate == "PASS" and transported,
            "authority_created": False,
        }
        if transported:
            receipt["content"] = text
        return receipt


def adjudicate_inventory_order(
    source_items: Iterable[str],
    reported_items: Iterable[str],
    *,
    requested_order: str | None = None,
) -> dict[str, Any]:
    source = list(source_items)
    reported = list(reported_items)
    semantics = SOURCE_NATIVE_ORDER if requested_order is None else requested_order
    if semantics == SOURCE_NATIVE_ORDER:
        expected = source
    elif semantics == LEXICOGRAPHIC_ORDER:
        expected = sorted(source)
    else:
        return {
            "schema": "kch.full-read-order-adjudication.v0.1.0",
            "gate": "FAIL_UNKNOWN_ORDER_SEMANTICS",
            "declared_order_semantics": semantics,
            "source_order_exact": False,
            "set_complete": set(source) == set(reported),
            "duplicates_absent": len(reported) == len(set(reported)),
        }
    exact = reported == expected
    return {
        "schema": "kch.full-read-order-adjudication.v0.1.0",
        "gate": "PASS" if exact else "FAIL_ORDER_MISMATCH",
        "declared_order_semantics": semantics,
        "source_order_exact": reported == source,
        "requested_order_exact": exact,
        "set_complete": set(source) == set(reported),
        "duplicates_absent": len(reported) == len(set(reported)),
        "set_equality_rescues_order_mismatch": False,
    }
