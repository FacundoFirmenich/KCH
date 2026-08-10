from __future__ import annotations

from pathlib import Path

import pytest

from kch_studio.advanced_runtime import KCHAdvancedRuntime
from kch_studio.mcp_server import TOOLS, StudioMCP
from kch_studio.operational_surface import OPERATIONAL_TOOLS
from kch_studio.surface_contract import audit_strategic_surface


def test_complete_operational_surface_has_handlers_and_scoped_consent(tmp_path: Path) -> None:
    server = StudioMCP(tmp_path / "runtime")
    try:
        names = [item["name"] for item in TOOLS]
        assert len(names) == len(set(names))
        assert set(names) == set(server.handlers)
        preflight = server.call("kch_preflight", {})["structuredContent"]
        assert preflight["gate"] == "PASS", preflight
        assert preflight["canonical_entrypoint"] == "kch_studio.mcp_server:StudioMCP"
        workbench = server.call("workbench_status", {})["structuredContent"]
        assert workbench["integrity"]["gate"] == "PASS"
        assert workbench["automatic_scheduler_binding"]["state"] == (
            "DEFAULT_ENABLED_USER_CUSTOMIZABLE"
        )
        denied_work = server.call(
            "workbench_ingest",
            {
                "source_kind": "CHAT",
                "title": "must not persist",
                "raw_text": "Primero no debe guardarse este texto.",
                "consent": "NO",
            },
        )["structuredContent"]
        assert denied_work["state"] == "NOT_EXECUTED_CONSENT_DENIED"
        accepted_work = server.call(
            "workbench_ingest",
            {
                "source_kind": "SESSION",
                "title": "evidence-derived protocol",
                "raw_text": (
                    "Primero, el paso debe leer cada archivo completo.\n"
                    "Después, el segundo paso debe calcular el hash.\n"
                    "Fallo: antes se leyó sólo un fragmento.\n"
                    "Decisión vinculante: conservar el recibo exacto.\n"
                    "Este caso no demuestra validación industrial."
                ),
                "workspace_id": "KCH-TEST",
                "consent": "YES",
            },
        )["structuredContent"]
        assert accepted_work["state"] == "EXECUTED_UNDER_SCOPED_USER_CONSENT"
        assert accepted_work["result"]["automatic_maintenance"]["generated"][0]["skill"][
            "state"
        ] == "STAGED_UNEVALUATED"
        assert len(OPERATIONAL_TOOLS) >= 60
        for descriptor in OPERATIONAL_TOOLS:
            if not descriptor["readOnly"]:
                consent = descriptor["inputSchema"]["properties"]["consent"]
                assert consent["enum"] == [
                    "YES",
                    "NO",
                    "NEVER_THIS_SESSION",
                    "ALWAYS_THIS_SESSION",
                ]
                assert "consent" in descriptor["inputSchema"]["required"]

        before = len(server.advanced.constitution.state()["boxes"])
        denied = server.call("constitution_box_add", {"content": "never written", "consent": "NO"})[
            "structuredContent"
        ]
        assert denied["state"] == "NOT_EXECUTED_CONSENT_DENIED"
        assert len(server.advanced.constitution.state()["boxes"]) == before

        first = server.call(
            "constitution_box_add",
            {"content": "first", "consent": "ALWAYS_THIS_SESSION"},
        )["structuredContent"]
        second = server.call("constitution_box_add", {"content": "second", "consent": "NO"})[
            "structuredContent"
        ]
        assert first["state"] == second["state"] == "EXECUTED_UNDER_SCOPED_USER_CONSENT"

        cross_action = server.call(
            "constitution_plane_add",
            {"label": "must remain denied", "orientation": "VERTICAL", "consent": "NO"},
        )["structuredContent"]
        assert cross_action["state"] == "NOT_EXECUTED_CONSENT_DENIED"
        assert server.advanced.direct_consent_status()["scope"] == "PER_ACTION_PER_RUNTIME_SESSION"

        never = server.call(
            "programmed_policy_preferences_set",
            {"enabled": False, "consent": "NEVER_THIS_SESSION"},
        )["structuredContent"]
        still_never = server.call(
            "programmed_policy_preferences_set",
            {"enabled": False, "consent": "YES"},
        )["structuredContent"]
        assert never["state"] == still_never["state"] == "NOT_EXECUTED_CONSENT_DENIED"

        started = server.call(
            "phl_session_start",
            {"trigger": "OPERATIONAL_SURFACE_LOCK_NO_FEEDBACK", "consent": "YES"},
        )["structuredContent"]
        with pytest.raises(PermissionError, match="BLOCKED_BY_PHL_EXCLUSIVE_LOCK"):
            server.call("constitution_box_add", {"content": "blocked", "consent": "YES"})
        server.call("phl_session_close", {"public_session_id": started["public_session_id"]})
        assert server.advanced.phl.status()["training_executed"] is False
    finally:
        server.advanced.close()


def test_standalone_advanced_runtime_audits_only_its_component_scope(tmp_path: Path) -> None:
    runtime = KCHAdvancedRuntime(tmp_path / "advanced-only")
    try:
        status = runtime.status()
        surface = status["components"]["strategic_surface"]
        assert surface["gate"] == "PASS", surface
        assert surface["scope"] == "EXPLICIT_COMPONENT_SCOPE"
    finally:
        runtime.close()


def test_safe_ui_templates_default_mutations_to_no() -> None:
    from kch_studio.ui import KCHStudioApp

    for descriptor in OPERATIONAL_TOOLS:
        template = KCHStudioApp._safe_tool_template(descriptor)
        if not descriptor["readOnly"]:
            assert template["consent"] == "NO"


def test_every_strategic_public_method_is_exposed_or_classified_internal() -> None:
    audit = audit_strategic_surface({item["name"] for item in TOOLS})
    assert audit["gate"] == "PASS", audit
    assert audit["public_methods"] >= 180
    assert audit["tool_exposed_methods"] > audit["composition_internal_methods"]
    assert audit["production_readiness_established"] is False
