from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from kch_studio.extension import ExtensionFabric, RecommendationEngine, RuntimeInventory


def now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.root).resolve()
    output = Path(args.output).resolve()
    fabric = ExtensionFabric(root)
    probes: list[tuple[str, str, Callable[[], list[dict[str, Any]]]]] = [
        ("pypi", "mcp", lambda: fabric.search("pypi", "mcp", 3)),
        (
            "npm",
            "model context protocol",
            lambda: fabric.search("npm", "model context protocol", 3),
        ),
        ("mcp-registry", "filesystem", lambda: fabric.search("mcp-registry", "filesystem", 3)),
        ("open-vsx", "cline", lambda: fabric.search("open-vsx", "cline", 3)),
    ]
    results: list[dict[str, Any]] = []
    all_records: list[dict[str, Any]] = []
    for provider, query, call in probes:
        try:
            records = call()
            passed = bool(records) and all(
                record.get("identifier") and record.get("source_url") for record in records
            )
            results.append(
                {
                    "provider": provider,
                    "query": query,
                    "state": "PASS" if passed else "FAIL_EMPTY_OR_INCOMPLETE",
                    "record_count": len(records),
                    "records": records,
                }
            )
            all_records.extend(records)
        except Exception as exc:
            results.append(
                {
                    "provider": provider,
                    "query": query,
                    "state": "UNAVAILABLE_PROVIDER_RUNTIME_OR_NETWORK",
                    "record_count": 0,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    inventory = RuntimeInventory().collect()
    available = [
        name for name, value in inventory["commands"].items() if value["state"] == "AVAILABLE"
    ]
    recommendations = RecommendationEngine().evaluate(
        all_records,
        objective="discover governed Model Context Protocol tools and editor integrations",
        available_runtimes=available,
    )
    pass_count = sum(item["state"] == "PASS" for item in results)
    gate = "PASS" if pass_count == len(results) else ("PARTIAL" if pass_count else "FAIL")
    value = {
        "schema": "kch.extension-fabric-live-gate.v0.1.0",
        "gate": gate,
        "provider_pass_count": pass_count,
        "provider_total": len(results),
        "results": results,
        "recommendations": recommendations,
        "global_winner": None,
        "search_implies_install": False,
        "registry_presence_implies_security": False,
        "state_changed": False,
        "executed_at": now(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "gate": gate,
                "provider_pass_count": pass_count,
                "provider_total": len(results),
                "output": str(output),
            },
            sort_keys=True,
        )
    )
    raise SystemExit(0 if gate == "PASS" else 2)


if __name__ == "__main__":
    main()
