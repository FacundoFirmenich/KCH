from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from .account_broker import AccountPermissionBroker
from .audio_hub import AudioHub
from .checkpoints import CheckpointManager
from .clipboard_hub import ClipboardHub
from .commitment_monitor import CommitmentMonitor
from .constitutional import ConstitutionalWorkspace
from .construct_mode import ConstructMode
from .continuity_guard import (
    AikidoLearningForge,
    ContinuityAndBurdenGovernor,
    ContinuousPeriodLedgerCompiler,
    RemoteTransportPreflight,
    SourceFitnessGate,
    TemporalScaleContractCompiler,
)
from .diction_learning import DictionLearning
from .federated_runtime import KwanPromptsRuntime, PHLRuntime, RigorRuntime, SCORuntime
from .full_read_contract import FullReadService
from .installation import ConsentDecision, ConsentPolicy
from .kwandata import KwanData
from .launcher import Capability, ProactiveLauncher
from .mis_service import MISService
from .operational_surface import OPERATIONAL_TOOLS, bind_operational_handlers
from .permissions import PermissionGovernor
from .persistence import PersistenceHub
from .proactive import ProgrammedPolicy
from .recovery import RecoveryVault
from .response_authority import ResponseAuthorityGovernor
from .response_modes import ResponseModeManager
from .safeguards import RiskAdvisor
from .scheduler import KCHScheduler
from .surface_contract import ADVANCED_RUNTIME_REFERENCES, audit_strategic_surface
from .universal_text import PlanBuildEngine
from .workbench_suite import WorkbenchSuite
from .workbench_surface import WORKBENCH_TOOLS, bind_workbench_handlers


def schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


S = {"type": "string"}
B = {"type": "boolean"}
I = {"type": "integer", "minimum": 1}  # noqa: E741 - compact JSON-schema atom
O = {"type": "object"}  # noqa: E741 - compact JSON-schema atom
A = {"type": "array"}


def tool(
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
        "inputSchema": schema(properties, required),
        "readOnly": read_only,
    }


ADVANCED_TOOLS = [
    tool(
        "kch_next_status",
        "Inspect integrated KCH-next layers",
        "Aggregate constitutional, launcher, recovery, data, permission, persistence, account, clipboard, audio, scheduler and MIS state.",
        {},
        [],
        read_only=True,
    ),
    tool("continuity_status", "Inspect continuity and burden governance", "Verify mission continuity, recurrent-failure controls and the append-only harm ledger.", {}, [], read_only=True),
    tool("continuity_reading_adjudicate", "Adjudicate lossless source reading", "Forbid a complete-reading claim unless pagination reached EOF and every material truncation was recovered.", {"receipt": O}, ["receipt"], read_only=False),
    tool("full_read_file", "Read one complete source file", "Read every byte twice, transport the complete UTF-8 text when it fits the declared bound, and return a verifiable receipt. External paths require explicit permission; fragments never satisfy the claim.", {"path": S, "max_return_bytes": {"type": "integer", "minimum": 1, "maximum": 5242880}, "expected_sha256": S}, ["path"], read_only=True),
    tool("full_read_batch", "Read an ordered complete source batch", "Generate one machine-owned ordered inventory with two-read receipts and optional exact source-span evidence. No agent-authored hash transcription is required.", {"items": A, "requested_order": S, "max_return_bytes_per_file": {"type": "integer", "minimum": 1, "maximum": 5242880}, "max_batch_return_bytes": {"type": "integer", "minimum": 1, "maximum": 5242880}}, ["items"], read_only=True),
    tool("full_read_verify_batch", "Verify a full-read batch against source", "Re-read every source file and reject a canonically self-consistent batch whose hashes, content, order, ordinals or exact-span evidence were corrupted after tool execution.", {"batch": O}, ["batch"], read_only=True),
    tool("continuity_mission_set", "Enact governing mission", "Freeze the user-authorized governing objective and its authority source.", {"objective": S, "authority_source": S}, ["objective", "authority_source"], read_only=False),
    tool("continuity_harm_record", "Record exact user burden evidence", "Append exact user-reported harm without inferring a medical diagnosis or rewriting historical evidence.", {"record": O}, ["record"], read_only=False),
    tool("continuity_action_preflight", "Gate an action against recurrent harm", "Fail closed on stale, non-material, mission-drifting, uncustodied, incompletely-read or recurrently unsafe work.", {"action": O}, ["action"], read_only=False),
    tool("continuity_integrity_verify", "Verify continuity ledger", "Verify the complete hash chain of continuity, burden and Aikido events.", {}, [], read_only=True),
    tool("continuity_protocol_register", "Register verified protocol", "Register a prehashed, explicitly verified historical protocol for mandatory reuse.", {"protocol": O}, ["protocol"], read_only=False),
    tool("continuity_protocol_resolve", "Resolve verified protocols", "Find matching verified protocols before fragments or replacement designs are allowed.", {"tags": A}, ["tags"], read_only=True),
    tool("aikido_transform", "Convert adverse evidence into KCH capability", "Synthesize a positive capability, dated protocol, skill and operator candidate, OBL/PHL envelope and regression contract from one prehashed incident; never auto-promotes it.", {"incident": O}, ["incident"], read_only=False),
    tool("aikido_catalog", "Inspect Aikido capability packages", "List prehashed adverse-to-capability transformations and their non-promoted status.", {}, [], read_only=True),
    tool("temporal_scale_compile", "Compile temporal learning contract", "Keep timestamp resolution, prediction horizon, event count, minimum period and update cadence distinct; enforce minimum complete period to minimum complete period.", {"specification": O}, ["specification"], read_only=True),
    tool("continuous_period_ledger_compile", "Compile consecutive minimum-period ledger", "Require every minimum period in the target interval and type it as OBSERVED, NO_EVENT or NOT_ESTIMABLE; block compressed calendars.", {"specification": O}, ["specification"], read_only=True),
    tool("source_fitness_adjudicate", "Adjudicate source fitness before learning", "Block training when time-window scope, continuous coverage, observed support or jurisdiction support is insufficient.", {"receipt": O}, ["receipt"], read_only=True),
    tool("commitment_monitor_register", "Register external process monitoring", "Persist an external PID, its OS creation identity, logs, artifacts and optional terminal receipt. Artifact presence alone never proves exit success.", {"label": S, "pid": I, "logs": A, "artifacts": A, "poll_seconds": I, "terminal_receipt": S, "expected_exit_codes": A}, ["label", "pid", "logs", "artifacts"], read_only=False),
    tool("commitment_monitor_launch", "Launch a durably supervised process", "Launch a shell-free argv through a dedicated worker that owns stdout, stderr and a canonically sealed terminal receipt. Secret-like environment overrides are rejected.", {"label": S, "argv": A, "cwd": S, "environment": O, "expected_artifacts": A, "expected_exit_codes": A, "poll_seconds": I}, ["label", "argv", "cwd"], read_only=False),
    tool("commitment_monitor_check", "Reconcile monitoring commitment", "Reconcile process identity, logs, artifacts and terminal receipt now; terminal alerting is exactly once and never relaunches the process.", {"commitment_id": S}, ["commitment_id"], read_only=False),
    tool("commitment_monitor_wait_terminal", "Wait boundedly for exact terminal evidence", "Follow the same registered execution until terminal evidence or a bounded wait timeout. Timeout keeps the commitment active and never kills or relaunches it.", {"commitment_id": S, "timeout_seconds": {"type": "number", "exclusiveMinimum": 0}, "poll_seconds": {"type": "number", "exclusiveMinimum": 0}}, ["commitment_id", "timeout_seconds"], read_only=False),
    tool("commitment_monitor_evidence", "Seal current monitoring evidence", "Return a canonically sealed evidence receipt with process identity, terminal status, exit code and hashed log metadata.", {"commitment_id": S}, ["commitment_id"], read_only=False),
    tool("commitment_monitor_status", "Inspect promised monitoring", "Inspect background monitoring, reconciliation errors and all terminal states without promoting them into general execution claims.", {}, [], read_only=True),
    tool("response_authority_register", "Register response authority constraint", "Freeze an explicit mission, terminology, provenance, jurisdiction, experiment-boundary or rejected-frame constraint with its authority source.", {"constraint": O}, ["constraint"], read_only=False),
    tool("response_authority_adjudicate", "Adjudicate candidate response before release", "Fail closed when structured response claims violate active semantic authority, conflate experiments, promote scope, add off-mission classifications or promise unregistered monitoring.", {"candidate": O}, ["candidate"], read_only=False),
    tool("response_authority_status", "Inspect response authority governance", "Inspect active response constraints, hash-chain integrity and the explicit host-interposition evidence boundary.", {}, [], read_only=True),
    tool("remote_transport_preflight", "Verify remote payload before launch", "Block empty, shell-mutated, stale-marker or hash-mismatched remote wrappers before any process starts.", {"receipt": O}, ["receipt"], read_only=True),
    tool(
        "constitution_state",
        "Read constitutional workspace",
        "Read the ranked, nested, connected user constitution. Models cannot mutate it.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "constitution_effective",
        "Compile effective constitution",
        "Compile active constitutional boxes in rank order without changing them.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "constitution_propose",
        "Propose constitutional amendment",
        "Store a model proposal separately; it does not enact or alter constitutional authority.",
        {"proposal": O},
        ["proposal"],
        read_only=False,
    ),
    tool(
        "programmed_policy_status",
        "Read programmed proactive policy",
        "Inspect direct if/then/else rules and startup-announcement preference.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "programmed_policy_evaluate",
        "Evaluate proactive event",
        "Evaluate every applicable programmed rule; does not execute it.",
        {"event": O},
        ["event"],
        read_only=True,
    ),
    tool(
        "proactive_launcher_status",
        "Inspect background launcher",
        "Inspect background state, capability coverage, and blind spots.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "proactive_event_publish",
        "Publish proactive event",
        "Queue an event for background governed dispatch.",
        {"event": O},
        ["event"],
        read_only=False,
    ),
    tool(
        "recovery_checkpoint",
        "Create recovery checkpoint",
        "Persist an optional event payload and snapshot all current master-vault assets.",
        {"label": S, "payload": O},
        ["label"],
        read_only=False,
    ),
    tool(
        "recovery_verify",
        "Verify recovery chains",
        "Verify append-only master recovery chains.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "risk_assess",
        "Advise on risky change",
        "Warn about dependency, history, authority, external-write, and lossy-conversion risk; does not censor.",
        {"proposal": O},
        ["proposal"],
        read_only=True,
    ),
    tool(
        "plan_build_plan",
        "Plan universal data build",
        "Persist a reviewable ingest/transform/restore plan without executing it.",
        {"operations": A},
        ["operations"],
        read_only=False,
    ),
    tool(
        "plan_build_execute",
        "Execute universal data plan",
        "Execute a previously persisted plan inside the KCH runtime with original-byte custody.",
        {"plan_id": S},
        ["plan_id"],
        read_only=False,
    ),
    tool(
        "persistence_status",
        "Inspect chat persistence",
        "Inspect exact KCH/SCO custody coverage and external-host transport limits.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "persistence_chat_create",
        "Create persistent chat",
        "Create a KCH chat record with explicit platform and capture mode.",
        {"platform": S, "title": S, "native_id": S, "source_uri": S, "capture_mode": S},
        ["platform"],
        read_only=False,
    ),
    tool(
        "persistence_turn_append",
        "Append persistent chat turn",
        "Append exact JSON payload to a chat hash chain.",
        {"chat_id": S, "role": S, "payload": {}, "timestamp": S},
        ["chat_id", "role", "payload"],
        read_only=False,
    ),
    tool(
        "persistence_superchat_create",
        "Create SCO manifest",
        "Orchestrate existing chats without merging their context or identity.",
        {"title": S, "members": A},
        ["title", "members"],
        read_only=False,
    ),
    tool(
        "kwandata_status",
        "Inspect KwanData",
        "Inspect source, record, tag, supertag, program and layer counts.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "kwandata_ingest",
        "Ingest into KwanData",
        "Ingest an authorized local file with exact source custody and deterministic structuring.",
        {"source": S, "program_id": S},
        ["source"],
        read_only=False,
    ),
    tool(
        "kwandata_query",
        "Query KwanData",
        "Query structured records and tags.",
        {"query": S, "limit": I},
        ["query"],
        read_only=True,
    ),
    tool(
        "permission_status",
        "Inspect permission governor",
        "Inspect governed capability domains and receipt counts.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "permission_check",
        "Evaluate permission",
        "Evaluate and record one actor/resource/operation decision.",
        {"actor": S, "resource": S, "operation": S, "session_id": S},
        ["actor", "resource", "operation"],
        read_only=False,
    ),
    tool(
        "scheduler_status",
        "Inspect scheduler",
        "Inspect agendas, active one-shot/interval/cron schedules, and occurrence history.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "scheduler_create",
        "Create finite schedule",
        "Create a persisted schedule that publishes events to the proactive launcher.",
        {
            "name": S,
            "kind": S,
            "expression": S,
            "event": O,
            "agenda_id": S,
            "timezone": S,
            "announce": B,
        },
        ["name", "kind", "expression", "event"],
        read_only=False,
    ),
    tool(
        "clipboard_status",
        "Inspect superclipboard",
        "Inspect clipboard monitor, persistent items, and post-it database.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "clipboard_capture_text",
        "Capture clipboard text",
        "Capture explicit text into the local clipboard history with secret detection.",
        {"text": S, "persist": B},
        ["text"],
        read_only=False,
    ),
    tool(
        "clipboard_search",
        "Search clipboard and post-its",
        "Search non-secret previews and post-it text.",
        {"query": S, "limit": I},
        ["query"],
        read_only=True,
    ),
    tool(
        "clipboard_postit_create",
        "Create persistent post-it",
        "Create a versioned post-it from text or a clipboard item.",
        {"title": S, "body": S, "source_item_id": S, "parent_postit_id": S, "color": S, "tags": A},
        [],
        read_only=False,
    ),
    tool(
        "clipboard_postit_edit",
        "Edit persistent post-it",
        "Autosave a post-it revision.",
        {"postit_id": S, "title": S, "body": S, "color": S},
        ["postit_id"],
        read_only=False,
    ),
    tool(
        "clipboard_explanation_context",
        "Read selected context",
        "Return one user-selected clipboard item for ad hoc explanation.",
        {"item_id": S},
        ["item_id"],
        read_only=True,
    ),
    tool(
        "account_broker_status",
        "Inspect temporal account broker",
        "Inspect providers, finite duration classes and local/remote revocation limits.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "account_permission_request",
        "Request finite account access",
        "Create a terminal-first, finite-duration account permission request; does not approve or authenticate.",
        {"provider": S, "scopes": A, "purpose": S, "account_hint": S},
        ["provider", "scopes", "purpose"],
        read_only=False,
    ),
    tool(
        "audio_status",
        "Inspect voice/audio hub",
        "Inspect transcription, microphone and TTS backends without activating the microphone.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "audio_ingest_transcribe",
        "Ingest and transcribe audio",
        "Custody an authorized audio clip and transcribe with an available local backend.",
        {"source": S, "culture": S, "consent_basis": S},
        ["source", "consent_basis"],
        read_only=False,
    ),
    tool(
        "voice_notify",
        "Speak proactive notice",
        "Preserve a KCH message transcript and synthesize it locally when available.",
        {"text": S, "culture": S},
        ["text"],
        read_only=False,
    ),
    tool(
        "diction_status",
        "Inspect diction learning",
        "Inspect OBL lexicon, resolution and PHL-shadow correction counts.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "diction_resolve",
        "Resolve transcription diction",
        "Preserve raw text and compute an auditable normalized overlay.",
        {"raw_transcription": S, "source_audio_id": S},
        ["raw_transcription"],
        read_only=False,
    ),
    tool(
        "mis_full_status",
        "Inspect full MIS integration",
        "Distinguish real MIS mathematics from the formerly amputated KCH 0.11 surface.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "mis_describe",
        "Describe MIS service",
        "Describe the full bounded MIS v0.3.1 mathematical service.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "mis_exact_decide",
        "Compute exact MIS decision",
        "Compute a rational Bayesian loss decision for declared inputs; creates no execution authority.",
        {"request": O},
        ["request"],
        read_only=True,
    ),
    tool(
        "mis_historical_audit",
        "Replay full MIS historical gate",
        "Recompute the exact 480-record/60-ledger bounded historical audit.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "mis_certificate_verify_full",
        "Verify MIS certificate",
        "Verify the packaged historical certificate or a supplied MIS certificate.",
        {"certificate": O},
        [],
        read_only=True,
    ),
    tool(
        "mis_csi_lowering",
        "Read MIS CSI lowering",
        "Read and verify the bounded four-instruction CSI lowering with its operational limitation.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "kch_mode_status",
        "Inspect PLAN/RUN/CONSTRUCT modes",
        "Inspect the three canonical modes and the successor-only CONSTRUCT pointer.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "checkpoint_status",
        "Inspect checkpoint persistence",
        "Inspect structured and full checkpoint coverage without creating a checkpoint.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "checkpoint_estimate",
        "Estimate checkpoint size",
        "Calculate exact current logical bytes and warn before any full checkpoint.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "checkpoint_full_plan",
        "Plan a full checkpoint",
        "Create a warning-bearing plan; it does not create the large full checkpoint.",
        {"label": S},
        ["label"],
        read_only=False,
    ),
    tool(
        "rgg_status",
        "Inspect Rigor Gradient Governor",
        "Inspect all packaged rigor profiles and the shadow-only authority boundary.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "rgg_resolve_profile",
        "Resolve rigor profile",
        "Resolve purpose, audience and risk into a bounded RGG profile.",
        {"request": O},
        ["request"],
        read_only=True,
    ),
    tool(
        "rgg_adjudicate_action",
        "Adjudicate governed action",
        "Separate action permission from claim ceiling under an explicit RGG profile.",
        {"request": O},
        ["request"],
        read_only=True,
    ),
    tool(
        "rgg_audit_review",
        "Audit three-plane review",
        "Audit fact, claim and action judgments without erasing adverse evidence.",
        {"request": O},
        ["request"],
        read_only=True,
    ),
    tool(
        "rgg_transition_plan",
        "Plan rigor transition",
        "Plan a rigor-regime transition while preserving frozen parents.",
        {"request": O},
        ["request"],
        read_only=True,
    ),
    tool(
        "kwanprompts_status",
        "Inspect KwanPrompts",
        "Inspect the persistent message-governance service.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "kwanprompts_ingest",
        "Ingest governed prompt",
        "Persist a KwanPrompts message record without granting authority.",
        {"record": O},
        ["record"],
        read_only=False,
    ),
    tool(
        "kwanprompts_inspect",
        "Inspect governed prompt",
        "Read one KwanPrompts message and its provenance.",
        {"message_id": S},
        ["message_id"],
        read_only=True,
    ),
    tool(
        "kwanprompts_adjudicate",
        "Adjudicate governed prompt",
        "Run KwanPrompts message-boundary adjudication.",
        {"request": O},
        ["request"],
        read_only=False,
    ),
    tool(
        "kwanprompts_kwandocs_envelope",
        "Build KwanDocs envelope",
        "Build a provenance-preserving thread envelope for KwanDocs.",
        {"thread_id": S},
        ["thread_id"],
        read_only=True,
    ),
    tool(
        "kwanprompts_verify",
        "Verify KwanPrompts ledger",
        "Verify the complete KwanPrompts ledger.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "sco_status",
        "Inspect sovereign SCO",
        "Inspect SCO projections and integrity without merging member context.",
        {"sco_id": S},
        [],
        read_only=True,
    ),
    tool(
        "sco_create",
        "Create sovereign SuperChat",
        "Create a full SCO record under optimistic concurrency.",
        {"record": O, "actor": S, "command_id": S, "expected_head_hash": S},
        ["record", "actor", "command_id", "expected_head_hash"],
        read_only=False,
    ),
    tool(
        "sco_add_node",
        "Add sovereign chat node",
        "Add a native Codex, Cline, Cowork, OpenCode, ChatGPT or custom node without copying its memory.",
        {"record": O, "actor": S, "command_id": S, "expected_head_hash": S},
        ["record", "actor", "command_id", "expected_head_hash"],
        read_only=False,
    ),
    tool(
        "sco_retire_node",
        "Retire SCO node",
        "Retire a node while preserving ledger history.",
        {"sco_id": S, "node_id": S, "actor": S, "command_id": S, "expected_head_hash": S},
        ["sco_id", "node_id", "actor", "command_id", "expected_head_hash"],
        read_only=False,
    ),
    tool(
        "sco_add_edge",
        "Add scoped SCO edge",
        "Connect two independent chats through an explicit disclosure contract.",
        {"record": O, "actor": S, "command_id": S, "expected_head_hash": S},
        ["record", "actor", "command_id", "expected_head_hash"],
        read_only=False,
    ),
    tool(
        "sco_issue_work_order",
        "Issue SCO work order",
        "Issue a bounded subsistemic work order with no implicit authority transfer.",
        {"record": O, "actor": S, "command_id": S, "expected_head_hash": S},
        ["record", "actor", "command_id", "expected_head_hash"],
        read_only=False,
    ),
    tool(
        "sco_ingest_receipt",
        "Ingest SCO receipt",
        "Ingest a bounded node receipt while preserving failures, abstentions and limitations.",
        {"record": O, "actor": S, "command_id": S, "expected_head_hash": S},
        ["record", "actor", "command_id", "expected_head_hash"],
        read_only=False,
    ),
    tool(
        "sco_declare_conflict",
        "Preserve SCO conflict",
        "Register irreducible divergence between node receipts.",
        {"record": O, "actor": S, "command_id": S, "expected_head_hash": S},
        ["record", "actor", "command_id", "expected_head_hash"],
        read_only=False,
    ),
    tool(
        "sco_schedule",
        "Schedule ready SCO work",
        "Compute dependency-ready work orders without dispatching external chats.",
        {"sco_id": S},
        ["sco_id"],
        read_only=True,
    ),
    tool(
        "sco_graph_diagnostics",
        "Diagnose SCO graph",
        "Inspect cycles, reachability and orchestration consistency.",
        {"sco_id": S},
        ["sco_id"],
        read_only=True,
    ),
    tool(
        "sco_export_bundle",
        "Export SCO bundle",
        "Export a context-separated orchestration bundle.",
        {"sco_id": S},
        ["sco_id"],
        read_only=True,
    ),
    tool(
        "sco_dispatch_envelopes",
        "Build SCO dispatch envelopes",
        "Build bounded per-node dispatch envelopes; a host bridge must transmit them.",
        {"sco_id": S},
        ["sco_id"],
        read_only=True,
    ),
    tool(
        "phl_status",
        "Inspect authorized PHL",
        "Inspect the authorized but possibly untrained PHL capability and both linked ledgers.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "phl_decision_register",
        "Register PHL-reviewable decision",
        "Register a conformant decision in both effective and learning ledgers; this does not train PHL.",
        {"record": O},
        ["record"],
        read_only=False,
    ),
    tool(
        "phl_decisions_list",
        "List PHL decisions",
        "List reviewable decisions without starting a PHL session.",
        {"component": S, "reviewed": B},
        [],
        read_only=True,
    ),
    tool(
        "phl_session_start",
        "Start exclusive PHL session",
        "Start linked effective and learning PHL sessions under one of the four explicit consent choices.",
        {
            "trigger": S,
            "consent": {
                "type": "string",
                "enum": ["YES", "NO", "NEVER_THIS_SESSION", "ALWAYS_THIS_SESSION"],
            },
        },
        ["trigger", "consent"],
        read_only=False,
    ),
    tool(
        "phl_score",
        "Record user PHL score",
        "Record an exact 000..100 user-authored score as future-only feedback.",
        {
            "public_session_id": S,
            "decision_id": S,
            "score_display": S,
            "contextual_text": S,
            "correction_text": S,
            "user_authored": B,
            "consent": {
                "type": "string",
                "enum": ["YES", "NO", "NEVER_THIS_SESSION", "ALWAYS_THIS_SESSION"],
            },
        },
        ["public_session_id", "decision_id", "score_display", "user_authored", "consent"],
        read_only=False,
    ),
    tool(
        "phl_packet_compile",
        "Compile PHL training packet",
        "Compile a future-only packet; activation remains prohibited pending replay and user approval.",
        {"public_session_id": S},
        ["public_session_id"],
        read_only=False,
    ),
    tool(
        "phl_session_close",
        "Close exclusive PHL session",
        "Close both linked ledgers and release the ordinary-work mutation lock.",
        {"public_session_id": S},
        ["public_session_id"],
        read_only=False,
    ),
    tool(
        "mis_integrity_verify",
        "Verify MIS federation",
        "Verify the MIS event chain, certificates, prospective ledgers and reviewable-decision projections.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "mis_atoms_list",
        "List MIS semantic atoms",
        "List canonical and user-declared semantic atoms as compositional CSI material.",
        {"kind": S},
        [],
        read_only=True,
    ),
    tool(
        "mis_atom_resolve",
        "Resolve MIS semantic atom",
        "Resolve a language skin to one stable semantic atom.",
        {"skin": S, "language": S},
        ["skin"],
        read_only=True,
    ),
    tool(
        "mis_atom_register",
        "Register MIS semantic atom",
        "Register a user-authored semantic atom without changing frozen MIS bytes.",
        {"atom_id": S, "kind": S, "skins": O, "user_authored": B},
        ["atom_id", "kind", "skins", "user_authored"],
        read_only=False,
    ),
    tool(
        "mis_study_create",
        "Create MIS prospective study",
        "Create an empty future-only exact Bayesian study; no outcome or empirical value is invented.",
        {"study": O},
        ["study"],
        read_only=False,
    ),
    tool(
        "mis_studies_list",
        "List MIS studies",
        "List persistent prospective MIS studies.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "mis_study_projection",
        "Inspect MIS study",
        "Inspect freezes, outcomes, next prior and local claim ceiling.",
        {"study_id": S},
        ["study_id"],
        read_only=True,
    ),
    tool(
        "mis_study_freeze",
        "Freeze prospective MIS decision",
        "Freeze the pre-outcome prior and exact decision certificate.",
        {"study_id": S, "request": O, "frozen_at": S},
        ["study_id", "request"],
        read_only=False,
    ),
    tool(
        "mis_study_observe",
        "Record prospective MIS outcome",
        "Record a source-hashed outcome only after its decision freeze.",
        {"study_id": S, "observed_state": S, "source_unit_hash": S, "observed_at": S},
        ["study_id", "observed_state", "source_unit_hash"],
        read_only=False,
    ),
    tool(
        "mis_study_close",
        "Close MIS study",
        "Close a prospective study only when no outcome is pending.",
        {"study_id": S},
        ["study_id"],
        read_only=False,
    ),
    tool(
        "mis_decision_register_phl",
        "Bridge MIS decision to PHL",
        "Convert a verified exact MIS certificate into a reviewable decision and register it without training.",
        {"certificate": O},
        ["certificate"],
        read_only=False,
    ),
    tool(
        "mis_dynamic_csi_lowering",
        "Lower MIS certificate to CSI",
        "Lower any verified MIS certificate to a compositional CSI program with no authority transfer.",
        {"certificate": O},
        ["certificate"],
        read_only=True,
    ),
    tool(
        "mis_kwandata_archive",
        "Archive MIS certificate in KwanData",
        "Export exact certificate bytes and ingest them into KwanData with provenance.",
        {"certificate": O},
        ["certificate"],
        read_only=False,
    ),
    tool(
        "mis_sco_issue_review",
        "Issue MIS review through SCO",
        "Build and issue a bounded MIS review work order to an independent SCO node.",
        {
            "certificate": O,
            "sco_id": S,
            "target_node_id": S,
            "objective": S,
            "required_outputs": A,
            "depends_on": A,
            "termination": S,
            "actor": S,
            "command_id": S,
            "expected_head_hash": S,
        },
        [
            "certificate",
            "sco_id",
            "target_node_id",
            "objective",
            "required_outputs",
            "depends_on",
            "termination",
            "actor",
            "command_id",
            "expected_head_hash",
        ],
        read_only=False,
    ),
    tool(
        "mis_rgg_adjudicate",
        "Adjudicate MIS claim with RGG",
        "Apply an explicit RGG action request to a verified MIS certificate while retaining both boundaries.",
        {"certificate": O, "rigor_request": O},
        ["certificate", "rigor_request"],
        read_only=True,
    ),
]
ADVANCED_TOOLS.extend(
    [
        tool(
            "response_mode_status",
            "Inspect response modes",
            "Inspect the three canonical chat-response presets, scope precedence, invariants and integrity without affecting outputs.",
            {},
            [],
            read_only=True,
        ),
        tool(
            "response_mode_profiles_list",
            "List response profiles",
            "List canonical and user-defined chat-response profiles.",
            {"include_archived": B},
            [],
            read_only=True,
        ),
        tool(
            "response_mode_resolve",
            "Resolve active response profile",
            "Resolve the effective response profile by message, session, task, SCO, workspace and global precedence.",
            {"context": O},
            [],
            read_only=True,
        ),
        tool(
            "response_mode_contract",
            "Compile host response contract",
            "Compile the exact host instruction for authored chat text; outputs remain outside this policy.",
            {"context": O},
            [],
            read_only=True,
        ),
        tool(
            "response_mode_profile_upsert",
            "Create or update custom response profile",
            "Create or revise a persistent custom response profile derived from a canonical or custom base.",
            {"profile": O},
            ["profile"],
            read_only=False,
        ),
        tool(
            "response_mode_profile_archive",
            "Archive custom response profile",
            "Archive an unbound custom profile; canonical presets cannot be altered or archived.",
            {"profile_id": S},
            ["profile_id"],
            read_only=False,
        ),
        tool(
            "response_mode_scope_set",
            "Bind response profile to scope",
            "Bind a response profile to global, workspace, SCO, task, session or message scope.",
            {"scope_type": S, "scope_key": S, "profile_id": S},
            ["scope_type", "scope_key", "profile_id"],
            read_only=False,
        ),
        tool(
            "response_mode_scope_clear",
            "Clear response profile scope",
            "Clear one exact response-profile binding and restore inheritance from the next broader scope.",
            {"scope_type": S, "scope_key": S},
            ["scope_type", "scope_key"],
            read_only=False,
        ),
        tool(
            "response_execution_register",
            "Save execution register as Markdown",
            "Persist the technical execution record separately as Markdown; it is never offered or substituted for the substantive answer.",
            {"record": O},
            ["record"],
            read_only=False,
        ),
        tool(
            "response_mode_integrity",
            "Verify response-mode custody",
            "Verify canonical presets, foreign keys and the response-policy audit hash chain.",
            {},
            [],
            read_only=True,
        ),
    ]
)
ADVANCED_TOOLS.extend(OPERATIONAL_TOOLS)
ADVANCED_TOOLS.extend(WORKBENCH_TOOLS)


class KCHAdvancedRuntime:
    def __init__(
        self,
        root: str | Path,
        *,
        extra_handlers: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
        extra_tools: list[dict[str, Any]] | None = None,
        stable_root: str | Path | None = None,
    ):
        self.root = Path(root).resolve()
        self._full_host_composition = extra_handlers is not None
        self.root.mkdir(parents=True, exist_ok=True)
        self.recovery = RecoveryVault(self.root / "master_recovery")
        self.constitution = ConstitutionalWorkspace(self.root / "constitution")
        self.continuity = ContinuityAndBurdenGovernor(self.root / "continuity")
        self.aikido = AikidoLearningForge(self.root / "aikido", self.continuity)
        self.commitments = CommitmentMonitor(self.root / "commitments")
        self.response_authority = ResponseAuthorityGovernor(self.root / "response_authority")
        self.policy = ProgrammedPolicy(self.root / "proactive_policy")
        self.risk = RiskAdvisor(self.root / "risk")
        self.plan_build = PlanBuildEngine(self.root / "plan_build")
        self.persistence = PersistenceHub(self.root / "persistence")
        self.kwandata = KwanData(self.root / "kwandata")
        self.permissions = PermissionGovernor(self.root / "permissions")
        self.clipboard = ClipboardHub(self.root / "clipboard")
        self.diction = DictionLearning(self.root / "diction")
        self.response_modes = ResponseModeManager(self.root / "response_modes")
        self.workbench = WorkbenchSuite(
            self.root / "workbench", normalizer=lambda text: self.diction.resolve(text)
        )
        self.mis = MISService(runtime_root=self.root / "mis")
        self.rgg = RigorRuntime()
        self.kwanprompts = KwanPromptsRuntime(self.root / "kwanprompts")
        self.sco = SCORuntime(self.root / "sco")
        self.phl = PHLRuntime(self.root / "phl")
        self._direct_consent: dict[str, ConsentPolicy] = {}
        self.voice_chat_id = self.persistence.create_chat(
            platform="KCH_AUDIO", title="KCH Voice Inbox"
        )["chat_id"]
        self.audio = AudioHub(self.root / "audio", on_transcript=self._on_transcript)
        self.account_broker = AccountPermissionBroker(self.root / "accounts", self.permissions)
        source_root = Path(
            stable_root
            or os.environ.get("KCH_CONSTRUCT_STABLE_ROOT", Path(__file__).resolve().parents[2])
        ).resolve()
        self.full_reader = FullReadService(source_root, self.permissions)
        self.construct = ConstructMode(self.root / "construct", source_root)
        self.checkpoints = CheckpointManager(
            self.root / "checkpoints",
            {"runtime": self.root, "stable": source_root},
        )

        self.handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "kch_next_status": lambda _a: self.status(),
            "continuity_status": lambda _a: self.continuity.status(),
            "continuity_reading_adjudicate": lambda a: self.continuity.adjudicate_reading(dict(a["receipt"])),
            "full_read_file": lambda a: self.full_reader.read(
                str(a["path"]),
                max_return_bytes=int(a.get("max_return_bytes", 1_048_576)),
                expected_sha256=a.get("expected_sha256"),
            ),
            "full_read_batch": lambda a: self.full_reader.read_batch(
                list(a["items"]),
                requested_order=str(a.get("requested_order", "SOURCE_NATIVE_ORDER")),
                max_return_bytes_per_file=int(
                    a.get("max_return_bytes_per_file", 1_048_576)
                ),
                max_batch_return_bytes=int(a.get("max_batch_return_bytes", 5_242_880)),
            ),
            "full_read_verify_batch": lambda a: self.full_reader.verify_batch(
                dict(a["batch"])
            ),
            "continuity_mission_set": lambda a: self.continuity.set_mission(str(a["objective"]), str(a["authority_source"])),
            "continuity_harm_record": lambda a: self.continuity.record_harm(dict(a["record"])),
            "continuity_action_preflight": lambda a: self.continuity.preflight(dict(a["action"])),
            "continuity_integrity_verify": lambda _a: self.continuity.verify(),
            "continuity_protocol_register": lambda a: self.continuity.register_protocol(dict(a["protocol"])),
            "continuity_protocol_resolve": lambda a: self.continuity.resolve_protocols(list(a["tags"])),
            "aikido_transform": lambda a: self.aikido.transform(dict(a["incident"])),
            "aikido_catalog": lambda _a: self.aikido.catalog(),
            "temporal_scale_compile": lambda a: TemporalScaleContractCompiler.compile(dict(a["specification"])),
            "continuous_period_ledger_compile": lambda a: ContinuousPeriodLedgerCompiler.compile(dict(a["specification"])),
            "source_fitness_adjudicate": lambda a: SourceFitnessGate.adjudicate(dict(a["receipt"])),
            "commitment_monitor_register": lambda a: self.commitments.register(label=str(a["label"]), pid=int(a["pid"]), logs=list(a["logs"]), artifacts=list(a["artifacts"]), poll_seconds=int(a.get("poll_seconds", 10)), terminal_receipt=str(a["terminal_receipt"]) if a.get("terminal_receipt") else None, expected_exit_codes=[int(code) for code in a.get("expected_exit_codes", [0])]),
            "commitment_monitor_launch": lambda a: self.commitments.launch(label=str(a["label"]), argv=[str(item) for item in a["argv"]], cwd=str(a["cwd"]), environment={str(key): str(value) for key, value in dict(a.get("environment", {})).items()}, expected_artifacts=[str(path) for path in a.get("expected_artifacts", [])], expected_exit_codes=[int(code) for code in a.get("expected_exit_codes", [0])], poll_seconds=int(a.get("poll_seconds", 2))),
            "commitment_monitor_check": lambda a: self.commitments.check(str(a["commitment_id"])),
            "commitment_monitor_wait_terminal": lambda a: self.commitments.wait_terminal(str(a["commitment_id"]), timeout_seconds=float(a["timeout_seconds"]), poll_seconds=float(a.get("poll_seconds", 0.25))),
            "commitment_monitor_evidence": lambda a: self.commitments.evidence(str(a["commitment_id"])),
            "commitment_monitor_status": lambda _a: self.commitments.status(),
            "response_authority_register": lambda a: self.response_authority.register(dict(a["constraint"])),
            "response_authority_adjudicate": lambda a: self.response_authority.adjudicate(dict(a["candidate"]), active_commitment_ids=self.commitments.active_ids()),
            "response_authority_status": lambda _a: self.response_authority.status(),
            "remote_transport_preflight": lambda a: RemoteTransportPreflight.adjudicate(dict(a["receipt"])),
            "constitution_state": lambda _a: self.constitution.state(),
            "constitution_effective": lambda _a: self.constitution.effective_mandates(),
            "constitution_propose": lambda a: self.constitution.propose(dict(a["proposal"])),
            "programmed_policy_status": lambda _a: self.policy.state(),
            "programmed_policy_evaluate": lambda a: self.policy.evaluate_all(dict(a["event"])),
            "proactive_launcher_status": lambda _a: self.launcher.status(),
            "proactive_event_publish": lambda a: self.launcher.publish(dict(a["event"])),
            "recovery_checkpoint": self._checkpoint,
            "recovery_verify": lambda _a: self.recovery.verify(),
            "risk_assess": lambda a: self.risk.assess(dict(a["proposal"])),
            "plan_build_plan": lambda a: self.plan_build.plan(list(a["operations"])),
            "plan_build_execute": lambda a: self.plan_build.build(str(a["plan_id"])),
            "persistence_status": lambda _a: {"coverage": self.persistence.coverage()},
            "persistence_chat_create": self._chat_create,
            "persistence_turn_append": self._turn_append,
            "persistence_superchat_create": lambda a: self.persistence.create_superchat(
                title=str(a["title"]), members=list(a["members"])
            ),
            "kwandata_status": lambda _a: self.kwandata.status(),
            "kwandata_ingest": self._kwandata_ingest_model,
            "kwandata_query": lambda a: self.kwandata.query(
                str(a["query"]), limit=int(a.get("limit", 50))
            ),
            "permission_status": lambda _a: self.permissions.status(),
            "permission_check": lambda a: self.permissions.decide(
                actor=str(a["actor"]),
                resource=str(a["resource"]),
                operation=str(a["operation"]),
                session_id=a.get("session_id"),
            ),
            "scheduler_status": lambda _a: self.scheduler.status(),
            "scheduler_create": self._scheduler_create_model,
            "clipboard_status": lambda _a: self.clipboard.status(),
            "clipboard_capture_text": lambda a: self.clipboard.capture(
                str(a["text"]),
                kind="TEXT",
                media_type="text/plain; charset=utf-8",
                explicit_persist=bool(a.get("persist", False)),
            ),
            "clipboard_search": lambda a: self.clipboard.search(
                str(a["query"]), limit=int(a.get("limit", 50))
            ),
            "clipboard_postit_create": lambda a: self.clipboard.create_postit(
                title=str(a.get("title", "")),
                body=str(a.get("body", "")),
                source_item_id=a.get("source_item_id"),
                parent_postit_id=a.get("parent_postit_id"),
                color=str(a.get("color", "#FFF4A3")),
                tags=list(a.get("tags", [])),
            ),
            "clipboard_postit_edit": lambda a: self.clipboard.edit_postit(
                str(a["postit_id"]), title=a.get("title"), body=a.get("body"), color=a.get("color")
            ),
            "clipboard_explanation_context": lambda a: self.clipboard.explanation_context(
                str(a["item_id"])
            ),
            "account_broker_status": lambda _a: self.account_broker.status(),
            "account_permission_request": lambda a: self.account_broker.request(
                provider=str(a["provider"]),
                scopes=list(a["scopes"]),
                purpose=str(a["purpose"]),
                account_hint=a.get("account_hint"),
            ),
            "audio_status": lambda _a: self.audio.status(),
            "audio_ingest_transcribe": self._audio_ingest_model,
            "voice_notify": self._voice_notify_model,
            "diction_status": lambda _a: self.diction.status(),
            "diction_resolve": lambda a: self.diction.resolve(
                str(a["raw_transcription"]), source_audio_id=a.get("source_audio_id")
            ),
            "response_mode_status": lambda _a: self.response_modes.status(),
            "response_mode_profiles_list": lambda a: self.response_modes.profiles(
                include_archived=bool(a.get("include_archived", False))
            ),
            "response_mode_resolve": lambda a: self.response_modes.resolve(
                dict(a.get("context", {}))
            ),
            "response_mode_contract": lambda a: self.response_modes.compile_contract(
                dict(a.get("context", {}))
            ),
            "response_mode_profile_upsert": lambda a: self.response_modes.upsert_profile(
                dict(a["profile"])
            ),
            "response_mode_profile_archive": lambda a: self.response_modes.archive_profile(
                str(a["profile_id"])
            ),
            "response_mode_scope_set": lambda a: self.response_modes.set_scope(
                str(a["scope_type"]), str(a["scope_key"]), str(a["profile_id"])
            ),
            "response_mode_scope_clear": lambda a: self.response_modes.clear_scope(
                str(a["scope_type"]), str(a["scope_key"])
            ),
            "response_execution_register": lambda a: self.response_modes.record_execution(
                dict(a["record"])
            ),
            "response_mode_integrity": lambda _a: self.response_modes.verify(),
            "mis_full_status": lambda _a: self.mis.status(),
            "mis_describe": lambda _a: self.mis.describe(),
            "mis_exact_decide": lambda a: self.mis.exact_decide(dict(a["request"])),
            "mis_historical_audit": lambda _a: self.mis.audit_historical(),
            "mis_certificate_verify_full": lambda a: self.mis.verify_certificate(
                a.get("certificate")
            ),
            "mis_csi_lowering": lambda _a: self.mis.csi_lowering(),
            "mis_integrity_verify": lambda _a: self.mis.verify_runtime(),
            "mis_atoms_list": lambda a: self.mis.atoms(a.get("kind")),
            "mis_atom_resolve": lambda a: self.mis.resolve_atom(
                str(a["skin"]), str(a.get("language", "canonical"))
            ),
            "mis_atom_register": lambda a: self.mis.register_atom(
                atom_id=str(a["atom_id"]),
                kind=str(a["kind"]),
                skins=dict(a["skins"]),
                user_authored=bool(a["user_authored"]),
            ),
            "mis_study_create": self._mis_study_create,
            "mis_studies_list": lambda _a: self.mis.study_projection(),
            "mis_study_projection": lambda a: self.mis.study_projection(str(a["study_id"])),
            "mis_study_freeze": lambda a: self.mis.freeze_decision(
                study_id=str(a["study_id"]),
                request=dict(a["request"]),
                frozen_at=a.get("frozen_at"),
            ),
            "mis_study_observe": lambda a: self.mis.observe(
                study_id=str(a["study_id"]),
                observed_state=str(a["observed_state"]),
                source_unit_hash=str(a["source_unit_hash"]),
                observed_at=a.get("observed_at"),
            ),
            "mis_study_close": lambda a: self.mis.close_study(str(a["study_id"])),
            "mis_decision_register_phl": self._mis_decision_register_phl,
            "mis_dynamic_csi_lowering": lambda a: self.mis.csi_lowering(dict(a["certificate"])),
            "mis_kwandata_archive": self._mis_kwandata_archive,
            "mis_sco_issue_review": self._mis_sco_issue_review,
            "mis_rgg_adjudicate": self._mis_rgg_adjudicate,
            "rgg_status": lambda _a: self.rgg.status(),
            "rgg_resolve_profile": lambda a: self.rgg.resolve_profile(dict(a["request"])),
            "rgg_adjudicate_action": lambda a: self.rgg.adjudicate_action(dict(a["request"])),
            "rgg_audit_review": lambda a: self.rgg.audit_review(dict(a["request"])),
            "rgg_transition_plan": lambda a: self.rgg.transition_plan(dict(a["request"])),
            "kwanprompts_status": lambda _a: self.kwanprompts.status(),
            "kwanprompts_ingest": lambda a: self.kwanprompts.ingest(dict(a["record"])),
            "kwanprompts_inspect": lambda a: self.kwanprompts.inspect(str(a["message_id"])),
            "kwanprompts_adjudicate": lambda a: self.kwanprompts.adjudicate(dict(a["request"])),
            "kwanprompts_kwandocs_envelope": lambda a: self.kwanprompts.kwandocs_envelope(
                str(a["thread_id"])
            ),
            "kwanprompts_verify": lambda _a: self.kwanprompts.verify(),
            "sco_status": lambda a: self.sco.status(a.get("sco_id")),
            "sco_create": self.sco.create,
            "sco_add_node": self.sco.add_node,
            "sco_retire_node": self.sco.retire_node,
            "sco_add_edge": self.sco.add_edge,
            "sco_issue_work_order": self.sco.issue_work_order,
            "sco_ingest_receipt": self.sco.ingest_receipt,
            "sco_declare_conflict": self.sco.declare_conflict,
            "sco_schedule": lambda a: self.sco.schedule(str(a["sco_id"])),
            "sco_graph_diagnostics": lambda a: self.sco.graph_diagnostics(str(a["sco_id"])),
            "sco_export_bundle": lambda a: self.sco.export_bundle(str(a["sco_id"])),
            "sco_dispatch_envelopes": lambda a: self.sco.dispatch_envelopes(str(a["sco_id"])),
            "phl_status": lambda _a: self.phl.status(),
            "phl_decision_register": lambda a: self.phl.register_decision(dict(a["record"])),
            "phl_decisions_list": lambda a: self.phl.list_decisions(
                component=a.get("component"), reviewed=a.get("reviewed")
            ),
            "phl_session_start": lambda a: self.phl.start(
                trigger=str(a["trigger"]), consent=str(a["consent"])
            ),
            "phl_score": self._phl_score,
            "phl_packet_compile": lambda a: self.phl.compile_packet(str(a["public_session_id"])),
            "phl_session_close": lambda a: self.phl.close_session(str(a["public_session_id"])),
            "kch_mode_status": lambda _a: self.construct.status(),
            "checkpoint_status": lambda _a: self.checkpoints.status(),
            "checkpoint_estimate": lambda _a: self.checkpoints.estimate(),
            "checkpoint_full_plan": lambda a: self.checkpoints.full_plan(str(a["label"])),
        }
        self.handlers.update(bind_operational_handlers(self))
        self.handlers.update(bind_workbench_handlers(self))
        if extra_handlers:
            overlap = set(self.handlers) & set(extra_handlers)
            if overlap:
                raise ValueError(f"duplicate advanced/host handlers: {sorted(overlap)}")
            self.handlers.update(extra_handlers)
        tool_by_name = {item["name"]: item for item in [*ADVANCED_TOOLS, *(extra_tools or [])]}
        missing_descriptors = set(self.handlers) - set(tool_by_name)
        if missing_descriptors:
            raise ValueError(
                f"tool descriptors missing for handlers: {sorted(missing_descriptors)}"
            )
        self.phl_catalog_receipt = self.phl.register_capabilities(list(tool_by_name.values()))
        raw_handlers = dict(self.handlers)
        self.handlers = {
            name: (
                handler
                if name in self.phl.CONTROL_TOOLS
                else lambda arguments, tool_name=name, raw_handler=handler: self.phl.dispatch(
                    tool_name, arguments, raw_handler
                )
            )
            for name, handler in raw_handlers.items()
        }
        capabilities = [
            Capability(
                name=name,
                purpose=tool_by_name[name]["description"],
                mode="DEFAULT_AUTO"
                if name
                in {
                    "constitution_effective",
                    "continuity_status",
                    "continuity_action_preflight",
                    "continuity_integrity_verify",
                    "response_authority_adjudicate",
                    "response_authority_status",
                    "recovery_checkpoint",
                    "risk_assess",
                    "response_mode_resolve",
                    "response_mode_contract",
                }
                else "USER_PROGRAMMABLE",
                event_types=("capability.requested",),
                mutating=not bool(tool_by_name[name]["readOnly"]),
                external_side_effect=name
                in {"voice_notify", "kwandata_ingest", "audio_ingest_transcribe"},
            )
            for name in self.handlers
        ]
        self.launcher = ProactiveLauncher(
            self.root / "launcher", self.policy, self.handlers, capabilities
        )
        self.commitments.set_alert_callback(self.launcher.publish)
        self.commitments.start()
        self.scheduler = KCHScheduler(self.root / "scheduler", self.launcher.publish)
        self.workbench_schedule = self._ensure_workbench_schedule()
        self.launch_receipt = self.launcher.start()
        self.scheduler.start()
        self.clipboard.start_monitor()
        start_event = self.launcher.publish(
            {"type": "session.start", "authority": "KCH_SYSTEM", "runtime_root": str(self.root)}
        )
        self.session_start_result = self.launcher.wait(start_event["event_id"])

    def _ensure_workbench_schedule(self) -> dict[str, Any]:
        binding = self.workbench._setting("scheduler_binding")
        if isinstance(binding, dict) and binding.get("schedule_id"):
            try:
                return self.scheduler.get_schedule(str(binding["schedule_id"]))
            except KeyError:
                pass
        schedule = self.scheduler.create_schedule(
            name="KCH workbench budget-aware maintenance tick",
            kind="INTERVAL",
            expression="60",
            event={
                "type": "capability.requested",
                "authority": "USER_PROGRAM",
                "capability": "workbench_maintenance_run",
                "arguments": {
                    "trigger": "AUTOMATIC_BUDGET_CADENCE_TICK",
                    "force": False,
                },
            },
            announce=False,
            created_by="KCH_DEFAULT_USER_PROGRAM",
        )
        self.workbench._set_setting(
            "scheduler_binding",
            {
                "schedule_id": schedule["schedule_id"],
                "state": "DEFAULT_ENABLED_USER_CUSTOMIZABLE",
                "tick_seconds": 60,
                "maintenance_interval_budget_derived": True,
            },
        )
        return schedule

    def direct_consent_status(self) -> dict[str, Any]:
        return {
            "schema": "kch.direct-action-consent-status.v0.2.0",
            "scope": "PER_ACTION_PER_RUNTIME_SESSION",
            "choices": [item.value for item in ConsentDecision],
            "policies": {
                name: policy.state() for name, policy in sorted(self._direct_consent.items())
            },
            "general_authority_created": False,
            "host_identity_cryptographically_verified": False,
        }

    def direct_user_action(
        self,
        action_name: str,
        arguments: dict[str, Any],
        operation: Callable[[], Any],
    ) -> dict[str, Any]:
        if "consent" not in arguments:
            raise ValueError("direct user action requires one of the four exact consent choices")
        decision = ConsentDecision(str(arguments["consent"]))
        policy = self._direct_consent.setdefault(action_name, ConsentPolicy())
        authorized = policy.adjudicate(decision)
        authority = {
            "schema": "kch.direct-action-authority-receipt.v0.2.0",
            "action": action_name,
            "choice": decision.value,
            "authorized_this_call": authorized,
            "session_policy": policy.state(),
            "scope": "THIS_ACTION_IN_THIS_RUNTIME_SESSION_ONLY",
            "attestation_boundary": "CALLER_DECLARED_USER_CHOICE_NOT_CRYPTOGRAPHIC_HOST_IDENTITY",
            "created_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        if not authorized:
            return {
                "state": "NOT_EXECUTED_CONSENT_DENIED",
                "authority": authority,
                "side_effect_executed": False,
            }
        result = operation()
        return {
            "state": "EXECUTED_UNDER_SCOPED_USER_CONSENT",
            "authority": authority,
            "result": result,
        }

    def _mis_study_create(self, args: dict[str, Any]) -> dict[str, Any]:
        study = dict(args["study"])
        required = {
            "study_id",
            "title",
            "purpose_id",
            "jurisdiction",
            "states",
            "alpha",
            "policy",
            "claim_ceiling",
        }
        if set(study) != required:
            raise ValueError(
                f"MIS study fields mismatch; missing={sorted(required - set(study))}; "
                f"extras={sorted(set(study) - required)}"
            )
        return self.mis.create_study(
            study_id=str(study["study_id"]),
            title=str(study["title"]),
            purpose_id=str(study["purpose_id"]),
            jurisdiction=str(study["jurisdiction"]),
            states=list(study["states"]),
            alpha=dict(study["alpha"]),
            policy=dict(study["policy"]),
            claim_ceiling=str(study["claim_ceiling"]),
        )

    def _mis_decision_register_phl(self, args: dict[str, Any]) -> dict[str, Any]:
        candidate = self.mis.register_reviewable_decision(dict(args["certificate"]))
        phl_receipt = self.phl.register_decision(dict(candidate["record"]))
        bridge = self.mis.mark_phl_registration(
            str(candidate["record"]["decision_id"]), phl_receipt
        )
        return {
            "schema": "kch.mis-phl-bridge-receipt.v0.2.0",
            "candidate": candidate,
            "phl": phl_receipt,
            "bridge": bridge,
            "phl_authorized": True,
            "training_executed": False,
            "automatic_promotion": False,
        }

    def _mis_kwandata_archive(self, args: dict[str, Any]) -> dict[str, Any]:
        permission = self.permissions.require(
            actor="KCH_SYSTEM",
            resource="runtime://mis/exports",
            operation="READ",
        )
        exported = self.mis.export_certificate(dict(args["certificate"]))
        ingested = self.kwandata.ingest(exported["path"])
        bridge = self.mis.record_bridge(
            "KWANDATA_ARCHIVE",
            f"mis://v0.3.1/certificates/{exported['certificate_sha256']}",
            f"kwandata://sources/{ingested['source_id']}",
            ingested,
        )
        return {
            "schema": "kch.mis-kwandata-bridge-receipt.v0.2.0",
            "permission": permission,
            "export": exported,
            "kwandata": ingested,
            "bridge": bridge,
            "KwanDocs_authority_inherited": False,
        }

    def _mis_sco_issue_review(self, args: dict[str, Any]) -> dict[str, Any]:
        certificate = dict(args["certificate"])
        record = self.mis.sco_work_order_template(
            certificate=certificate,
            sco_id=str(args["sco_id"]),
            target_node_id=str(args["target_node_id"]),
            objective=str(args["objective"]),
            required_outputs=list(args["required_outputs"]),
            depends_on=list(args["depends_on"]),
            termination=str(args["termination"]),
        )
        receipt = self.sco.issue_work_order(
            {
                "record": record,
                "actor": str(args["actor"]),
                "command_id": str(args["command_id"]),
                "expected_head_hash": str(args["expected_head_hash"]),
            }
        )
        digest = str(certificate["certificate_sha256"])
        bridge = self.mis.record_bridge(
            "SCO_REVIEW_WORK_ORDER",
            f"mis://v0.3.1/certificates/{digest}",
            f"sco://{args['sco_id']}/work-orders/{record['order_id']}",
            receipt,
        )
        return {
            "schema": "kch.mis-sco-bridge-receipt.v0.2.0",
            "work_order": record,
            "sco": receipt,
            "bridge": bridge,
            "external_dispatch_performed": False,
            "host_bridge_required": True,
        }

    def _mis_rgg_adjudicate(self, args: dict[str, Any]) -> dict[str, Any]:
        certificate = dict(args["certificate"])
        verification = self.mis.verify_certificate(certificate)
        rigor = self.rgg.adjudicate_action(dict(args["rigor_request"]))
        return {
            "schema": "kch.mis-rgg-adjudication.v0.2.0",
            "certificate_sha256": certificate["certificate_sha256"],
            "certificate_verification": verification,
            "mis_claim_ceiling": certificate["claim_ceiling"],
            "rgg": rigor,
            "effective_claim_requires_both_boundaries": True,
            "execution_authorized": False,
            "authority_created": False,
        }

    def _phl_score(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.phl.score(
            public_session_id=str(args["public_session_id"]),
            decision_id=str(args["decision_id"]),
            score_display=str(args["score_display"]),
            contextual_text=str(args.get("contextual_text", "")),
            correction_text=str(args.get("correction_text", "")),
            user_authored=bool(args["user_authored"]),
            consent=str(args["consent"]),
        )

    def _checkpoint(self, args: dict[str, Any]) -> dict[str, Any]:
        label = str(args.get("label", "checkpoint"))
        payload = args.get("payload")
        custody = None
        if payload is not None:
            custody = self.recovery.save_json(
                f"events/{label}/{uuid.uuid4()}.json",
                payload,
                kind="PROACTIVE_EVENT",
                actor="KCH_SYSTEM",
                operation="AUTOMATIC_CHECKPOINT",
            )
        return {"custody": custody, "snapshot": self.recovery.snapshot(label)}

    def _chat_create(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.persistence.create_chat(
            platform=str(args["platform"]),
            title=str(args.get("title", "")),
            native_id=args.get("native_id"),
            source_uri=args.get("source_uri"),
            capture_mode=str(args.get("capture_mode", "KCH_NATIVE_AUTOMATIC")),
        )

    def _turn_append(self, args: dict[str, Any]) -> dict[str, Any]:
        return self.persistence.append_turn(
            str(args["chat_id"]),
            role=str(args["role"]),
            payload=args["payload"],
            timestamp=args.get("timestamp"),
        )

    def _kwandata_ingest_model(self, args: dict[str, Any]) -> dict[str, Any]:
        source = str(Path(args["source"]).resolve())
        permission = self.permissions.decide(
            actor="MODEL", resource="file://external/" + source, operation="READ"
        )
        if not permission["authorized"]:
            return {"state": "PERMISSION_REQUIRED", "permission": permission}
        return self.kwandata.ingest(source, program_id=args.get("program_id"))

    def _scheduler_create_model(self, args: dict[str, Any]) -> dict[str, Any]:
        permission = self.permissions.decide(
            actor="MODEL", resource="scheduler://runtime", operation="SCHEDULE"
        )
        if not permission["authorized"]:
            return {"state": "PERMISSION_REQUIRED", "permission": permission}
        return self.scheduler.create_schedule(
            name=str(args["name"]),
            kind=str(args["kind"]),
            expression=str(args["expression"]),
            event=dict(args["event"]),
            agenda_id=str(args.get("agenda_id", "AGENDA-DEFAULT")),
            timezone=args.get("timezone"),
            announce=bool(args.get("announce", True)),
            created_by="MODEL_WITH_PERMISSION",
        )

    def _audio_ingest_model(self, args: dict[str, Any]) -> dict[str, Any]:
        source = str(Path(args["source"]).resolve())
        permission = self.permissions.decide(
            actor="MODEL", resource="file://external/" + source, operation="READ"
        )
        if not permission["authorized"]:
            return {"state": "PERMISSION_REQUIRED", "permission": permission}
        return self.audio.ingest_and_transcribe(
            source,
            culture=str(args.get("culture", "es-ES")),
            consent_basis=str(args["consent_basis"]),
        )

    def _voice_notify_model(self, args: dict[str, Any]) -> dict[str, Any]:
        permission = self.permissions.decide(
            actor="PROACTIVE_LAUNCHER", resource="voice://local/alerts", operation="SPEAK"
        )
        if not permission["authorized"]:
            return {"state": "PERMISSION_REQUIRED", "permission": permission}
        return self.audio.speak(str(args["text"]), culture=str(args.get("culture", "es-ES")))

    def _on_transcript(self, transcript: dict[str, Any]) -> None:
        resolution = self.diction.resolve(transcript["text"], source_audio_id=transcript["clip_id"])
        self.persistence.append_turn(
            self.voice_chat_id,
            role="user",
            payload={
                "raw_transcription": transcript["text"],
                "normalized_transcription": resolution["normalized_transcription"],
                "resolution": resolution,
                "audio_clip_id": transcript["clip_id"],
            },
        )
        if hasattr(self, "launcher"):
            self.launcher.publish(
                {
                    "type": "audio.transcribed",
                    "authority": "KCH_SYSTEM",
                    "transcript": transcript,
                    "diction_resolution": resolution,
                }
            )

    def status(self) -> dict[str, Any]:
        components = {
            "constitution": self.constitution.effective_mandates(),
            "continuity": self.continuity.status(),
            "aikido": self.aikido.catalog(),
            "commitments": self.commitments.status(),
            "response_authority": self.response_authority.status(),
            "programmed_policy": self.policy.session_announcement(),
            "launcher": self.launcher.status(),
            "recovery": self.recovery.verify(),
            "persistence": self.persistence.coverage(),
            "kwandata": self.kwandata.status(),
            "permissions": self.permissions.status(),
            "scheduler": self.scheduler.status(),
            "clipboard": self.clipboard.status(),
            "accounts": self.account_broker.status(),
            "audio": self.audio.status(),
            "diction": self.diction.status(),
            "response_modes": self.response_modes.status(),
            "workbench": self.workbench.status(),
            "workbench_schedule": self.workbench_schedule,
            "mis": self.mis.status(),
            "mis_integrity": self.mis.verify_runtime(),
            "rgg": self.rgg.status(),
            "kwanprompts": self.kwanprompts.status(),
            "sco": self.sco.status(),
            "phl": self.phl.status(),
            "direct_consent": self.direct_consent_status(),
            "modes": self.construct.status(),
            "checkpoints": self.checkpoints.status(),
            "strategic_surface": audit_strategic_surface(
                set(self.handlers),
                references=None if self._full_host_composition else ADVANCED_RUNTIME_REFERENCES,
            ),
        }
        return {
            "schema": "kch.integrated-pre2g-runtime-status.v0.1.0",
            "components": components,
            "background_launcher_running": components["launcher"]["running"],
            "capability_blind_spots": components["launcher"]["coverage"]["unbound"],
            "strategic_surface_gate": components["strategic_surface"]["gate"],
            "phl_authorized": True,
            "phl_training_executed": components["phl"]["training_executed"],
            "phl_real_executed": components["phl"]["training_executed"],
            "external_installation_performed": False,
        }

    def close(self) -> None:
        self.commitments.stop()
        self.clipboard.stop_monitor()
        self.scheduler.stop()
        self.audio.stop_monitor()
        self.launcher.stop()
