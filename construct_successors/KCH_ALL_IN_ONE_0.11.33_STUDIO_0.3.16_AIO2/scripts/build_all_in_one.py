from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(os.environ.get("KCH_AIO_ROOT", str(Path(__file__).absolute().parents[1])))
WORKSPACE = ROOT.parents[1]
NAME = "KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2"
PLUGIN_NAME = "kch-all-in-one-0-11-33"
R21 = Path(os.environ.get("KCH_AIO_R21_ROOT", str(ROOT / "vendor" / "kch-native-r21-0.11.33")))
R33 = Path(os.environ.get("KCH_AIO_R33_ROOT", str(ROOT / "vendor" / "kch-native-r33-0.11.33")))
CORE = WORKSPACE / "work" / "KCH_0.11"
STUDIO = Path(os.environ.get("KCH_AIO_STUDIO_ROOT", str(ROOT / "vendor" / "kch-studio-0.3.16")))
STUDIO_WHEELS = Path(os.environ.get("KCH_AIO_STUDIO_WHEELS", str(WORKSPACE / "work" / "KCH_CSI_STUDIO_EXTENSION_FABRIC_v0.1.0" / "dependency_wheels")))
MIS = ROOT / "vendor" / "KCH_MIS03_REEXTRACT_v0.1.0"
IGNORED_NAMES = {"__pycache__", ".pytest_cache", ".ruff_cache", ".git", "build", "dist", ".venv", "venv"}
IGNORED_SUFFIXES = {".pyc", ".pyo"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def allowed(path: Path) -> bool:
    return not any(part in IGNORED_NAMES for part in path.parts) and path.suffix.lower() not in IGNORED_SUFFIXES


def copy_tree(source: Path, target: Path) -> None:
    if not source.is_dir():
        raise FileNotFoundError(source)
    for item in sorted(source.rglob("*")):
        rel = item.relative_to(source)
        if not allowed(rel):
            continue
        out = target / rel
        if item.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, out)


def copy_source_subset(source: Path, target: Path, neutral_readme: str) -> None:
    for name in ("pyproject.toml", "LICENSE", "LICENSE.md", "LICENSE.txt"):
        src = source / name
        if src.is_file():
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target / name)
    for name in ("src", "tests"):
        src = source / name
        if src.is_dir():
            copy_tree(src, target / name)
    target.mkdir(parents=True, exist_ok=True)
    (target / "README.md").write_text(neutral_readme, encoding="utf-8")


def tree_digest(root: Path) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    h = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        digest = sha256(path)
        size = path.stat().st_size
        rows.append({"path": rel, "size": size, "sha256": digest})
        h.update(rel.encode("utf-8") + b"\0" + digest.encode("ascii") + b"\0" + str(size).encode("ascii") + b"\n")
    return {"files": len(rows), "bytes": sum(int(x["size"]) for x in rows), "tree_sha256": h.hexdigest()}


def safe_reset(path: Path, parent: Path) -> None:
    resolved = Path(os.path.abspath(path))
    expected = Path(os.path.abspath(parent))
    if resolved.parent != expected:
        raise RuntimeError(f"unsafe reset target: {resolved}")
    if resolved.exists():
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True)


def build_wheel(source: Path, wheelhouse: Path, python: str) -> None:
    subprocess.run(
        [python, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--wheel-dir", str(wheelhouse), str(source)],
        check=True,
    )


def collect_wheels(wheelhouse: Path, extra: Path | None = None) -> None:
    candidates = [CORE / "vendor", STUDIO_WHEELS, R33 / "runtime" / "wheels", MIS]
    if extra is not None:
        candidates.append(extra)
    first_party_prefixes = ("kwancode_harness-", "kch_csi_studio_extension_fabric-")
    by_name: dict[str, str] = {p.name.lower(): sha256(p) for p in wheelhouse.glob("*.whl")}
    for base in candidates:
        if not base.exists():
            continue
        for src in sorted(base.rglob("*.whl")):
            key = src.name.lower()
            if extra is not None and base == extra and key.startswith(first_party_prefixes):
                continue
            digest = sha256(src)
            if key in by_name and by_name[key] != digest:
                raise RuntimeError(f"wheel filename collision with different bytes: {src.name}")
            if key not in by_name:
                shutil.copy2(src, wheelhouse / src.name)
                by_name[key] = digest

def configure_plugin(plugin: Path) -> None:
    manifest = {
        "name": PLUGIN_NAME,
        "version": "0.11.33-aio.2",
        "description": "KCH All-in-One: stable R21/R33 lineage, native governance, Studio 0.3.16, Super-MCP and corrected recoverable host projection.",
        "author": {"name": "Facundo Firmenich"},
        "skills": "./skills/",
        "interface": {
            "displayName": "KCH All-in-One 0.11.33",
            "shortDescription": "KCH nativo, Studio y Super-MCP en una proyeccion recuperable.",
            "longDescription": "Unifica la superficie nativa R33, conserva R21/R33, integra Studio 0.3.16 y Super-MCP sin promover ramas posteriores ni ejecutar PHL.",
            "developerName": "KCH",
            "category": "Productivity",
            "capabilities": ["skills", "hooks", "mcp", "runtime", "custody"],
            "defaultPrompt": "Gobierna esta tarea con KCH All-in-One 0.11.33 y usa Studio o Super-MCP solo cuando corresponda.",
        },
        "mcpServers": "./.mcp.json",
    }
    (plugin / ".codex-plugin" / "plugin.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    mcp = {
        "mcpServers": {
            "kch-codex-preflight": {"command": "kch-codex-preflight-mcp", "args": []},
            "kch-codex-bootstrap": {"command": "kch-codex-bootstrap-mcp", "args": []},
        }
    }
    (plugin / ".mcp.json").write_text(json.dumps(mcp, indent=2) + "\n", encoding="utf-8")
    (plugin / "README.md").write_text(
        "# KCH All-in-One 0.11.33\n\nSingle active Codex projection based on stable R33; "
        "R21 and R33 lineage snapshots are preserved at package level. Studio 0.3.16 and "
        "Super-MCP are exposed through governed MCP bootstrap.\n",
        encoding="utf-8",
    )


def configure_rigor_fader(plugin: Path) -> None:
    overlay = ROOT / "adapters" / "codex" / "overlay"
    copy_tree(overlay, plugin)
    hooks_path = plugin / "hooks" / "hooks.json"
    payload = json.loads(hooks_path.read_text(encoding="utf-8-sig"))
    hook = {
        "type": "command",
        "command": 'python3 -B "$PLUGIN_ROOT/scripts/kch_contractual_rigor.py"',
        "commandWindows": '& "C:\\Python314\\python.exe" -B -X utf8 "$env:PLUGIN_ROOT\\scripts\\kch_contractual_rigor.py"',
        "timeout": 10,
        "statusMessage": "KCH calibra rigor contractual",
        "additionalContextLimit": 1000,
    }
    for event in ("SessionStart", "UserPromptSubmit"):
        groups = payload["hooks"][event]
        if not groups:
            raise RuntimeError(f"missing hook group: {event}")
        commands = groups[0].setdefault("hooks", [])
        if not any("kch_contractual_rigor.py" in str(item.get("command", "")) for item in commands):
            commands.append(dict(hook))
    for groups in payload["hooks"].values():
        for group in groups:
            for item in group.get("hooks", []):
                command = str(item.get("command", ""))
                if command.startswith("python3 ") and not command.startswith("python3 -B "):
                    item["command"] = command.replace("python3 ", "python3 -B ", 1)
                windows = str(item.get("commandWindows", ""))
                if " -X utf8 " in windows and " -B -X utf8 " not in windows:
                    item["commandWindows"] = windows.replace(" -X utf8 ", " -B -X utf8 ", 1)
    hooks_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def configure_marketplace(path: Path) -> None:
    data = {
        "name": "kch-all-in-one-local",
        "interface": {"displayName": "KCH All-in-One Local"},
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "source": {"source": "local", "path": f"./plugins/{PLUGIN_NAME}"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_USE"},
                "category": "developer-tools",
            }
        ],
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_manifest(payload: Path) -> dict[str, object]:
    rows = []
    for path in sorted(p for p in payload.rglob("*") if p.is_file() and p.name != "PACKAGE_MANIFEST.json"):
        rows.append({"path": path.relative_to(payload).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)})
    manifest = {
        "schema": "kch.aio.package-manifest.v1",
        "package": NAME,
        "files": rows,
        "file_count": len(rows),
        "total_bytes": sum(int(r["bytes"]) for r in rows),
        "automatic_promotion": False,
        "phl_training_executed": False,
    }
    (payload / "PACKAGE_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def deterministic_zip(payload: Path, target: Path) -> None:
    fixed = (2026, 8, 25, 0, 0, 0)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(p for p in payload.rglob("*") if p.is_file()):
            rel = Path(payload.name) / path.relative_to(payload)
            info = zipfile.ZipInfo(rel.as_posix(), fixed)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--output-root", type=Path, default=ROOT)
    parser.add_argument("--dependency-wheelhouse", type=Path)
    args = parser.parse_args()
    for source in (R21, R33, CORE, STUDIO, MIS):
        if not source.exists():
            raise FileNotFoundError(source)

    output_root = args.output_root.absolute()
    output_root.mkdir(parents=True, exist_ok=True)
    build_root = output_root / "build"
    build_root.mkdir(exist_ok=True)
    payload = build_root / NAME
    safe_reset(payload, build_root)

    for name in ("README_ES.md", "README_EN.md", "CONSTRUCT_RECORD.json"):
        shutil.copy2(ROOT / name, payload / name)
    copy_tree(ROOT / "docs", payload / "docs")
    copy_tree(ROOT / "adapters", payload / "adapters")
    shutil.copy2(ROOT / "scripts" / "install_all_in_one.py", payload / "install_all_in_one.py")
    shutil.copy2(ROOT / "scripts" / "verify_all_in_one.py", payload / "verify_all_in_one.py")
    shutil.copy2(ROOT / "scripts" / "rollback_all_in_one.py", payload / "rollback_all_in_one.py")

    lineage = payload / "lineage"
    copy_tree(R21, lineage / "kch-native-r21-0.11.33")
    copy_tree(R33, lineage / "kch-native-r33-0.11.33")
    copy_source_subset(
        CORE,
        payload / "sources" / "kwancode-harness-0.11.0",
        "# KwanCode Harness 0.11.0\n\nCanonical shared core embedded in KCH All-in-One AIO2.\n",
    )
    copy_source_subset(
        STUDIO,
        payload / "sources" / "kch-studio-0.3.16",
        "# KCH Studio 0.3.16\n\nNeutral source snapshot embedded in KCH All-in-One AIO2.\n",
    )
    copy_tree(MIS, payload / "sources" / "mis-0.3.1")
    validation = payload / "validation"
    validation.mkdir()
    post_gate = STUDIO / "scripts" / "post_install_gate.py"
    if post_gate.is_file():
        shutil.copy2(post_gate, validation / post_gate.name)
    projection_gate = ROOT / "scripts" / "verify_marketplace_projection.py"
    if projection_gate.is_file():
        shutil.copy2(projection_gate, validation / projection_gate.name)

    plugin = payload / "adapters" / "codex" / "marketplace" / "plugins" / PLUGIN_NAME
    if plugin.exists():
        shutil.rmtree(plugin)
    copy_tree(R33, plugin)
    configure_plugin(plugin)
    configure_rigor_fader(plugin)
    configure_marketplace(payload / "adapters" / "codex" / "marketplace" / "marketplace.json")

    wheelhouse = payload / "wheelhouse"
    wheelhouse.mkdir()
    build_wheel(CORE, wheelhouse, args.python)
    build_wheel(STUDIO, wheelhouse, args.python)
    collect_wheels(wheelhouse, args.dependency_wheelhouse)

    provenance = {
        "schema": "kch.aio.provenance.v1",
        "inputs": {
            "r21": {"source": str(R21), **tree_digest(lineage / "kch-native-r21-0.11.33")},
            "r33": {"source": str(R33), **tree_digest(lineage / "kch-native-r33-0.11.33")},
            "core": {"source": str(CORE), **tree_digest(payload / "sources" / "kwancode-harness-0.11.0")},
            "studio": {"source": str(STUDIO), **tree_digest(payload / "sources" / "kch-studio-0.3.16")},
            "mis": {"source": str(MIS), **tree_digest(payload / "sources" / "mis-0.3.1")},
        },
        "excluded": ["transient caches", "build outputs", "runtime state", "every R34 or newer parallel lineage"],
        "active_projection_basis": "r33",
        "r21_r33_mutated": False,
    }
    (payload / "PROVENANCE.json").write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = write_manifest(payload)

    release = output_root / "release"
    release.mkdir(exist_ok=True)
    archive = release / f"{NAME}.zip"
    if archive.exists():
        archive.unlink()
    deterministic_zip(payload, archive)
    with zipfile.ZipFile(archive) as zf:
        bad = zf.testzip()
        if bad:
            raise RuntimeError(f"zip CRC failure: {bad}")
    build_validation = release / "BUILD_PACKAGE_VALIDATION.json"
    subprocess.run(
        [args.python, str(payload / "verify_all_in_one.py"), "--package-root", str(payload), "--zip", str(archive), "--output", str(build_validation)],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    receipt = {
        "schema": "kch.aio.build-receipt.v1",
        "package": NAME,
        "zip": archive.name,
        "bytes": archive.stat().st_size,
        "sha256": sha256(archive),
        "file_count": manifest["file_count"],
        "zip_crc": "PASS",
        "live_installation_performed": False,
        "automatic_promotion": False,
    }
    (release / "BUILD_RECEIPT.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
