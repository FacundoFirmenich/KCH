from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from .permissions import PermissionGovernor

SOURCE_NATIVE_ORDER = "SOURCE_NATIVE_ORDER"
LEXICOGRAPHIC_ORDER = "LEXICOGRAPHIC_ORDER"
DEFAULT_MAX_RETURN_BYTES = 1_048_576
MAX_RETURN_BYTES = 5_242_880
MAX_BATCH_ITEMS = 64
MAX_EXACT_SPANS_PER_FILE = 32
MAX_EXACT_SPAN_CHARACTERS = 16_384


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def seal_receipt(value: dict[str, Any], field: str = "receipt_payload_sha256") -> dict[str, Any]:
    value[field] = canonical_sha256({key: item for key, item in value.items() if key != field})
    return value


def verify_receipt_seal(
    value: dict[str, Any], field: str = "receipt_payload_sha256"
) -> dict[str, Any]:
    claimed = value.get(field)
    calculated = canonical_sha256({key: item for key, item in value.items() if key != field})
    return {
        "field": field,
        "claimed": claimed,
        "calculated": calculated,
        "match": isinstance(claimed, str) and claimed == calculated,
    }


def full_read_contract_status() -> dict[str, Any]:
    return {
        "schema": "kch.full-read-contract.v0.2.0",
        "complete_bytes_required": True,
        "fragment_substitution_forbidden": True,
        "default_inventory_order": SOURCE_NATIVE_ORDER,
        "alternate_order_requires_explicit_user_or_preregistered_contract": True,
        "order_semantics_must_be_declared": True,
        "independent_receipt_verification_required": True,
        "set_equality_does_not_rescue_order_mismatch": True,
        "executable_tool": "full_read_file",
        "machine_generated_batch_tool": "full_read_batch",
        "source_backed_verifier_tool": "full_read_verify_batch",
        "exact_span_semantic_evidence_required": True,
        "receipt_self_seal_is_not_source_truth": True,
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
                return seal_receipt({
                    "schema": "kch.full-read-file-receipt.v0.2.0",
                    "gate": "PERMISSION_REQUIRED",
                    "path": str(target),
                    "permission": permission,
                    "complete_read_claim_allowed": False,
                    "authority_created": False,
                })
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
            "schema": "kch.full-read-file-receipt.v0.2.0",
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
        return seal_receipt(receipt)

    @staticmethod
    def _exact_span_evidence(text: str | None, expected_spans: list[str]) -> dict[str, Any]:
        if len(expected_spans) > MAX_EXACT_SPANS_PER_FILE:
            raise ValueError(
                f"expected_evidence_spans cannot exceed {MAX_EXACT_SPANS_PER_FILE}"
            )
        evidence: list[dict[str, Any]] = []
        for span in expected_spans:
            if not isinstance(span, str) or not span:
                raise ValueError("every expected evidence span must be a non-empty string")
            if len(span) > MAX_EXACT_SPAN_CHARACTERS:
                raise ValueError(
                    "an expected evidence span cannot exceed "
                    f"{MAX_EXACT_SPAN_CHARACTERS} characters"
                )
            starts: list[int] = []
            if text is not None:
                cursor = 0
                while True:
                    index = text.find(span, cursor)
                    if index < 0:
                        break
                    starts.append(index)
                    cursor = index + max(1, len(span))
            locations = [
                {
                    "start_character": start,
                    "end_character_exclusive": start + len(span),
                    "start_line": text.count("\n", 0, start) + 1 if text is not None else None,
                    "end_line": text.count("\n", 0, start + len(span)) + 1
                    if text is not None
                    else None,
                }
                for start in starts
            ]
            evidence.append(
                {
                    "expected_text": span,
                    "expected_text_sha256": hashlib.sha256(span.encode("utf-8")).hexdigest(),
                    "occurrence_count": len(starts),
                    "found": bool(starts),
                    "locations": locations,
                }
            )
        if not expected_spans:
            gate = "NOT_REQUESTED"
        elif text is None:
            gate = "FAIL_CONTENT_NOT_TRANSPORTED"
        elif all(item["found"] for item in evidence):
            gate = "PASS"
        else:
            gate = "FAIL_EXPECTED_EXACT_SPAN_ABSENT"
        return {
            "schema": "kch.exact-span-evidence.v0.1.0",
            "gate": gate,
            "all_expected_spans_found": bool(expected_spans)
            and all(item["found"] for item in evidence),
            "spans": evidence,
            "semantic_claim_allowed": gate == "PASS",
        }

    def read_batch(
        self,
        items: list[dict[str, Any]],
        *,
        requested_order: str = SOURCE_NATIVE_ORDER,
        max_return_bytes_per_file: int = DEFAULT_MAX_RETURN_BYTES,
        max_batch_return_bytes: int = MAX_RETURN_BYTES,
    ) -> dict[str, Any]:
        """Produce one ordered machine receipt; no agent-authored inventory is needed."""
        if not 1 <= len(items) <= MAX_BATCH_ITEMS:
            raise ValueError(f"items must contain between 1 and {MAX_BATCH_ITEMS} entries")
        if not 1 <= int(max_batch_return_bytes) <= MAX_RETURN_BYTES:
            raise ValueError(
                f"max_batch_return_bytes must be between 1 and {MAX_RETURN_BYTES}"
            )
        requested_paths = [str(item["path"]) for item in items]
        order = adjudicate_inventory_order(
            requested_paths,
            requested_paths,
            requested_order=requested_order,
        )
        receipts: list[dict[str, Any]] = []
        semantic_requested = False
        for ordinal, item in enumerate(items, start=1):
            receipt = self.read(
                str(item["path"]),
                max_return_bytes=int(item.get("max_return_bytes", max_return_bytes_per_file)),
                expected_sha256=item.get("expected_sha256"),
            )
            expected_spans = list(item.get("expected_evidence_spans", []))
            semantic_requested = semantic_requested or bool(expected_spans)
            receipt["ordinal"] = ordinal
            receipt["requested_path"] = str(item["path"])
            receipt["expected_evidence_spans"] = expected_spans
            receipt["exact_span_evidence"] = self._exact_span_evidence(
                receipt.get("content"), expected_spans
            )
            seal_receipt(receipt)
            receipts.append(receipt)

        total_content_bytes = sum(
            int(receipt.get("byte_count", 0))
            for receipt in receipts
            if "content" in receipt
        )
        batch_transport_allowed = total_content_bytes <= int(max_batch_return_bytes)
        if not batch_transport_allowed:
            for receipt in receipts:
                receipt.pop("content", None)
                receipt["complete_content_transported"] = False
                receipt["complete_read_claim_allowed"] = False
                if receipt["gate"] == "PASS":
                    receipt["gate"] = "FAIL_BATCH_TRANSPORT_LIMIT"
                receipt["exact_span_evidence"] = self._exact_span_evidence(
                    None, list(receipt["expected_evidence_spans"])
                )
                seal_receipt(receipt)

        read_gate = (
            order["gate"] == "PASS"
            and all(receipt["gate"] == "PASS" for receipt in receipts)
            and all(receipt["complete_read_claim_allowed"] for receipt in receipts)
        )
        if not semantic_requested:
            semantic_gate = "NOT_REQUESTED"
        elif all(
            receipt["exact_span_evidence"]["gate"] in {"PASS", "NOT_REQUESTED"}
            for receipt in receipts
        ):
            semantic_gate = "PASS"
        else:
            semantic_gate = "FAIL"
        batch: dict[str, Any] = {
            "schema": "kch.full-read-batch-receipt.v0.1.0",
            "gate": "PASS" if read_gate and semantic_gate != "FAIL" else "FAIL",
            "declared_order_semantics": requested_order,
            "requested_paths": requested_paths,
            "order_adjudication": order,
            "receipts": receipts,
            "file_count": len(receipts),
            "total_content_bytes": total_content_bytes,
            "max_batch_return_bytes": int(max_batch_return_bytes),
            "batch_transport_allowed": batch_transport_allowed,
            "semantic_evidence_gate": semantic_gate,
            "complete_read_batch_claim_allowed": read_gate,
            "semantic_batch_claim_allowed": semantic_requested and semantic_gate == "PASS",
            "manual_inventory_transcription_required": False,
            "authority_created": False,
        }
        return seal_receipt(batch, "batch_payload_sha256")

    def verify_receipt(self, receipt: dict[str, Any]) -> dict[str, Any]:
        """Re-read source and reject a self-consistent but factually corrupted receipt."""
        seal = verify_receipt_seal(receipt)
        if not isinstance(receipt.get("path"), str):
            raise ValueError("receipt.path must be a string")
        source = self.read(
            str(receipt["path"]),
            max_return_bytes=int(receipt.get("max_return_bytes", DEFAULT_MAX_RETURN_BYTES)),
            expected_sha256=receipt.get("expected_sha256"),
        )
        compared_fields = (
            "path",
            "gate",
            "byte_count",
            "physical_lines",
            "sha256",
            "verification_sha256",
            "stable_across_independent_reads",
            "expected_sha256",
            "expected_sha256_match",
            "encoding",
            "binary",
            "max_return_bytes",
            "complete_bytes_read_by_tool",
            "complete_content_transported",
            "fragment_substitution_used",
            "complete_read_claim_allowed",
        )
        mismatches: list[dict[str, Any]] = []
        for field in compared_fields:
            if receipt.get(field) != source.get(field):
                mismatches.append(
                    {
                        "field": field,
                        "recorded": receipt.get(field),
                        "source_backed": source.get(field),
                    }
                )
        recorded_content = receipt.get("content")
        source_content = source.get("content")
        if recorded_content != source_content:
            mismatches.append(
                {
                    "field": "content",
                    "recorded_sha256": hashlib.sha256(
                        str(recorded_content).encode("utf-8")
                    ).hexdigest()
                    if recorded_content is not None
                    else None,
                    "source_backed_sha256": hashlib.sha256(
                        str(source_content).encode("utf-8")
                    ).hexdigest()
                    if source_content is not None
                    else None,
                }
            )
        expected_spans = list(receipt.get("expected_evidence_spans", []))
        source_span_evidence = self._exact_span_evidence(source_content, expected_spans)
        if expected_spans and receipt.get("exact_span_evidence") != source_span_evidence:
            mismatches.append({"field": "exact_span_evidence", "recorded_matches": False})
        verified = seal["match"] and not mismatches
        return {
            "schema": "kch.full-read-receipt-verification.v0.1.0",
            "gate": "PASS_VERIFIED_AGAINST_SOURCE"
            if verified
            else "FAIL_RECEIPT_NOT_SOURCE_TRUE",
            "receipt_seal": seal,
            "mismatches": mismatches,
            "source_backed_receipt_payload_sha256": source["receipt_payload_sha256"],
            "complete_read_claim_allowed": verified
            and source["complete_read_claim_allowed"],
            "semantic_claim_allowed": verified
            and source_span_evidence["semantic_claim_allowed"],
            "authority_created": False,
        }

    def verify_batch(self, batch: dict[str, Any]) -> dict[str, Any]:
        seal = verify_receipt_seal(batch, "batch_payload_sha256")
        receipts = batch.get("receipts")
        if not isinstance(receipts, list) or not receipts:
            raise ValueError("batch.receipts must be a non-empty list")
        verifications = [self.verify_receipt(dict(receipt)) for receipt in receipts]
        recorded_paths = [str(receipt.get("requested_path")) for receipt in receipts]
        requested_paths = [str(path) for path in batch.get("requested_paths", [])]
        order = adjudicate_inventory_order(
            requested_paths,
            recorded_paths,
            requested_order=str(batch.get("declared_order_semantics", SOURCE_NATIVE_ORDER)),
        )
        ordinals_exact = [receipt.get("ordinal") for receipt in receipts] == list(
            range(1, len(receipts) + 1)
        )
        verified = (
            seal["match"]
            and order["gate"] == "PASS"
            and ordinals_exact
            and all(item["gate"] == "PASS_VERIFIED_AGAINST_SOURCE" for item in verifications)
        )
        return {
            "schema": "kch.full-read-batch-verification.v0.1.0",
            "gate": "PASS_VERIFIED_AGAINST_SOURCE"
            if verified
            else "FAIL_BATCH_NOT_SOURCE_TRUE",
            "batch_seal": seal,
            "order_adjudication": order,
            "ordinals_exact": ordinals_exact,
            "receipt_verifications": verifications,
            "complete_read_batch_claim_allowed": verified
            and bool(batch.get("complete_read_batch_claim_allowed")),
            "semantic_batch_claim_allowed": verified
            and bool(batch.get("semantic_batch_claim_allowed")),
            "authority_created": False,
        }


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
    duplicates_absent = len(reported) == len(set(reported))
    return {
        "schema": "kch.full-read-order-adjudication.v0.1.0",
        "gate": "PASS" if exact and duplicates_absent else "FAIL_ORDER_MISMATCH",
        "declared_order_semantics": semantics,
        "source_order_exact": reported == source,
        "requested_order_exact": exact,
        "set_complete": set(source) == set(reported),
        "duplicates_absent": duplicates_absent,
        "set_equality_rescues_order_mismatch": False,
    }
