from __future__ import annotations

import json
import os
import subprocess
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from .contracts import (
    ArtifactKind,
    ArtifactSpec,
    ValidationCheck,
    file_manifest,
    safe_child,
)

def resolve_system_skill_root(name: str, override_environment: str) -> Path:
    """Resolve a Codex system skill without binding the release to its builder account."""
    override = os.environ.get(override_environment)
    if override:
        return Path(override).expanduser().resolve()
    codex_home = Path(
        os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))
    ).expanduser()
    return (codex_home / "skills" / ".system" / name).resolve()

FORBIDDEN_MARKERS = ("[TODO:", "lorem ipsum", "lipsum")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))


def module_name(spec: ArtifactSpec) -> str:
    return spec.slug.replace("-", "_")


def run_checked(
    command: list[str], *, cwd: Path | None = None, input_text: str | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
        env={**os.environ, "PYTHONUTF8": "1"},
    )


class ArtifactProvider(ABC):
    kind: ArtifactKind

    @abstractmethod
    def generate(self, spec: ArtifactSpec, stage_root: Path) -> Path:
        raise NotImplementedError

    def validate(self, spec: ArtifactSpec, artifact_root: Path) -> list[ValidationCheck]:
        manifest = file_manifest(artifact_root)
        marker_hits: list[str] = []
        for item in manifest:
            path = artifact_root / item["path"]
            if path.suffix.lower() not in {".md", ".py", ".json", ".toml", ".yaml", ".yml", ".txt"}:
                continue
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            for marker in FORBIDDEN_MARKERS:
                if marker.lower() in text:
                    marker_hits.append(f"{item['path']}:{marker}")
        return [
            ValidationCheck(
                "artifact.nonempty",
                bool(manifest),
                f"{len(manifest)} files",
                {"manifest": manifest},
            ),
            ValidationCheck(
                "artifact.no_forbidden_markers",
                not marker_hits,
                "no unfinished markers" if not marker_hits else str(marker_hits),
            ),
            ValidationCheck(
                "artifact.spec_binding",
                (artifact_root / "kch-artifact-spec.json").is_file(),
                "canonical input specification is persisted",
            ),
        ]

    @staticmethod
    def prepare(spec: ArtifactSpec, stage_root: Path) -> Path:
        root = safe_child(stage_root, spec.slug)
        if root.exists():
            raise ValueError(f"staged target already exists: {root}")
        root.mkdir(parents=True)
        write_json(root / "kch-artifact-spec.json", spec.to_dict())
        return root


class SkillProvider(ArtifactProvider):
    kind = ArtifactKind.SKILL

    def generate(self, spec: ArtifactSpec, stage_root: Path) -> Path:
        instructions = spec.metadata.get("instructions")
        if (
            not isinstance(instructions, list)
            or not instructions
            or any(not str(item).strip() for item in instructions)
        ):
            raise ValueError("SKILL metadata.instructions must be a non-empty string array")
        skill_creator = resolve_system_skill_root("skill-creator", "KCH_SKILL_CREATOR_ROOT")
        init_script = skill_creator / "scripts" / "init_skill.py"
        if not init_script.is_file():
            raise FileNotFoundError(f"official skill initializer unavailable: {init_script}")
        short = f"Guided KCH workflow for {spec.slug}"[:64]
        if len(short) < 25:
            short = (short + " with governed validation")[:64]
        command = [
            sys.executable,
            str(init_script),
            spec.slug,
            "--path",
            str(stage_root),
            "--interface",
            f"display_name={spec.name}",
            "--interface",
            f"short_description={short}",
            "--interface",
            f"default_prompt=Use ${spec.slug} to {spec.objective.rstrip('.')}.",
        ]
        resources = spec.metadata.get("resources", [])
        if resources:
            allowed = {"scripts", "references", "assets"}
            if not isinstance(resources, list) or not set(resources).issubset(allowed):
                raise ValueError(f"unsupported skill resources: {resources}")
            command.extend(["--resources", ",".join(resources)])
        result = run_checked(command)
        if result.returncode:
            raise RuntimeError(f"skill initializer failed: {result.stderr or result.stdout}")
        root = safe_child(stage_root, spec.slug)
        if not root.is_dir() or not (root / "SKILL.md").is_file():
            raise RuntimeError(
                "skill initializer reported success without durable output; "
                f"target={root}, stdout={result.stdout!r}, stderr={result.stderr!r}"
            )
        body = "\n".join(
            f"{index}. {str(item).strip()}" for index, item in enumerate(instructions, start=1)
        )
        description = str(
            spec.metadata.get("description")
            or f"Execute {spec.objective}. Use when this governed workflow is requested."
        )
        skill_md = f"""---
name: {spec.slug}
description: {description}
---

# {spec.name}

{body}

## Completion contract

Return the achieved result, evidence boundary, unresolved uncertainty, changed artifacts, and next decision-critical action.
Never infer installation, execution authority, or validation beyond the observed evidence.
"""
        write_text(root / "SKILL.md", skill_md)
        write_json(root / "kch-artifact-spec.json", spec.to_dict())
        return root

    def validate(self, spec: ArtifactSpec, artifact_root: Path) -> list[ValidationCheck]:
        checks = super().validate(spec, artifact_root)
        skill_creator = resolve_system_skill_root("skill-creator", "KCH_SKILL_CREATOR_ROOT")
        validator = skill_creator / "scripts" / "quick_validate.py"
        result = run_checked([sys.executable, str(validator), str(artifact_root)])
        checks.append(
            ValidationCheck(
                "skill.official_quick_validate",
                result.returncode == 0,
                (result.stdout or result.stderr).strip(),
                {"returncode": result.returncode},
            )
        )
        openai_yaml = artifact_root / "agents" / "openai.yaml"
        text = openai_yaml.read_text(encoding="utf-8") if openai_yaml.is_file() else ""
        checks.append(
            ValidationCheck(
                "skill.openai_yaml_binding",
                f"${spec.slug}" in text,
                "default prompt explicitly invokes the generated skill",
            )
        )
        return checks


TOOL_RUNTIME = """from __future__ import annotations

import json
import sys
from typing import Any

CONTRACT = __CONTRACT__


def run(arguments: dict[str, Any]) -> dict[str, Any]:
    operation = CONTRACT["operation"]
    if operation == "inspect_contract":
        return {"contract": CONTRACT, "received_keys": sorted(arguments)}
    if operation == "validate_required_fields":
        required = CONTRACT.get("required_fields", [])
        missing = [name for name in required if name not in arguments]
        return {"valid": not missing, "missing": missing}
    if operation == "render_template":
        template = CONTRACT["template"]
        missing = [name for name in CONTRACT.get("required_fields", []) if name not in arguments]
        if missing:
            return {"rendered": False, "missing": missing}
        return {"rendered": True, "text": template.format_map(arguments)}
    raise ValueError(f"unsupported operation: {operation}")


def main() -> None:
    payload = json.load(sys.stdin)
    json.dump(run(payload), sys.stdout, ensure_ascii=False, sort_keys=True)
    sys.stdout.write("\\n")


if __name__ == "__main__":
    main()
"""


class ToolProvider(ArtifactProvider):
    kind = ArtifactKind.TOOL

    def generate(self, spec: ArtifactSpec, stage_root: Path) -> Path:
        operation = str(spec.metadata.get("operation", "inspect_contract"))
        if operation not in {"inspect_contract", "validate_required_fields", "render_template"}:
            raise ValueError(f"unsupported deterministic tool operation: {operation}")
        contract = {
            "schema": "kch.generated-tool.v0.1.0",
            "name": spec.slug,
            "objective": spec.objective,
            "operation": operation,
            "required_fields": list(spec.metadata.get("required_fields", spec.inputs)),
            "template": spec.metadata.get("template", ""),
            "authority_ceiling": sorted(spec.authority_ceiling),
        }
        if operation == "render_template" and not contract["template"]:
            raise ValueError("render_template tools require metadata.template")
        root = self.prepare(spec, stage_root)
        package = module_name(spec)
        write_json(root / "tool-contract.json", contract)
        source = TOOL_RUNTIME.replace("__CONTRACT__", repr(contract))
        write_text(
            root / "src" / package / "__init__.py", "from .tool import run\n\n__all__ = ['run']"
        )
        write_text(root / "src" / package / "tool.py", source)
        write_text(
            root / "pyproject.toml",
            f"""[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "{spec.slug}"
version = "0.1.0"
description = "{spec.objective.replace(chr(34), chr(39))}"
requires-python = ">=3.11"

[project.scripts]
{spec.slug} = "{package}.tool:main"

[tool.setuptools.packages.find]
where = ["src"]
""",
        )
        return root

    def validate(self, spec: ArtifactSpec, artifact_root: Path) -> list[ValidationCheck]:
        checks = super().validate(spec, artifact_root)
        package = module_name(spec)
        code = (
            "import json,sys;sys.path.insert(0,r'" + str(artifact_root / "src") + "');"
            f"from {package}.tool import run;print(json.dumps(run({{}}),sort_keys=True))"
        )
        result = run_checked([sys.executable, "-c", code])
        checks.append(
            ValidationCheck(
                "tool.import_and_call",
                result.returncode == 0,
                (result.stdout or result.stderr).strip(),
            )
        )
        return checks


MCP_SERVER_RUNTIME = """from __future__ import annotations

import json
import sys
from typing import Any

SERVER = __SERVER__
TOOLS = __TOOLS__


def tool_result(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    tool = next((item for item in TOOLS if item["name"] == name), None)
    if tool is None:
        raise ValueError(f"unknown tool: {name}")
    operation = tool["operation"]
    if operation == "inspect_contract":
        value = {"server": SERVER, "tool": tool, "received_keys": sorted(arguments)}
    elif operation == "validate_required_fields":
        required = tool.get("required_fields", [])
        missing = [field for field in required if field not in arguments]
        value = {"valid": not missing, "missing": missing}
    elif operation == "render_template":
        required = tool.get("required_fields", [])
        missing = [field for field in required if field not in arguments]
        value = {"rendered": not missing, "missing": missing}
        if not missing:
            value["text"] = tool["template"].format_map(arguments)
    else:
        raise ValueError(f"unsupported operation: {operation}")
    return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, sort_keys=True)}], "structuredContent": value}


def handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    request_id = message.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}, "serverInfo": SERVER, "instructions": SERVER["instructions"]}
    elif method == "tools/list":
        result = {"tools": [{"name": item["name"], "title": item["title"], "description": item["description"], "inputSchema": item["input_schema"], "annotations": {"readOnlyHint": True}} for item in TOOLS]}
    elif method == "tools/call":
        params = message.get("params", {})
        result = tool_result(str(params.get("name", "")), dict(params.get("arguments", {})))
    elif method == "ping":
        result = {}
    else:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def main() -> None:
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            response = handle(json.loads(line))
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32603, "message": str(exc)}}
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
"""


class MCPProvider(ArtifactProvider):
    kind = ArtifactKind.MCP

    def _tools(self, spec: ArtifactSpec) -> list[dict[str, Any]]:
        raw_tools = spec.metadata.get("tools") or [
            {
                "name": "inspect_contract",
                "title": "Inspect generated contract",
                "description": "Inspect this MCP server's bounded generated contract.",
                "operation": "inspect_contract",
                "required_fields": [],
                "input_schema": {"type": "object", "properties": {}, "additionalProperties": True},
            }
        ]
        if not isinstance(raw_tools, list) or not raw_tools:
            raise ValueError("MCP metadata.tools must be a non-empty array")
        tools: list[dict[str, Any]] = []
        for item in raw_tools:
            tool = dict(item)
            operation = tool.get("operation")
            if operation not in {"inspect_contract", "validate_required_fields", "render_template"}:
                raise ValueError(f"unsupported MCP tool operation: {operation}")
            required = {"name", "title", "description", "operation", "input_schema"}
            if not required.issubset(tool):
                raise ValueError(f"MCP tool missing fields: {sorted(required - set(tool))}")
            if operation == "render_template" and not tool.get("template"):
                raise ValueError("render_template MCP tools require template")
            tool.setdefault("required_fields", [])
            tools.append(tool)
        return tools

    def generate(self, spec: ArtifactSpec, stage_root: Path) -> Path:
        tools = self._tools(spec)
        root = self.prepare(spec, stage_root)
        package = module_name(spec)
        server = {
            "name": spec.slug,
            "version": "0.1.0",
            "instructions": f"Operate only within {spec.jurisdiction}. Do not infer install or action authority.",
        }
        source = MCP_SERVER_RUNTIME.replace("__SERVER__", repr(server)).replace(
            "__TOOLS__", repr(tools)
        )
        write_text(
            root / "src" / package / "__init__.py",
            "from .server import handle\n\n__all__ = ['handle']",
        )
        write_text(root / "src" / package / "server.py", source)
        write_json(root / "mcp-tools.json", {"server": server, "tools": tools})
        write_text(
            root / "pyproject.toml",
            f"""[build-system]
requires = ["setuptools>=77"]
build-backend = "setuptools.build_meta"

[project]
name = "{spec.slug}"
version = "0.1.0"
description = "{spec.objective.replace(chr(34), chr(39))}"
requires-python = ">=3.11"

[project.scripts]
{spec.slug} = "{package}.server:main"

[tool.setuptools.packages.find]
where = ["src"]
""",
        )
        return root

    def validate(self, spec: ArtifactSpec, artifact_root: Path) -> list[ValidationCheck]:
        checks = super().validate(spec, artifact_root)
        package = module_name(spec)
        initialize = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        list_tools = json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        result = run_checked(
            [sys.executable, "-m", f"{package}.server"],
            cwd=artifact_root,
            input_text=initialize + "\n" + list_tools + "\n",
        )
        if result.returncode != 0 and "No module named" in result.stderr:
            env_code = (
                "import runpy,sys;sys.path.insert(0,r'" + str(artifact_root / "src") + "');"
                f"runpy.run_module('{package}.server',run_name='__main__')"
            )
            result = run_checked(
                [sys.executable, "-c", env_code], input_text=initialize + "\n" + list_tools + "\n"
            )
        responses: list[dict[str, Any]] = []
        try:
            responses = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        except json.JSONDecodeError:
            pass
        passed = (
            result.returncode == 0
            and len(responses) == 2
            and "tools" in responses[1].get("result", {})
        )
        checks.append(
            ValidationCheck(
                "mcp.stdio_initialize_and_list",
                passed,
                f"returncode={result.returncode}, responses={len(responses)}",
                {"stderr": result.stderr, "responses": responses},
            )
        )
        return checks


OPERATOR_RUNTIME = """from __future__ import annotations

from typing import Any

STEPS = __STEPS__


def operate(value: dict[str, Any]) -> dict[str, Any]:
    current = dict(value)
    trace: list[dict[str, Any]] = []
    for step in STEPS:
        kind = step["kind"]
        if kind == "require":
            missing = [name for name in step["fields"] if name not in current]
            trace.append({"kind": kind, "passed": not missing, "missing": missing})
            if missing:
                return {"status": "ABSTAIN_MISSING_INPUT", "value": current, "trace": trace}
        elif kind == "select":
            current = {name: current[name] for name in step["fields"] if name in current}
            trace.append({"kind": kind, "fields": sorted(current)})
        elif kind == "rename":
            source, target = step["source"], step["target"]
            if source in current:
                current[target] = current.pop(source)
            trace.append({"kind": kind, "source": source, "target": target})
        else:
            raise ValueError(f"unsupported operator step: {kind}")
    return {"status": "COMPLETED", "value": current, "trace": trace}
"""


class OperatorProvider(ArtifactProvider):
    kind = ArtifactKind.OPERATOR

    def generate(self, spec: ArtifactSpec, stage_root: Path) -> Path:
        steps = spec.metadata.get("steps") or [{"kind": "require", "fields": list(spec.inputs)}]
        if not isinstance(steps, list) or not steps:
            raise ValueError("OPERATOR metadata.steps must be a non-empty array")
        for step in steps:
            if step.get("kind") not in {"require", "select", "rename"}:
                raise ValueError(f"unsupported operator step: {step}")
        root = self.prepare(spec, stage_root)
        package = module_name(spec)
        write_json(
            root / "operator-contract.json", {"schema": "kch.operator.v0.1.0", "steps": steps}
        )
        write_text(
            root / "src" / package / "__init__.py",
            "from .operator import operate\n\n__all__ = ['operate']",
        )
        write_text(
            root / "src" / package / "operator.py",
            OPERATOR_RUNTIME.replace("__STEPS__", repr(steps)),
        )
        return root

    def validate(self, spec: ArtifactSpec, artifact_root: Path) -> list[ValidationCheck]:
        checks = super().validate(spec, artifact_root)
        package = module_name(spec)
        code = (
            "import json,sys;sys.path.insert(0,r'" + str(artifact_root / "src") + "');"
            f"from {package}.operator import operate;print(json.dumps(operate({{}}),sort_keys=True))"
        )
        result = run_checked([sys.executable, "-c", code])
        checks.append(
            ValidationCheck(
                "operator.executable",
                result.returncode == 0,
                (result.stdout or result.stderr).strip(),
            )
        )
        return checks


class AgentProvider(ArtifactProvider):
    kind = ArtifactKind.AGENT

    def generate(self, spec: ArtifactSpec, stage_root: Path) -> Path:
        root = self.prepare(spec, stage_root)
        agent = {
            "schema": "kch.csi-agent.v0.1.0",
            "id": spec.slug,
            "objective": spec.objective,
            "jurisdiction": spec.jurisdiction,
            "inputs": list(spec.inputs),
            "outputs": list(spec.outputs),
            "authority_ceiling": sorted(spec.authority_ceiling),
            "parallel_group": spec.metadata.get("parallel_group"),
            "supervisor": spec.metadata.get("supervisor"),
            "execution_authority": False,
        }
        write_json(root / "agent.json", agent)
        write_text(
            root / "AGENT.md",
            f"""# {spec.name}

Objective: {spec.objective}

Jurisdiction: {spec.jurisdiction}

Accept only work orders containing: {", ".join(spec.inputs) or "no mandatory payload fields"}.
Return only declared outputs: {", ".join(spec.outputs) or "a bounded receipt"}.
Respect the authority ceiling: {", ".join(sorted(spec.authority_ceiling))}.
Composition with another agent does not merge memory, context, provenance, authority, or claim jurisdiction.
""",
        )
        runner = f"""from __future__ import annotations
import json
from typing import Any

AGENT = {agent!r}

def admit(work_order: dict[str, Any]) -> dict[str, Any]:
    missing = [name for name in AGENT["inputs"] if name not in work_order]
    return {{"admitted": not missing, "missing": missing, "agent_id": AGENT["id"], "execution_authority": False}}
"""
        write_text(root / "agent_runner.py", runner)
        return root

    def validate(self, spec: ArtifactSpec, artifact_root: Path) -> list[ValidationCheck]:
        checks = super().validate(spec, artifact_root)
        result = run_checked(
            [
                sys.executable,
                "-c",
                f"import runpy;d=runpy.run_path(r'{artifact_root / 'agent_runner.py'}');print(d['admit']({{}}))",
            ]
        )
        checks.append(
            ValidationCheck(
                "agent.work_order_admission",
                result.returncode == 0,
                (result.stdout or result.stderr).strip(),
            )
        )
        return checks


RULE_RUNTIME = """from __future__ import annotations

from typing import Any

RULE = __RULE__


def evaluate(context: dict[str, Any]) -> dict[str, Any]:
    missing = [name for name in RULE["required_fields"] if name not in context]
    forbidden = [{"field": field, "value": context.get(field)} for field, values in RULE["forbidden_values"].items() if context.get(field) in values]
    if forbidden:
        decision = "DENY"
    elif missing:
        decision = "ASK"
    else:
        decision = "ALLOW"
    return {"decision": decision, "missing": missing, "forbidden": forbidden, "rule_id": RULE["id"]}
"""


class RuleProvider(ArtifactProvider):
    kind = ArtifactKind.RULE

    def generate(self, spec: ArtifactSpec, stage_root: Path) -> Path:
        rule = {
            "schema": "kch.csi-rule.v0.1.0",
            "id": spec.slug,
            "objective": spec.objective,
            "required_fields": list(spec.metadata.get("required_fields", spec.inputs)),
            "forbidden_values": dict(spec.metadata.get("forbidden_values", {})),
            "authority_ceiling": sorted(spec.authority_ceiling),
            "native_exec_rules": list(spec.metadata.get("native_exec_rules", [])),
        }
        root = self.prepare(spec, stage_root)
        write_json(root / "rule.json", rule)
        write_text(
            root / "RULES.md",
            f"# {spec.name}\n\n{spec.objective}\n\nThis rule restricts authority and never grants installation or execution permission.",
        )
        write_text(root / "evaluate.py", RULE_RUNTIME.replace("__RULE__", repr(rule)))
        return root

    def validate(self, spec: ArtifactSpec, artifact_root: Path) -> list[ValidationCheck]:
        checks = super().validate(spec, artifact_root)
        code = (
            "import json,runpy;d=runpy.run_path(r'" + str(artifact_root / "evaluate.py") + "');"
            "print(json.dumps(d['evaluate']({}),sort_keys=True))"
        )
        result = run_checked([sys.executable, "-c", code])
        value: dict[str, Any] = {}
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError:
            pass
        checks.append(
            ValidationCheck(
                "rule.forward_evaluation",
                result.returncode == 0 and value.get("decision") in {"ALLOW", "ASK", "DENY"},
                (result.stdout or result.stderr).strip(),
                value,
            )
        )
        return checks


class KwanForkProvider(ArtifactProvider):
    kind = ArtifactKind.KWANFORK

    def generate(self, spec: ArtifactSpec, stage_root: Path) -> Path:
        parent = spec.metadata.get("parent")
        transformations = spec.metadata.get("transformations")
        if (
            not isinstance(parent, dict)
            or not parent.get("id")
            or not parent.get("sha256")
            or not parent.get("path")
        ):
            raise ValueError("KWANFORK metadata.parent requires id, path, and sha256")
        parent_path = Path(str(parent["path"])).resolve()
        if not parent_path.is_file():
            raise ValueError(f"KWANFORK parent bytes unavailable: {parent_path}")
        if not isinstance(transformations, list) or not transformations:
            raise ValueError("KWANFORK metadata.transformations must be non-empty")
        manifest = {
            "schema": "kch.kwanfork.v0.1.0",
            "id": spec.slug,
            "parent": parent,
            "transformations": transformations,
            "purpose_identity_preservation": spec.metadata.get(
                "purpose_identity_preservation", "NOT_ESTIMABLE"
            ),
            "decision_equivalence": spec.metadata.get("decision_equivalence", "NOT_ESTIMABLE"),
            "evidence_contract_equivalence": spec.metadata.get(
                "evidence_contract_equivalence", "NOT_ESTIMABLE"
            ),
            "provenance_preservation": spec.metadata.get(
                "provenance_preservation", "NOT_ESTIMABLE"
            ),
            "transport_integrity": spec.metadata.get("transport_integrity", "NOT_ESTIMABLE"),
            "authority_inherited": False,
        }
        root = self.prepare(spec, stage_root)
        write_json(root / "kwanfork.json", manifest)
        verifier = f"""from __future__ import annotations
import hashlib, json
from pathlib import Path

MANIFEST = {manifest!r}

def verify_parent(path: str | Path) -> dict[str, object]:
    raw = Path(path).read_bytes()
    observed = hashlib.sha256(raw).hexdigest()
    expected = MANIFEST["parent"]["sha256"]
    return {{"passed": observed == expected, "expected": expected, "observed": observed, "authority_inherited": False}}
"""
        write_text(root / "verify_lineage.py", verifier)
        return root

    def validate(self, spec: ArtifactSpec, artifact_root: Path) -> list[ValidationCheck]:
        checks = super().validate(spec, artifact_root)
        parent_path = Path(str(spec.metadata["parent"]["path"])).resolve()
        code = (
            "import json,runpy;d=runpy.run_path(r'"
            + str(artifact_root / "verify_lineage.py")
            + "');"
            "print(json.dumps(d['verify_parent'](r'" + str(parent_path) + "'),sort_keys=True))"
        )
        result = run_checked([sys.executable, "-c", code])
        value: dict[str, Any] = {}
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError:
            pass
        checks.append(
            ValidationCheck(
                "kwanfork.parent_byte_integrity",
                result.returncode == 0 and bool(value.get("passed")),
                (result.stdout or result.stderr).strip(),
                value,
            )
        )
        return checks


MOD_RUNTIME = """from __future__ import annotations

import copy
from typing import Any

OPERATIONS = __OPERATIONS__


def apply(document: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(document)
    for operation in OPERATIONS:
        path = operation["path"]
        if not path.startswith("/") or "/" in path[1:]:
            raise ValueError("v0.1 supports exact top-level JSON pointer paths only")
        key = path[1:].replace("~1", "/").replace("~0", "~")
        if operation["op"] in {"add", "replace"}:
            if operation["op"] == "replace" and key not in result:
                raise KeyError(key)
            result[key] = operation["value"]
        elif operation["op"] == "remove":
            if key not in result:
                raise KeyError(key)
            del result[key]
        else:
            raise ValueError(f"unsupported operation: {operation['op']}")
    return result
"""


class ModProvider(ArtifactProvider):
    kind = ArtifactKind.MOD

    def generate(self, spec: ArtifactSpec, stage_root: Path) -> Path:
        operations = spec.metadata.get("operations")
        if not isinstance(operations, list) or not operations:
            raise ValueError("MOD metadata.operations must be a non-empty JSON patch subset")
        for operation in operations:
            if operation.get("op") not in {"add", "replace", "remove"} or not str(
                operation.get("path", "")
            ).startswith("/"):
                raise ValueError(f"unsupported MOD operation: {operation}")
            if operation["op"] in {"add", "replace"} and "value" not in operation:
                raise ValueError(f"MOD operation requires value: {operation}")
        if not isinstance(spec.metadata.get("sample_document"), dict) or not isinstance(
            spec.metadata.get("expected_document"), dict
        ):
            raise ValueError("MOD requires sample_document and expected_document for validation")
        root = self.prepare(spec, stage_root)
        write_json(
            root / "mod.json",
            {"schema": "kch.mod.v0.1.0", "operations": operations, "rollback_required": True},
        )
        write_text(root / "apply_mod.py", MOD_RUNTIME.replace("__OPERATIONS__", repr(operations)))
        return root

    def validate(self, spec: ArtifactSpec, artifact_root: Path) -> list[ValidationCheck]:
        checks = super().validate(spec, artifact_root)
        sample = repr(spec.metadata["sample_document"])
        code = (
            "import json,runpy;d=runpy.run_path(r'" + str(artifact_root / "apply_mod.py") + "');"
            f"print(json.dumps(d['apply']({sample}),sort_keys=True))"
        )
        result = run_checked([sys.executable, "-c", code])
        value: dict[str, Any] = {}
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError:
            pass
        passed = result.returncode == 0 and value == spec.metadata["expected_document"]
        checks.append(
            ValidationCheck(
                "mod.forward_example",
                passed,
                (result.stdout or result.stderr).strip(),
                {"expected": spec.metadata["expected_document"]},
            )
        )
        return checks


class PluginProvider(ArtifactProvider):
    kind = ArtifactKind.PLUGIN

    def generate(self, spec: ArtifactSpec, stage_root: Path) -> Path:
        plugin_creator = resolve_system_skill_root("plugin-creator", "KCH_PLUGIN_CREATOR_ROOT")
        script = plugin_creator / "scripts" / "create_basic_plugin.py"
        if not script.is_file():
            raise FileNotFoundError(f"official plugin scaffold unavailable: {script}")
        result = run_checked(
            [sys.executable, str(script), spec.slug, "--path", str(stage_root), "--with-skills"]
        )
        if result.returncode:
            raise RuntimeError(f"plugin scaffold failed: {result.stderr or result.stdout}")
        root = safe_child(stage_root, spec.slug)
        if not root.is_dir() or not (root / ".codex-plugin" / "plugin.json").is_file():
            raise RuntimeError("plugin scaffold reported success without a durable manifest")
        instructions = spec.metadata.get("instructions") or [
            "Inspect the requested objective and applicable authority before acting.",
            "Use only the plugin capabilities declared by its manifest.",
            "Return evidence, limits, and the next decision-critical action.",
        ]
        skill_spec = ArtifactSpec(
            name=f"{spec.slug}-workflow",
            kind=ArtifactKind.SKILL,
            objective=spec.objective,
            jurisdiction=spec.jurisdiction,
            inputs=spec.inputs,
            outputs=spec.outputs,
            authority_ceiling=spec.authority_ceiling,
            metadata={
                "instructions": instructions,
                "description": f"Guide {spec.objective}. Use for {spec.slug} plugin workflows.",
            },
        )
        SkillProvider().generate(skill_spec, root / "skills")
        manifest_path = root / ".codex-plugin" / "plugin.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["skills"] = "./skills/"
        write_json(manifest_path, manifest)
        write_json(root / "kch-artifact-spec.json", spec.to_dict())
        return root

    def validate(self, spec: ArtifactSpec, artifact_root: Path) -> list[ValidationCheck]:
        checks = super().validate(spec, artifact_root)
        plugin_creator = resolve_system_skill_root("plugin-creator", "KCH_PLUGIN_CREATOR_ROOT")
        validator = plugin_creator / "scripts" / "validate_plugin.py"
        result = run_checked([sys.executable, str(validator), str(artifact_root)])
        checks.append(
            ValidationCheck(
                "plugin.official_validate",
                result.returncode == 0,
                (result.stdout or result.stderr).strip(),
            )
        )
        skill_dirs = list((artifact_root / "skills").glob("*/SKILL.md"))
        checks.append(
            ValidationCheck(
                "plugin.contains_valid_workflow",
                bool(skill_dirs),
                f"{len(skill_dirs)} packaged skills",
            )
        )
        return checks


class HostAdapterProvider(ArtifactProvider):
    kind = ArtifactKind.HOST_ADAPTER

    def generate(self, spec: ArtifactSpec, stage_root: Path) -> Path:
        if not spec.host_targets:
            raise ValueError("HOST_ADAPTER requires at least one host target")
        command = spec.metadata.get("command")
        if not isinstance(command, list) or not command:
            raise ValueError("HOST_ADAPTER metadata.command must be a non-empty argv array")
        root = self.prepare(spec, stage_root)
        from .adapters import HostAdapterCompiler

        receipt = HostAdapterCompiler(root).compile(
            name=spec.slug,
            command=[str(item) for item in command],
            targets=spec.host_targets,
            cwd=spec.metadata.get("cwd"),
        )
        write_json(root / "adapter-receipt.json", receipt)
        return root

    def validate(self, spec: ArtifactSpec, artifact_root: Path) -> list[ValidationCheck]:
        import tomllib

        checks = super().validate(spec, artifact_root)
        parsed: list[str] = []
        errors: list[str] = []
        for path in artifact_root.rglob("*"):
            if not path.is_file():
                continue
            try:
                if path.suffix == ".json":
                    json.loads(path.read_text(encoding="utf-8"))
                    parsed.append(path.relative_to(artifact_root).as_posix())
                elif path.suffix == ".toml":
                    tomllib.loads(path.read_text(encoding="utf-8"))
                    parsed.append(path.relative_to(artifact_root).as_posix())
            except Exception as exc:
                errors.append(f"{path.name}:{exc}")
        checks.append(
            ValidationCheck(
                "host_adapter.parse_all_configs",
                not errors and bool(parsed),
                f"parsed={len(parsed)}, errors={errors}",
                {"parsed": parsed},
            )
        )
        receipt = json.loads((artifact_root / "adapter-receipt.json").read_text(encoding="utf-8"))
        checks.append(
            ValidationCheck(
                "host_adapter.inert_projection",
                receipt.get("installation_authorized") is False
                and receipt.get("activation_authorized") is False,
                "all host projections remain staged and inert",
            )
        )
        return checks


PRESET_RUNTIME = """from __future__ import annotations

TEMPLATE = __TEMPLATE__
VARIABLES = __VARIABLES__


def render(values: dict[str, object]) -> str:
    missing = [name for name in VARIABLES if name not in values]
    if missing:
        raise ValueError(f"missing preset variables: {missing}")
    return TEMPLATE.format_map(values)
"""


class PresetProvider(ArtifactProvider):
    kind = ArtifactKind.PRESET

    def generate(self, spec: ArtifactSpec, stage_root: Path) -> Path:
        template = spec.metadata.get("template")
        variables = spec.metadata.get("variables", [])
        if not isinstance(template, str) or not template.strip():
            raise ValueError("PRESET metadata.template must be non-empty")
        if not isinstance(variables, list) or any(not isinstance(item, str) for item in variables):
            raise ValueError("PRESET metadata.variables must be a string array")
        sample_values = spec.metadata.get("sample_values")
        if not isinstance(sample_values, dict) or any(
            name not in sample_values for name in variables
        ):
            raise ValueError("PRESET metadata.sample_values must bind every declared variable")
        root = self.prepare(spec, stage_root)
        write_json(
            root / "preset.json",
            {
                "schema": "kch.kwanprompts-preset.v0.1.0",
                "template": template,
                "variables": variables,
            },
        )
        write_text(
            root / "render.py",
            PRESET_RUNTIME.replace("__TEMPLATE__", repr(template)).replace(
                "__VARIABLES__", repr(variables)
            ),
        )
        return root

    def validate(self, spec: ArtifactSpec, artifact_root: Path) -> list[ValidationCheck]:
        checks = super().validate(spec, artifact_root)
        values = repr(spec.metadata["sample_values"])
        code = (
            "import runpy;d=runpy.run_path(r'" + str(artifact_root / "render.py") + "');"
            f"print(d['render']({values}))"
        )
        result = run_checked([sys.executable, "-c", code])
        expected = str(
            spec.metadata.get("expected_render")
            or spec.metadata["template"].format_map(spec.metadata["sample_values"])
        )
        checks.append(
            ValidationCheck(
                "preset.forward_render",
                result.returncode == 0 and result.stdout.strip() == expected,
                (result.stdout or result.stderr).strip(),
                {"expected": expected},
            )
        )
        return checks


class ProviderRegistry:
    def __init__(self) -> None:
        providers: list[ArtifactProvider] = [
            SkillProvider(),
            ToolProvider(),
            MCPProvider(),
            OperatorProvider(),
            AgentProvider(),
            RuleProvider(),
            KwanForkProvider(),
            ModProvider(),
            PluginProvider(),
            HostAdapterProvider(),
            PresetProvider(),
        ]
        self._providers = {provider.kind: provider for provider in providers}

    def get(self, kind: ArtifactKind) -> ArtifactProvider:
        try:
            return self._providers[kind]
        except KeyError as exc:
            raise KeyError(f"UNAVAILABLE_PROVIDER:{kind.value}") from exc

    def describe(self) -> list[dict[str, Any]]:
        return [
            {"kind": kind.value, "provider": type(provider).__name__, "state": "AVAILABLE"}
            for kind, provider in sorted(self._providers.items(), key=lambda item: item[0].value)
        ]
