from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable

from .advanced_runtime import ADVANCED_TOOLS, KCHAdvancedRuntime
from .contracts import ArtifactSpec
from .extension import ExtensionFabric, RecommendationEngine, RuntimeInventory
from .installation import ConsentDecision, InstallPlan, IsolatedInstaller
from .studio import Studio

SERVER_INFO = {"name": "kch-csi-studio", "version": "0.3.2"}
PROTOCOL_VERSION = "2025-06-18"


def obj(properties: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


STRING = {"type": "string"}
INTEGER = {"type": "integer", "minimum": 1, "maximum": 100}


BASE_TOOLS = [
    {
        "name": "kch_preflight",
        "title": "Verify canonical KCH startup",
        "description": "Return one canonical gate over compiled governance, full strategic surface, launcher coverage, and PHL state. Use this instead of probing internal runtime classes.",
        "inputSchema": obj({}, []),
        "readOnly": True,
    },
    {
        "name": "studio_status",
        "title": "Inspect CSI Studio",
        "description": "Inspect Studio, governance, providers, and sessions without changing state.",
        "inputSchema": obj({}, []),
        "readOnly": True,
    },
    {
        "name": "studio_create_session",
        "title": "Create CSI build session",
        "description": "Validate and persist a governed artifact specification.",
        "inputSchema": obj({"spec": {"type": "object"}}, ["spec"]),
        "readOnly": False,
    },
    {
        "name": "studio_generate",
        "title": "Generate staged artifact",
        "description": "Generate only inside KCH staging; does not install or enable.",
        "inputSchema": obj({"session_id": STRING}, ["session_id"]),
        "readOnly": False,
    },
    {
        "name": "studio_validate",
        "title": "Validate staged artifact",
        "description": "Run provider, custody, and ledger validation.",
        "inputSchema": obj({"session_id": STRING}, ["session_id"]),
        "readOnly": False,
    },
    {
        "name": "studio_seal",
        "title": "Seal candidate",
        "description": "Seal a validated candidate without installation authority.",
        "inputSchema": obj({"session_id": STRING}, ["session_id"]),
        "readOnly": False,
    },
    {
        "name": "studio_build_and_seal",
        "title": "Build and seal CSI artifact",
        "description": "Run the complete create, generate, validate and seal pipeline; no installation or enablement authority is created.",
        "inputSchema": obj({"spec": {"type": "object"}}, ["spec"]),
        "readOnly": False,
    },
    {
        "name": "extension_inventory",
        "title": "Inventory local runtimes",
        "description": "Read runtime and host availability without reading secrets.",
        "inputSchema": obj({}, []),
        "readOnly": True,
    },
    {
        "name": "extension_search",
        "title": "Search extension source",
        "description": "Search a declared provider; search does not download or install.",
        "inputSchema": obj(
            {"provider": STRING, "query": STRING, "limit": INTEGER}, ["provider", "query"]
        ),
        "readOnly": True,
    },
    {
        "name": "extension_recommend",
        "title": "Adjudicate extension candidates",
        "description": "Evaluate independent recommendation lanes without a global winner score.",
        "inputSchema": obj(
            {
                "records": {"type": "array", "items": {"type": "object"}},
                "objective": STRING,
                "available_runtimes": {"type": "array", "items": STRING},
            },
            ["records", "objective", "available_runtimes"],
        ),
        "readOnly": True,
    },
    {
        "name": "extension_resolve",
        "title": "Resolve extension candidate",
        "description": "Resolve one exact provider identifier to current metadata; this does not download or install it.",
        "inputSchema": obj({"provider": STRING, "identifier": STRING}, ["provider", "identifier"]),
        "readOnly": True,
    },
    {
        "name": "isolated_install_plan",
        "title": "Plan isolated install",
        "description": "Create a reviewable install and rollback plan; does not execute it.",
        "inputSchema": obj(
            {"source": STRING, "artifact_kind": STRING, "target_name": STRING},
            ["source", "artifact_kind", "target_name"],
        ),
        "readOnly": True,
    },
    {
        "name": "isolated_install_execute",
        "title": "Execute isolated install",
        "description": "Execute only within the disposable KCH sandbox and only with one of the four explicit consent choices.",
        "inputSchema": obj(
            {
                "plan": {"type": "object"},
                "consent": {"type": "string", "enum": [item.value for item in ConsentDecision]},
            },
            ["plan", "consent"],
        ),
        "readOnly": False,
    },
    {
        "name": "isolated_install_rollback",
        "title": "Rollback isolated install",
        "description": "Remove the exact disposable target described by a receipt.",
        "inputSchema": obj({"receipt": {"type": "object"}}, ["receipt"]),
        "readOnly": False,
    },
    {
        "name": "isolated_install_verify",
        "title": "Verify isolated install",
        "description": "Verify the isolated target against its receipt without changing it.",
        "inputSchema": obj({"receipt": {"type": "object"}}, ["receipt"]),
        "readOnly": True,
    },
]
TOOLS = [*BASE_TOOLS, *ADVANCED_TOOLS]


class StudioMCP:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.studio: Studio | None = None
        self.fabric: ExtensionFabric | None = None
        self.installer: IsolatedInstaller | None = None
        self.advanced: KCHAdvancedRuntime | None = None
        self.handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            descriptor["name"]: (
                lambda arguments, tool_name=descriptor["name"]: self.call(
                    tool_name, arguments
                )["structuredContent"]
            )
            for descriptor in TOOLS
        }

    def ensure_runtime(self) -> KCHAdvancedRuntime:
        """Materialize heavy components only for a real tool call.

        MCP initialize and tools/list are static contract operations and must
        remain available inside strict host startup deadlines.
        """
        if self.advanced is not None:
            return self.advanced
        self.studio = Studio(self.root / "studio")
        self.fabric = ExtensionFabric(self.root / "extension_fabric")
        self.installer = IsolatedInstaller(self.root / "isolated_installs")
        raw_handlers: dict[str, Callable[[dict[str, Any]], Any]] = {
            "kch_preflight": lambda _args: self.preflight(),
            "studio_status": lambda _args: self.studio.status(),  # type: ignore[union-attr]
            "studio_create_session": lambda args: self.studio.create_session(  # type: ignore[union-attr]
                ArtifactSpec.from_dict(dict(args["spec"]))
            ),
            "studio_generate": lambda args: self.studio.generate(str(args["session_id"])),  # type: ignore[union-attr]
            "studio_validate": lambda args: self.studio.validate(str(args["session_id"])),  # type: ignore[union-attr]
            "studio_seal": lambda args: self.studio.seal(str(args["session_id"])),  # type: ignore[union-attr]
            "studio_build_and_seal": lambda args: self.studio.build_and_seal(  # type: ignore[union-attr]
                ArtifactSpec.from_dict(dict(args["spec"]))
            ),
            "extension_inventory": lambda _args: RuntimeInventory().collect(),
            "extension_search": lambda args: self.fabric.search(  # type: ignore[union-attr]
                str(args["provider"]), str(args["query"]), int(args.get("limit", 10))
            ),
            "extension_recommend": lambda args: RecommendationEngine().evaluate(
                args["records"],
                objective=str(args["objective"]),
                available_runtimes=args["available_runtimes"],
            ),
            "extension_resolve": lambda args: self.fabric.resolve(  # type: ignore[union-attr]
                str(args["provider"]), str(args["identifier"])
            ),
            "isolated_install_plan": lambda args: self.installer.plan(  # type: ignore[union-attr]
                args["source"],
                artifact_kind=str(args["artifact_kind"]),
                target_name=str(args["target_name"]),
            ).to_dict(),
            "isolated_install_execute": self._install,
            "isolated_install_rollback": lambda args: self.installer.rollback(  # type: ignore[union-attr]
                dict(args["receipt"])
            ),
            "isolated_install_verify": lambda args: self.installer.verify(dict(args["receipt"])),  # type: ignore[union-attr]
        }
        self.advanced = KCHAdvancedRuntime(
            self.root / "advanced",
            extra_handlers=raw_handlers,
            extra_tools=BASE_TOOLS,
        )
        # The advanced runtime returns one uniformly governed handler map,
        # including the base Studio tools passed above.  Retaining the earlier
        # raw handlers here would bypass the PHL exclusive mutation gate.
        self.handlers = dict(self.advanced.handlers)
        return self.advanced

    def preflight(self) -> dict[str, Any]:
        self.ensure_runtime()
        assert self.studio is not None and self.advanced is not None
        studio = self.studio.status()
        runtime = self.advanced.status()
        governance = studio["governance"]
        surface = runtime["components"]["strategic_surface"]
        response_modes = runtime["components"]["response_modes"]
        continuity = runtime["components"]["continuity"]
        blind_spots = runtime["capability_blind_spots"]
        checks = {
            "compiled_governance": governance["state"] == "VERIFIED_COMPILED_GOVERNANCE",
            "governance_hierarchy": governance["hierarchy"] == ["HARNESS", "AGENTS", "RULES"],
            "all_strategic_invariant": governance["all_strategic_invariant"] is True,
            "full_strategic_surface": surface["gate"] == "PASS"
            and surface["scope"] == "FULL_INTEGRATED",
            "launcher_blind_spots_absent": not blind_spots,
            "phl_authorized": runtime["phl_authorized"] is True,
            "response_modes_integrity": response_modes["integrity"]["gate"] == "PASS",
            "continuity_integrity": continuity["integrity"]["gate"] == "PASS",
        }
        passed = all(checks.values())
        return {
            "schema": "kch.canonical-preflight.v0.2.0",
            "gate": "PASS" if passed else "FAIL",
            "canonical_entrypoint": "kch_studio.mcp_server:StudioMCP",
            "internal_component_not_a_canonical_entrypoint": (
                "kch_studio.advanced_runtime:KCHAdvancedRuntime"
            ),
            "checks": checks,
            "governance": governance,
            "strategic_surface": surface,
            "capability_blind_spots": blind_spots,
            "phl": {
                "authorized": runtime["phl_authorized"],
                "training_executed": runtime["phl_training_executed"],
                "real_feedback_executed": runtime["phl_real_executed"],
            },
            "response_modes": response_modes,
            "continuity": continuity,
            "aikido": runtime["components"]["aikido"],
            "external_installation_performed": runtime["external_installation_performed"],
            "claim_ceiling": "CANONICAL_LOCAL_STARTUP_AND_BINDING_GATE_ONLY",
            "industrial_validation_established": False,
        }

    def _install(self, args: dict[str, Any]) -> dict[str, Any]:
        self.ensure_runtime()
        assert self.installer is not None
        plan_value = dict(args["plan"])
        plan_value["preconditions"] = tuple(plan_value["preconditions"])
        plan_value["rollback"] = tuple(plan_value["rollback"])
        plan = InstallPlan(**plan_value)
        return self.installer.execute(plan, ConsentDecision(str(args["consent"])))

    def call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.ensure_runtime()
        if name not in self.handlers:
            raise ValueError(f"unknown tool: {name}")
        value = self.handlers[name](arguments)
        return {
            "content": [
                {"type": "text", "text": json.dumps(value, ensure_ascii=False, sort_keys=True)}
            ],
            "structuredContent": value,
        }

    def handle(self, message: dict[str, Any]) -> dict[str, Any] | None:
        request_id = message.get("id")
        method = message.get("method")
        if method == "notifications/initialized":
            return None
        try:
            if method == "initialize":
                result: Any = {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": SERVER_INFO,
                    "instructions": "KCH governance is HARNESS > AGENTS > RULES. Every component is strategically material and must pass both local-completeness and systemic-synergy gates. The user constitution and programmed DIRECT rules govern orchestration. Before material action, continuity_action_preflight must preserve the governing mission, require complete source reading, reconcile current state, prefer a cheap materiality probe, protect custody and block known recurrent failures. Adverse evidence is converted through Aikido into capability, dated protocol, skill/operator candidates, OBL/PHL envelopes and regression contracts without automatic promotion. Before each authored chat response, resolve response_mode_contract: CONCISO, EXPLICATIVO and EXTENSO affect only chat prose, never outputs. Every response remains informative, explanatory and holistic. Execution chronology is saved separately as Markdown, never offered, and represented in chat only by one final path line. PLAN, RUN and CONSTRUCT are distinct; CONSTRUCT changes only a versioned successor. Search is not install. Installation requires four-way consent and remains isolated. Full checkpoints require a size warning and explicit confirmation. PHL is authorized and operationally available; it remains untrained until genuine user-authored feedback exists, and an active PHL session exclusively blocks ordinary KCH mutations.",
                }
            elif method == "tools/list":
                result = {
                    "tools": [
                        {
                            "name": tool["name"],
                            "title": tool["title"],
                            "description": tool["description"],
                            "inputSchema": tool["inputSchema"],
                            "annotations": {"readOnlyHint": tool["readOnly"]},
                        }
                        for tool in TOOLS
                    ]
                }
            elif method == "tools/call":
                params = dict(message.get("params", {}))
                result = self.call(str(params.get("name", "")), dict(params.get("arguments", {})))
            elif method == "ping":
                result = {}
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"method not found: {method}"},
                }
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32602, "message": str(exc)},
            }


def main() -> None:
    root = Path(os.environ.get("KCH_STUDIO_RUNTIME", Path.cwd() / ".kch-studio-runtime"))
    server = StudioMCP(root)
    try:
        for line in sys.stdin:
            if not line.strip():
                continue
            try:
                message = json.loads(line)
                response = server.handle(message)
            except Exception as exc:
                response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": str(exc)},
                }
            if response is not None:
                sys.stdout.write(
                    json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n"
                )
                sys.stdout.flush()
    finally:
        server.advanced.close()


if __name__ == "__main__":
    main()
