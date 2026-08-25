from __future__ import annotations

import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from kch_native_state import classify_tool_operation, extract_resources  # noqa: E402


def test_direct_read_tool_is_read() -> None:
    assert classify_tool_operation("view_image", {"path": "x.png"}) == "READ"


def test_simple_powershell_read_is_read() -> None:
    payload = {"command": "Get-Content -Raw -LiteralPath C:\\evidence.txt"}
    assert classify_tool_operation("shell_command", payload) == "READ"


def test_apply_patch_is_mutation() -> None:
    assert classify_tool_operation("apply_patch", "*** Begin Patch") == "MUTATE"


def test_freeform_apply_patch_extracts_exact_protected_file() -> None:
    patch = "*** Begin Patch\n*** Update File: C:\\protected\\HARNESS.md\n@@\n-old\n+new\n*** End Patch"
    resources = extract_resources("apply_patch", patch, "C:\\workspace")
    assert "file:c:\\protected\\harness.md" in resources


def test_pipeline_assignment_script_and_unknown_tool_fail_closed() -> None:
    assert classify_tool_operation("shell_command", {"command": "Get-Content x | Set-Content y"}) == "UNKNOWN"
    assert classify_tool_operation("shell_command", {"command": "$p='x'; Get-Content $p"}) == "UNKNOWN"
    assert classify_tool_operation("shell_command", {"command": "python inspect.py"}) == "UNKNOWN"
    assert classify_tool_operation("unclassified_tool", {}) == "UNKNOWN"


def test_read_only_git_is_read_but_commit_is_not() -> None:
    assert classify_tool_operation("shell_command", {"command": "git status --short"}) == "READ"
    assert classify_tool_operation("shell_command", {"command": "git commit -m test"}) == "UNKNOWN"
