from __future__ import annotations

import pytest

from kch_instruction_governance.native_lock_patch import classify_native_tool_operation


@pytest.mark.parametrize(
    "command",
    [
        "Get-Content -Raw 'C:\\protected\\SKILL.md'",
        "Get-FileHash 'C:\\protected\\source.py' -Algorithm SHA256",
        "rg -n 'pattern' 'C:\\protected\\source.py'",
        "git status --short",
    ],
)
def test_simple_allowlisted_inspection_is_read(command: str) -> None:
    assert classify_native_tool_operation("shell_command", {"command": command}) == "READ"


@pytest.mark.parametrize(
    "command",
    [
        "Get-Content x; Set-Content x changed",
        "Get-Content x | Set-Content y",
        "python -c \"open('x','w').write('y')\"",
        "Start-Process calc",
        "Remove-Item x",
    ],
)
def test_compound_unknown_or_mutating_command_fails_closed(command: str) -> None:
    assert classify_native_tool_operation("shell_command", {"command": command}) == "MUTATE"


def test_apply_patch_is_mutation() -> None:
    assert classify_native_tool_operation("apply_patch", "*** Begin Patch") == "MUTATE"
