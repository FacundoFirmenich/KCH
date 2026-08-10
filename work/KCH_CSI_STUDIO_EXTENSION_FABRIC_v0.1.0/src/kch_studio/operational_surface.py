from __future__ import annotations

import base64
from typing import Any, Callable

from .constitutional import Actor

S = {"type": "string"}
B = {"type": "boolean"}
O = {"type": "object"}  # noqa: E741 - compact JSON-schema atom
A = {"type": "array"}
I = {"type": "integer"}  # noqa: E741 - compact JSON-schema atom
N = {"type": "number"}
CONSENT = {
    "type": "string",
    "enum": ["YES", "NO", "NEVER_THIS_SESSION", "ALWAYS_THIS_SESSION"],
}


def _schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _tool(
    name: str,
    title: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
    *,
    read_only: bool,
) -> dict[str, Any]:
    return {
        "name": name,
        "title": title,
        "description": description,
        "inputSchema": _schema(properties, required),
        "readOnly": read_only,
    }


def ro(
    name: str, title: str, description: str, properties: dict[str, Any], required: list[str]
) -> dict[str, Any]:
    return _tool(name, title, description, properties, required, read_only=True)


def mut(
    name: str, title: str, description: str, properties: dict[str, Any], required: list[str]
) -> dict[str, Any]:
    return _tool(
        name,
        title,
        description,
        {**properties, "consent": CONSENT},
        [*required, "consent"],
        read_only=False,
    )


OPERATIONAL_TOOLS = [
    ro(
        "direct_consent_status",
        "Inspect direct-action consent",
        "Inspect per-action session consent without granting authority.",
        {},
        [],
    ),
    mut(
        "mis_certificate_export",
        "Export MIS certificate",
        "Write one verified exact MIS certificate to the governed local export area without promoting its claim ceiling.",
        {"certificate": O},
        ["certificate"],
    ),
    ro(
        "mis_sco_work_order_template",
        "Build MIS SCO template",
        "Build a bounded no-dispatch SCO review work order for one verified MIS certificate.",
        {
            "certificate": O,
            "sco_id": S,
            "target_node_id": S,
            "objective": S,
            "required_outputs": A,
            "depends_on": A,
            "termination": S,
        },
        [
            "certificate",
            "sco_id",
            "target_node_id",
            "objective",
            "required_outputs",
            "depends_on",
            "termination",
        ],
    ),
    mut(
        "constitution_plane_add",
        "Add constitutional plane",
        "User-enact a ranked horizontal, vertical, diagonal or freeform constitutional plane.",
        {"label": S, "orientation": S, "rank": I},
        ["label", "orientation"],
    ),
    mut(
        "constitution_box_add",
        "Add constitutional box",
        "User-enact a ranked and optionally nested constitutional box.",
        {
            "plane_id": S,
            "parent_box_id": S,
            "rank": I,
            "content": S,
            "tags": A,
            "constitutional": B,
        },
        ["content"],
    ),
    mut(
        "constitution_box_update",
        "Update constitutional box",
        "User-update the exact content of an existing constitutional box.",
        {"box_id": S, "content": S},
        ["box_id", "content"],
    ),
    mut(
        "constitution_box_set_active",
        "Activate constitutional box",
        "User-activate or deactivate one constitutional box without deleting its history.",
        {"box_id": S, "active": B},
        ["box_id", "active"],
    ),
    mut(
        "constitution_boxes_connect",
        "Connect constitutional boxes",
        "User-enact a typed, optionally directed relation between constitutional boxes.",
        {"source_box_id": S, "target_box_id": S, "relation": S, "label": S, "directed": B},
        ["source_box_id", "target_box_id", "relation"],
    ),
    mut(
        "programmed_policy_replace",
        "Replace programmed policy",
        "User-replace the complete versioned proactive if/then/else policy.",
        {"state": O},
        ["state"],
    ),
    mut(
        "programmed_policy_rule_add",
        "Add programmed rule",
        "User-add one validated proactive rule to the current policy.",
        {"rule": O},
        ["rule"],
    ),
    mut(
        "programmed_policy_preferences_set",
        "Set proactive preferences",
        "User-enable or disable the proactive program and its startup announcement.",
        {"enabled": B, "announce_on_session_start": B},
        [],
    ),
    ro(
        "proactive_launcher_manifest",
        "Read launcher manifest",
        "Read every registered capability and its declared side-effect class.",
        {},
        [],
    ),
    mut(
        "proactive_launcher_start",
        "Start proactive launcher",
        "Start the governed background dispatcher for this runtime.",
        {},
        [],
    ),
    mut(
        "proactive_launcher_stop",
        "Stop proactive launcher",
        "Stop the governed background dispatcher for this runtime.",
        {"timeout_seconds": N},
        [],
    ),
    mut(
        "proactive_launcher_run_once",
        "Run one launcher event",
        "Claim and dispatch at most one queued event through governed handlers.",
        {},
        [],
    ),
    ro(
        "proactive_launcher_wait",
        "Wait for launcher event",
        "Read the bounded result of one event without creating another event.",
        {"event_id": S, "timeout_seconds": N},
        ["event_id"],
    ),
    mut(
        "risk_override_record",
        "Record risk override",
        "Record warnings and a recovery snapshot for an explicitly user-authorized proposal; this tool does not execute the proposal itself.",
        {"proposal": O},
        ["proposal"],
    ),
    ro(
        "recovery_latest",
        "Read latest recovery revision",
        "Read one exact recovery asset revision with binary content encoded as base64.",
        {"logical_key": S},
        ["logical_key"],
    ),
    ro(
        "recovery_revision",
        "Read recovery revision",
        "Read one numbered recovery revision with binary content encoded as base64.",
        {"logical_key": S, "seq": I},
        ["logical_key", "seq"],
    ),
    mut(
        "recovery_restore_revision",
        "Restore recovery revision",
        "Append a selected historic revision as the new current revision; history is retained.",
        {"logical_key": S, "seq": I},
        ["logical_key", "seq"],
    ),
    mut(
        "recovery_alert_record",
        "Record recovery alert",
        "Persist a warning or overridden-warning receipt for later diagnosis and rescue.",
        {
            "severity": S,
            "code": S,
            "message": S,
            "target": S,
            "proposed_operation": S,
            "overridden": B,
            "recovery_snapshot": S,
            "evidence": O,
        },
        ["severity", "code", "message", "target", "proposed_operation", "overridden"],
    ),
    mut(
        "recovery_export_latest",
        "Export latest recovery asset",
        "Export exact current bytes under an explicitly selected safe root and relative path.",
        {"logical_key": S, "export_root": S, "relative_path": S},
        ["logical_key", "export_root", "relative_path"],
    ),
    ro(
        "persistence_chat_get",
        "Read persistent chat",
        "Read chat identity, capture mode, completeness ceiling and turn count.",
        {"chat_id": S},
        ["chat_id"],
    ),
    mut(
        "persistence_page_mark",
        "Record pagination receipt",
        "Record a hash-bearing page receipt; caller EOF remains unverified until an authenticated connector exists.",
        {"chat_id": S, "next_cursor": {"type": ["string", "null"]}, "source_receipt": O},
        ["chat_id", "next_cursor", "source_receipt"],
    ),
    ro(
        "persistence_chat_verify",
        "Verify persistent chat",
        "Verify the complete local turn hash chain without asserting external transport completeness.",
        {"chat_id": S},
        ["chat_id"],
    ),
    ro(
        "persistence_superchat_get",
        "Read SCO persistence manifest",
        "Read one no-merge superchat membership manifest.",
        {"superchat_id": S},
        ["superchat_id"],
    ),
    mut(
        "kwandata_program_create",
        "Create KwanData program",
        "Create a deterministic user-programmable structuring and tagging program.",
        {"name": S, "program": O},
        ["name", "program"],
    ),
    mut(
        "kwandata_supertag_create",
        "Create KwanData supertag",
        "Create a ranked semantic relation from one supertag to declared child tags.",
        {"name": S, "children": A, "relation": S},
        ["name", "children"],
    ),
    mut(
        "kwandata_watch_add",
        "Add KwanData watch root",
        "Register an authorized finite local root for proactive deterministic ingestion.",
        {"path": S, "recursive": B, "program_id": S},
        ["path"],
    ),
    mut(
        "kwandata_watch_scan",
        "Scan KwanData watch root",
        "Scan one registered root and ingest observed files with exact byte custody.",
        {"watch_id": S},
        ["watch_id"],
    ),
    mut(
        "permission_grant",
        "Grant governed permission",
        "User-enact one scoped, ranked and optionally expiring permission rule.",
        {
            "actor_pattern": S,
            "resource_pattern": S,
            "operation_pattern": S,
            "effect": S,
            "priority": I,
            "scope": S,
            "session_id": S,
            "expires_at": S,
            "rationale": S,
        },
        [
            "actor_pattern",
            "resource_pattern",
            "operation_pattern",
            "effect",
            "priority",
            "rationale",
        ],
    ),
    mut(
        "permission_revoke",
        "Revoke governed permission",
        "User-disable one permission rule while retaining its history and receipt.",
        {"rule_id": S},
        ["rule_id"],
    ),
    mut(
        "scheduler_agenda_create",
        "Create scheduler agenda",
        "Create an independently named agenda with an IANA timezone.",
        {"name": S, "timezone": S},
        ["name", "timezone"],
    ),
    ro(
        "scheduler_get",
        "Read schedule",
        "Read one schedule, its event payload and current enabled state.",
        {"schedule_id": S},
        ["schedule_id"],
    ),
    mut(
        "scheduler_set_enabled",
        "Enable or disable schedule",
        "User-enable or disable one persisted schedule without deleting it.",
        {"schedule_id": S, "enabled": B},
        ["schedule_id", "enabled"],
    ),
    mut(
        "scheduler_run_due",
        "Run due schedules",
        "Publish all currently due occurrences exactly once through the proactive launcher.",
        {},
        [],
    ),
    mut(
        "scheduler_start", "Start scheduler", "Start the governed background schedule loop.", {}, []
    ),
    mut(
        "scheduler_stop",
        "Stop scheduler",
        "Stop the governed background schedule loop.",
        {"timeout_seconds": N},
        [],
    ),
    mut(
        "clipboard_pin",
        "Pin clipboard item",
        "Persist exact bytes for one previously captured clipboard item.",
        {"item_id": S},
        ["item_id"],
    ),
    ro(
        "clipboard_postit_get",
        "Read post-it",
        "Read one persistent post-it, tags, links and revision.",
        {"postit_id": S},
        ["postit_id"],
    ),
    mut(
        "clipboard_postit_link",
        "Link post-it",
        "Connect a post-it to any declared KCH entity by a user-defined relation.",
        {"postit_id": S, "target_type": S, "target_id": S, "relation": S},
        ["postit_id", "target_type", "target_id", "relation"],
    ),
    mut(
        "clipboard_region_capture",
        "Capture screen region",
        "Capture a user-declared rectangle as persistent PNG and optionally copy it to the system clipboard.",
        {
            "bbox": {"type": "array", "items": I, "minItems": 4, "maxItems": 4},
            "copy_to_system_clipboard": B,
        },
        ["bbox"],
    ),
    mut(
        "clipboard_monitor_start",
        "Start clipboard monitor",
        "Start bounded polling of system clipboard text under the current persistence policy.",
        {"interval_seconds": N},
        [],
    ),
    mut(
        "clipboard_poll_once",
        "Poll clipboard once",
        "Read and adjudicate the current system clipboard text once under the persistence policy.",
        {},
        [],
    ),
    mut(
        "clipboard_monitor_stop",
        "Stop clipboard monitor",
        "Stop system clipboard polling without deleting captured history.",
        {},
        [],
    ),
    ro(
        "audio_backends",
        "Inspect audio backends",
        "Inspect local transcription, monitoring and speech backends without recording.",
        {},
        [],
    ),
    mut(
        "audio_monitor_start",
        "Start microphone monitor",
        "Start visible microphone monitoring under an explicit consent basis and third-party notice contract.",
        {
            "mode": S,
            "consent_basis": S,
            "participant_notice": S,
            "culture": S,
            "threshold": N,
            "silence_seconds": N,
        },
        ["consent_basis"],
    ),
    mut(
        "audio_monitor_stop",
        "Stop microphone monitor",
        "Stop microphone monitoring and seal the local monitor session.",
        {},
        [],
    ),
    mut(
        "account_lease_approve",
        "Approve finite account lease",
        "User-approve one pending request for a punctual, daily, weekly, monthly, quarterly or custom finite interval.",
        {"request_id": S, "duration_class": S, "custom_expires_at": S},
        ["request_id", "duration_class"],
    ),
    ro(
        "account_lease_get",
        "Read account lease",
        "Read one finite lease without exposing secrets.",
        {"lease_id": S},
        ["lease_id"],
    ),
    mut(
        "account_auth_launch",
        "Launch account authentication",
        "Launch a terminal-first interactive authentication flow, with browser fallback only when required.",
        {"lease_id": S, "ssh_key": S},
        ["lease_id"],
    ),
    mut(
        "account_use_authorize",
        "Authorize leased account use",
        "Consume one authorized finite lease use and return its bounded receipt.",
        {"lease_id": S},
        ["lease_id"],
    ),
    mut(
        "account_expire_due",
        "Expire due account leases",
        "Remove validated disposable local profiles for leases whose finite interval has ended.",
        {},
        [],
    ),
    mut(
        "diction_obl_add",
        "Add OBL diction entry",
        "User-add canonical diction variants to onboarding learning.",
        {"canonical": S, "variants": A, "scope": S, "pronunciation_note": S},
        ["canonical", "variants"],
    ),
    mut(
        "diction_correction_record",
        "Stage diction correction",
        "Record a transcription correction as PHL-authorized but untrained future-only feedback.",
        {
            "raw_token": S,
            "corrected_term": S,
            "confirmed_by_user": B,
            "resolution_id": S,
            "context": O,
        },
        ["raw_token", "corrected_term", "confirmed_by_user"],
    ),
    mut(
        "checkpoint_structured_create",
        "Create structured checkpoint",
        "Create an exact content-addressed incremental checkpoint with bidirectional traceability.",
        {"label": S},
        ["label"],
    ),
    mut(
        "checkpoint_full_create",
        "Create full checkpoint",
        "Create the warned large ZIP checkpoint only after a prior plan and explicit size confirmation.",
        {"plan_id": S, "confirm_large_checkpoint": B},
        ["plan_id", "confirm_large_checkpoint"],
    ),
    ro(
        "checkpoint_manifest_get",
        "Read checkpoint manifest",
        "Read and verify one structured checkpoint manifest.",
        {"checkpoint_id": S},
        ["checkpoint_id"],
    ),
    ro(
        "checkpoint_diff_current",
        "Diff checkpoint against current",
        "Compute missing, extra and changed files without restoring anything.",
        {"checkpoint_id": S},
        ["checkpoint_id"],
    ),
    mut(
        "checkpoint_restore_new_root",
        "Restore checkpoint to new root",
        "Reconstruct exact bytes only into a new or empty destination and verify every hash.",
        {"checkpoint_id": S, "destination": S},
        ["checkpoint_id", "destination"],
    ),
    ro(
        "checkpoint_trace_file",
        "Trace file across checkpoints",
        "Read the presence and exact hash of one path across structured checkpoints.",
        {"root_name": S, "relative_path": S},
        ["root_name", "relative_path"],
    ),
    mut(
        "construct_start",
        "Start CONSTRUCT session",
        "Copy the stable KCH into a versioned candidate after creating an exact stable backup.",
        {"objective": S},
        ["objective"],
    ),
    ro(
        "construct_session_get",
        "Read CONSTRUCT session",
        "Read candidate state, changes, validation and stable-backup reference.",
        {"session_id": S},
        ["session_id"],
    ),
    mut(
        "construct_file_write",
        "Write CONSTRUCT candidate file",
        "Write only inside a versioned candidate while preserving any preimage.",
        {"session_id": S, "relative_path": S, "content": S},
        ["session_id", "relative_path", "content"],
    ),
    mut(
        "construct_validate",
        "Validate CONSTRUCT candidate",
        "Compile and test a candidate without modifying active runtime bytes.",
        {"session_id": S, "timeout_seconds": I},
        ["session_id"],
    ),
    mut(
        "construct_promote_next_start",
        "Promote CONSTRUCT candidate",
        "Promote only a validated candidate through the next-start pointer.",
        {"session_id": S},
        ["session_id"],
    ),
    mut(
        "construct_rollback_pointer",
        "Rollback CONSTRUCT pointer",
        "Restore the previous stable pointer for the next start; current runtime bytes remain untouched.",
        {},
        [],
    ),
    mut(
        "universal_asset_ingest",
        "Ingest universal asset",
        "Custody exact original bytes and create a readable TXT projection when deterministically supported.",
        {"source": S},
        ["source"],
    ),
    mut(
        "universal_asset_restore",
        "Restore universal asset",
        "Restore exact original bytes of one universal asset to a safe relative runtime target.",
        {"asset_id": S, "relative_target": S},
        ["asset_id", "relative_target"],
    ),
    mut(
        "universal_asset_transform",
        "Transform universal asset",
        "Create a declared derivative while retaining exact original-byte recovery.",
        {"asset_id": S, "target_format": S},
        ["asset_id", "target_format"],
    ),
]


def _recovery_value(value: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    raw = result.pop("content")
    if not isinstance(raw, (bytes, bytearray)):
        raw = str(raw).encode("utf-8")
    result["content_base64"] = base64.b64encode(bytes(raw)).decode("ascii")
    result["content_encoding"] = "base64"
    return result


def bind_operational_handlers(runtime: Any) -> dict[str, Callable[[dict[str, Any]], Any]]:
    def guarded(name: str, args: dict[str, Any], operation: Callable[[], Any]) -> Any:
        return runtime.direct_user_action(name, args, operation)

    return {
        "direct_consent_status": lambda _a: runtime.direct_consent_status(),
        "mis_certificate_export": lambda a: guarded(
            "mis_certificate_export",
            a,
            lambda: runtime.mis.export_certificate(dict(a["certificate"])),
        ),
        "mis_sco_work_order_template": lambda a: runtime.mis.sco_work_order_template(
            certificate=dict(a["certificate"]),
            sco_id=str(a["sco_id"]),
            target_node_id=str(a["target_node_id"]),
            objective=str(a["objective"]),
            required_outputs=list(a["required_outputs"]),
            depends_on=list(a["depends_on"]),
            termination=str(a["termination"]),
        ),
        "constitution_plane_add": lambda a: guarded(
            "constitution_plane_add",
            a,
            lambda: runtime.constitution.add_plane(
                label=str(a["label"]),
                orientation=str(a["orientation"]),
                rank=a.get("rank"),
                actor=Actor.USER,
            ),
        ),
        "constitution_box_add": lambda a: guarded(
            "constitution_box_add",
            a,
            lambda: runtime.constitution.add_box(
                plane_id=str(a.get("plane_id", "main")),
                parent_box_id=a.get("parent_box_id"),
                rank=a.get("rank"),
                content=str(a["content"]),
                tags=list(a.get("tags", [])),
                constitutional=bool(a.get("constitutional", True)),
                actor=Actor.USER,
            ),
        ),
        "constitution_box_update": lambda a: guarded(
            "constitution_box_update",
            a,
            lambda: runtime.constitution.update_box(
                str(a["box_id"]), str(a["content"]), actor=Actor.USER
            ),
        ),
        "constitution_box_set_active": lambda a: guarded(
            "constitution_box_set_active",
            a,
            lambda: runtime.constitution.set_box_active(
                str(a["box_id"]), bool(a["active"]), actor=Actor.USER
            ),
        ),
        "constitution_boxes_connect": lambda a: guarded(
            "constitution_boxes_connect",
            a,
            lambda: runtime.constitution.connect(
                str(a["source_box_id"]),
                str(a["target_box_id"]),
                relation=str(a["relation"]),
                label=str(a.get("label", "")),
                directed=bool(a.get("directed", True)),
                actor=Actor.USER,
            ),
        ),
        "programmed_policy_replace": lambda a: guarded(
            "programmed_policy_replace",
            a,
            lambda: runtime.policy.replace(dict(a["state"]), actor=Actor.USER),
        ),
        "programmed_policy_rule_add": lambda a: guarded(
            "programmed_policy_rule_add",
            a,
            lambda: runtime.policy.add_rule(dict(a["rule"]), actor=Actor.USER),
        ),
        "programmed_policy_preferences_set": lambda a: guarded(
            "programmed_policy_preferences_set",
            a,
            lambda: runtime.policy.set_preferences(
                enabled=a.get("enabled"),
                announce_on_session_start=a.get("announce_on_session_start"),
                actor=Actor.USER,
            ),
        ),
        "proactive_launcher_manifest": lambda _a: runtime.launcher.manifest(),
        "proactive_launcher_start": lambda a: guarded(
            "proactive_launcher_start", a, runtime.launcher.start
        ),
        "proactive_launcher_stop": lambda a: guarded(
            "proactive_launcher_stop",
            a,
            lambda: runtime.launcher.stop(float(a.get("timeout_seconds", 5.0))),
        ),
        "proactive_launcher_run_once": lambda a: guarded(
            "proactive_launcher_run_once", a, runtime.launcher.run_once
        ),
        "proactive_launcher_wait": lambda a: runtime.launcher.wait(
            str(a["event_id"]), min(60.0, float(a.get("timeout_seconds", 10.0)))
        ),
        "risk_override_record": lambda a: guarded(
            "risk_override_record",
            a,
            lambda: runtime.risk.proceed(dict(a["proposal"]), user_authorized=True),
        ),
        "recovery_latest": lambda a: _recovery_value(
            runtime.recovery.latest(str(a["logical_key"]))
        ),
        "recovery_revision": lambda a: _recovery_value(
            runtime.recovery.revision(str(a["logical_key"]), int(a["seq"]))
        ),
        "recovery_restore_revision": lambda a: guarded(
            "recovery_restore_revision",
            a,
            lambda: runtime.recovery.restore(str(a["logical_key"]), int(a["seq"]), actor="USER"),
        ),
        "recovery_alert_record": lambda a: guarded(
            "recovery_alert_record",
            a,
            lambda: runtime.recovery.record_alert(
                severity=str(a["severity"]),
                code=str(a["code"]),
                message=str(a["message"]),
                target=str(a["target"]),
                proposed_operation=str(a["proposed_operation"]),
                overridden=bool(a["overridden"]),
                recovery_snapshot=a.get("recovery_snapshot"),
                evidence=dict(a.get("evidence", {})),
            ),
        ),
        "recovery_export_latest": lambda a: guarded(
            "recovery_export_latest",
            a,
            lambda: runtime.recovery.export_latest(
                str(a["logical_key"]), str(a["export_root"]), str(a["relative_path"])
            ),
        ),
        "persistence_chat_get": lambda a: runtime.persistence.get_chat(str(a["chat_id"])),
        "persistence_page_mark": lambda a: guarded(
            "persistence_page_mark",
            a,
            lambda: runtime.persistence.mark_page(
                str(a["chat_id"]), a.get("next_cursor"), source_receipt=dict(a["source_receipt"])
            ),
        ),
        "persistence_chat_verify": lambda a: runtime.persistence.verify_chat(str(a["chat_id"])),
        "persistence_superchat_get": lambda a: runtime.persistence.get_superchat(
            str(a["superchat_id"])
        ),
        "kwandata_program_create": lambda a: guarded(
            "kwandata_program_create",
            a,
            lambda: runtime.kwandata.create_program(str(a["name"]), dict(a["program"])),
        ),
        "kwandata_supertag_create": lambda a: guarded(
            "kwandata_supertag_create",
            a,
            lambda: runtime.kwandata.create_supertag(
                str(a["name"]), list(a["children"]), relation=str(a.get("relation", "CONTAINS"))
            ),
        ),
        "kwandata_watch_add": lambda a: guarded(
            "kwandata_watch_add",
            a,
            lambda: runtime.kwandata.add_watch_root(
                str(a["path"]),
                recursive=bool(a.get("recursive", True)),
                program_id=a.get("program_id"),
            ),
        ),
        "kwandata_watch_scan": lambda a: guarded(
            "kwandata_watch_scan", a, lambda: runtime.kwandata.scan_watch_root(str(a["watch_id"]))
        ),
        "permission_grant": lambda a: guarded(
            "permission_grant",
            a,
            lambda: runtime.permissions.grant(
                actor_pattern=str(a["actor_pattern"]),
                resource_pattern=str(a["resource_pattern"]),
                operation_pattern=str(a["operation_pattern"]),
                effect=str(a["effect"]),
                priority=int(a["priority"]),
                scope=str(a.get("scope", "GLOBAL")),
                session_id=a.get("session_id"),
                expires_at=a.get("expires_at"),
                rationale=str(a["rationale"]),
                enacting_actor=Actor.USER,
            ),
        ),
        "permission_revoke": lambda a: guarded(
            "permission_revoke",
            a,
            lambda: runtime.permissions.revoke(str(a["rule_id"]), enacting_actor=Actor.USER),
        ),
        "scheduler_agenda_create": lambda a: guarded(
            "scheduler_agenda_create",
            a,
            lambda: runtime.scheduler.create_agenda(str(a["name"]), str(a["timezone"])),
        ),
        "scheduler_get": lambda a: runtime.scheduler.get_schedule(str(a["schedule_id"])),
        "scheduler_set_enabled": lambda a: guarded(
            "scheduler_set_enabled",
            a,
            lambda: runtime.scheduler.set_enabled(
                str(a["schedule_id"]), bool(a["enabled"]), actor="USER"
            ),
        ),
        "scheduler_run_due": lambda a: guarded("scheduler_run_due", a, runtime.scheduler.run_due),
        "scheduler_start": lambda a: guarded("scheduler_start", a, runtime.scheduler.start),
        "scheduler_stop": lambda a: guarded(
            "scheduler_stop",
            a,
            lambda: runtime.scheduler.stop(float(a.get("timeout_seconds", 5.0))),
        ),
        "clipboard_pin": lambda a: guarded(
            "clipboard_pin", a, lambda: runtime.clipboard.pin(str(a["item_id"]))
        ),
        "clipboard_postit_get": lambda a: runtime.clipboard.get_postit(str(a["postit_id"])),
        "clipboard_postit_link": lambda a: guarded(
            "clipboard_postit_link",
            a,
            lambda: runtime.clipboard.link_postit(
                str(a["postit_id"]),
                target_type=str(a["target_type"]),
                target_id=str(a["target_id"]),
                relation=str(a["relation"]),
            ),
        ),
        "clipboard_region_capture": lambda a: guarded(
            "clipboard_region_capture",
            a,
            lambda: runtime.clipboard.capture_region(
                tuple(int(value) for value in a["bbox"]),
                copy_to_system_clipboard=bool(a.get("copy_to_system_clipboard", True)),
            ),
        ),
        "clipboard_monitor_start": lambda a: guarded(
            "clipboard_monitor_start",
            a,
            lambda: runtime.clipboard.start_monitor(float(a.get("interval_seconds", 0.35))),
        ),
        "clipboard_poll_once": lambda a: guarded(
            "clipboard_poll_once", a, runtime.clipboard.poll_once
        ),
        "clipboard_monitor_stop": lambda a: guarded(
            "clipboard_monitor_stop", a, runtime.clipboard.stop_monitor
        ),
        "audio_backends": lambda _a: runtime.audio.backends(),
        "audio_monitor_start": lambda a: guarded(
            "audio_monitor_start",
            a,
            lambda: runtime.audio.start_monitor(
                mode=str(a.get("mode", "BRAINSTORM_USER_ONLY")),
                consent_basis=str(a["consent_basis"]),
                participant_notice=a.get("participant_notice"),
                culture=str(a.get("culture", "es-ES")),
                threshold=float(a.get("threshold", 550.0)),
                silence_seconds=float(a.get("silence_seconds", 1.2)),
            ),
        ),
        "audio_monitor_stop": lambda a: guarded(
            "audio_monitor_stop", a, runtime.audio.stop_monitor
        ),
        "account_lease_approve": lambda a: guarded(
            "account_lease_approve",
            a,
            lambda: runtime.account_broker.approve(
                str(a["request_id"]),
                duration_class=str(a["duration_class"]),
                custom_expires_at=a.get("custom_expires_at"),
            ),
        ),
        "account_lease_get": lambda a: runtime.account_broker.get_lease(str(a["lease_id"])),
        "account_auth_launch": lambda a: guarded(
            "account_auth_launch",
            a,
            lambda: runtime.account_broker.launch_auth(
                str(a["lease_id"]), ssh_key=a.get("ssh_key")
            ),
        ),
        "account_use_authorize": lambda a: guarded(
            "account_use_authorize",
            a,
            lambda: runtime.account_broker.authorize_use(str(a["lease_id"])),
        ),
        "account_expire_due": lambda a: guarded(
            "account_expire_due", a, runtime.account_broker.expire_due
        ),
        "diction_obl_add": lambda a: guarded(
            "diction_obl_add",
            a,
            lambda: runtime.diction.obl_add(
                str(a["canonical"]),
                list(a["variants"]),
                scope=str(a.get("scope", "USER")),
                pronunciation_note=str(a.get("pronunciation_note", "")),
            ),
        ),
        "diction_correction_record": lambda a: guarded(
            "diction_correction_record",
            a,
            lambda: runtime.diction.record_correction(
                raw_token=str(a["raw_token"]),
                corrected_term=str(a["corrected_term"]),
                confirmed_by_user=bool(a["confirmed_by_user"]),
                resolution_id=a.get("resolution_id"),
                context=dict(a.get("context", {})),
            ),
        ),
        "checkpoint_structured_create": lambda a: guarded(
            "checkpoint_structured_create",
            a,
            lambda: runtime.checkpoints.create_structured(str(a["label"]), actor=Actor.USER),
        ),
        "checkpoint_full_create": lambda a: guarded(
            "checkpoint_full_create",
            a,
            lambda: runtime.checkpoints.create_full(
                str(a["plan_id"]),
                confirm_large_checkpoint=bool(a["confirm_large_checkpoint"]),
                actor=Actor.USER,
            ),
        ),
        "checkpoint_manifest_get": lambda a: runtime.checkpoints.get_manifest(
            str(a["checkpoint_id"])
        ),
        "checkpoint_diff_current": lambda a: runtime.checkpoints.diff_current(
            str(a["checkpoint_id"])
        ),
        "checkpoint_restore_new_root": lambda a: guarded(
            "checkpoint_restore_new_root",
            a,
            lambda: runtime.checkpoints.restore_to_new_root(
                str(a["checkpoint_id"]), str(a["destination"]), actor=Actor.USER
            ),
        ),
        "checkpoint_trace_file": lambda a: runtime.checkpoints.trace_file(
            str(a["root_name"]), str(a["relative_path"])
        ),
        "construct_start": lambda a: guarded(
            "construct_start",
            a,
            lambda: runtime.construct.start(str(a["objective"]), actor=Actor.USER),
        ),
        "construct_session_get": lambda a: runtime.construct.state(str(a["session_id"])),
        "construct_file_write": lambda a: guarded(
            "construct_file_write",
            a,
            lambda: runtime.construct.write_file(
                str(a["session_id"]), str(a["relative_path"]), str(a["content"]), actor=Actor.USER
            ),
        ),
        "construct_validate": lambda a: guarded(
            "construct_validate",
            a,
            lambda: runtime.construct.validate(
                str(a["session_id"]),
                actor=Actor.USER,
                timeout_seconds=int(a.get("timeout_seconds", 600)),
            ),
        ),
        "construct_promote_next_start": lambda a: guarded(
            "construct_promote_next_start",
            a,
            lambda: runtime.construct.promote_for_next_start(
                str(a["session_id"]), actor=Actor.USER
            ),
        ),
        "construct_rollback_pointer": lambda a: guarded(
            "construct_rollback_pointer",
            a,
            lambda: runtime.construct.rollback_pointer(actor=Actor.USER),
        ),
        "universal_asset_ingest": lambda a: guarded(
            "universal_asset_ingest",
            a,
            lambda: runtime.plan_build.assets.ingest(str(a["source"]), actor="USER"),
        ),
        "universal_asset_restore": lambda a: guarded(
            "universal_asset_restore",
            a,
            lambda: runtime.plan_build.assets.restore_original(
                str(a["asset_id"]), str(a["relative_target"])
            ),
        ),
        "universal_asset_transform": lambda a: guarded(
            "universal_asset_transform",
            a,
            lambda: runtime.plan_build.assets.transform(
                str(a["asset_id"]), str(a["target_format"])
            ),
        ),
    }
