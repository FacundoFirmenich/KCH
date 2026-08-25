from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from kch_studio.advanced_runtime import KCHAdvancedRuntime
from kch_studio.libresource import (
    COMPATIBILITY_DIMENSIONS,
    FLUSH_DECISION_GATES,
    PLUG_AND_PLAY_GATES,
    ROUTES,
    UNIVERSAL_WITHDRAWAL_GATES,
    LibresourceError,
    LibresourceRuntime,
    validate_package_manifest,
)


def manifest(*, version: str = "1.0.0", zone: str = "FOREIGN_CAPABILITY_ZONE") -> dict:
    return {
        "schema": "kch.libresource.package.v0.1.0",
        "node_id": "test-adapter",
        "version": version,
        "zone": zone,
        "initial_authority": "NONE",
        "license": "TEST-ONLY",
        "state_export": "state/export.json",
        "content_hashes": ["sha256:" + "a" * 64],
        "csi_contracts": ["csi:test-adapter.v1"],
        "sbom": ["sbom/test.spdx.json"],
        "provenance": ["provenance/test.json"],
        "dependencies": [
            {
                "resource_id": "foreign:test",
                "kind": "PROVIDER",
                "role": "OPTIONAL_ADAPTER",
                "jurisdiction": "TEST",
                "constitutive": False,
                "alternatives": ["native:test"],
                "authority": "NONE",
                "removal_route": "flush:test",
            }
        ],
        "permissions": ["scope:test:read"],
        "build_recipes": ["build/test.json"],
        "platforms": ["test-platform"],
        "alternatives": ["native:test"],
        "migrations": ["migration:test-v1"],
        "conformance_tests": ["test:round-trip"],
        "signatures": [],
        "capability_contract": {
            "core": ["test"],
            "namespaced_extensions": ["test.vendor/feature"],
            "degradation_policy": "DECLARE_AND_PRESERVE",
        },
        "canonical_state": {
            "schema": "test.state.v1",
            "export": "state/export.json",
            "restore": "test:restore",
            "verification": "test:round-trip",
        },
        "platform_independence": {
            "reference_implementation": "test-platform",
            "alternate_paths": ["test-platform-2"],
            "single_platform_is_canonical": False,
        },
        "compatibility": {
            dimension: {
                "contract": f"csi:compatibility:{dimension.lower()}",
                "evidence_refs": [],
            }
            for dimension in COMPATIBILITY_DIMENSIONS
        },
        "routes": {
            route: {"supported": True, "evidence_refs": [f"test:{route.lower()}"]}
            for route in ROUTES
        },
        "human_policy": {"nationality_discrimination": False},
    }


def register(runtime: LibresourceRuntime) -> dict:
    return runtime.register_node({"command_id": "CMD-REGISTER", "manifest": manifest()})


def begin(runtime: LibresourceRuntime) -> dict:
    register(runtime)
    return runtime.begin_flush(
        {
            "command_id": "CMD-BEGIN",
            "node_id": "test-adapter",
            "version": "1.0.0",
            "resource_id": "foreign:test",
            "csi_contract": {"input": "x", "output": "y", "semantic_equivalence": True},
            "rollback": {"snapshot": "sha256:" + "b" * 64, "restore": "test:restore"},
        }
    )


def test_manifest_enforces_authority_routes_and_non_discrimination() -> None:
    value = manifest()
    assert validate_package_manifest(value)["initial_authority"] == "NONE"
    value["initial_authority"] = "PROVIDER"
    with pytest.raises(LibresourceError, match="authority NONE"):
        validate_package_manifest(value)
    value = manifest()
    value["routes"].pop("ROLLBACK")
    with pytest.raises(LibresourceError, match="routes must be exactly"):
        validate_package_manifest(value)
    value = manifest()
    value["human_policy"]["nationality_discrimination"] = True
    with pytest.raises(LibresourceError, match="forbids discrimination"):
        validate_package_manifest(value)


def test_node_registration_is_idempotent_and_version_immutable(tmp_path: Path) -> None:
    runtime = LibresourceRuntime(tmp_path)
    first = register(runtime)
    second = register(runtime)
    assert first == second
    assert first["registered"] is True
    changed = manifest()
    changed["license"] = "CHANGED"
    with pytest.raises((LibresourceError, sqlite3.IntegrityError)):
        runtime.register_node({"command_id": "CMD-CHANGED", "manifest": changed})


def test_adapter_contracts_are_exterior_zero_authority_and_not_prevalidated(tmp_path: Path) -> None:
    runtime = LibresourceRuntime(tmp_path)
    for adapter in ("WINDOWS", "VSCODE", "GITHUB", "GOOGLE", "UNSEEN_PROVIDER"):
        contract = runtime.adapter_contract(adapter)
        assert contract["zone"] == "FOREIGN_CAPABILITY_ZONE"
        assert contract["authority"] == "NONE"
        assert contract["core_state_allowed"] is False
        assert contract["plug_and_play_established"] is False
        assert contract["required_routes"] == list(ROUTES)
        assert contract["required_plug_and_play_gates"] == list(PLUG_AND_PLAY_GATES)


def test_dependency_audit_detects_no_declared_single_point_but_does_not_claim_independence(
    tmp_path: Path,
) -> None:
    runtime = LibresourceRuntime(tmp_path)
    register(runtime)
    result = runtime.dependency_audit("test-adapter", "1.0.0")
    assert result["conclusion"] == (
        "NO_DECLARED_CONSTITUTIVE_SINGLE_POINT_WITHDRAWAL_NOT_PROVEN"
    )
    assert result["constitutive_without_alternative"] == []
    assert result["authority_violations"] == []
    assert result["independence_established"] is False
    assert len(result["receipt_sha256"]) == 64


def observations(names: tuple[str, ...], outcome: str = "PASS") -> dict:
    return {
        name: {"outcome": outcome, "evidence_refs": [f"receipt:{name.lower()}"]}
        for name in names
    }


def test_ultracompatibility_requires_independent_evidence_after_structural_pass(
    tmp_path: Path,
) -> None:
    runtime = LibresourceRuntime(tmp_path)
    result = runtime.adjudicate_compatibility(
        {
            "subject": "test-adapter@1.0.0",
            "scope": {"external_system": "test", "version": "1"},
            "dimensions": observations(COMPATIBILITY_DIMENSIONS),
            "routes": observations(ROUTES),
        }
    )
    assert result["bounded_candidate_pass"] is True
    assert result["ultracompatibility_established"] is False
    assert result["reason_not_established"] == (
        "INDEPENDENT_EVIDENCE_VERIFICATION_REQUIRED"
    )
    adverse = observations(COMPATIBILITY_DIMENSIONS)
    adverse["SEMANTIC"] = {
        "outcome": "FAIL",
        "evidence_refs": ["receipt:semantic-fail"],
    }
    result = runtime.adjudicate_compatibility(
        {
            "subject": "test-adapter@1.0.0",
            "scope": {"external_system": "test", "version": "1"},
            "dimensions": adverse,
            "routes": observations(ROUTES),
        }
    )
    assert result["dimension_result"] == "FAIL"
    assert result["bounded_candidate_pass"] is False


def test_plug_and_play_is_scoped_and_never_self_certifies(tmp_path: Path) -> None:
    runtime = LibresourceRuntime(tmp_path)
    result = runtime.adjudicate_plug_and_play(
        {
            "adapter": "VSCODE",
            "environment": {
                "host": "fixture-host",
                "os": "fixture-os",
                "architecture": "fixture-arch",
                "client_version": "fixture-client-1",
            },
            "capabilities": ["chat-and-execution"],
            "gates": observations(PLUG_AND_PLAY_GATES),
        }
    )
    assert result["bounded_candidate_pass"] is True
    assert result["plug_and_play_established"] is False
    assert result["generalization_authorized"] is False
    assert result["reason_not_established"] == (
        "INDEPENDENT_EXECUTION_RECEIPT_VERIFICATION_REQUIRED"
    )


def test_flush_is_sequential_evidence_bound_and_not_automatic(tmp_path: Path) -> None:
    runtime = LibresourceRuntime(tmp_path)
    receipt = begin(runtime)
    with pytest.raises(LibresourceError, match="must be sequential"):
        runtime.transition_flush(
            {
                "command_id": "CMD-SKIP",
                "flush_id": receipt["flush_id"],
                "target_state": "CSI_SHADOW",
                "evidence_refs": ["test:skip"],
            }
        )
    moved = runtime.transition_flush(
        {
            "command_id": "CMD-CONTRACTED",
            "flush_id": receipt["flush_id"],
            "target_state": "CSI_CONTRACTED",
            "evidence_refs": ["test:contract"],
        }
    )
    assert moved["automatic_promotion"] is False
    with pytest.raises(LibresourceError, match="requires evidence"):
        runtime.transition_flush(
            {
                "command_id": "CMD-NO-EVIDENCE",
                "flush_id": receipt["flush_id"],
                "target_state": "CSI_SHADOW",
                "evidence_refs": [],
            }
        )


def test_flush_cannot_remove_a_useful_resource_without_competence_and_proportionality(
    tmp_path: Path,
) -> None:
    runtime = LibresourceRuntime(tmp_path)
    receipt = begin(runtime)
    states = [
        "CSI_CONTRACTED",
        "CSI_SHADOW",
        "CSI_DIFFERENTIAL_PASS",
        "CSI_PREFERRED",
        "FOREIGN_OPTIONAL",
        "FOREIGN_REMOVABLE",
    ]
    for index, state in enumerate(states):
        runtime.transition_flush(
            {
                "command_id": f"CMD-STATE-{index}",
                "flush_id": receipt["flush_id"],
                "target_state": state,
                "evidence_refs": [f"test:{state.lower()}"],
            }
        )
    for index, gate in enumerate(UNIVERSAL_WITHDRAWAL_GATES):
        runtime.record_gate(
            {
                "command_id": f"CMD-GATE-{index}",
                "flush_id": receipt["flush_id"],
                "gate_name": gate,
                "outcome": "PASS",
                "evidence_refs": [f"test:{gate.lower()}"],
            }
        )
    with pytest.raises(LibresourceError, match="SUCCESSOR_COMPETENCE"):
        runtime.transition_flush(
            {
                "command_id": "CMD-PREMATURE",
                "flush_id": receipt["flush_id"],
                "target_state": "LIBRESOURCE_FLUSHED",
                "evidence_refs": ["test:premature"],
            }
        )


def test_full_flush_requires_every_gate_and_preserves_history(tmp_path: Path) -> None:
    runtime = LibresourceRuntime(tmp_path)
    receipt = begin(runtime)
    flush_id = receipt["flush_id"]
    states = [
        "CSI_CONTRACTED",
        "CSI_SHADOW",
        "CSI_DIFFERENTIAL_PASS",
        "CSI_PREFERRED",
        "FOREIGN_OPTIONAL",
        "FOREIGN_REMOVABLE",
    ]
    for index, state in enumerate(states):
        runtime.transition_flush(
            {
                "command_id": f"CMD-T-{index}",
                "flush_id": flush_id,
                "target_state": state,
                "evidence_refs": [f"test:{state.lower()}"],
            }
        )
    for index, gate in enumerate((*UNIVERSAL_WITHDRAWAL_GATES, *FLUSH_DECISION_GATES)):
        runtime.record_gate(
            {
                "command_id": f"CMD-G-{index}",
                "flush_id": flush_id,
                "gate_name": gate,
                "outcome": "PASS",
                "evidence_refs": [f"test:{gate.lower()}"],
            }
        )
    flushed = runtime.transition_flush(
        {
            "command_id": "CMD-FLUSHED",
            "flush_id": flush_id,
            "target_state": "LIBRESOURCE_FLUSHED",
            "evidence_refs": ["test:withdrawal"],
        }
    )
    assert flushed["state"] == "LIBRESOURCE_FLUSHED"
    assert runtime.evaluate(flush_id)["conclusion"] == "LIBRESOURCE_INDEPENDENCE_PASS"
    assert runtime.evaluate(flush_id)["absence_established"] is True
    sealed = runtime.transition_flush(
        {
            "command_id": "CMD-SEALED",
            "flush_id": flush_id,
            "target_state": "SEALED",
            "evidence_refs": ["test:sealed"],
        }
    )
    assert sealed["state"] == "SEALED"
    assert runtime.verify()["valid"] is True


def test_adverse_and_degraded_results_are_preserved_without_pass_promotion(tmp_path: Path) -> None:
    runtime = LibresourceRuntime(tmp_path)
    flush_id = begin(runtime)["flush_id"]
    runtime.record_gate(
        {
            "command_id": "CMD-FAIL",
            "flush_id": flush_id,
            "gate_name": "INDEPENDENT_BOOT",
            "outcome": "FAIL",
            "evidence_refs": ["test:boot-failed"],
        }
    )
    result = runtime.evaluate(flush_id)
    assert result["conclusion"] == "LIBRESOURCE_FAIL_CONSTITUTIVE_DEPENDENCY"
    assert result["independence_established"] is False
    status = runtime.status()
    assert status["sovereignty_principle"] == "VOCATIONALLY_SOVEREIGN_NOT_RECKLESS"
    assert status["license_legally_validated"] is False
    assert status["alternate_os_execution_established"] is False
    assert status["plug_and_play_hosts_established"] == []


def test_libresource_is_composed_before_phl_and_constitutional_lock_wrappers(
    tmp_path: Path,
) -> None:
    stable = tmp_path / "stable"
    stable.mkdir()
    runtime = KCHAdvancedRuntime(tmp_path / "runtime", stable_root=stable)
    try:
        expected = {
            "libresource_status",
            "libresource_node_register",
            "libresource_node_inspect",
            "libresource_flush_begin",
            "libresource_gate_record",
            "libresource_flush_transition",
            "libresource_evaluate",
            "libresource_adapter_contract",
            "libresource_dependency_audit",
            "libresource_compatibility_adjudicate",
            "libresource_pnp_adjudicate",
        }
        assert expected <= set(runtime.handlers)
        assert {
            "libresource_node_register",
            "libresource_flush_begin",
            "libresource_gate_record",
            "libresource_flush_transition",
        } <= runtime._mutating_tool_names
        status = runtime.status()
        assert status["components"]["libresource"]["sovereignty_principle"] == (
            "VOCATIONALLY_SOVEREIGN_NOT_RECKLESS"
        )
        assert status["phl_training_executed"] is False
        assert status["capability_blind_spots"] == []
    finally:
        runtime.close()
