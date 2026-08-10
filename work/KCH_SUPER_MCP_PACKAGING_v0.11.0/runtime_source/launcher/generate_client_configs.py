from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "launcher" / "run_super_mcp.py"


def codex_toml(python: Path) -> str:
    quote = lambda value: json.dumps(str(value), ensure_ascii=False)
    return "\n".join(
        [
            "[mcp_servers.kch_super_mcp]",
            f"command = {quote(python)}",
            f"args = [\"-X\", \"utf8\", \"-u\", {quote(LAUNCHER)}]",
            f"cwd = {quote(ROOT)}",
            "startup_timeout_sec = 30",
            "tool_timeout_sec = 60",
            "enabled = true",
            "required = true",
            'default_tools_approval_mode = "prompt"',
            "",
            "[mcp_servers.kch_super_mcp.env]",
            'KCH_011_PROFILE = "agent-shadow"',
            f"KCH_011_STATE = {quote(ROOT / 'runtime' / 'state' / 'codex_kch_011.sqlite3')}",
            "",
        ]
    )


def cline_json(python: Path) -> dict:
    return {
        "mcpServers": {
            "kch-super-mcp": {
                "command": str(python),
                "args": ["-X", "utf8", "-u", str(LAUNCHER)],
                "env": {
                    "KCH_011_PROFILE": "agent-shadow",
                    "KCH_011_STATE": str(ROOT / "runtime" / "state" / "cline_kch_011.sqlite3"),
                },
                "disabled": False,
                "autoApprove": [],
            }
        }
    }


def vscode_json(python: Path) -> dict:
    return {
        "servers": {
            "kchSuperMcp": {
                "type": "stdio",
                "command": str(python),
                "args": ["-X", "utf8", "-u", str(LAUNCHER)],
                "cwd": str(ROOT),
                "env": {
                    "KCH_011_PROFILE": "agent-shadow",
                    "KCH_011_STATE": str(ROOT / "runtime" / "state" / "vscode_kch_011.sqlite3"),
                },
            }
        }
    }


def write_exact(path: Path, content: str, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite {path}; pass --force only after reviewing the existing file")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate absolute-path client configuration files for KCH Super-MCP.")
    parser.add_argument("--python", type=Path, default=Path(sys.executable), help="Python >= 3.11 executable used to launch the server")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "generated_configs")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    python = args.python.expanduser().resolve()
    if not python.is_file():
        raise SystemExit(f"Python executable unavailable: {python}")
    if sys.version_info < (3, 11):
        raise SystemExit("Run this generator with Python >= 3.11")

    outputs = {
        "codex": args.output_dir / "codex_config.toml",
        "cline": args.output_dir / "cline_mcp_settings.json",
        "vscode": args.output_dir / "vscode_mcp.json",
    }
    write_exact(outputs["codex"], codex_toml(python), args.force)
    write_exact(outputs["cline"], json.dumps(cline_json(python), ensure_ascii=False, indent=2) + "\n", args.force)
    write_exact(outputs["vscode"], json.dumps(vscode_json(python), ensure_ascii=False, indent=2) + "\n", args.force)
    print(json.dumps({"generated": {key: str(value.resolve()) for key, value in outputs.items()}, "auto_approve": "EMPTY_BY_DEFAULT"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
