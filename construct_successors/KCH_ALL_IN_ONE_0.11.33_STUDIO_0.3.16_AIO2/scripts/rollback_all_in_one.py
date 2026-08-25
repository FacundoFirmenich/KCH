from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any


NAME = "KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2"
ACK = "KCH-AIO2-ROLLBACK"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_receipt(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict) or value.get("package") != NAME:
        raise RuntimeError(f"invalid KCH AIO2 receipt: {path}")
    if value.get("schema") != "kch.aio.installation-receipt.v1":
        raise RuntimeError(f"unsupported receipt schema: {value.get('schema')}")
    return value


def rollback_operation(backup: Path | None, origin_existed: bool | None) -> str:
    if backup is not None:
        return "RESTORE"
    if origin_existed is True:
        return "PRESERVE_EXISTING_IDENTICAL"
    return "REMOVE_CREATED_TARGET"


def file_action(
    label: str,
    target_value: str | None,
    backup_value: str | None,
    origin_existed: bool | None = None,
) -> dict[str, Any] | None:
    if not target_value:
        return None
    target = Path(target_value).absolute()
    backup = Path(backup_value).absolute() if backup_value else None
    return {
        "kind": "file",
        "label": label,
        "target": str(target),
        "backup": str(backup) if backup else None,
        "operation": rollback_operation(backup, origin_existed),
        "rollback_origin_existed": origin_existed,
        "backup_exists": bool(backup and backup.is_file()),
        "target_exists": target.exists(),
    }


def directory_action(
    label: str,
    target_value: str | None,
    backup_value: str | None,
    origin_existed: bool | None = None,
) -> dict[str, Any] | None:
    if not target_value:
        return None
    target = Path(target_value).absolute()
    backup = Path(backup_value).absolute() if backup_value else None
    return {
        "kind": "directory",
        "label": label,
        "target": str(target),
        "backup": str(backup) if backup else None,
        "operation": rollback_operation(backup, origin_existed),
        "rollback_origin_existed": origin_existed,
        "backup_exists": bool(backup and backup.is_dir()),
        "target_exists": target.exists(),
    }


def plan(receipt: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    hosts = receipt.get("host_results", {})
    codex = hosts.get("codex", {}) if isinstance(hosts, dict) else {}
    cline = hosts.get("cline", {}) if isinstance(hosts, dict) else {}
    if isinstance(codex, dict) and codex:
        plugin = codex.get("plugin", {})
        if isinstance(plugin, dict):
            row = directory_action(
                "codex_plugin",
                plugin.get("target"),
                plugin.get("rollback_origin_backup") or plugin.get("backup"),
                plugin.get("rollback_origin_existed"),
            )
            if row:
                rows.append(row)
        row = file_action(
            "codex_marketplace",
            codex.get("marketplace"),
            codex.get("marketplace_rollback_origin_backup") or codex.get("marketplace_backup"),
            codex.get("marketplace_rollback_origin_existed"),
        )
        if row:
            rows.append(row)
    if isinstance(cline, dict) and cline:
        row = file_action(
            "cline_settings",
            cline.get("settings"),
            cline.get("settings_rollback_origin_backup") or cline.get("settings_backup"),
            cline.get("settings_rollback_origin_existed"),
        )
        if row:
            rows.append(row)
        components = cline.get("components", [])
        if isinstance(components, list) and components:
            for component in components:
                if not isinstance(component, dict):
                    continue
                label = str(component.get("label", "cline_component"))
                target = component.get("target")
                backup = component.get("rollback_origin_backup") or component.get("backup")
                origin_existed = component.get("rollback_origin_existed")
                if component.get("kind") == "directory":
                    row = directory_action(label, target, backup, origin_existed)
                else:
                    row = file_action(label, target, backup, origin_existed)
                if row:
                    rows.append(row)
        else:
            row = file_action(
                "cline_rule",
                cline.get("rule"),
                cline.get("rule_rollback_origin_backup") or cline.get("rule_backup"),
            )
            if row:
                rows.append(row)
    return rows


def replace_file(target: Path, backup: Path | None) -> None:
    if backup is not None:
        if not backup.is_file():
            raise FileNotFoundError(backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        stage = target.with_name(target.name + ".rollback.kch-aio2")
        shutil.copy2(backup, stage)
        os.replace(stage, target)
    elif target.exists():
        target.unlink()


def replace_directory(target: Path, backup: Path | None) -> None:
    stage = target.parent / f".{target.name}.rollback.kch-aio2"
    if stage.exists():
        shutil.rmtree(stage)
    if backup is not None:
        if not backup.is_dir():
            raise FileNotFoundError(backup)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(backup, stage)
    if target.exists():
        shutil.rmtree(target)
    if backup is not None:
        os.replace(stage, target)


def execute(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        if row.get("operation") == "PRESERVE_EXISTING_IDENTICAL":
            continue
        target = Path(row["target"])
        backup = Path(row["backup"]) if row.get("backup") else None
        if row["kind"] == "file":
            replace_file(target, backup)
        elif row["kind"] == "directory":
            replace_directory(target, backup)
        else:
            raise RuntimeError(f"unsupported rollback action: {row}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Receipt-bound rollback for KCH AIO2 host projections")
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--ack")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    receipt_path = args.receipt.absolute()
    receipt = load_receipt(receipt_path)
    rows = plan(receipt)
    result: dict[str, Any] = {
        "schema": "kch.aio.rollback-plan.v1",
        "package": NAME,
        "receipt": str(receipt_path),
        "receipt_sha256": sha256(receipt_path),
        "mode": "APPLY" if args.apply else "DRY_RUN",
        "actions": rows,
        "runtime_policy": "PRESERVE_RUNTIME_FOR_RECOVERY_NO_AUTOMATIC_DELETION",
        "applied": False,
    }
    if args.apply:
        if args.ack != ACK:
            raise RuntimeError(f"rollback requires --ack {ACK}")
        execute(rows)
        result["applied"] = True
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())