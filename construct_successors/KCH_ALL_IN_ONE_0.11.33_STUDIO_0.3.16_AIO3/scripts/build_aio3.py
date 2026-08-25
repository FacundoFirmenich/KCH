from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BASE_NAME = "KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2"
NAME = "KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO3"
PLUGIN_NAME = "kch-all-in-one-0-11-33"
PLUGIN_VERSION = "0.11.33-aio.3"
BASE_SHA256 = "be9ce17553ac534fbe66c5764abcc9e30b630ff5a04f16a73570b7264fdae78b"
FIXED_TIME = (2026, 8, 25, 0, 0, 0)
CLOSURE_HOOK = "kch_substantive_closure.py"
CLINE_BEGIN = "<!-- KCH-SUBSTANTIVE-CLOSURE-V1:BEGIN -->"
CLINE_END = "<!-- KCH-SUBSTANTIVE-CLOSURE-V1:END -->"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_digest(root: Path) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        rel = path.relative_to(root).as_posix()
        item_hash = sha256(path)
        size = path.stat().st_size
        rows.append({"path": rel, "bytes": size, "sha256": item_hash})
        digest.update(rel.encode() + b"\0" + item_hash.encode() + b"\0" + str(size).encode() + b"\n")
    return {"files": len(rows), "bytes": sum(row["bytes"] for row in rows), "tree_sha256": digest.hexdigest()}


def safe_extract(archive: zipfile.ZipFile, target: Path) -> None:
    root = target.resolve()
    for item in archive.infolist():
        destination = (target / item.filename).resolve()
        if destination != root and root not in destination.parents:
            raise RuntimeError(f"unsafe archive path: {item.filename}")
    archive.extractall(target)


def copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(source)
    shutil.copytree(source, target, dirs_exist_ok=True)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def replace_text(path: Path, replacements: list[tuple[str, str]]) -> None:
    text = path.read_text(encoding="utf-8")
    for old, new in replacements:
        if old not in text:
            raise RuntimeError(f"required predecessor token absent in {path}: {old}")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8", newline="\n")


def configure_hooks(plugin: Path) -> None:
    path = plugin / "hooks" / "hooks.json"
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    hook = {
        "type": "command",
        "command": 'python3 -B "$PLUGIN_ROOT/scripts/kch_substantive_closure.py"',
        "commandWindows": '& "C:\\Python314\\python.exe" -B -X utf8 "$env:PLUGIN_ROOT\\scripts\\kch_substantive_closure.py"',
        "timeout": 10,
        "statusMessage": "KCH aplica el contrato de cierre sustantivo",
        "additionalContextLimit": 2200,
    }
    for event in ("SessionStart", "UserPromptSubmit"):
        groups = payload["hooks"].get(event)
        if not groups:
            raise RuntimeError(f"missing lifecycle group: {event}")
        commands = groups[0].setdefault("hooks", [])
        commands[:] = [item for item in commands if CLOSURE_HOOK not in str(item.get("command", ""))]
        commands.append(dict(hook))
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def configure_plugin(package: Path) -> Path:
    plugin = package / "adapters" / "codex" / "marketplace" / "plugins" / PLUGIN_NAME
    if not plugin.is_dir():
        raise FileNotFoundError(plugin)
    copy_tree(ROOT / "overlay" / "codex", plugin)
    config = plugin / "config"
    config.mkdir(exist_ok=True)
    for name in ("substantive_closure.v1.json", "construct_persistence.v1.json"):
        shutil.copy2(ROOT / "contracts" / name, config / name)
    configure_hooks(plugin)
    manifest_path = plugin / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["version"] = PLUGIN_VERSION
    manifest["description"] = "KCH All-in-One with universal substantive closure and governed CONSTRUCT persistence."
    interface = manifest.setdefault("interface", {})
    interface["longDescription"] = (
        "KCH nativo con cierre sustantivo universal y CONSTRUCT persistente sólo en la instalación seleccionada, "
        "las instalaciones registradas o una rama no predeterminada de un fork verificado."
    )
    interface["defaultPrompt"] = (
        "Gobierna la tarea con KCH; cierra checkpoints materiales de forma sustantiva y consulta el ámbito antes de persistir CONSTRUCT."
    )
    capabilities = interface.setdefault("capabilities", [])
    for capability in ("substantive-closure", "governed-construct-persistence"):
        if capability not in capabilities:
            capabilities.append(capability)
    write_json(manifest_path, manifest)
    readme = plugin / "README.md"
    text = readme.read_text(encoding="utf-8") if readme.is_file() else "# KCH All-in-One\n"
    block = (
        "\n## AIO3 governance contracts\n\n"
        "Every material closure is explanatory; archivistic mechanics are supporting evidence. "
        "Installed CONSTRUCT can persist only within a user-selected local scope or a verified fork branch and never into the official upstream.\n"
    )
    if "## AIO3 governance contracts" not in text:
        text += block
    readme.write_text(text, encoding="utf-8", newline="\n")
    return plugin


def configure_cline(package: Path) -> None:
    path = package / "adapters" / "cline-vscode" / "kch-all-in-one.md"
    text = path.read_text(encoding="utf-8")
    block = f'''\n{CLINE_BEGIN}\n\n## Cierre sustantivo y persistencia CONSTRUCT\n\nTodo checkpoint o cierre material termina con uno o dos párrafos explicativos en castellano: objetivo, posición, resultado, significado, frontera de evidencia, incertidumbre, reparabilidad, consecuencia y próxima acción crítica. Una tabla compacta sólo se usa si aclara scoring o comparación. La archivística se concentra en un único MD/TXT y se referencia en una línea; hashes, manifests e inventarios no prueban por sí mismos validez, corrección, completitud, utilidad ni autoridad. No firmes ni cierres con ceremonial, etiquetas o inventarios.\n\nAntes de persistir CONSTRUCT, consulta y elige `LOCAL_CURRENT_INSTALLATION`, `LOCAL_ALL_REGISTERED_INSTALLATIONS` o `PUBLIC_FORK_BRANCH`. Las decisiones son exactamente `Sí`, `No`, `Nunca en esta sesión` y `Siempre en esta sesión`; una política de sesión no crea autoridad futura. El paquete instalable nunca puede escribir en `FacundoFirmenich/KCH` ni en una rama predeterminada. La persistencia pública exige GitHub autenticado, fork verificado y una rama propia no predeterminada.\n\n{CLINE_END}\n'''
    if CLINE_BEGIN in text or CLINE_END in text:
        start = text.index(CLINE_BEGIN)
        end = text.index(CLINE_END, start) + len(CLINE_END)
        text = text[:start].rstrip() + "\n\n" + block.strip() + text[end:]
    else:
        text = text.rstrip() + "\n" + block
    path.write_text(text, encoding="utf-8", newline="\n")


def configure_installer(package: Path) -> None:
    installer = package / "install_all_in_one.py"
    replace_text(installer, [(f'NAME = "{BASE_NAME}"', f'NAME = "{NAME}"')])
    text = installer.read_text(encoding="utf-8")
    old = '''    custody_receipt = runtime_root / ".kch-aio2-custody" / "INSTALLATION_RECEIPT.json"\n    aio1_custody_receipt = runtime_root / ".kch-aio1-custody" / "INSTALLATION_RECEIPT.json"\n    prior_source = (\n        custody_receipt\n        if custody_receipt.exists()\n        else aio1_custody_receipt\n        if aio1_custody_receipt.exists()\n        else receipt\n        if receipt.exists()\n        else None\n    )'''
    new = '''    custody_receipt = runtime_root / ".kch-aio3-custody" / "INSTALLATION_RECEIPT.json"\n    aio2_custody_receipt = runtime_root / ".kch-aio2-custody" / "INSTALLATION_RECEIPT.json"\n    aio1_custody_receipt = runtime_root / ".kch-aio1-custody" / "INSTALLATION_RECEIPT.json"\n    prior_source = (\n        custody_receipt\n        if custody_receipt.exists()\n        else aio2_custody_receipt\n        if aio2_custody_receipt.exists()\n        else aio1_custody_receipt\n        if aio1_custody_receipt.exists()\n        else receipt\n        if receipt.exists()\n        else None\n    )'''
    if old not in text:
        raise RuntimeError("AIO2 custody predecessor block changed")
    text = text.replace(old, new)
    text = text.replace("Transactional installer for KCH AIO2", "Transactional installer for KCH AIO3")
    text = text.replace("receipts-aio2", "receipts-aio3").replace("kch-aio2-receipts", "kch-aio3-receipts")
    text = text.replace(".tmp.kch-aio2", ".tmp.kch-aio3")
    text = text.replace('workspace / ".cline" / "kch-aio2"', 'workspace / ".cline" / "kch-aio3"')
    text = text.replace('workspace / ".cline" / "hooks" / "_kch-aio2"', 'workspace / ".cline" / "hooks" / "_kch-aio3"')
    old_stage = '''    shutil.copytree(source_plugin / "scripts", native_stage / "scripts")\n    shutil.copytree(source_plugin / "runtime", native_stage / "runtime")'''
    new_stage = '''    shutil.copytree(source_plugin / "scripts", native_stage / "scripts")\n    shutil.copytree(source_plugin / "runtime", native_stage / "runtime")\n    shutil.copytree(source_plugin / "config", native_stage / "config")'''
    if old_stage not in text:
        raise RuntimeError("AIO2 Cline native staging block changed")
    text = text.replace(old_stage, new_stage)
    text = text.replace(BASE_NAME, NAME)
    installer.write_text(text, encoding="utf-8", newline="\n")

    rollback = package / "rollback_all_in_one.py"
    replace_text(rollback, [(f'NAME = "{BASE_NAME}"', f'NAME = "{NAME}"'), ('ACK = "KCH-AIO2-ROLLBACK"', 'ACK = "KCH-AIO3-ROLLBACK"')])
    text = rollback.read_text(encoding="utf-8").replace("KCH AIO2", "KCH AIO3").replace("kch-aio2", "kch-aio3")
    rollback.write_text(text, encoding="utf-8", newline="\n")

    gate = package / "validation" / "verify_marketplace_projection.py"
    replace_text(gate, [('PLUGIN_VERSION = "0.11.33-aio.2"', f'PLUGIN_VERSION = "{PLUGIN_VERSION}"')])
    text = gate.read_text(encoding="utf-8").replace("AIO2", "AIO3").replace("aio2", "aio3")
    gate.write_text(text, encoding="utf-8", newline="\n")


def write_manifest(package: Path) -> dict[str, Any]:
    rows = []
    for path in sorted(item for item in package.rglob("*") if item.is_file() and item.name != "PACKAGE_MANIFEST.json"):
        rows.append({"path": path.relative_to(package).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)})
    payload = {
        "schema": "kch.aio.package-manifest.v1",
        "package": NAME,
        "files": rows,
        "file_count": len(rows),
        "total_bytes": sum(row["bytes"] for row in rows),
        "automatic_promotion": False,
        "phl_training_executed": False,
    }
    write_json(package / "PACKAGE_MANIFEST.json", payload)
    return payload


def deterministic_zip(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in source.rglob("*") if item.is_file()):
            rel = Path(source.name) / path.relative_to(source)
            info = zipfile.ZipInfo(rel.as_posix(), FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def host_bundle(package: Path, target: Path, host: str) -> None:
    if host == "codex":
        installer = f'''param([string]$RuntimeRoot = "D:\\CodexRuntimes\\kch-aio3", [string]$Marketplace = "$env:USERPROFILE\\.agents\\plugins\\marketplace.json", [string]$ReceiptRoot = "D:\\CodexRuntimes\\kch-aio3-receipts")\n$ErrorActionPreference = "Stop"\n$package = Join-Path $PSScriptRoot "{NAME}"\npy -3 (Join-Path $package "install_all_in_one.py") --package-root $package --runtime-root $RuntimeRoot --hosts codex --codex-marketplace $Marketplace --receipt-root $ReceiptRoot\n'''
        installer_name = "INSTALL_CODEX.ps1"
    else:
        installer = f'''param([Parameter(Mandatory=$true)][string]$Workspace, [Parameter(Mandatory=$true)][string]$ClineSettings, [string]$RuntimeRoot = "D:\\CodexRuntimes\\kch-aio3", [string]$ReceiptRoot = "D:\\CodexRuntimes\\kch-aio3-receipts")\n$ErrorActionPreference = "Stop"\n$package = Join-Path $PSScriptRoot "{NAME}"\npy -3 (Join-Path $package "install_all_in_one.py") --package-root $package --runtime-root $RuntimeRoot --hosts cline --cline-workspace $Workspace --cline-settings $ClineSettings --receipt-root $ReceiptRoot\n'''
        installer_name = "INSTALL_CLINE.ps1"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(item for item in package.rglob("*") if item.is_file()):
            rel = Path(package.name) / path.relative_to(package)
            info = zipfile.ZipInfo(rel.as_posix(), FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())
        info = zipfile.ZipInfo(installer_name, FIXED_TIME)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o100644 << 16
        archive.writestr(info, installer.encode("utf-8"))


def build(base_zip: Path, output: Path) -> dict[str, Any]:
    observed = sha256(base_zip)
    if observed != BASE_SHA256:
        raise RuntimeError(f"AIO2 base digest mismatch: expected {BASE_SHA256}, observed {observed}")
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    package = output / NAME
    if package.exists():
        if package.parent != output or package.name != NAME:
            raise RuntimeError("unsafe AIO3 replacement target")
        shutil.rmtree(package)
    with tempfile.TemporaryDirectory(prefix="kch-aio3-base-", dir=output) as raw:
        temp = Path(raw)
        with zipfile.ZipFile(base_zip) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("AIO2 base ZIP failed CRC")
            safe_extract(archive, temp)
        base = temp / BASE_NAME
        if not base.is_dir() or not (base / "PACKAGE_MANIFEST.json").is_file():
            raise RuntimeError("AIO2 base package root not found")
        base_lineage = tree_digest(base / "lineage")
        shutil.move(str(base), package)
    configure_plugin(package)
    configure_cline(package)
    configure_installer(package)
    copy_tree(ROOT / "contracts", package / "contracts")
    shutil.copy2(ROOT / "docs" / "CIERRE_SUSTANTIVO_AIO3_ES.md", package / "docs" / "CIERRE_SUSTANTIVO_AIO3_ES.md")
    shutil.copy2(ROOT / "CONSTRUCT_RECORD.json", package / "CONSTRUCT_RECORD.json")
    shutil.copy2(ROOT / "README_ES.md", package / "README_ES_AIO3.md")
    shutil.copy2(ROOT / "scripts" / "verify_aio3.py", package / "verify_all_in_one.py")
    after_lineage = tree_digest(package / "lineage")
    if after_lineage != base_lineage:
        raise RuntimeError("immutable R21/R33 lineage changed during AIO3 lowering")
    provenance = {
        "schema": "kch.aio3.provenance.v1",
        "predecessor_release": "v0.11.33-aio.2",
        "predecessor_asset": base_zip.name,
        "predecessor_sha256": observed,
        "lineage_before": base_lineage,
        "lineage_after": after_lineage,
        "lowered_contracts": ["KCH_SUBSTANTIVE_CLOSURE_V1", "KCH_CONSTRUCT_PERSISTENCE_V1"],
        "official_upstream_write_enabled": False,
        "automatic_promotion": False,
    }
    write_json(package / "AIO3_PROVENANCE.json", provenance)
    manifest = write_manifest(package)
    universal = output / f"{NAME}.zip"
    deterministic_zip(package, universal)
    host_bundle(package, output / "KCH_AIO3_CODEX_COMPLETE.zip", "codex")
    host_bundle(package, output / "KCH_AIO3_CLINE_COMPLETE.zip", "cline")
    receipt = {
        "schema": "kch.aio3.build-receipt.v1",
        "package": NAME,
        "predecessor_sha256": observed,
        "universal_zip": universal.name,
        "universal_zip_sha256": sha256(universal),
        "universal_zip_bytes": universal.stat().st_size,
        "file_count": manifest["file_count"],
        "lineage_unchanged": True,
        "official_upstream_write_enabled": False,
        "automatic_promotion": False,
        "phl_training_executed": False,
    }
    write_json(output / "AIO3_BUILD_RECEIPT.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Build KCH AIO3 as a verified delta over immutable AIO2")
    parser.add_argument("--base-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.base_zip.resolve(), args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())