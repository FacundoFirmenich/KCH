from __future__ import annotations

from pathlib import Path

import pytest

from kch_studio.response_modes import ResponseModeManager


def test_canonical_profiles_and_scope_precedence(tmp_path: Path) -> None:
    manager = ResponseModeManager(tmp_path / "response-modes")
    status = manager.status()
    assert [item["name"] for item in status["presets"]] == [
        "Conciso",
        "Explicativo",
        "Extenso",
    ]
    assert status["default_profile"] == "builtin.explicativo"
    assert status["integrity"]["gate"] == "PASS"
    assert status["constitutional_invariants"]["outputs_out_of_scope"] is True
    assert status["constitutional_invariants"]["execution_register_is_never_offered"] is True

    manager.set_scope("WORKSPACE", "workspace-a", "builtin.conciso")
    manager.set_scope("TASK", "task-a", "builtin.extenso")
    task = manager.resolve({"workspace_id": "workspace-a", "task_id": "task-a"})
    assert task["profile"]["profile_id"] == "builtin.extenso"
    assert task["selected_scope"]["scope_type"] == "TASK"

    manager.clear_scope("TASK", "task-a")
    inherited = manager.resolve({"workspace_id": "workspace-a", "task_id": "task-a"})
    assert inherited["profile"]["profile_id"] == "builtin.conciso"
    assert inherited["selected_scope"]["scope_type"] == "WORKSPACE"


def test_custom_profile_is_persistent_but_cannot_break_register_rule(tmp_path: Path) -> None:
    root = tmp_path / "response-modes"
    manager = ResponseModeManager(root)
    receipt = manager.upsert_profile(
        {
            "profile_id": "custom.investigacion",
            "name": "Investigación",
            "base_profile_id": "builtin.extenso",
            "config": {
                "composition": {"citation_density": "HIGH", "formal_structure": True},
                "viewport": {"max_scrolls": 12},
            },
        }
    )
    assert receipt["profile"]["config"]["composition"]["citation_density"] == "HIGH"
    assert receipt["profile"]["config"]["viewport"]["output_footprint_excluded"] is True
    manager.set_scope("SESSION", "session-a", "custom.investigacion")

    reopened = ResponseModeManager(root)
    resolution = reopened.resolve({"session_id": "session-a"})
    assert resolution["profile"]["profile_id"] == "custom.investigacion"
    assert resolution["profile"]["config"]["viewport"]["max_scrolls"] == 12
    with pytest.raises(ValueError, match="constitutional"):
        reopened.upsert_profile(
            {
                "profile_id": "custom.investigacion",
                "name": "Investigación",
                "config": {"execution_trace": {"followup_policy": "ASK_AT_END"}},
            }
        )
    with pytest.raises(ValueError, match="clear every active scope"):
        reopened.archive_profile("custom.investigacion")
    reopened.clear_scope("SESSION", "session-a")
    assert reopened.archive_profile("custom.investigacion")["archived"] is True
    assert reopened.verify()["gate"] == "PASS"


def test_contract_separates_outputs_and_register_is_saved_not_offered(tmp_path: Path) -> None:
    manager = ResponseModeManager(tmp_path / "response-modes")
    contract = manager.compile_contract({"task_id": "task-a"})
    assert contract["outputs_affected"] is False
    assert contract["execution_trace_followup"]["policy"] == "DO_NOT_OFFER"
    assert contract["automatic_application"]["direct_model_control_claimed"] is False
    assert contract["resolution"]["viewport_guarantee"]["guaranteed_without_host_metrics"] is False

    receipt = manager.record_execution(
        {
            "title": "Prueba de ficha",
            "substantive_result": "La explicación principal quedó separada del registro.",
            "changes": ["perfil resuelto", "ficha persistida"],
            "api_token": "must-not-be-written",
            "claim_limits": "No prueba medición real del viewport del host.",
        }
    )
    path = Path(receipt["path"])
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "La explicación principal" in text
    assert "[REDACTED]" in text
    assert "must-not-be-written" not in text
    assert receipt["offered_to_user"] is False
    assert receipt["final_notice"].startswith("Ficha técnica guardada en")
    assert manager.verify()["gate"] == "PASS"


def test_builtin_profiles_are_immutable(tmp_path: Path) -> None:
    manager = ResponseModeManager(tmp_path / "response-modes")
    with pytest.raises(ValueError, match="custom profile_id"):
        manager.upsert_profile(
            {
                "profile_id": "builtin.conciso",
                "name": "Alterado",
                "config": {},
            }
        )
    with pytest.raises(ValueError, match="cannot be archived"):
        manager.archive_profile("builtin.conciso")
