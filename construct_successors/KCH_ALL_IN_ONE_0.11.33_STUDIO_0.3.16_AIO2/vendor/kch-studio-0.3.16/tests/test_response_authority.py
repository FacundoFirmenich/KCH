from kch_studio.response_authority import ResponseAuthorityGovernor


def _governor(tmp_path):
    gate = ResponseAuthorityGovernor(tmp_path)
    gate.register(
        {
            "constraint_id": "TERM-CN4",
            "dimension": "TERMINOLOGY",
            "key": "CN4",
            "operator": "EQ",
            "expected": "AEAT_TARIFF_AGGREGATION_NOT_PHYSICAL_PRODUCT",
            "authority_source": "native-thread:user-correction",
        }
    )
    gate.register(
        {
            "constraint_id": "SCOPE-LOCAL",
            "dimension": "JURISDICTION",
            "key": "evaluation_scope",
            "operator": "EQ",
            "expected": "LOCAL_MONTHLY",
            "authority_source": "native-thread:user-decision",
        }
    )
    gate.register(
        {
            "constraint_id": "REJECT-GLOBAL",
            "dimension": "REJECTED_FRAME",
            "key": "global_aggregation_wording",
            "operator": "ABSENT_TEXT",
            "expected": ["mejora global", "ganador global"],
            "authority_source": "native-thread:user-rejection",
        }
    )
    return gate


def test_response_authority_passes_exact_local_contract(tmp_path):
    gate = _governor(tmp_path)
    result = gate.adjudicate(
        {
            "text": "CN4 es una agrupación arancelaria; se informan los meses locales.",
            "assertions": [
                {"dimension": "TERMINOLOGY", "key": "CN4", "value": "AEAT_TARIFF_AGGREGATION_NOT_PHYSICAL_PRODUCT"},
                {"dimension": "JURISDICTION", "key": "evaluation_scope", "value": "LOCAL_MONTHLY"},
            ],
            "claims": [{"experiment_id": "bridge", "provenance_declared": True}],
        }
    )
    assert result["gate"] == "PASS"
    assert result["release_authorized"] is True
    assert gate.verify()["gate"] == "PASS"


def test_response_authority_blocks_case_recurrence(tmp_path):
    gate = _governor(tmp_path)
    result = gate.adjudicate(
        {
            "text": "CN4 es un producto y no hay mejora global.",
            "assertions": [
                {"dimension": "TERMINOLOGY", "key": "CN4", "value": "BMA_PHYSICAL_PRODUCT"},
                {"dimension": "JURISDICTION", "key": "evaluation_scope", "value": "GLOBAL"},
            ],
            "claims": [
                {"combines_experiments": True, "separation_declared": False, "scope_promoted": True, "provenance_declared": False}
            ],
            "off_mission_classification": True,
            "promises": [{"kind": "MONITOR_PROCESS", "commitment_id": ""}],
        }
    )
    assert result["gate"] == "BLOCK"
    assert "EXPERIMENT_BOUNDARIES_CONFLATED" in result["failures"]
    assert "JURISDICTION_PROMOTED_WITHOUT_AUTHORITY" in result["failures"]
    assert "MONITORING_PROMISE_WITHOUT_ACTIVE_COMMITMENT" in result["failures"]
    assert "OFF_MISSION_CLASSIFICATION_DERAILMENT" in result["failures"]


def test_monitoring_promise_requires_registered_active_id(tmp_path):
    gate = ResponseAuthorityGovernor(tmp_path)
    candidate = {
        "text": "El proceso queda bajo monitor.",
        "promises": [{"kind": "MONITOR_PROCESS", "commitment_id": "MONITOR-1"}],
    }
    assert gate.adjudicate(candidate, active_commitment_ids=[])["gate"] == "BLOCK"
    assert gate.adjudicate(candidate, active_commitment_ids=["MONITOR-1"])["gate"] == "PASS"
