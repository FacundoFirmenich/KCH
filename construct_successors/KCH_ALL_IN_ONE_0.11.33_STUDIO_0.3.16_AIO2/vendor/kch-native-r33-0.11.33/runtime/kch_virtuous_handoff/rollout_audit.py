from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .canonical import canonical_bytes, sha256_file
from .contracts import OBSERVATION_SCHEMA


THREAD = re.compile(r"threadId\s*:\s*['\"]([^'\"]+)['\"]")
CURSOR = re.compile(r"cursor\s*:\s*['\"]([^'\"]+)['\"]")
INCLUDE_OUTPUTS = re.compile(r"includeOutputs\s*:\s*(true|false)")
TOOL_CALL = re.compile(r"tools\.([A-Za-z0-9_]+)\s*\(")

READ_ONLY_NESTED_TOOLS = {
    "codex_app__read_thread",
    "codex_app__read_thread_terminal",
    "get_goal",
    "list_mcp_resource_templates",
    "list_mcp_resources",
    "read_mcp_resource",
    "view_image",
}

SHELL_MUTATION_MARKERS = (
    "set-content", "add-content", "clear-content", "out-file", "tee-object",
    "new-item", "remove-item", "move-item", "copy-item", "rename-item",
    "start-process", "stop-process", "invoke-webrequest", "invoke-restmethod",
    "git add", "git commit", "git push", "git checkout", "git reset",
    "gh ", "pip install", "npm install", "python ", "python.exe",
    "cmd.exe", "powershell.exe", "pwsh ", "taskkill", "::write", "writeall",
    ".unlink(", ".mkdir(", ".replace(", "open(",
)


def _json_object_from_text(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        value = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _exec_has_material_capability(source: str) -> bool:
    """Fail closed when an exec cell invokes anything beyond attested readers."""

    tools = set(TOOL_CALL.findall(source))
    unknown = tools - READ_ONLY_NESTED_TOOLS - {"shell_command"}
    if unknown:
        return True
    if "shell_command" in tools:
        lower = source.casefold()
        return any(marker in lower for marker in SHELL_MUTATION_MARKERS)
    return False


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} no contiene objeto JSON")
    return value


def audit_rollout(
    rollout_path: Path,
    contract_path: Path,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    contract = _load(contract_path)
    calls: list[dict[str, Any]] = []
    material_actions: list[dict[str, Any]] = []
    final_receipts: list[str] = []
    outputs_by_call: dict[str, str] = {}
    destination_thread_id: str | None = None
    with rollout_path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            row = json.loads(line)
            payload = row.get("payload", {})
            if row.get("type") == "session_meta":
                destination_thread_id = str(payload.get("id") or payload.get("session_id") or "")
            if row.get("type") != "response_item":
                continue
            if payload.get("type") == "custom_tool_call_output":
                parts = payload.get("output", [])
                if isinstance(parts, list):
                    outputs_by_call[str(payload.get("call_id", ""))] = "".join(
                        str(part.get("text", "")) for part in parts if isinstance(part, dict)
                    )
                else:
                    outputs_by_call[str(payload.get("call_id", ""))] = str(parts)
                continue
            if payload.get("type") == "custom_tool_call" and payload.get("name") == "exec":
                source = str(payload.get("input", ""))
                if "codex_app__read_thread" in source:
                    thread = THREAD.search(source)
                    cursor = CURSOR.search(source)
                    outputs = INCLUDE_OUTPUTS.search(source)
                    calls.append({
                        "line": line_number,
                        "call_id": payload.get("call_id"),
                        "thread_id": thread.group(1) if thread else None,
                        "cursor": cursor.group(1) if cursor else None,
                        "include_outputs": outputs.group(1) == "true" if outputs else None,
                    })
                if _exec_has_material_capability(source):
                    material_actions.append({"line": line_number, "name": "exec", "call_id": payload.get("call_id")})
            elif payload.get("type") == "custom_tool_call":
                name = str(payload.get("name", ""))
                if name != "wait":
                    material_actions.append({"line": line_number, "name": name, "call_id": payload.get("call_id")})
            if payload.get("type") == "message" and payload.get("role") == "assistant":
                for content in payload.get("content", []):
                    if content.get("type") == "output_text" and "kch.virtuous-handoff.destination-receipt" in str(content.get("text", "")):
                        final_receipts.append(str(content["text"]))

    emitted_sources: dict[str, dict[str, Any]] = {}
    for call in calls:
        raw_output = outputs_by_call.get(str(call["call_id"]), "")
        marker = raw_output.find("Output:\n")
        candidate = raw_output[marker + len("Output:\n"):].strip() if marker >= 0 else raw_output.strip()
        try:
            value = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        rows = value if isinstance(value, list) else [value]
        for row in rows:
            if isinstance(row, dict) and isinstance(row.get("source_id"), str) and isinstance(row.get("pages"), list):
                emitted_sources[row["source_id"]] = row

    trace_rows = []
    all_pass = True
    for source in contract["sources"]:
        thread_id = source["source_uri"].rsplit("/", 1)[-1]
        observed = [call for call in calls if call["thread_id"] == thread_id]
        expected_cursors = [page["requested_cursor"] for page in source["page_receipts"]]
        emitted = emitted_sources.get(source["source_id"])
        if emitted is not None:
            emitted_pages = emitted["pages"]
            emitted_pairs = [
                (page.get("requested_cursor"), page.get("next_cursor"))
                for page in emitted_pages if isinstance(page, dict)
            ]
            expected_pairs = [
                (page["requested_cursor"], page["next_cursor"])
                for page in source["page_receipts"]
            ]
            passed = emitted_pairs == expected_pairs and bool(emitted_pages) and emitted_pages[-1].get("has_more") is False
            matched_cursors = [pair[0] for pair in emitted_pairs] if passed else []
        else:
            passed = False
            matched_cursors = []
        position = 0
        matched: list[dict[str, Any]] = []
        if not passed:
            for call in observed:
                if position < len(expected_cursors) and call["cursor"] == expected_cursors[position]:
                    matched.append(call)
                    position += 1
            passed = position == len(expected_cursors)
            matched_cursors = [call["cursor"] for call in matched]
        all_pass = all_pass and passed
        trace_rows.append({
            "source_id": source["source_id"],
            "source_uri": source["source_uri"],
            "expected_pages": len(expected_cursors),
            "observed_read_calls": len(observed),
            "matched_cursor_chain": matched_cursors,
            "native_calls_observed": passed,
            "eof_observed": passed,
            "page_receipts": source["page_receipts"] if passed else [],
            "required_item_ids_observed": source.get("required_item_ids", []) if passed else [],
            "acknowledged_bounded_tool_outputs": source.get("truncation_signal_count", 0),
        })
    receipt_exactly_observed = False
    receipt_sha256 = None
    if receipt_path is not None:
        receipt = _load(receipt_path)
        expected = canonical_bytes(receipt)
        receipt_sha256 = sha256_file(receipt_path)
        receipt_exactly_observed = any(
            (parsed := _json_object_from_text(text)) is not None and canonical_bytes(parsed) == expected
            for text in final_receipts
        )
    passed = all_pass and not material_actions and bool(final_receipts)
    if receipt_path is not None:
        passed = passed and receipt_exactly_observed
    result = {
        "schema": OBSERVATION_SCHEMA if receipt_path is not None else "kch.virtuous-handoff.rollout-audit.v0.2.2",
        "passed": passed,
        "destination_thread_id": destination_thread_id,
        "rollout_path": str(rollout_path.resolve()),
        "read_trace_passed": all_pass,
        "read_call_count": len(calls),
        "read_traces": trace_rows,
        "pre_receipt_material_actions": material_actions,
        "receipt_messages_observed": len(final_receipts),
    }
    if receipt_path is not None:
        result["receipt_sha256"] = receipt_sha256
        result["receipt_exactly_observed"] = receipt_exactly_observed
    return result
