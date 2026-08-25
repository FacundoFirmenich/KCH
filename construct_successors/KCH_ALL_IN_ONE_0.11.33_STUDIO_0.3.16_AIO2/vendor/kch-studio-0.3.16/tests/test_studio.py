from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

from kch_studio.contracts import ArtifactKind, ArtifactSpec
from kch_studio.installation import ConsentDecision, IsolatedInstaller
from kch_studio.studio import Studio

AUTHORITY = frozenset(
    {"INSPECT", "DESIGN", "BUILD_STAGED", "VALIDATE", "RECOMMEND", "REQUEST_INSTALL"}
)


def make_specs(tmp_path: Path) -> list[ArtifactSpec]:
    parent = tmp_path / "parent.bin"
    parent.write_bytes(b"canonical-parent-bytes\n")
    parent_sha = hashlib.sha256(parent.read_bytes()).hexdigest()
    common = {
        "jurisdiction": "KCH_PREINSTALL_TEST_ONLY",
        "inputs": ("request",),
        "outputs": ("receipt",),
        "authority_ceiling": AUTHORITY,
    }
    return [
        ArtifactSpec(
            name="evidence-inspector",
            kind=ArtifactKind.SKILL,
            objective="inspect evidence without expanding claims",
            metadata={
                "instructions": [
                    "Inspect the supplied evidence.",
                    "Separate observation from inference.",
                    "Return limits and next action.",
                ]
            },
            **common,
        ),
        ArtifactSpec(
            name="required-field-tool",
            kind=ArtifactKind.TOOL,
            objective="validate required request fields",
            metadata={"operation": "validate_required_fields", "required_fields": ["request"]},
            **common,
        ),
        ArtifactSpec(
            name="bounded-contract-mcp",
            kind=ArtifactKind.MCP,
            objective="expose bounded contract inspection",
            metadata={
                "tools": [
                    {
                        "name": "validate_request",
                        "title": "Validate request",
                        "description": "Validate the request field without side effects.",
                        "operation": "validate_required_fields",
                        "required_fields": ["request"],
                        "input_schema": {
                            "type": "object",
                            "properties": {"request": {"type": "string"}},
                            "required": ["request"],
                            "additionalProperties": False,
                        },
                    }
                ]
            },
            **common,
        ),
        ArtifactSpec(
            name="request-selector",
            kind=ArtifactKind.OPERATOR,
            objective="admit and select request fields",
            metadata={
                "steps": [
                    {"kind": "require", "fields": ["request"]},
                    {"kind": "select", "fields": ["request"]},
                ]
            },
            **common,
        ),
        ArtifactSpec(
            name="bounded-builder-agent",
            kind=ArtifactKind.AGENT,
            objective="admit bounded staged build work orders",
            metadata={"parallel_group": "builders", "supervisor": "KCH-AGENT-CSI-STUDIO"},
            **common,
        ),
        ArtifactSpec(
            name="request-authority-rule",
            kind=ArtifactKind.RULE,
            objective="ask when required authority context is absent",
            metadata={
                "required_fields": ["request", "authority"],
                "forbidden_values": {"authority": ["INSTALL", "PUBLISH"]},
            },
            **common,
        ),
        ArtifactSpec(
            name="verified-lineage-fork",
            kind=ArtifactKind.KWANFORK,
            objective="record a non-authority-inheriting lineage transformation",
            metadata={
                "parent": {"id": "PARENT-01", "path": str(parent), "sha256": parent_sha},
                "transformations": [
                    {"id": "T1", "operation": "host_projection", "loss_accounted": True}
                ],
                "purpose_identity_preservation": "PASS_LOCAL",
                "decision_equivalence": "NOT_ESTIMABLE",
                "evidence_contract_equivalence": "NOT_ESTIMABLE",
                "provenance_preservation": "PASS_PARENT_BYTES",
                "transport_integrity": "PASS_PARENT_BYTES",
            },
            **common,
        ),
        ArtifactSpec(
            name="add-receipt-mod",
            kind=ArtifactKind.MOD,
            objective="add a receipt state to a JSON object",
            metadata={
                "operations": [{"op": "add", "path": "/state", "value": "REVIEW"}],
                "sample_document": {"request": "x"},
                "expected_document": {"request": "x", "state": "REVIEW"},
            },
            **common,
        ),
        ArtifactSpec(
            name="governed-workflow-plugin",
            kind=ArtifactKind.PLUGIN,
            objective="package a governed evidence workflow",
            metadata={
                "instructions": [
                    "Inspect evidence.",
                    "Apply the declared workflow.",
                    "Return a bounded receipt.",
                ]
            },
            **common,
        ),
        ArtifactSpec(
            name="cross-host-staged-adapter",
            kind=ArtifactKind.HOST_ADAPTER,
            objective="project an inert MCP configuration into supported hosts",
            host_targets=("codex", "vscode", "cline", "opencode"),
            metadata={
                "command": [sys.executable, "-m", "kch_studio.mcp_server"],
                "cwd": str(tmp_path),
            },
            **common,
        ),
        ArtifactSpec(
            name="bounded-receipt-preset",
            kind=ArtifactKind.PRESET,
            objective="render a bounded evidence receipt prompt",
            metadata={
                "template": "Evidence: {evidence}; limit: {limit}",
                "variables": ["evidence", "limit"],
                "sample_values": {"evidence": "observed", "limit": "local"},
            },
            **common,
        ),
    ]


def test_all_eleven_generators_build_validate_and_seal(tmp_path: Path) -> None:
    studio = Studio(tmp_path / "studio")
    results = []
    for spec in make_specs(tmp_path):
        result = studio.build_and_seal(spec)
        results.append(result)
        assert result["state"] == "SEALED_CANDIDATE", (spec.kind, result.get("validation"))
        assert result["seal_body"]["installation_authorized"] is False
        assert result["seal_body"]["phl_real_executed"] is False
        assert studio.store.verify_chain(result["session_id"])["passed"] is True
    assert len(results) == 11
    assert {result["spec"]["kind"] for result in results} == {kind.value for kind in ArtifactKind}


def test_transition_cannot_skip_generation(tmp_path: Path) -> None:
    studio = Studio(tmp_path / "studio")
    session = studio.create_session(make_specs(tmp_path)[1])
    with pytest.raises(ValueError, match="sealing requires VALIDATED"):
        studio.seal(session["session_id"])


def test_isolated_install_four_way_consent_and_rollback(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "artifact.txt").write_text("sealed bytes\n", encoding="utf-8")
    installer = IsolatedInstaller(tmp_path / "sandbox")
    plan = installer.plan(source, artifact_kind="TOOL", target_name="candidate")
    declined = installer.execute(plan, ConsentDecision.NO)
    assert declined["state"] == "DECLINED_NO_SIDE_EFFECTS"
    assert not (tmp_path / "sandbox" / "profiles" / "candidate").exists()
    receipt = installer.execute(plan, ConsentDecision.ALWAYS_THIS_SESSION)
    assert receipt["state"] == "INSTALLED_ISOLATED_DISABLED"
    assert installer.verify(receipt)["passed"] is True
    rollback = installer.rollback(receipt)
    assert rollback["state"] == "ROLLED_BACK"
    assert rollback["target_exists_after"] is False
    second = IsolatedInstaller(tmp_path / "second-sandbox")
    second_plan = second.plan(source, artifact_kind="TOOL", target_name="candidate")
    never = second.execute(second_plan, ConsentDecision.NEVER_THIS_SESSION)
    assert never["state"] == "DECLINED_NO_SIDE_EFFECTS"
    assert second.execute(second_plan, ConsentDecision.YES)["state"] == "DECLINED_NO_SIDE_EFFECTS"
