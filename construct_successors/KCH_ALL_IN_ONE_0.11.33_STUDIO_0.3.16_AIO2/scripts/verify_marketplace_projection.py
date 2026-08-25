from __future__ import annotations

import argparse
import importlib.util
import json
import tempfile
from pathlib import Path
from typing import Any


PLUGIN_NAME = "kch-all-in-one-0-11-33"
PLUGIN_VERSION = "0.11.33-aio.2"


def load_installer(package: Path) -> Any:
    installer_path = package / "install_all_in_one.py"
    spec = importlib.util.spec_from_file_location("kch_aio2_installer", installer_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load installer: {installer_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check(condition: bool, label: str, detail: Any, rows: list[dict[str, Any]]) -> None:
    rows.append({"check": label, "pass": bool(condition), "detail": detail})
    if not condition:
        raise AssertionError(f"{label}: {detail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="AIO2 Codex marketplace projection regression gate")
    parser.add_argument("--package-root", type=Path, required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--temp-parent", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    # Keep a user-supplied short drive alias intact: resolving it here expands
    # back to a long physical path before the marketplace gate is exercised.
    package = args.package_root.absolute()
    runtime = args.runtime_root.absolute()
    rows: list[dict[str, Any]] = []
    error: str | None = None
    try:
        installer = load_installer(package)
        parent = args.temp_parent.absolute() if args.temp_parent else None
        if parent is not None:
            parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="kch-aio2-marketplace-", dir=parent) as raw:
            root = Path(raw)
            marketplace = root / ".agents" / "plugins" / "marketplace.json"
            receipt_root = root / "receipts"
            result = installer.deploy_codex(package, runtime, marketplace, receipt_root)

            expected = marketplace.parent / "plugins" / PLUGIN_NAME
            escaped = root / "plugins" / PLUGIN_NAME
            check(expected.is_dir(), "served_plugin_target_exists", str(expected), rows)
            check(not escaped.exists(), "legacy_escaped_target_absent", str(escaped), rows)
            check(
                Path(result["marketplace_plugin_target"]) == expected.resolve(),
                "receipt_target_matches_served_target",
                result["marketplace_plugin_target"],
                rows,
            )

            market = json.loads(marketplace.read_text(encoding="utf-8"))
            entry = next(row for row in market["plugins"] if row.get("name") == PLUGIN_NAME)
            resolved_source = (marketplace.parent / entry["source"]["path"]).resolve()
            check(resolved_source == expected.resolve(), "marketplace_source_resolves_to_target", str(resolved_source), rows)

            manifest = json.loads((expected / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
            check(manifest.get("version") == PLUGIN_VERSION, "served_plugin_version", manifest.get("version"), rows)

            mcp = json.loads((expected / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]
            expected_mis = installer.mis_evidence_root(runtime).resolve()
            expected_mis_runtime = (runtime / "state" / "mis").resolve()
            for server in ("kch-codex-preflight", "kch-codex-bootstrap"):
                env = mcp[server].get("env", {})
                check(Path(env.get("KCH_MIS_ROOT", "")).resolve() == expected_mis, f"{server}_mis_root", env, rows)
                check(expected_mis.is_dir(), f"{server}_mis_root_exists", str(expected_mis), rows)
                check(Path(env.get("KCH_MIS_RUNTIME", "")).resolve() == expected_mis_runtime, f"{server}_mis_runtime", env, rows)
        status = "PASS"
    except Exception as exc:
        status = "FAIL"
        error = f"{type(exc).__name__}: {exc}"

    report = {
        "schema": "kch.aio2.marketplace-projection-gate.v1",
        "status": status,
        "checks_passed": sum(1 for row in rows if row["pass"]),
        "checks_total": len(rows),
        "checks": rows,
        "error": error,
        "live_codex_mutation": False,
        "authority_created": False,
        "phl_training_executed": False,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
