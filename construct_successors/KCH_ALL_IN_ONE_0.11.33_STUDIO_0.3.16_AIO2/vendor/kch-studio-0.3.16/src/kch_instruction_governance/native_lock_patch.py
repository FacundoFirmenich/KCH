from __future__ import annotations

import re
from typing import Any

READ_ONLY_POWERSHELL = re.compile(
    r"(?is)^\s*(?:"
    r"Get-Content|Get-Item|Get-ChildItem|Get-FileHash|Test-Path|Select-String|"
    r"Resolve-Path|Measure-Object|Compare-Object"
    r")\b"
)
READ_ONLY_PROGRAM = re.compile(
    r"(?is)^\s*(?:"
    r"rg(?:\.exe)?\b|git\s+(?:status|diff|log|show|rev-parse|ls-files)\b"
    r")"
)
CONTROL_OR_MUTATION = re.compile(
    r"(?is)(?:;|&&|\|\||\||(?<![<>])>(?!>)|>>|"
    r"\b(?:Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|Copy-Item|"
    r"Rename-Item|New-Item|Clear-Content|Invoke-Expression|Start-Process)\b)"
)


def classify_native_tool_operation(tool_name: str, tool_input: Any) -> str:
    """Conservative READ/MUTATE classifier for constitutional mutation locks.

    Only a small, single-command allowlist is classified READ.  Compound or
    unknown shell commands remain MUTATE/EXECUTE and therefore fail closed.
    """

    name = tool_name.casefold()
    if name in {
        "view_image",
        "read_mcp_resource",
        "list_mcp_resources",
        "list_mcp_resource_templates",
    }:
        return "READ"
    if name == "apply_patch":
        return "MUTATE"
    if name not in {"shell_command", "exec_command"}:
        return "MUTATE"
    command = str(tool_input.get("command", "")) if isinstance(tool_input, dict) else ""
    if not command.strip() or CONTROL_OR_MUTATION.search(command):
        return "MUTATE"
    if READ_ONLY_POWERSHELL.match(command) or READ_ONLY_PROGRAM.match(command):
        return "READ"
    return "MUTATE"
