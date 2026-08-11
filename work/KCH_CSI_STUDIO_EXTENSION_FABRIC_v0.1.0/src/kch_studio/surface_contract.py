from __future__ import annotations

import importlib
from typing import Any

INTERNAL = "INTERNAL:"


# Every public method in the strategic runtime classes is classified either as
# a user-facing MCP operation or as an explicitly named composition primitive.
# This is a tested anti-orphan contract, not a claim that every implementation
# has reached production maturity.
STRATEGIC_SURFACE_CONTRACT: dict[str, dict[str, str]] = {
    "kch_studio.account_broker:AccountPermissionBroker": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "request": "account_permission_request",
        "approve": "account_lease_approve",
        "get_lease": "account_lease_get",
        "launch_auth": "account_auth_launch",
        "authorize_use": "account_use_authorize",
        "expire_due": "account_expire_due",
        "status": "account_broker_status",
    },
    "kch_studio.audio_hub:AudioHub": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "audio_data_root": "INTERNAL:GOVERNED_STORAGE_LOCATOR",
        "backends": "audio_backends",
        "ingest_and_transcribe": "audio_ingest_transcribe",
        "speak": "voice_notify",
        "start_monitor": "audio_monitor_start",
        "stop_monitor": "audio_monitor_stop",
        "status": "audio_status",
    },
    "kch_studio.checkpoints:CheckpointManager": {
        "estimate": "checkpoint_estimate",
        "create_structured": "checkpoint_structured_create",
        "full_plan": "checkpoint_full_plan",
        "create_full": "checkpoint_full_create",
        "get_manifest": "checkpoint_manifest_get",
        "diff_current": "checkpoint_diff_current",
        "restore_to_new_root": "checkpoint_restore_new_root",
        "trace_file": "checkpoint_trace_file",
        "status": "checkpoint_status",
    },
    "kch_studio.clipboard_hub:ClipboardHub": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "capture": "clipboard_capture_text",
        "pin": "clipboard_pin",
        "create_postit": "clipboard_postit_create",
        "edit_postit": "clipboard_postit_edit",
        "link_postit": "clipboard_postit_link",
        "get_postit": "clipboard_postit_get",
        "search": "clipboard_search",
        "explanation_context": "clipboard_explanation_context",
        "capture_region": "clipboard_region_capture",
        "read_system_text": "INTERNAL:PLATFORM_CLIPBOARD_READER",
        "poll_once": "clipboard_poll_once",
        "start_monitor": "clipboard_monitor_start",
        "stop_monitor": "clipboard_monitor_stop",
        "status": "clipboard_status",
    },
    "kch_studio.constitutional:ConstitutionalWorkspace": {
        "state": "constitution_state",
        "add_plane": "constitution_plane_add",
        "add_box": "constitution_box_add",
        "update_box": "constitution_box_update",
        "set_box_active": "constitution_box_set_active",
        "connect": "constitution_boxes_connect",
        "propose": "constitution_propose",
        "effective_mandates": "constitution_effective",
    },
    "kch_studio.construct_mode:ConstructMode": {
        "start": "construct_start",
        "state": "construct_session_get",
        "write_file": "construct_file_write",
        "validate": "construct_validate",
        "promote_for_next_start": "construct_promote_next_start",
        "rollback_pointer": "construct_rollback_pointer",
        "status": "kch_mode_status",
    },
    "kch_studio.diction_learning:DictionLearning": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "obl_add": "diction_obl_add",
        "resolve": "diction_resolve",
        "record_correction": "diction_correction_record",
        "status": "diction_status",
    },
    "kch_studio.extension:RuntimeInventory": {"collect": "extension_inventory"},
    "kch_studio.extension:ExtensionFabric": {
        "describe": "studio_status",
        "search": "extension_search",
        "resolve": "extension_resolve",
    },
    "kch_studio.extension:RecommendationEngine": {"evaluate": "extension_recommend"},
    "kch_studio.installation:ConsentPolicy": {
        "adjudicate": "INTERNAL:PER_OPERATION_SESSION_CONSENT_STATE_MACHINE",
        "state": "direct_consent_status",
    },
    "kch_studio.installation:IsolatedInstaller": {
        "plan": "isolated_install_plan",
        "execute": "isolated_install_execute",
        "verify": "isolated_install_verify",
        "rollback": "isolated_install_rollback",
    },
    "kch_studio.kwandata:KwanData": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "create_program": "kwandata_program_create",
        "ingest": "kwandata_ingest",
        "create_supertag": "kwandata_supertag_create",
        "query": "kwandata_query",
        "add_watch_root": "kwandata_watch_add",
        "scan_watch_root": "kwandata_watch_scan",
        "status": "kwandata_status",
    },
    "kch_studio.workbench_suite:WorkbenchSuite": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "ingest": "workbench_ingest",
        "lessons": "workbench_lessons_list",
        "protocols": "workbench_protocols_list",
        "skills": "workbench_skills_list",
        "create_group": "workbench_archive_group_create",
        "attach": "workbench_archive_attach",
        "connect_nodes": "workbench_graph_connect",
        "archive_tree": "workbench_archive_tree",
        "graph": "workbench_graph",
        "resolve_node": "workbench_graph_resolve_node",
        "set_group_archived": "workbench_archive_group_set_archived",
        "configure_budget_account": "workbench_budget_account_configure",
        "set_budget_policy": "workbench_budget_policy_set",
        "record_budget_sample": "workbench_budget_sample_record",
        "budget_status": "workbench_budget_status",
        "run_maintenance": "workbench_maintenance_run",
        "handoffs": "workbench_handoffs_list",
        "kwandata_envelope": "workbench_kwandata_envelope",
        "kwandocs_envelope": "workbench_kwandocs_envelope",
        "verify": "workbench_integrity_verify",
        "status": "workbench_status",
    },
    "kch_studio.launcher:ProactiveLauncher": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "manifest": "proactive_launcher_manifest",
        "start": "proactive_launcher_start",
        "stop": "proactive_launcher_stop",
        "publish": "proactive_event_publish",
        "run_once": "proactive_launcher_run_once",
        "wait": "proactive_launcher_wait",
        "status": "proactive_launcher_status",
    },
    "kch_studio.permissions:PermissionGovernor": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "grant": "permission_grant",
        "revoke": "permission_revoke",
        "decide": "permission_check",
        "require": "INTERNAL:FAIL_CLOSED_COMPOSITION_PRIMITIVE",
        "status": "permission_status",
    },
    "kch_studio.persistence:PersistenceHub": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "create_chat": "persistence_chat_create",
        "append_turn": "persistence_turn_append",
        "mark_page": "persistence_page_mark",
        "get_chat": "persistence_chat_get",
        "create_superchat": "persistence_superchat_create",
        "get_superchat": "persistence_superchat_get",
        "coverage": "persistence_status",
        "verify_chat": "persistence_chat_verify",
    },
    "kch_studio.proactive:ProgrammedPolicy": {
        "state": "programmed_policy_status",
        "replace": "programmed_policy_replace",
        "add_rule": "programmed_policy_rule_add",
        "set_preferences": "programmed_policy_preferences_set",
        "evaluate": "programmed_policy_evaluate",
        "evaluate_all": "programmed_policy_evaluate",
        "session_announcement": "kch_next_status",
    },
    "kch_studio.proactive:ProgrammedDispatcher": {
        "dispatch": "INTERNAL:LEGACY_SYNCHRONOUS_POLICY_COMPOSITOR",
        "dispatch_all": "INTERNAL:LEGACY_SYNCHRONOUS_POLICY_COMPOSITOR",
    },
    "kch_studio.recovery:RecoveryVault": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "save": "INTERNAL:BYTE_CUSTODY_PRIMITIVE",
        "save_json": "INTERNAL:JSON_CUSTODY_PRIMITIVE",
        "latest": "recovery_latest",
        "revision": "recovery_revision",
        "restore": "recovery_restore_revision",
        "record_alert": "recovery_alert_record",
        "snapshot": "recovery_checkpoint",
        "verify": "recovery_verify",
        "export_latest": "recovery_export_latest",
    },
    "kch_studio.response_modes:ResponseModeManager": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "profiles": "response_mode_profiles_list",
        "upsert_profile": "response_mode_profile_upsert",
        "archive_profile": "response_mode_profile_archive",
        "set_scope": "response_mode_scope_set",
        "clear_scope": "response_mode_scope_clear",
        "resolve": "response_mode_resolve",
        "compile_contract": "response_mode_contract",
        "record_execution": "response_execution_register",
        "verify": "response_mode_integrity",
        "status": "response_mode_status",
    },
    "kch_studio.safeguards:RiskAdvisor": {
        "assess": "risk_assess",
        "proceed": "risk_override_record",
    },
    "kch_studio.continuity_guard:ContinuityAndBurdenGovernor": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "freeze_source": "INTERNAL:CONTENT_ADDRESSABLE_SOURCE_FREEZE",
        "adjudicate_reading": "continuity_reading_adjudicate",
        "set_mission": "continuity_mission_set",
        "active_mission": "INTERNAL:MISSION_CONTINUITY_PRIMITIVE",
        "record_harm": "continuity_harm_record",
        "register_protocol": "continuity_protocol_register",
        "resolve_protocols": "continuity_protocol_resolve",
        "preflight": "continuity_action_preflight",
        "verify": "continuity_integrity_verify",
        "status": "continuity_status",
    },
    "kch_studio.continuity_guard:AikidoLearningForge": {
        "transform": "aikido_transform",
        "catalog": "aikido_catalog",
    },
    "kch_studio.continuity_guard:TemporalScaleContractCompiler": {
        "compile": "temporal_scale_compile",
    },
    "kch_studio.continuity_guard:ContinuousPeriodLedgerCompiler": {
        "compile": "continuous_period_ledger_compile",
    },
    "kch_studio.continuity_guard:SourceFitnessGate": {
        "adjudicate": "source_fitness_adjudicate",
    },
    "kch_studio.commitment_monitor:CommitmentMonitor": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "set_alert_callback": "INTERNAL:LAUNCHER_ALERT_BINDING",
        "register": "commitment_monitor_register",
        "launch": "commitment_monitor_launch",
        "check": "commitment_monitor_check",
        "check_all": "INTERNAL:BACKGROUND_RECONCILIATION_TICK",
        "active_ids": "INTERNAL:RESPONSE_PROMISE_AUTHORITY_BINDING",
        "wait_terminal": "commitment_monitor_wait_terminal",
        "evidence": "commitment_monitor_evidence",
        "start": "INTERNAL:CANONICAL_RUNTIME_STARTUP",
        "stop": "INTERNAL:CANONICAL_RUNTIME_SHUTDOWN",
        "status": "commitment_monitor_status",
    },
    "kch_studio.response_authority:ResponseAuthorityGovernor": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "register": "response_authority_register",
        "active_constraints": "INTERNAL:ACTIVE_SEMANTIC_AUTHORITY_RESOLUTION",
        "adjudicate": "response_authority_adjudicate",
        "verify": "INTERNAL:RESPONSE_AUTHORITY_HASH_CHAIN_VERIFY",
        "status": "response_authority_status",
    },
    "kch_studio.continuity_guard:RemoteTransportPreflight": {
        "adjudicate": "remote_transport_preflight",
    },
    "kch_studio.scheduler:KCHScheduler": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "create_agenda": "scheduler_agenda_create",
        "create_schedule": "scheduler_create",
        "get_schedule": "scheduler_get",
        "set_enabled": "scheduler_set_enabled",
        "run_due": "scheduler_run_due",
        "start": "scheduler_start",
        "stop": "scheduler_stop",
        "status": "scheduler_status",
    },
    "kch_studio.studio:Studio": {
        "status": "studio_status",
        "create_session": "studio_create_session",
        "generate": "studio_generate",
        "validate": "studio_validate",
        "seal": "studio_seal",
        "build_and_seal": "studio_build_and_seal",
    },
    "kch_studio.universal_text:UniversalAssetStore": {
        "ingest": "universal_asset_ingest",
        "restore_original": "universal_asset_restore",
        "transform": "universal_asset_transform",
    },
    "kch_studio.universal_text:PlanBuildEngine": {
        "plan": "plan_build_plan",
        "run": "plan_build_execute",
        "build": "plan_build_execute",
    },
    "kch_studio.mis_service:MISService": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "status": "mis_full_status",
        "describe": "mis_describe",
        "exact_decide": "mis_exact_decide",
        "audit_historical": "mis_historical_audit",
        "verify_certificate": "mis_certificate_verify_full",
        "csi_lowering": "mis_dynamic_csi_lowering",
        "atoms": "mis_atoms_list",
        "register_atom": "mis_atom_register",
        "resolve_atom": "mis_atom_resolve",
        "create_study": "mis_study_create",
        "freeze_decision": "mis_study_freeze",
        "observe": "mis_study_observe",
        "study_projection": "mis_study_projection",
        "close_study": "mis_study_close",
        "register_reviewable_decision": "INTERNAL:MIS_TO_PHL_CONSISTENCY_BRIDGE",
        "mark_phl_registration": "INTERNAL:MIS_TO_PHL_CONSISTENCY_BRIDGE",
        "lower_certificate_to_csi": "mis_dynamic_csi_lowering",
        "export_certificate": "mis_certificate_export",
        "sco_work_order_template": "mis_sco_work_order_template",
        "record_bridge": "INTERNAL:HASH_CHAINED_BRIDGE_LEDGER",
        "verify_runtime": "mis_integrity_verify",
    },
    "kch_studio.federated_runtime:RigorRuntime": {
        "status": "rgg_status",
        "resolve_profile": "rgg_resolve_profile",
        "adjudicate_action": "rgg_adjudicate_action",
        "audit_review": "rgg_audit_review",
        "transition_plan": "rgg_transition_plan",
    },
    "kch_studio.federated_runtime:KwanPromptsRuntime": {
        "status": "kwanprompts_status",
        "ingest": "kwanprompts_ingest",
        "inspect": "kwanprompts_inspect",
        "adjudicate": "kwanprompts_adjudicate",
        "kwandocs_envelope": "kwanprompts_kwandocs_envelope",
        "verify": "kwanprompts_verify",
    },
    "kch_studio.federated_runtime:SCORuntime": {
        "status": "sco_status",
        "create": "sco_create",
        "add_node": "sco_add_node",
        "retire_node": "sco_retire_node",
        "add_edge": "sco_add_edge",
        "issue_work_order": "sco_issue_work_order",
        "ingest_receipt": "sco_ingest_receipt",
        "declare_conflict": "sco_declare_conflict",
        "schedule": "sco_schedule",
        "graph_diagnostics": "sco_graph_diagnostics",
        "export_bundle": "sco_export_bundle",
        "dispatch_envelopes": "sco_dispatch_envelopes",
    },
    "kch_studio.federated_runtime:PHLRuntime": {
        "connect": "INTERNAL:SQLITE_CONNECTION_FACTORY",
        "register_capabilities": "INTERNAL:GLOBAL_MUTATION_CATALOG_BOOTSTRAP",
        "dispatch": "INTERNAL:GLOBAL_PHL_EXCLUSIVE_GATE",
        "register_decision": "phl_decision_register",
        "list_decisions": "phl_decisions_list",
        "start": "phl_session_start",
        "score": "phl_score",
        "compile_packet": "phl_packet_compile",
        "close_session": "phl_session_close",
        "status": "phl_status",
    },
}

HOST_COMPOSITION_REFERENCES = {
    "kch_studio.extension:RuntimeInventory",
    "kch_studio.extension:ExtensionFabric",
    "kch_studio.extension:RecommendationEngine",
    "kch_studio.installation:IsolatedInstaller",
    "kch_studio.studio:Studio",
}
ADVANCED_RUNTIME_REFERENCES = set(STRATEGIC_SURFACE_CONTRACT) - HOST_COMPOSITION_REFERENCES


def audit_strategic_surface(
    tool_names: set[str], *, references: set[str] | None = None
) -> dict[str, Any]:
    selected = set(STRATEGIC_SURFACE_CONTRACT) if references is None else set(references)
    unknown = selected - set(STRATEGIC_SURFACE_CONTRACT)
    if unknown:
        raise ValueError(f"unknown strategic surface references: {sorted(unknown)}")
    missing_classifications: dict[str, list[str]] = {}
    stale_classifications: dict[str, list[str]] = {}
    missing_tools: dict[str, list[str]] = {}
    public_methods = 0
    exposed_methods = 0
    internal_methods = 0
    for reference in sorted(selected):
        classification = STRATEGIC_SURFACE_CONTRACT[reference]
        module_name, class_name = reference.split(":", 1)
        cls = getattr(importlib.import_module(module_name), class_name)
        observed = {
            name
            for name, value in cls.__dict__.items()
            if not name.startswith("_")
            and (callable(value) or isinstance(value, (staticmethod, classmethod, property)))
        }
        declared = set(classification)
        if observed - declared:
            missing_classifications[reference] = sorted(observed - declared)
        if declared - observed:
            stale_classifications[reference] = sorted(declared - observed)
        for method, route in classification.items():
            public_methods += 1
            if route.startswith(INTERNAL):
                internal_methods += 1
            else:
                exposed_methods += 1
                if route not in tool_names:
                    missing_tools.setdefault(reference, []).append(f"{method}->{route}")
    passed = not missing_classifications and not stale_classifications and not missing_tools
    return {
        "schema": "kch.strategic-surface-audit.v0.2.0",
        "gate": "PASS" if passed else "FAIL",
        "classes": len(selected),
        "scope": "FULL_INTEGRATED" if references is None else "EXPLICIT_COMPONENT_SCOPE",
        "public_methods": public_methods,
        "tool_exposed_methods": exposed_methods,
        "composition_internal_methods": internal_methods,
        "missing_classifications": missing_classifications,
        "stale_classifications": stale_classifications,
        "missing_tools": missing_tools,
        "claim_ceiling": "SURFACE_CLASSIFICATION_AND_BINDING_ONLY",
        "production_readiness_established": False,
    }
