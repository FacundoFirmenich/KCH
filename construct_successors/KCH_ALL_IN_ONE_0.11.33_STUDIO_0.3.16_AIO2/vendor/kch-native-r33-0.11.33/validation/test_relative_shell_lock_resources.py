from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "kch_native_state.py"
SPEC = importlib.util.spec_from_file_location("kch_native_state_under_test", MODULE_PATH)
assert SPEC and SPEC.loader
STATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STATE)


def test_relative_destination_is_extracted_and_matches_prefix(tmp_path: Path) -> None:
    command = (
        "Copy-Item -Path 'construct_successors\\overlay\\*' "
        "-Destination 'native_integration\\personal_marketplace\\plugins\\kch-native-r33' "
        "-Recurse -Force"
    )
    resources = STATE.extract_resources("Bash", {"command": command}, str(tmp_path))
    destination = STATE.normalize_file(
        "native_integration\\personal_marketplace\\plugins\\kch-native-r33", str(tmp_path)
    )
    protected = STATE.normalize_file("native_integration\\personal_marketplace", str(tmp_path))
    assert destination in resources
    assert STATE.lock_matches("PREFIX", protected + "\\", destination)


def test_absolute_and_literal_path_operands_are_extracted(tmp_path: Path) -> None:
    target = tmp_path / "protected" / "file.txt"
    command = f"Get-Content -LiteralPath '{target}'"
    resources = STATE.extract_resources("Bash", {"command": command}, str(tmp_path))
    assert STATE.normalize_file(str(target), str(tmp_path)) in resources
