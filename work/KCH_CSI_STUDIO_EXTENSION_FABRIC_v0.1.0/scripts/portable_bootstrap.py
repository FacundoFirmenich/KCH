from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run(command: list[str], *, cwd: Path | None = None) -> dict[str, object]:
    completed = subprocess.run(command, cwd=cwd, capture_output=True, text=True, shell=False)
    receipt = {
        "command": command,
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }
    if completed.returncode != 0:
        raise RuntimeError(json.dumps(receipt, ensure_ascii=False))
    return receipt


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


HOST_ADAPTER_FILENAMES = (
    "AGENTS_KCH.md",
    "cline_mcp_settings.json",
    "codex-plugin-reference.json",
    "codex.config.toml",
    "opencode.json",
    "vscode.mcp.json",
)


def collect_host_adapters(adapters: Path) -> list[str]:
    """Return the complete, explicit host-adapter contract or fail closed."""
    paths = [adapters / name for name in HOST_ADAPTER_FILENAMES]
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing generated host adapters: {missing}")
    return [str(path) for path in paths]


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]).resolve()
    wheelhouse = root / "wheelhouse"
    if not wheelhouse.is_dir():
        raise FileNotFoundError(wheelhouse)
    root_fingerprint = hashlib.sha256(str(root).casefold().encode("utf-8")).hexdigest()[:12]
    explicit_runtime = os.environ.get("KCH_PORTABLE_RUNTIME")
    if explicit_runtime:
        runtime = Path(explicit_runtime).resolve()
        runtime_strategy = "USER_EXPLICIT_FINITE_PATH"
    elif os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        runtime = (
            Path(os.environ["LOCALAPPDATA"]) / "KCH" / "runtimes" / root_fingerprint
        ).resolve()
        runtime_strategy = "WINDOWS_SHORT_PERSISTENT_LOCALAPPDATA"
    else:
        runtime = root / ".runtime"
        runtime_strategy = "PACKAGE_LOCAL_RUNTIME"
    venv = runtime / "venv"
    runtime.mkdir(parents=True, exist_ok=True)
    steps: list[dict[str, object]] = []
    if not (venv / "Scripts" / "python.exe").is_file():
        steps.append(run([sys.executable, "-m", "venv", str(venv)]))
    python = venv / "Scripts" / "python.exe"
    wheels = sorted(str(path) for path in wheelhouse.glob("*.whl"))
    if not wheels:
        raise RuntimeError("wheelhouse is empty")
    steps.append(
        run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-index",
                "--find-links",
                str(wheelhouse),
                *wheels,
            ]
        )
    )
    state = runtime / "state"
    state.mkdir(exist_ok=True)
    command = str(venv / "Scripts" / "kch-super-mcp-studio.exe")
    codex_command = str(venv / "Scripts" / "kch-codex-bootstrap-mcp.exe")
    codex_preflight_command = str(venv / "Scripts" / "kch-codex-preflight-mcp.exe")
    environment = {
        "KCH_STUDIO_RUNTIME": str(state),
        "KCH_MIS_ROOT": str(root / "mis"),
        "KCH_CONSTRUCT_STABLE_ROOT": str(root / "source" / "kch-studio"),
    }
    adapters = root / "adapters_runtime"
    write_json(
        adapters / "vscode.mcp.json",
        {
            "servers": {
                "kch-0-11-pre2g": {
                    "type": "stdio",
                    "command": command,
                    "args": [],
                    "env": environment,
                }
            }
        },
    )
    write_json(
        adapters / "cline_mcp_settings.json",
        {
            "mcpServers": {
                "kch-0-11-pre2g": {
                    "type": "stdio",
                    "command": command,
                    "args": [],
                    "env": environment,
                    "disabled": False,
                    "autoApprove": [],
                }
            }
        },
    )
    write_json(
        adapters / "opencode.json",
        {
            "$schema": "https://opencode.ai/config.json",
            "mcp": {
                "servers": {
                    "kch-0-11-pre2g": {
                        "type": "local",
                        "command": [command],
                        "environment": environment,
                        "disabled": False,
                    }
                }
            },
        },
    )
    write_json(
        adapters / "codex-plugin-reference.json",
        {
            "plugin_path": str(root / "plugin" / "kch-csi-studio"),
            "mcp_command": codex_command,
            "preflight_mcp_command": codex_preflight_command,
            "full_super_mcp_command": command,
            "environment": environment,
            "automatic_external_configuration_write": False,
        },
    )
    write_text(
        adapters / "codex.config.toml",
        "[mcp_servers.kch_0_11_preflight]\n"
        f'command = "{codex_preflight_command.replace(chr(92), chr(92) * 2)}"\n'
        "args = []\nstartup_timeout_sec = 30\ntool_timeout_sec = 180\n"
        'enabled = true\nrequired = true\ndefault_tools_approval_mode = "auto"\n\n'
        "[mcp_servers.kch_0_11_preflight.env]\n"
        f'KCH_STUDIO_RUNTIME = "{str(state).replace(chr(92), chr(92) * 2)}"\n\n'
        "[mcp_servers.kch_0_11_bootstrap]\n"
        f'command = "{codex_command.replace(chr(92), chr(92) * 2)}"\n'
        "args = []\nstartup_timeout_sec = 30\ntool_timeout_sec = 180\n"
        'enabled = true\nrequired = true\ndefault_tools_approval_mode = "prompt"\n\n'
        "[mcp_servers.kch_0_11_bootstrap.env]\n"
        f'KCH_STUDIO_RUNTIME = "{str(state).replace(chr(92), chr(92) * 2)}"\n',
    )
    shutil.copy2(root / "docs" / "CODEX_PROJECT_BINDING_AGENTS.md", adapters / "AGENTS_KCH.md")
    write_text(
        root / "runtime_paths.cmd",
        "@echo off\r\n"
        f'set "KCH_ROOT={root}"\r\n'
        f'set "KCH_RUNTIME_ROOT={runtime}"\r\n'
        f'set "KCH_STUDIO_RUNTIME={state}"\r\n'
        f'set "KCH_MIS_ROOT={root / "mis"}"\r\n'
        f'set "KCH_CONSTRUCT_STABLE_ROOT={root / "source" / "kch-studio"}"\r\n'
        f'set "KCH_SUPER_MCP_COMMAND={command}"\r\n'
        f'set "KCH_CODEX_BOOTSTRAP_MCP_COMMAND={codex_command}"\r\n'
        f'set "KCH_CODEX_PREFLIGHT_MCP_COMMAND={codex_preflight_command}"\r\n',
    )
    receipt = {
        "schema": "kch.portable-bootstrap-receipt.v0.2.0",
        "state": "INSTALLED_ISOLATED_LOCAL_RUNTIME",
        "root": str(root),
        "python": str(python),
        "runtime": str(runtime),
        "runtime_path_strategy": runtime_strategy,
        "package_root_characters": len(str(root)),
        "runtime_root_characters": len(str(runtime)),
        "windows_deep_venv_avoided": os.name == "nt" and runtime != root / ".runtime",
        "wheel_count": len(wheels),
        "steps": steps,
        "host_adapters": collect_host_adapters(adapters),
        "external_host_configuration_modified": False,
        "credentials_embedded": False,
        "microphone_activated": False,
        "phl_authorized": True,
        "phl_training_executed": False,
        "phl_real_executed": False,
    }
    write_json(runtime / "INSTALL_RECEIPT.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
