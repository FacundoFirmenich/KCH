"""Generate concrete additive MCP configurations; never start or modify a host."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


def profiles(*, repository: Path, state: Path, workspace: Path,
             principal: str, session_prefix: str, host: str = "both") -> dict[str, dict]:
    repository = repository.expanduser().resolve(strict=True)
    workspace = workspace.expanduser().resolve(strict=True)
    state = state.expanduser().resolve()
    source = repository / "integrations" / "kch-composed-runtime" / "src"
    if not repository.is_dir() or not workspace.is_dir():
        raise ValueError("repository and workspace must be existing directories")
    if not (source / "kch_composed" / "__main__.py").is_file():
        raise ValueError("repository does not contain the composed runtime entry point")
    if state.exists() and not state.is_dir():
        raise ValueError("state must be a directory path")
    if not isinstance(principal, str) or not principal.strip() or any(ord(c) < 32 for c in principal):
        raise ValueError("principal must be nonempty and contain no control characters")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,95}", session_prefix):
        raise ValueError("session-prefix must be 1-96 letters, digits, dots, underscores or hyphens")
    if host not in {"both", "qwenpaw", "openclaw"}:
        raise ValueError("host must be both, qwenpaw or openclaw")
    interpreter = Path(sys.executable).resolve(strict=True)
    result = {}
    for host in (("qwenpaw", "openclaw") if host == "both" else (host,)):
        client = {
            "transport": "stdio", "command": str(interpreter),
            "args": ["-m", "kch_composed", "--repository", str(repository),
                     "--state", str(state), "--workspace", str(workspace),
                     "--principal", principal, "--session", f"{host}-{session_prefix}", "mcp"],
            "cwd": str(source), "enabled": True,
        }
        if host == "qwenpaw":
            client["name"] = "kch_composed"
            result[f"{host}.local.json"] = {"mcpServers": {"kch_composed": client}}
        else:
            result[f"{host}.local.json"] = {"mcp": {"servers": {"kch_composed": client}}}
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--principal", required=True)
    parser.add_argument("--session-prefix", required=True,
                        help="Explicit local binding; generated sessions are openclaw-/qwenpaw- plus this value")
    parser.add_argument("--host", choices=("both", "qwenpaw", "openclaw"), default="both",
                        help="Select either own platform composition or generate both alternatives")
    parser.add_argument("--output", type=Path, required=True,
                        help="Output directory; neither host configuration is automatically changed")
    args = parser.parse_args(argv)
    try:
        documents = profiles(repository=args.repository, state=args.state,
                             workspace=args.workspace, principal=args.principal,
                             session_prefix=args.session_prefix, host=args.host)
        output = args.output.expanduser().resolve()
        targets = [output / name for name in documents]
        if any(path.exists() for path in targets):
            raise ValueError("output already contains a generated profile; choose a fresh output directory")
        output.mkdir(parents=True, exist_ok=True)
        for name, document in documents.items():
            # Exclusive creation also protects against a concurrent generator.
            with (output / name).open("x", encoding="utf-8") as stream:
                json.dump(document, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.write("\n")
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"generated": [str(path) for path in targets],
                      "host_activated": False, "host_configuration_modified": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
