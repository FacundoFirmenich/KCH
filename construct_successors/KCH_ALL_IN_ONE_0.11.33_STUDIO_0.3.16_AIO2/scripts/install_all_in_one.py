from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


NAME = "KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2"
PLUGIN_NAME = "kch-all-in-one-0-11-33"


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return default
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON object required: {path}")
    return value


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp.kch-aio2")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def backup_file(path: Path, receipt_root: Path, label: str) -> str | None:
    if not path.exists():
        return None
    receipt_root.mkdir(parents=True, exist_ok=True)
    target = receipt_root / f"{label}.{now_stamp()}.bak"
    shutil.copy2(path, target)
    return str(target)


def governed_json_write(path: Path, value: dict[str, Any], receipt_root: Path, label: str) -> dict[str, Any]:
    desired = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    before = sha256(path) if path.exists() else None
    if path.exists() and path.read_bytes() == desired:
        return {"before_sha256": before, "after_sha256": before, "backup": None, "changed": False}
    backup = backup_file(path, receipt_root, label)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp.kch-aio2")
    temp.write_bytes(desired)
    os.replace(temp, path)
    return {
        "before_sha256": before,
        "after_sha256": sha256(path),
        "backup": backup,
        "changed": True,
    }


def tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        h.update(rel.encode("utf-8") + b"\0" + sha256(path).encode("ascii") + b"\n")
    return h.hexdigest()

def mis_evidence_root(runtime_root: Path) -> Path:
    return runtime_root / "share" / "kch-aio1" / "mis-0.3.1"


def install_mis_evidence(package: Path, runtime_root: Path) -> dict[str, Any]:
    source = package / "sources" / "mis-0.3.1"
    target = mis_evidence_root(runtime_root)
    stage = target.parent / f".{target.name}.stage.{os.getpid()}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for name in ("evidence", "results", "vendor"):
        source_part = source / name
        if not source_part.is_dir():
            raise FileNotFoundError(source_part)
        shutil.copytree(source_part, stage / name)
    desired_hash = tree_hash(stage)
    if target.is_dir() and tree_hash(target) == desired_hash:
        shutil.rmtree(stage)
        changed = False
    else:
        if target.exists():
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
        target.parent.mkdir(parents=True, exist_ok=True)
        os.replace(stage, target)
        changed = True
    files = [path for path in target.rglob("*") if path.is_file()]
    return {
        "root": str(target.resolve()),
        "tree_sha256": tree_hash(target),
        "files": len(files),
        "bytes": sum(path.stat().st_size for path in files),
        "changed": changed,
    }



def runtime_python(runtime_root: Path) -> Path:
    return runtime_root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def runtime_command(runtime_root: Path, name: str) -> Path:
    base = runtime_root / ("Scripts" if os.name == "nt" else "bin")
    candidates = [base / name, base / f"{name}.exe", base / f"{name}.cmd"]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(f"runtime command not found: {name}")


def install_runtime(package: Path, runtime_root: Path, python: str) -> dict[str, Any]:
    wheelhouse = package / "wheelhouse"
    if not wheelhouse.is_dir():
        raise FileNotFoundError(wheelhouse)
    py = runtime_python(runtime_root)
    expanded_runtime = str(runtime_root.resolve())
    if os.name == "nt" and not py.exists() and len(expanded_runtime) > 180:
        raise RuntimeError(
            "Windows runtime path is too long for reliable venv/ensurepip creation "
            f"({len(expanded_runtime)} characters). Choose a short --runtime-root, for example "
            r"C:\KCH\aio1 or C:\Users\<user>\.codex\runtimes\kch-aio1."
        )
    if not py.exists():
        runtime_root.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run([python, "-m", "venv", str(runtime_root)], check=True)
    subprocess.run(
        [
            str(py),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(wheelhouse),
            "--upgrade",
            "kwancode-harness==0.11.0",
            "kch-csi-studio-extension-fabric==0.3.16",
            "kch-virtuous-handoff==0.2.2",
        ],
        check=True,
    )
    mis_evidence = install_mis_evidence(package, runtime_root)
    smoke = (
        "import importlib,json;"
        "mods=['kwancode_harness','kch_studio','kch_virtuous_handoff','kch_mis_v03_integration',"
        "'kch_phl_integration','kch_learning','kch_sco',"
        "'kch_rigor_governor','kwanprompts','mis_v03'];"
        "print(json.dumps({m:bool(importlib.import_module(m)) for m in mods},sort_keys=True))"
    )
    result = subprocess.run([str(py), "-X", "utf8", "-c", smoke], check=True, capture_output=True, text=True)
    return {
        "runtime_root": str(runtime_root.resolve()),
        "python": str(py.resolve()),
        "smoke": json.loads(result.stdout),
        "mis_evidence": mis_evidence,
        "policy": "CLOUD_FIRST_LOCAL_MINIMAL",
    }


def render_codex_plugin(plugin: Path, runtime_root: Path) -> None:
    preflight = str(runtime_command(runtime_root, "kch-codex-preflight-mcp"))
    bootstrap = str(runtime_command(runtime_root, "kch-codex-bootstrap-mcp"))
    mis_root = str(mis_evidence_root(runtime_root).resolve())
    mis_runtime = str((runtime_root / "state" / "mis").resolve())
    env = {"KCH_MIS_ROOT": mis_root, "KCH_MIS_RUNTIME": mis_runtime}
    atomic_json(
        plugin / ".mcp.json",
        {
            "mcpServers": {
                "kch-codex-preflight": {
                    "command": preflight,
                    "args": [],
                    "env": env,
                },
                "kch-codex-bootstrap": {
                    "command": bootstrap,
                    "args": [],
                    "env": env,
                },
            }
        },
    )
    hooks_path = plugin / "hooks" / "hooks.json"
    hooks = load_json(hooks_path, {})
    py = str(runtime_python(runtime_root).resolve())

    def rewrite(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: rewrite(item) for key, item in value.items()}
        if isinstance(value, list):
            return [rewrite(item) for item in value]
        if isinstance(value, str) and "C:\\Python314\\python.exe" in value:
            return value.replace("C:\\Python314\\python.exe", py)
        return value

    atomic_json(hooks_path, rewrite(hooks))


def replace_directory(source: Path, target: Path, receipt_root: Path) -> dict[str, Any]:
    target.parent.mkdir(parents=True, exist_ok=True)
    source_hash = tree_hash(source)
    target_existed = target.exists()
    if target_existed and tree_hash(target) == source_hash:
        return {
            "target": str(target),
            "changed": False,
            "tree_sha256": source_hash,
            "backup": None,
            "target_existed_before": True,
        }
    backup = None
    if target.exists():
        backup_path = receipt_root / f"{target.name}.{now_stamp()}.bak"
        if backup_path.exists():
            raise FileExistsError(backup_path)
        shutil.copytree(target, backup_path)
        backup = str(backup_path)
    stage = target.parent / f".{target.name}.stage.{now_stamp()}"
    if stage.exists():
        shutil.rmtree(stage)
    shutil.copytree(source, stage)
    if target.exists():
        shutil.rmtree(target)
    os.replace(stage, target)
    return {
        "target": str(target),
        "changed": True,
        "tree_sha256": tree_hash(target),
        "backup": backup,
        "target_existed_before": target_existed,
    }


def deploy_codex(package: Path, runtime_root: Path, marketplace_path: Path, receipt_root: Path) -> dict[str, Any]:
    source_plugin = (
        package
        / "adapters"
        / "codex"
        / "marketplace"
        / "plugins"
        / PLUGIN_NAME
    )
    if not source_plugin.is_dir():
        raise FileNotFoundError(source_plugin)
    # Keep the rendered plugin staging tree beside the deliberately short
    # runtime path. A receipt directory can be archival and deeply nested;
    # using it as staging crosses MAX_PATH on Windows before Codex is touched.
    stage_source = runtime_root.parent / f".{PLUGIN_NAME}.rendered-{os.getpid()}"
    if stage_source.exists():
        shutil.rmtree(stage_source)
    shutil.copytree(source_plugin, stage_source)
    render_codex_plugin(stage_source, runtime_root)
    # Marketplace sources are relative to marketplace.json itself. AIO1
    # escaped that root and wrote a plugin copy Codex never served.
    plugin_target = marketplace_path.parent / "plugins" / PLUGIN_NAME
    deployed = replace_directory(stage_source, plugin_target, receipt_root)
    shutil.rmtree(stage_source)

    market = load_json(
        marketplace_path,
        {"name": "personal", "interface": {"displayName": "Personal"}, "plugins": []},
    )
    plugins = market.setdefault("plugins", [])
    if not isinstance(plugins, list):
        raise ValueError("marketplace plugins must be a list")
    entry = {
        "name": PLUGIN_NAME,
        "source": {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"},
        "policy": {"installation": "AVAILABLE", "authentication": "ON_USE"},
        "category": "developer-tools",
    }
    found = False
    for index, row in enumerate(plugins):
        if isinstance(row, dict) and row.get("name") == PLUGIN_NAME:
            plugins[index] = entry
            found = True
            break
    if not found:
        plugins.append(entry)
    write = governed_json_write(marketplace_path, market, receipt_root, "codex-marketplace")
    return {
        "plugin": deployed,
        "marketplace": str(marketplace_path.resolve()),
        "marketplace_before_sha256": write["before_sha256"],
        "marketplace_after_sha256": write["after_sha256"],
        "marketplace_backup": write["backup"],
        "marketplace_changed": write["changed"],
        "marketplace_plugin_target": str(plugin_target.resolve()),
        "marketplace_source_resolution": "RELATIVE_TO_MARKETPLACE_JSON",
        "hooks": "NATIVE_SINGLE_R33_LIFECYCLE",
        "mcp": ["kch-codex-preflight", "kch-codex-bootstrap"],
    }


CLINE_HOOKS = (
    "TaskStart",
    "TaskResume",
    "TaskCancel",
    "TaskComplete",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "PreCompact",
)


def governed_bytes_write(path: Path, desired: bytes, receipt_root: Path, label: str) -> dict[str, Any]:
    before = sha256(path) if path.exists() else None
    if path.exists() and path.read_bytes() == desired:
        return {
            "kind": "file",
            "label": label,
            "target": str(path.resolve()),
            "before_sha256": before,
            "after_sha256": before,
            "backup": None,
            "changed": False,
        }
    backup = backup_file(path, receipt_root, label)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp.kch-aio2")
    temp.write_bytes(desired)
    os.replace(temp, path)
    return {
        "kind": "file",
        "label": label,
        "target": str(path.resolve()),
        "before_sha256": before,
        "after_sha256": sha256(path),
        "backup": backup,
        "changed": True,
    }


def deploy_cline(
    package: Path,
    runtime_root: Path,
    settings_path: Path,
    workspace: Path,
    receipt_root: Path,
) -> dict[str, Any]:
    settings = load_json(settings_path, {"mcpServers": {}})
    servers = settings.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError("mcpServers must be an object")
    server = {
        "command": str(runtime_command(runtime_root, "kch-super-mcp-studio")),
        "args": [],
        "disabled": False,
        "autoApprove": [],
        "env": {
            "KCH_MIS_ROOT": str(mis_evidence_root(runtime_root).resolve()),
            "KCH_MIS_RUNTIME": str((runtime_root / "state" / "mis").resolve()),
        },
    }
    before_servers = sorted(servers)
    servers["kch-all-in-one-super-mcp"] = server
    write = governed_json_write(settings_path, settings, receipt_root, "cline-mcp-settings")
    after_servers = sorted(load_json(settings_path, {})["mcpServers"])

    source_plugin = (
        package
        / "adapters"
        / "codex"
        / "marketplace"
        / "plugins"
        / PLUGIN_NAME
    )
    source_adapter = package / "adapters" / "cline-vscode"
    if not source_plugin.is_dir() or not source_adapter.is_dir():
        raise FileNotFoundError("Cline projection sources are incomplete")

    components: list[dict[str, Any]] = []
    source_rule = source_adapter / "kch-all-in-one.md"
    target_rule = workspace / ".clinerules" / "kch-all-in-one.md"
    components.append(
        governed_bytes_write(target_rule, source_rule.read_bytes(), receipt_root, "cline-rule")
    )

    native_stage = runtime_root.parent / f".{PLUGIN_NAME}.cline-native-{os.getpid()}"
    if native_stage.exists():
        shutil.rmtree(native_stage)
    native_stage.mkdir(parents=True)
    shutil.copytree(source_plugin / "scripts", native_stage / "scripts")
    shutil.copytree(source_plugin / "runtime", native_stage / "runtime")
    native_target = workspace / ".cline" / "kch-aio2" / "native"
    native_row = replace_directory(native_stage, native_target, receipt_root)
    native_row.update({"kind": "directory", "label": "cline-native-projection"})
    components.append(native_row)
    shutil.rmtree(native_stage)

    bridge_source = source_adapter / "hooks"
    bridge_target = workspace / ".cline" / "hooks" / "_kch-aio2"
    bridge_row = replace_directory(bridge_source, bridge_target, receipt_root)
    bridge_row.update({"kind": "directory", "label": "cline-hook-bridge"})
    components.append(bridge_row)

    template = (bridge_source / "kch-cline-hook.ps1.template").read_text(encoding="utf-8")
    py = str(runtime_python(runtime_root).resolve()).replace("'", "''")
    bridge = str((bridge_target / "kch_cline_hook_bridge.py").resolve()).replace("'", "''")
    rendered = template.replace("__KCH_RUNTIME_PYTHON__", py).replace("__KCH_CLINE_BRIDGE__", bridge)
    for event in CLINE_HOOKS:
        components.append(
            governed_bytes_write(
                workspace / ".cline" / "hooks" / f"{event}.ps1",
                rendered.encode("utf-8"),
                receipt_root,
                f"cline-hook-{event}",
            )
        )

    skills_source = source_plugin / "skills"
    if not skills_source.is_dir():
        raise FileNotFoundError(skills_source)
    skill_names: list[str] = []
    for source_skill in sorted(path for path in skills_source.iterdir() if path.is_dir()):
        skill_names.append(source_skill.name)
        row = replace_directory(
            source_skill,
            workspace / ".cline" / "skills" / source_skill.name,
            receipt_root,
        )
        row.update({"kind": "directory", "label": f"cline-skill-{source_skill.name}"})
        components.append(row)

    return {
        "settings": str(settings_path.resolve()),
        "settings_before_sha256": write["before_sha256"],
        "settings_after_sha256": write["after_sha256"],
        "settings_backup": write["backup"],
        "settings_changed": write["changed"],
        "preserved_server_names": [name for name in before_servers if name in after_servers],
        "server": "kch-all-in-one-super-mcp",
        "components": components,
        "rule": str(target_rule.resolve()),
        "hooks_layout": ".cline/hooks",
        "hooks_installed": list(CLINE_HOOKS),
        "skills_layout": ".cline/skills",
        "skills_installed": skill_names,
        "native_projection": str(native_target.resolve()),
        "host_activation_claim": "PENDING_USER_CLINE_SMOKE",
    }


def _component_origin(
    current: dict[str, Any],
    prior: dict[str, Any] | None,
    legacy_backup: str | None = None,
) -> None:
    if isinstance(prior, dict) and prior:
        if "rollback_origin_existed" in prior:
            existed = bool(prior["rollback_origin_existed"])
            backup = prior.get("rollback_origin_backup")
        else:
            backup = (
                prior.get("rollback_origin_backup")
                if "rollback_origin_backup" in prior
                else prior.get("backup")
            )
            existed = bool(prior.get("target_existed_before", backup is not None))
    else:
        backup = legacy_backup or current.get("backup")
        if "target_existed_before" in current:
            existed = bool(current["target_existed_before"])
        else:
            existed = bool(current.get("before_sha256") is not None or backup is not None)
    current["rollback_origin_existed"] = existed
    current["rollback_origin_backup"] = backup


def _host_file_origin(
    current: dict[str, Any],
    prior: dict[str, Any],
    prefix: str,
) -> None:
    existed_key = f"{prefix}_rollback_origin_existed"
    backup_key = f"{prefix}_rollback_origin_backup"
    current_before_key = f"{prefix}_before_sha256"
    current_backup_key = f"{prefix}_backup"
    if existed_key in prior:
        existed = bool(prior[existed_key])
        backup = prior.get(backup_key)
    elif prior:
        backup = prior.get(backup_key) if backup_key in prior else prior.get(current_backup_key)
        existed = bool(prior.get(current_before_key) is not None or backup is not None)
    else:
        backup = current.get(current_backup_key)
        existed = bool(current.get(current_before_key) is not None or backup is not None)
    current[existed_key] = existed
    current[backup_key] = backup


def preserve_rollback_origins(current: dict[str, Any], prior: dict[str, Any] | None) -> None:
    prior_hosts = prior.get("host_results", {}) if isinstance(prior, dict) else {}
    current_hosts = current.get("host_results", {})
    for host_name, host in current_hosts.items():
        if not isinstance(host, dict):
            continue
        prior_host = prior_hosts.get(host_name, {}) if isinstance(prior_hosts, dict) else {}
        prior_host = prior_host if isinstance(prior_host, dict) else {}
        if host_name == "codex":
            plugin = host.get("plugin", {})
            old_plugin = prior_host.get("plugin", {})
            if isinstance(plugin, dict):
                _component_origin(plugin, old_plugin if isinstance(old_plugin, dict) else None)
            _host_file_origin(host, prior_host, "marketplace")
        elif host_name == "cline":
            _host_file_origin(host, prior_host, "settings")
            current_components = host.get("components", [])
            prior_components = prior_host.get("components", [])
            prior_by_label = {
                row.get("label"): row
                for row in prior_components
                if isinstance(row, dict) and row.get("label")
            } if isinstance(prior_components, list) else {}
            if isinstance(current_components, list):
                for component in current_components:
                    if not isinstance(component, dict):
                        continue
                    legacy_rule = None
                    if component.get("label") == "cline-rule":
                        legacy_rule = (
                            prior_host.get("rule_rollback_origin_backup")
                            or prior_host.get("rule_backup")
                        )
                    old = prior_by_label.get(component.get("label"))
                    _component_origin(
                        component,
                        old if isinstance(old, dict) else None,
                        legacy_backup=legacy_rule,
                    )

def main() -> int:
    parser = argparse.ArgumentParser(description="Transactional installer for KCH AIO2")
    parser.add_argument("--package-root", type=Path, default=Path(__file__).absolute().parent)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--hosts", nargs="+", choices=["codex", "cline"], required=True)
    parser.add_argument("--codex-marketplace", type=Path)
    parser.add_argument("--cline-settings", type=Path)
    parser.add_argument("--cline-workspace", type=Path)
    parser.add_argument("--receipt-root", type=Path)
    args = parser.parse_args()

    package = args.package_root.absolute()
    if os.name == "nt" and len(str(package)) > 120:
        raise RuntimeError(
            "Windows package root is too long for reliable plugin projection "
            f"({len(str(package))} characters). Extract or link the package to a short root, for example "
            r"C:\KCH\KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2."
        )
    runtime_root = args.runtime_root.absolute()
    receipt_root = (args.receipt_root or runtime_root.parent / "receipts-aio2").absolute()
    if os.name == "nt" and len(str(receipt_root)) > 180:
        raise RuntimeError(
            "Windows receipt path is too long for recoverable tree backups "
            f"({len(str(receipt_root))} characters). Choose a short --receipt-root, for example "
            r"D:\CodexRuntimes\kch-aio2-receipts."
        )
    receipt_root.mkdir(parents=True, exist_ok=True)
    if package.name != NAME or not (package / "PACKAGE_MANIFEST.json").is_file():
        raise RuntimeError(f"invalid package root: {package}")

    receipt = receipt_root / "INSTALLATION_RECEIPT.json"
    custody_receipt = runtime_root / ".kch-aio2-custody" / "INSTALLATION_RECEIPT.json"
    aio1_custody_receipt = runtime_root / ".kch-aio1-custody" / "INSTALLATION_RECEIPT.json"
    prior_source = (
        custody_receipt
        if custody_receipt.exists()
        else aio1_custody_receipt
        if aio1_custody_receipt.exists()
        else receipt
        if receipt.exists()
        else None
    )
    prior_receipt = load_json(prior_source, {}) if prior_source is not None else None
    result: dict[str, Any] = {
        "schema": "kch.aio.installation-receipt.v1",
        "package": NAME,
        "hosts_requested": args.hosts,
        "runtime": install_runtime(package, runtime_root, args.python),
        "host_results": {},
        "live_installation_claim": False,
        "authority_created": False,
        "phl_training_executed": False,
    }
    if "codex" in args.hosts:
        if args.codex_marketplace is None:
            parser.error("--codex-marketplace is required for host codex")
        result["host_results"]["codex"] = deploy_codex(
            package, runtime_root, args.codex_marketplace.absolute(), receipt_root
        )
    if "cline" in args.hosts:
        if args.cline_settings is None or args.cline_workspace is None:
            parser.error("--cline-settings and --cline-workspace are required for host cline")
        result["host_results"]["cline"] = deploy_cline(
            package,
            runtime_root,
            args.cline_settings.absolute(),
            args.cline_workspace.absolute(),
            receipt_root,
        )
    preserve_rollback_origins(result, prior_receipt)
    if prior_receipt is not None and prior_source is not None:
        prior_hash = sha256(prior_source)
        history = receipt_root / f"INSTALLATION_RECEIPT.{prior_hash[:16]}.json"
        if not history.exists():
            shutil.copy2(prior_source, history)
        result["predecessor_receipt"] = str(history)
        result["predecessor_receipt_sha256"] = prior_hash
    custody_receipt.parent.mkdir(parents=True, exist_ok=True)
    if custody_receipt.exists():
        custody_prior_hash = sha256(custody_receipt)
        custody_history = custody_receipt.parent / (
            f"INSTALLATION_RECEIPT.{custody_prior_hash[:16]}.json"
        )
        if not custody_history.exists():
            shutil.copy2(custody_receipt, custody_history)
        result["custody_predecessor_receipt"] = str(custody_history)
        result["custody_predecessor_receipt_sha256"] = custody_prior_hash
    result["custody_receipt"] = str(custody_receipt)
    atomic_json(custody_receipt, result)
    atomic_json(receipt, result)
    print(json.dumps({**result, "receipt": str(receipt)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
