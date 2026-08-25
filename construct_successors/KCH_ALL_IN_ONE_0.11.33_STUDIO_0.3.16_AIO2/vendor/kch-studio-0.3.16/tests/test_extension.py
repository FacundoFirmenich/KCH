from __future__ import annotations

from pathlib import Path

from kch_studio.extension import ExtensionFabric, RecommendationEngine, RuntimeInventory


def test_provider_contract_and_explicit_unavailable_sources(tmp_path: Path) -> None:
    fabric = ExtensionFabric(tmp_path / "fabric")
    value = fabric.describe()
    assert {item["provider"] for item in value["providers"]} == {
        "pypi",
        "npm",
        "mcp-registry",
        "open-vsx",
    }
    assert (
        value["vscode_marketplace"]["public_search"] == "UNAVAILABLE_PROVIDER_SUPPORTED_PUBLIC_API"
    )
    assert "conda" in value["additional_planned_ecosystems"]


def test_recommendation_has_independent_lanes_and_no_global_winner() -> None:
    records = [
        {
            "provider": "pypi",
            "identifier": "evidence-governance",
            "version": "1.2.3",
            "summary": "Evidence governance for Python workflows",
            "license": "MIT",
            "runtimes": ["python"],
            "source_url": "https://pypi.org/project/evidence-governance/",
            "provenance": "PYPI_JSON_API",
            "security_evidence": {"status": "NOT_ESTIMABLE"},
        },
        {
            "provider": "npm",
            "identifier": "unrelated",
            "version": None,
            "summary": "Theme package",
            "license": None,
            "runtimes": ["node"],
            "source_url": "https://www.npmjs.com/package/unrelated",
            "provenance": "NPM_CLI_SEARCH_JSON",
            "security_evidence": {"status": "NOT_ESTIMABLE"},
        },
    ]
    values = RecommendationEngine().evaluate(
        records, objective="Python evidence governance", available_runtimes=["python"]
    )
    assert values[0]["decision"] == "RECOMMEND"
    assert values[0]["global_score"] is None
    assert set(values[0]["lanes"]) == {
        "objective_fit",
        "host_runtime_compatibility",
        "authority_permissions",
        "provenance",
        "maintenance",
        "security",
        "license",
        "cost_network",
        "reproducibility_lock_rollback",
        "popularity_secondary",
    }
    assert values[1]["decision"] == "INCOMPATIBLE"


def test_runtime_inventory_is_read_only_and_does_not_read_secrets() -> None:
    value = RuntimeInventory().collect()
    assert value["state_changed"] is False
    assert value["secrets_read"] is False
    assert "python" in value["commands"]
