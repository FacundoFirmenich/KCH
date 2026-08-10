from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapter import AdapterContractError, EXPECTED, MISV03Adapter, sha256_file, sha256_json
from .csi import lower_to_csi


CLIENT = {"client_id": "kch-mis-v03-adapter", "client_instance_id": "effective-integration-gate-v0.1.0"}


def _write(service: Any, method: Any, request_id: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
    return method(*args, client=CLIENT, request_id=request_id, expected_head_hash=service.head(), **kwargs)


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _copy_sqlite(source: Path, target: Path) -> None:
    source_uri = f"file:{source.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(source_uri, uri=True) as origin, sqlite3.connect(target) as replica:
        origin.backup(replica)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decision_records(certificate: dict[str, Any], dispatch_event_hash: str) -> list[dict[str, Any]]:
    cert_sha = certificate["certificate_sha256"]
    common = {
        "schema": "kch.reviewable-decision.v0.2.0",
        "emitted_at": _now(),
        "component_id": "kch.mis.v03.adapter",
        "initiator": "kch-mis-v03-adapter",
        "objective_contract_sha256": cert_sha,
        "purpose_id": "GATE_KCH_MIS_V03_EFFECTIVE_INTEGRATION_v0.1.0",
        "jurisdiction": "MIS v0.3.1 exact structural replay over the sealed KHC v2.0.7 corpus; no causal or prospective jurisdiction.",
        "input_provenance_ids": [
            f"sha256:{EXPECTED['wheel']}",
            f"sha256:{EXPECTED['corpus']}",
            f"sha256:{EXPECTED['report']}",
            f"sha256:{EXPECTED['ledgers']}",
        ],
        "source_event_ids": [dispatch_event_hash],
        "evidence_ids": [f"sha256:{cert_sha}"],
        "authority_granted": [],
        "authority_exercised": [],
        "reversibility": "The integration ledger is an isolated replica; source MIS and personal KCH state remain byte-identical.",
        "source_uri": f"mis://v0.3.1/certificates/{cert_sha}",
    }
    admission = {
        **common,
        "decision_id": f"mis-v03:structural-certificate:admit:{cert_sha[:16]}",
        "decision_type": "MIS_STRUCTURAL_CERTIFICATE_ADMISSION",
        "trigger": "LIVE_KCH_ROUTED_MIS_V03_REPLAY_EXACT_MATCH",
        "active_rule_ids": [
            "DECISION_EQUIVALENCE_IS_NOT_AUTHORITY_EQUIVALENCE",
            "PRESERVE_PROVENANCE_PURPOSE_JURISDICTION",
            "CAPABILITY_DOES_NOT_IMPLY_PERMISSION",
            "FUTURE_ONLY_CHRONOLOGY",
        ],
        "summary": "Admit the exact MIS v0.3.1 structural certificate as reviewable KCH evidence.",
        "rationale": "KCH routed the sealed MIS wheel over all 480 real KHC records; the live audit and 60 persisted ledgers match the qualified frozen report exactly.",
        "alternatives_considered": ["REJECT_HASH_MISMATCHED_EVIDENCE", "TREAT_MIS_OUTPUT_AS_EXECUTION_AUTHORITY_PROHIBITED"],
        "confidence_representation": {
            "kind": "DETERMINISTIC_EXACT_REPLAY",
            "value": "480_RECORDS_60_STREAMS_EXACT_MATCH",
            "meaning": "Confidence is limited to custody, exact calculation, structural round-trip and future-only ledger integrity.",
        },
        "risk_class": "BOUNDED_MATHEMATICAL_EVIDENCE_ADMISSION",
        "claim_ceiling": certificate["claim_ceiling"],
        "consequence": "The certificate becomes KCH-reviewable evidence; no action, commit, promotion or authority is created.",
        "stop_condition_ids": ["ANY_CUSTODY_HASH_MISMATCH", "CERTIFICATE_TAMPER", "PURPOSE_OR_JURISDICTION_DRIFT"],
    }
    abstention = {
        **common,
        "emitted_at": _now(),
        "decision_id": f"mis-v03:causal-global-promotion:abstain:{cert_sha[:16]}",
        "decision_type": "MIS_CAUSAL_AND_GLOBAL_PROMOTION_ABSTENTION",
        "trigger": "HISTORICAL_REPLAY_HAS_NO_ADJUDICATED_CAUSAL_OUTCOME",
        "active_rule_ids": [
            "NO_CAUSAL_CLAIM_FROM_HISTORICAL_ACTION_REPLAY",
            "NO_GLOBAL_WINNER_WITHOUT_PROSPECTIVE_EVIDENCE",
            "PRESERVE_NOT_ESTIMABLE_AND_ABSTENTION",
        ],
        "summary": "Abstain from promoting MIS v0.3.1 to a causal, prospective or globally superior claim.",
        "rationale": "The replay observes historical model actions rather than adjudicated quality outcomes; exact reproduction cannot manufacture the missing empirical jurisdiction.",
        "alternatives_considered": ["OVERPROMOTE_STRUCTURAL_REPLAY_PROHIBITED", "REWRITE_HISTORICAL_RESULTS_PROHIBITED"],
        "confidence_representation": {
            "kind": "EVIDENCE_BOUNDARY",
            "value": "NOT_DEMONSTRATED",
            "meaning": "Causal improvement, prospective superiority, human utility, open-domain scaling and a global winner remain outside this gate.",
        },
        "risk_class": "NO_PROMOTION_ABSTENTION",
        "claim_ceiling": "NO_CAUSAL_PROSPECTIVE_OR_GLOBAL_PROMOTION_AUTHORIZED",
        "consequence": "MIS is integrated as bounded decision support while KCH retains authority and empirical promotion gates remain closed.",
        "stop_condition_ids": ["PROSPECTIVE_OUTCOME_EVIDENCE_AVAILABLE_FOR_NEW_PREREGISTERED_GATE"],
    }
    return [admission, abstention]


def _formal_request(report: dict[str, Any]) -> dict[str, Any]:
    example = report["loss_decision_example"]
    return {
        "schema": "kch.mis.v03.exact-decision-request.v0.1.0",
        "request_id": "mis-v03-qualified-formal-interface-conformance",
        "purpose_id": "VERIFY_KCH_MIS_EXACT_DECISION_INTERFACE_AGAINST_FROZEN_FORMAL_EXAMPLE",
        "jurisdiction": "Formal interface conformance only; parameters are declared validation values, not empirical estimates.",
        "evidence_ids": [f"sha256:{EXPECTED['report']}"],
        "states": list(example["prior"]["masses"]),
        "prior": example["prior"]["masses"],
        "likelihood": example["likelihood"],
        "actions": example["loss"]["actions"],
        "losses": example["loss"]["losses"],
        "tie_action": None,
    }


def _registry_successor(source: list[dict[str, Any]], certificate_path: Path, certificate: dict[str, Any]) -> list[dict[str, Any]]:
    if any(row.get("active_name") == "MIS v0.3.1 exact qualitative Bayes service" for row in source):
        raise RuntimeError("registry source already contains the MIS v0.3.1 integration row")
    return source + [
        {
            "active_name": "MIS v0.3.1 exact qualitative Bayes service",
            "legacy_source_directory": "MIS_QUALITATIVE_BAYES_v0_3_1",
            "family": "KCH_FEDERATED_MATHEMATICAL_SERVICE",
            "state": "LOCAL_VALIDATED_EFFECTIVE_INTEGRATION_CANDIDATE",
            "jurisdiction": "exact semantic atoms, rational posterior/loss/decision, structural KHC replay and future-only certificates; KCH retains authority and commit",
            "evidence_file": str(certificate_path.resolve()),
            "evidence_sha256": sha256_file(certificate_path),
            "mis_version": "0.3.1",
            "records_live_replayed": certificate["records"],
            "streams_verified": certificate["streams"],
            "authority_inheritance": False,
            "automatic_promotion": False,
            "claim_ceiling": certificate["claim_ceiling"],
        }
    ]


def run(args: argparse.Namespace) -> dict[str, Any]:
    outputs = [args.replica_output, args.certificate_output, args.decisions_output, args.registry_output, args.result_output, args.csi_output]
    existing = [str(path) for path in outputs if path.exists()]
    if existing:
        raise SystemExit(f"refusing to overwrite: {existing}")

    for source in (args.source_state, args.integration_src, args.wheel, args.corpus, args.report, args.ledgers, args.manifest, args.catalog, args.registry_input):
        if not source.exists():
            raise SystemExit(f"missing input: {source}")

    source_state_before = sha256_file(args.source_state)
    custody_before = {key: sha256_file(path) for key, path in {
        "wheel": args.wheel, "corpus": args.corpus, "report": args.report, "ledgers": args.ledgers, "manifest": args.manifest
    }.items()}
    _copy_sqlite(args.source_state, args.replica_output)

    sys.path.insert(0, str(args.integration_src.resolve()))
    from kch_phl_integration.contracts import validate_reviewable_decision
    from kch_phl_integration.service import EffectiveIntegrationService

    adapter = MISV03Adapter(wheel=args.wheel, corpus=args.corpus, report=args.report, ledgers=args.ledgers, manifest=args.manifest)
    service = EffectiveIntegrationService(args.replica_output)
    initial_projection = service.projection()

    catalog = _json(args.catalog)
    for index, row in enumerate(catalog):
        _write(service, service.register_mutability, f"mis-v03-catalog-{index:02d}", row)
    emitter = {
        "component_id": "kch.mis.v03.adapter",
        "registry_name": "MIS v0.3.1 exact qualitative Bayes service",
        "inventory_state": "DECISION_EMITTER",
        "evidence_ref": "GATE_KCH_MIS_V03_EFFECTIVE_INTEGRATION_v0.1.0",
    }
    _write(service, service.register_emitter, "mis-v03-emitter", emitter)

    description_dispatch = _write(
        service,
        service.dispatch,
        "mis-v03-dispatch-describe",
        "MIS.v0.3.1",
        "describe",
        {},
        adapter.describe,
    )
    audit_payload = {"custody": custody_before, "operation": "FULL_480_RECORD_HISTORICAL_AUDIT"}
    historical_dispatch = _write(
        service,
        service.dispatch,
        "mis-v03-dispatch-historical",
        "MIS.v0.3.1",
        "audit_historical_khc",
        audit_payload,
        adapter.audit_historical_khc,
    )
    historical = historical_dispatch["result"]["executor_result"]
    adapter.verify_certificate(historical)
    _write_json(args.certificate_output, historical)

    report = _json(args.report)
    exact_request = _formal_request(report)
    exact_dispatch = _write(
        service,
        service.dispatch,
        "mis-v03-dispatch-exact-decision",
        "MIS.v0.3.1",
        "exact_decide",
        exact_request,
        lambda: adapter.exact_decide(exact_request),
    )
    exact_certificate = exact_dispatch["result"]["executor_result"]
    verify_dispatch = _write(
        service,
        service.dispatch,
        "mis-v03-dispatch-verify-certificate",
        "MIS.v0.3.1",
        "verify_certificate",
        {"certificate_sha256": exact_certificate["certificate_sha256"]},
        lambda: adapter.verify_certificate(exact_certificate),
    )

    forbidden_executor_called = False
    def forbidden_executor() -> dict[str, Any]:
        nonlocal forbidden_executor_called
        forbidden_executor_called = True
        return {"invalid": True}
    blocked = _write(
        service,
        service.dispatch,
        "mis-v03-dispatch-forbidden-authorize",
        "MIS.v0.3.1",
        "authorize_execution",
        {},
        forbidden_executor,
    )

    decisions = _decision_records(historical, historical_dispatch["result"]["event_hash"])
    validations = [validate_reviewable_decision(record) for record in decisions]
    for index, record in enumerate(decisions):
        _write(service, service.register_decision, f"mis-v03-decision-{index:02d}", record)
    _write_json(args.decisions_output, decisions)

    second_historical = adapter.audit_historical_khc()
    tampered = dict(historical)
    tampered["records"] = 479
    tamper_rejected = False
    try:
        adapter.verify_certificate(tampered)
    except AdapterContractError:
        tamper_rejected = True

    registry = _registry_successor(_json(args.registry_input), args.certificate_output, historical)
    _write_json(args.registry_output, registry)

    source_state_after = sha256_file(args.source_state)
    custody_after = {key: sha256_file(path) for key, path in {
        "wheel": args.wheel, "corpus": args.corpus, "report": args.report, "ledgers": args.ledgers, "manifest": args.manifest
    }.items()}
    final_projection = service.projection()
    integrity = service.verify()
    gate_state = service.gate_state(expected_admitted_rows=18)
    exact_example = report["loss_decision_example"]
    checks = {
        "sealed_mis_custody_hashes_exact": custody_before == EXPECTED == custody_after,
        "source_kch_state_unchanged": source_state_before == source_state_after,
        "kch_routed_description_read_only": description_dispatch["result"]["allowed"] and description_dispatch["result"]["classification"] == "READ_ONLY",
        "kch_routed_all_480_real_records": historical_dispatch["result"]["allowed"] and historical["records"] == 480 and historical["units_unique"] == 480,
        "sixty_persisted_future_only_ledgers_verified": historical["persisted_ledgers_verified"] == 60 and historical["freezes"] == 480 and historical["outcomes"] == 480,
        "live_results_exact_match_frozen_v031": historical["frozen_report_exact_match"] is True,
        "historical_certificate_replay_deterministic": historical == second_historical,
        "historical_certificate_tamper_rejected": tamper_rejected,
        "exact_decision_interface_matches_frozen_formal_example": exact_certificate["posterior"] == exact_example["posterior"] and exact_certificate["decision"] == exact_example["decision"],
        "certificate_verification_routed": verify_dispatch["result"]["executor_result"]["valid"] is True,
        "unclassified_authority_method_failed_closed": blocked["result"]["allowed"] is False and blocked["result"]["executed"] is False and not forbidden_executor_called,
        "mis_methods_registered_read_only": final_projection["mutability_methods"] == initial_projection["mutability_methods"] + 4,
        "mis_registered_as_decision_emitter": final_projection["emitters"] == initial_projection["emitters"] + 1 and final_projection["emitter_states"].get("DECISION_EMITTER") == initial_projection["emitter_states"].get("DECISION_EMITTER", 0) + 1,
        "two_kch_decisions_conformant": len(validations) == 2 and all(item["contract_state"] == "CONFORMANT" for item in validations),
        "two_kch_decisions_registered": final_projection["decisions"] == initial_projection["decisions"] + 2,
        "zero_authority_and_zero_automatic_promotion": not historical["authority_created"] and not historical["execution_authorized"] and not historical["automatic_promotion"] and all(not item["authority_exercised"] for item in decisions),
        "no_phl_session_started": initial_projection["active_phl_session_id"] is None and final_projection["active_phl_session_id"] is None,
        "zero_user_feedback_preserved": final_projection["feedback"] == initial_projection["feedback"] == 0,
        "kch_integration_ledger_integrity_pass": integrity["gate"] == "PASS",
        "bounded_kch_gate_preserved": gate_state["state"] == "PASS_EFFECTIVE_KCH_PHL_INTEGRATION_BOUNDED",
        "registry_successor_adds_exactly_one_mis_row": len(registry) == len(_json(args.registry_input)) + 1,
    }
    result = {
        "schema": "kch.mis.v03.effective-integration-gate-result.v0.1.0",
        "gate": "PASS_BOUNDED" if all(checks.values()) else "FAIL",
        "checks": checks,
        "checks_passed": sum(checks.values()),
        "checks_total": len(checks),
        "initial_projection": initial_projection,
        "final_projection": final_projection,
        "integrity": integrity,
        "gate_state": gate_state,
        "historical_certificate_sha256": historical["certificate_sha256"],
        "exact_decision_certificate_sha256": exact_certificate["certificate_sha256"],
        "decision_ids": [record["decision_id"] for record in decisions],
        "decision_hashes": [item["record_sha256"] for item in validations],
        "source_state_sha256_before": source_state_before,
        "source_state_sha256_after": source_state_after,
        "replica_sha256": sha256_file(args.replica_output),
        "registry_sha256": sha256_file(args.registry_output),
        "evidence_boundary": {
            "demonstrated": [
                "SEALED_MIS_V0_3_1_RUNTIME_INVOCATION_THROUGH_KCH_CONTROL_PLANE",
                "480_REAL_KHC_RECORD_STRUCTURAL_ROUNDTRIP",
                "60_PERSISTED_FUTURE_ONLY_LEDGER_VERIFICATION",
                "EXACT_RATIONAL_DECISION_INTERFACE",
                "KCH_REVIEWABLE_DECISION_ADAPTATION",
                "FAIL_CLOSED_UNCLASSIFIED_AUTHORITY_METHOD",
            ],
            "not_demonstrated": historical["not_demonstrated"],
        },
        "limitations": [
            "The gate is local and replica-bounded; it does not mutate the personal KCH state.",
            "The 480-record corpus is historical; its actions are observations, not adjudicated causal outcomes.",
            "The exact-decision interface conformance call reuses the frozen formal example, whose parameters are not empirical estimates.",
            "Twelve older registry rows remain UNAVAILABLE_CONTRACT, so the complete pre-2G KCH integration gate remains bounded.",
            "No PHL session, user feedback, policy activation, external deployment or global promotion occurred.",
        ],
    }
    _write_json(args.result_output, result)
    csi = lower_to_csi(historical, sha256_file(args.result_output))
    _write_json(args.csi_output, csi)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the effective KCH integration gate for sealed MIS v0.3.1")
    parser.add_argument("--source-state", type=Path, required=True)
    parser.add_argument("--integration-src", type=Path, required=True)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--ledgers", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--registry-input", type=Path, required=True)
    parser.add_argument("--replica-output", type=Path, required=True)
    parser.add_argument("--certificate-output", type=Path, required=True)
    parser.add_argument("--decisions-output", type=Path, required=True)
    parser.add_argument("--registry-output", type=Path, required=True)
    parser.add_argument("--result-output", type=Path, required=True)
    parser.add_argument("--csi-output", type=Path, required=True)
    return parser


def main() -> int:
    result = run(build_parser().parse_args())
    print(json.dumps({"gate": result["gate"], "checks": f"{result['checks_passed']}/{result['checks_total']}", "records": 480, "streams": 60}))
    return 0 if result["gate"] == "PASS_BOUNDED" else 1


if __name__ == "__main__":
    raise SystemExit(main())

