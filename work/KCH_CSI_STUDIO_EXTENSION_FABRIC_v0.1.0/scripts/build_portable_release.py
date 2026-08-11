from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

EXCLUDES = {
    "__pycache__",
    ".pytest_cache",
    ".pytest*",
    ".pytest_tmp",
    ".pytest_tmp*",
    ".ruff_cache",
    ".runtime",
    ".runtime*",
    "runtime_live",
    "runtime_*",
    "runtime_live_r2",
    "runtime_probe",
    "runtime_cli_probe",
    "results",
    "dist",
    "build",
    "release_build",
    "dependency_wheels",
    ".git",
    "compiled_governance_*",
    "KCH_PRE2G_INTEGRATED_MACROGATE_v0.1.0.json",
    "KCH_PORTABLE_INSTALL_RECEIPT_R3.json",
    "KCH_PORTABLE_POST_INSTALL_GATE_R3.json",
    "CHECKPOINT_MATERIAL_ES.md",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def copy_tree(source: Path, target: Path) -> None:
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(*EXCLUDES))


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def run(command: list[str], cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, text=True, capture_output=True, shell=False)
    if completed.returncode:
        raise RuntimeError(
            json.dumps(
                {
                    "command": command,
                    "stdout": completed.stdout[-4000:],
                    "stderr": completed.stderr[-4000:],
                },
                ensure_ascii=False,
            )
        )


def main() -> None:
    candidate = Path(__file__).resolve().parents[1]
    workspace = candidate.parent
    base = workspace / "KCH_0.11_REEXTRACT_FINAL"
    mis = workspace / "KCH_MIS03_REEXTRACT_v0.1.0"
    governance = candidate / "governance"
    final_output = candidate / "release_build"
    final_output.mkdir(exist_ok=True)
    output_root = Path(tempfile.mkdtemp(prefix="kch_release_"))
    package = output_root / "KCH_0.11_PRE2G_R16"
    package.mkdir(parents=True)

    # Build into this release jurisdiction only.  candidate/dist may contain a
    # historically valid but stale wheel with the same versioned filename.
    dist = output_root / "dist"
    dist.mkdir(exist_ok=True)
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            ".",
            "--no-deps",
            "--no-build-isolation",
            "-w",
            str(dist),
        ],
        candidate,
    )
    wheelhouse = package / "wheelhouse"
    wheelhouse.mkdir()
    for source in [
        *dist.glob("*.whl"),
        *(base / "dist").glob("*.whl"),
        *(base / "vendor").glob("*.whl"),
        *(mis / "dist").glob("*.whl"),
        *(mis / "vendor").glob("*.whl"),
    ]:
        shutil.copy2(source, wheelhouse / source.name)
    dependency_wheels = candidate / "dependency_wheels"
    if dependency_wheels.is_dir():
        for source in dependency_wheels.glob("*.whl"):
            shutil.copy2(source, wheelhouse / source.name)
    if not any(path.name.casefold().startswith("tzdata-") for path in wheelhouse.glob("*.whl")):
        raise RuntimeError("portable Windows wheelhouse requires an explicit tzdata wheel")

    copy_tree(candidate, package / "source" / "kch-studio")
    copy_tree(base, package / "source" / "kch-0.11-frozen")
    shutil.copy2(candidate / "README_ES.md", package / "README_ES.md")
    copy_tree(candidate / "docs", package / "docs")
    copy_tree(candidate / "plugin", package / "plugin")
    copy_tree(mis / "evidence", package / "mis" / "evidence")
    copy_tree(mis / "results", package / "mis" / "results")
    copy_tree(mis / "vendor", package / "mis" / "vendor")
    (package / "governance").mkdir()
    for name in ("HARNESS.md", "AGENTS.md", "RULES.md"):
        shutil.copy2(governance / name, package / "governance" / name)
    copy_tree(governance / "agents", package / "governance" / "agents")
    copy_tree(governance / "rules", package / "governance" / "rules")
    shutil.copy2(
        candidate / "src" / "kch_studio" / "data" / "governance" / "csi" / "governance_graph.json",
        package / "governance" / "governance_graph.json",
    )
    shutil.copy2(
        candidate / "src" / "kch_studio" / "data" / "governance" / "governance.lock.json",
        package / "governance" / "governance.lock.json",
    )
    (package / "scripts").mkdir()
    shutil.copy2(
        candidate / "scripts" / "portable_bootstrap.py",
        package / "scripts" / "portable_bootstrap.py",
    )
    shutil.copy2(
        candidate / "scripts" / "post_install_gate.py", package / "scripts" / "post_install_gate.py"
    )

    environment = {
        "KCH_STUDIO_RUNTIME": "<KCH_RUNTIME_ROOT>\\state",
        "KCH_MIS_ROOT": "<KCH_ROOT>\\mis",
        "KCH_CONSTRUCT_STABLE_ROOT": "<KCH_ROOT>\\source\\kch-studio",
    }
    write_json(
        package / "adapters" / "vscode.mcp.json",
        {
            "servers": {
                "kch-0-11-pre2g": {
                    "type": "stdio",
                    "command": "<KCH_RUNTIME_ROOT>\\venv\\Scripts\\kch-super-mcp-studio.exe",
                    "args": [],
                    "env": environment,
                }
            }
        },
    )
    write_json(
        package / "adapters" / "cline_mcp_settings.json",
        {
            "mcpServers": {
                "kch-0-11-pre2g": {
                    "type": "stdio",
                    "command": "<KCH_RUNTIME_ROOT>\\venv\\Scripts\\kch-super-mcp-studio.exe",
                    "args": [],
                    "env": environment,
                    "disabled": False,
                    "autoApprove": [],
                }
            }
        },
    )
    write_json(
        package / "adapters" / "opencode.json",
        {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {
                "servers": {
                    "kch-0-11-pre2g": {
                        "type": "local",
                        "command": ["<KCH_RUNTIME_ROOT>\\venv\\Scripts\\kch-super-mcp-studio.exe"],
                        "environment": environment,
                        "disabled": False,
                    }
                }
            },
        },
    )
    write_json(
        package / "adapters" / "codex-plugin.json",
        {
            "plugin_path": "<KCH_ROOT>\\plugin\\kch-csi-studio",
            "mcp_command": "<KCH_RUNTIME_ROOT>\\venv\\Scripts\\kch-codex-bootstrap-mcp.exe",
            "preflight_mcp_command": "<KCH_RUNTIME_ROOT>\\venv\\Scripts\\kch-codex-preflight-mcp.exe",
            "full_super_mcp_command": "<KCH_RUNTIME_ROOT>\\venv\\Scripts\\kch-super-mcp-studio.exe",
            "automatic_external_configuration_write": False,
        },
    )
    shutil.copy2(
        candidate / "docs" / "CODEX_PROJECT_BINDING_AGENTS.md",
        package / "adapters" / "AGENTS_KCH.md",
    )

    write(
        package / "INSTALL_KCH.cmd",
        '@echo off\r\nset "KCH_ROOT=%~dp0"\r\npython "%KCH_ROOT%scripts\\portable_bootstrap.py" "%KCH_ROOT%."\r\n',
    )
    common = 'set "KCH_ROOT=%~dp0"\r\nif not exist "%KCH_ROOT%runtime_paths.cmd" (echo Ejecuta INSTALL_KCH.cmd primero.& exit /b 2)\r\ncall "%KCH_ROOT%runtime_paths.cmd"\r\n'
    write(
        package / "LAUNCH_KCH_UI.cmd",
        "@echo off\r\n"
        + common
        + '"%KCH_RUNTIME_ROOT%\\venv\\Scripts\\kch-studio.exe" --root "%KCH_STUDIO_RUNTIME%" ui\r\n',
    )
    write(
        package / "LAUNCH_SUPER_MCP.cmd", "@echo off\r\n" + common + '"%KCH_SUPER_MCP_COMMAND%"\r\n'
    )
    write(
        package / "CHECK_KCH.cmd",
        "@echo off\r\n"
        + common
        + '"%KCH_RUNTIME_ROOT%\\venv\\Scripts\\python.exe" "%KCH_ROOT%\\scripts\\post_install_gate.py" "%KCH_ROOT%"\r\n',
    )

    manifest = []
    for path in sorted(
        (item for item in package.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(package).as_posix(),
    ):
        manifest.append(
            {
                "path": path.relative_to(package).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    max_member_characters = max(len(f"{package.name}/{item['path']}") for item in manifest)
    if max_member_characters > 210:
        raise RuntimeError(f"portable archive member path budget exceeded: {max_member_characters}")
    write_json(
        package / "MANIFEST_PRESEAL.json",
        {
            "schema": "kch.0.11.pre2g-integrated-candidate-manifest.v0.2.0",
            "files": manifest,
            "file_count": len(manifest),
            "phl_authorized": True,
            "phl_training_executed": False,
            "phl_real_executed": False,
            "external_installation_performed": False,
            "runtime_path_strategy": "WINDOWS_SHORT_PERSISTENT_LOCALAPPDATA",
            "max_archive_member_characters": max_member_characters,
        },
    )

    archive = output_root / "KCH_0.11_PRE2G_INTEGRATED_CANDIDATE_R16.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as stream:
        for path in sorted(
            (item for item in package.rglob("*") if item.is_file()),
            key=lambda item: item.relative_to(output_root).as_posix(),
        ):
            info = zipfile.ZipInfo(path.relative_to(output_root).as_posix(), (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            stream.writestr(info, path.read_bytes())
    if zipfile.ZipFile(archive).testzip() is not None:
        raise RuntimeError("release ZIP CRC verification failed")
    final_archive = final_output / archive.name
    if final_archive.exists():
        raise FileExistsError(f"refusing to overwrite existing release evidence: {final_archive}")
    shutil.copy2(archive, final_archive)
    shutil.copy2(
        candidate / "scripts" / "extract_and_install.py",
        final_output / "EXTRACT_AND_INSTALL_KCH_R16.py",
    )
    write(
        final_output / "EXTRACT_AND_INSTALL_KCH_R16.cmd",
        '@echo off\r\npython "%~dp0EXTRACT_AND_INSTALL_KCH_R16.py" "%~dp0KCH_0.11_PRE2G_INTEGRATED_CANDIDATE_R16.zip"\r\n',
    )
    print(
        json.dumps(
            {
                "staging_package": str(package),
                "archive": str(final_archive),
                "archive_bytes": final_archive.stat().st_size,
                "archive_sha256": sha256(final_archive),
                "preseal_file_count": len(manifest),
                "max_archive_member_characters": max_member_characters,
                "safe_short_extractor": str(final_output / "EXTRACT_AND_INSTALL_KCH_R16.cmd"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
