import hashlib

from kch_studio.full_read_contract import (
    LEXICOGRAPHIC_ORDER,
    FullReadService,
    adjudicate_inventory_order,
    full_read_contract_status,
)
from kch_studio.permissions import PermissionGovernor


def test_source_order_is_constitutional_default() -> None:
    status = full_read_contract_status()
    assert status["default_inventory_order"] == "SOURCE_NATIVE_ORDER"
    assert status["set_equality_does_not_rescue_order_mismatch"] is True
    result = adjudicate_inventory_order(["b", "a"], ["a", "b"])
    assert result["set_complete"] is True
    assert result["gate"] == "FAIL_ORDER_MISMATCH"


def test_alternate_order_requires_explicit_semantics() -> None:
    result = adjudicate_inventory_order(
        ["b", "a"], ["a", "b"], requested_order=LEXICOGRAPHIC_ORDER
    )
    assert result["gate"] == "PASS"
    assert result["source_order_exact"] is False


def test_executable_full_read_transports_every_line_and_verifies_twice(tmp_path) -> None:
    stable = tmp_path / "stable"
    stable.mkdir()
    source = stable / "long-source.txt"
    text = "".join(f"line-{number:04d}\n" for number in range(1, 902))
    source.write_text(text, encoding="utf-8")
    service = FullReadService(stable, PermissionGovernor(tmp_path / "permissions"))

    on_disk = source.read_bytes()
    receipt = service.read(
        "long-source.txt", expected_sha256=hashlib.sha256(on_disk).hexdigest()
    )

    assert receipt["gate"] == "PASS"
    assert receipt["content"].splitlines() == text.splitlines()
    assert receipt["byte_count"] == len(on_disk)
    assert receipt["physical_lines"] == 901
    assert receipt["stable_across_independent_reads"] is True
    assert receipt["complete_read_claim_allowed"] is True


def test_executable_full_read_refuses_untransported_or_hash_mismatched_claim(tmp_path) -> None:
    stable = tmp_path / "stable"
    stable.mkdir()
    source = stable / "source.txt"
    source.write_text("complete source", encoding="utf-8")
    service = FullReadService(stable, PermissionGovernor(tmp_path / "permissions"))

    oversize = service.read("source.txt", max_return_bytes=5)
    mismatch = service.read("source.txt", expected_sha256="0" * 64)

    assert oversize["gate"] == "FAIL_SINGLE_TRANSPORT_LIMIT"
    assert "content" not in oversize
    assert oversize["complete_read_claim_allowed"] is False
    assert mismatch["gate"] == "FAIL_EXPECTED_SHA256_MISMATCH"
    assert mismatch["complete_read_claim_allowed"] is False


def test_executable_full_read_requires_permission_outside_stable_root(tmp_path) -> None:
    stable = tmp_path / "stable"
    stable.mkdir()
    external = tmp_path / "external.txt"
    external.write_text("outside", encoding="utf-8")
    service = FullReadService(stable, PermissionGovernor(tmp_path / "permissions"))

    receipt = service.read(str(external))

    assert receipt["gate"] == "PERMISSION_REQUIRED"
    assert receipt["complete_read_claim_allowed"] is False
