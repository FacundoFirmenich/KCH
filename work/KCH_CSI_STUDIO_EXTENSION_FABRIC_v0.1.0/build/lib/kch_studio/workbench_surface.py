from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .advanced_runtime import KCHAdvancedRuntime


def schema(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


S = {"type": "string"}
B = {"type": "boolean"}
OBJECT = {"type": "object"}
CONSENT = {
    "type": "string",
    "enum": ["YES", "NO", "NEVER_THIS_SESSION", "ALWAYS_THIS_SESSION"],
}


def tool(
    name: str,
    title: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
    *,
    read_only: bool,
    direct_consent: bool = False,
) -> dict[str, Any]:
    props = dict(properties)
    needs = list(required)
    if direct_consent:
        props["consent"] = CONSENT
        needs.append("consent")
    return {
        "name": name,
        "title": title,
        "description": description,
        "inputSchema": schema(props, needs),
        "readOnly": read_only,
    }


WORKBENCH_TOOLS = [
    tool(
        "workbench_status",
        "Inspect learning and continuity workbench",
        "Inspect automatic learning, protocols, staged skills, archives, graph, weekly budget and integrity.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "workbench_ingest",
        "Ingest exact work evidence",
        "Preserve raw and normalized layers, redact secrets, detect evidence candidates, and run governed maintenance.",
        {
            "source_kind": S,
            "title": S,
            "raw_text": S,
            "source_path": S,
            "source_uri": S,
            "workspace_id": S,
            "session_id": S,
            "provenance": OBJECT,
        },
        ["source_kind", "title"],
        read_only=False,
        direct_consent=True,
    ),
    tool(
        "workbench_lessons_list",
        "List detected learning candidates",
        "List evidence-linked candidates by scope or domain; lexical detection is not promoted to truth.",
        {"scope_key": S, "domain": S},
        [],
        read_only=True,
    ),
    tool(
        "workbench_protocols_list",
        "List dated protocols",
        "List evidence-derived, pre-hashed protocols without installing anything.",
        {"scope_key": S},
        [],
        read_only=True,
    ),
    tool(
        "workbench_skills_list",
        "List staged skills",
        "List generated skill candidates and their unevaluated, uninstalled and inactive lifecycle state.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "workbench_maintenance_run",
        "Run automatic workbench maintenance",
        "Apply the configured evidence and weekly-budget cadence; may stage local protocols, skills, checkpoints requests and handoff packets.",
        {"trigger": S, "force": B, "scope_key": S},
        ["trigger"],
        read_only=False,
    ),
    tool(
        "workbench_archive_group_create",
        "Create nested archive group",
        "Create one ranked group or subgroup without deleting or merging its members.",
        {"title": S, "group_kind": S, "parent_group_id": S, "rank": {"type": "integer"}},
        ["title", "group_kind"],
        read_only=False,
        direct_consent=True,
    ),
    tool(
        "workbench_archive_group_set_archived",
        "Archive or restore group",
        "Change only the archive visibility state; no member or artifact is deleted.",
        {"group_id": S, "archived": B},
        ["group_id", "archived"],
        read_only=False,
        direct_consent=True,
    ),
    tool(
        "workbench_archive_attach",
        "Attach item to archive group",
        "Attach a source, protocol, skill, handoff or external reference to a ranked group.",
        {"group_id": S, "item_type": S, "item_id": S, "relation": S},
        ["group_id", "item_type", "item_id"],
        read_only=False,
        direct_consent=True,
    ),
    tool(
        "workbench_archive_tree",
        "Inspect nested archive tree",
        "Return all groups and ranked members with no deletion or merge.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "workbench_graph_connect",
        "Connect work graph nodes",
        "Add an explicit typed, multidimensional relationship without conflating node authority.",
        {
            "source_type": S,
            "source_id": S,
            "target_type": S,
            "target_id": S,
            "relation": S,
            "dimensions": OBJECT,
        },
        ["source_type", "source_id", "target_type", "target_id", "relation"],
        read_only=False,
        direct_consent=True,
    ),
    tool(
        "workbench_graph",
        "Inspect multidimensional work graph",
        "Return clickable nodes and provenance, archive, workspace, session, domain and artifact edges.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "workbench_graph_resolve_node",
        "Resolve graph node",
        "Resolve one clicked node to its exact local record or declared dimension.",
        {"node_id": S},
        ["node_id"],
        read_only=True,
    ),
    tool(
        "workbench_budget_account_configure",
        "Configure weekly account budget",
        "Declare a token, currency or percentage budget and its telemetry source without inferring limits or prices.",
        {
            "account_id": S,
            "provider": S,
            "unit": S,
            "weekly_limit": {},
            "currency": S,
            "week_anchor": S,
            "telemetry_source": S,
        },
        ["account_id", "provider", "unit", "week_anchor", "telemetry_source"],
        read_only=False,
        direct_consent=True,
    ),
    tool(
        "workbench_budget_policy_set",
        "Replace budget cadence policy",
        "Replace the complete user-controlled cadence policy after exact schema validation.",
        {"policy": OBJECT},
        ["policy"],
        read_only=False,
        direct_consent=True,
    ),
    tool(
        "workbench_budget_sample_record",
        "Record verified budget sample",
        "Record explicit use or availability with a source receipt; never infer account prices.",
        {
            "account_id": S,
            "used_value": {},
            "available_percent": {},
            "source_receipt": OBJECT,
            "observed_at": S,
        },
        ["account_id", "source_receipt"],
        read_only=False,
        direct_consent=True,
    ),
    tool(
        "workbench_budget_status",
        "Inspect weekly budget and cadence",
        "Return exact source-derived availability or NOT_ESTIMABLE when live evidence is absent.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "workbench_handoffs_list",
        "List prepared handoff packets",
        "List local continuity packets; task creation and predecessor archival remain host-connector actions.",
        {},
        [],
        read_only=True,
    ),
    tool(
        "workbench_kwandata_envelope",
        "Prepare KwanData bridge envelope",
        "Describe a structured-data bridge without executing ingestion or transferring authority.",
        {"item_type": S, "item_id": S},
        ["item_type", "item_id"],
        read_only=True,
    ),
    tool(
        "workbench_kwandocs_envelope",
        "Prepare KwanDocs bridge envelope",
        "Describe a canonical-evidence bridge without executing ingestion or transferring authority.",
        {"item_type": S, "item_id": S},
        ["item_type", "item_id"],
        read_only=True,
    ),
    tool(
        "workbench_integrity_verify",
        "Verify workbench custody",
        "Verify raw and normalized bytes, protocols, staged skill manifests and the event hash chain.",
        {},
        [],
        read_only=True,
    ),
]


def _direct(
    runtime: KCHAdvancedRuntime,
    action: str,
    arguments: dict[str, Any],
    operation: Callable[[dict[str, Any]], Any],
) -> dict[str, Any]:
    payload = {key: value for key, value in arguments.items() if key != "consent"}
    return runtime.direct_user_action(action, arguments, lambda: operation(payload))


def bind_workbench_handlers(
    runtime: KCHAdvancedRuntime,
) -> dict[str, Callable[[dict[str, Any]], Any]]:
    workbench = runtime.workbench
    return {
        "workbench_status": lambda _a: workbench.status(),
        "workbench_ingest": lambda a: _direct(
            runtime,
            "workbench_ingest",
            a,
            lambda p: workbench.ingest(
                source_kind=str(p["source_kind"]),
                title=str(p["title"]),
                raw_text=p.get("raw_text"),
                source_path=p.get("source_path"),
                source_uri=p.get("source_uri"),
                workspace_id=p.get("workspace_id"),
                session_id=p.get("session_id"),
                provenance=dict(p.get("provenance", {})),
            ),
        ),
        "workbench_lessons_list": lambda a: workbench.lessons(
            scope_key=a.get("scope_key"), domain=a.get("domain")
        ),
        "workbench_protocols_list": lambda a: workbench.protocols(a.get("scope_key")),
        "workbench_skills_list": lambda _a: workbench.skills(),
        "workbench_maintenance_run": lambda a: workbench.run_maintenance(
            trigger=str(a["trigger"]),
            force=bool(a.get("force", False)),
            scope_key=a.get("scope_key"),
        ),
        "workbench_archive_group_create": lambda a: _direct(
            runtime,
            "workbench_archive_group_create",
            a,
            lambda p: workbench.create_group(
                title=str(p["title"]),
                group_kind=str(p["group_kind"]),
                parent_group_id=str(p.get("parent_group_id", "GROUP-ROOT")),
                rank=p.get("rank"),
            ),
        ),
        "workbench_archive_group_set_archived": lambda a: _direct(
            runtime,
            "workbench_archive_group_set_archived",
            a,
            lambda p: workbench.set_group_archived(str(p["group_id"]), bool(p["archived"])),
        ),
        "workbench_archive_attach": lambda a: _direct(
            runtime,
            "workbench_archive_attach",
            a,
            lambda p: workbench.attach(
                group_id=str(p["group_id"]),
                item_type=str(p["item_type"]),
                item_id=str(p["item_id"]),
                relation=str(p.get("relation", "CONTAINS")),
            ),
        ),
        "workbench_archive_tree": lambda _a: workbench.archive_tree(),
        "workbench_graph_connect": lambda a: _direct(
            runtime,
            "workbench_graph_connect",
            a,
            lambda p: workbench.connect_nodes(
                source_type=str(p["source_type"]),
                source_id=str(p["source_id"]),
                target_type=str(p["target_type"]),
                target_id=str(p["target_id"]),
                relation=str(p["relation"]),
                dimensions=dict(p.get("dimensions", {})),
            ),
        ),
        "workbench_graph": lambda _a: workbench.graph(),
        "workbench_graph_resolve_node": lambda a: workbench.resolve_node(str(a["node_id"])),
        "workbench_budget_account_configure": lambda a: _direct(
            runtime,
            "workbench_budget_account_configure",
            a,
            lambda p: workbench.configure_budget_account(
                account_id=str(p["account_id"]),
                provider=str(p["provider"]),
                unit=str(p["unit"]),
                weekly_limit=p.get("weekly_limit"),
                currency=p.get("currency"),
                week_anchor=str(p["week_anchor"]),
                telemetry_source=str(p["telemetry_source"]),
            ),
        ),
        "workbench_budget_policy_set": lambda a: _direct(
            runtime,
            "workbench_budget_policy_set",
            a,
            lambda p: workbench.set_budget_policy(dict(p["policy"])),
        ),
        "workbench_budget_sample_record": lambda a: _direct(
            runtime,
            "workbench_budget_sample_record",
            a,
            lambda p: workbench.record_budget_sample(
                account_id=str(p["account_id"]),
                used_value=p.get("used_value"),
                available_percent=p.get("available_percent"),
                source_receipt=dict(p["source_receipt"]),
                observed_at=p.get("observed_at"),
            ),
        ),
        "workbench_budget_status": lambda _a: workbench.budget_status(),
        "workbench_handoffs_list": lambda _a: workbench.handoffs(),
        "workbench_kwandata_envelope": lambda a: workbench.kwandata_envelope(
            str(a["item_type"]), str(a["item_id"])
        ),
        "workbench_kwandocs_envelope": lambda a: workbench.kwandocs_envelope(
            str(a["item_type"]), str(a["item_id"])
        ),
        "workbench_integrity_verify": lambda _a: workbench.verify(),
    }
