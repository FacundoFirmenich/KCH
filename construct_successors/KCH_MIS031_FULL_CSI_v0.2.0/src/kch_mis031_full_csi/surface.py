from __future__ import annotations

import ast
import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


EXPECTED_WHEEL_SHA256 = "be03cb2b594e22f662da5b74d8689384de8c1bde3d466fe18772dedbf0c89157"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    return ast.unparse(node.args)


def _decorators(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    return {ast.unparse(item) for item in node.decorator_list}


def _symbol_route(module: str, symbol: str, kind: str) -> str:
    leaf = module.rsplit(".", 1)[-1]
    name = symbol.rsplit(".", 1)[-1]
    owner = symbol.split(".", 1)[0] if "." in symbol else ""

    if kind == "CONSTANT":
        return "mis_status"
    if kind == "CLASS":
        return "ERROR_CONTRACT" if name.endswith("Error") else "TYPE_CONTRACT"
    if name in {"__init__", "__post_init__"}:
        return "TYPE_CONTRACT"
    if name == "main":
        return "CLI_ENTRYPOINT"

    explicit: dict[tuple[str, str], str] = {
        ("canonical", "exact_fraction"): "mis_canonical_exact_fraction",
        ("canonical", "validate_identifier_tuple"): "mis_canonical_validate_identifiers",
        ("canonical", "fraction_text"): "mis_canonical_fraction_text",
        ("canonical", "parse_fraction"): "mis_canonical_parse_fraction",
        ("canonical", "canonical_value"): "mis_canonical_value",
        ("canonical", "canonical_json"): "mis_canonical_json",
        ("canonical", "sha256_payload"): "mis_canonical_sha256_payload",
        ("canonical", "sha256_file"): "mis_canonical_sha256_file",
        ("decision", "bayes_decide"): "mis_bayes_decide",
        ("exact", "dirichlet_predictive"): "mis_dirichlet_predictive",
        ("exact", "categorical_brier"): "mis_categorical_brier",
        ("experiments", "exact_structural_exhaustion"): "mis_exact_structural_exhaustion",
        ("experiments", "exact_loss_example"): "mis_exact_loss_example",
        ("experiments", "khc_future_only_replay"): "mis_khc_future_only_replay",
        ("experiments", "run_all"): "mis_experiments_run_all",
        ("khc", "khc_action_registry"): "mis_khc_action_registry",
        ("khc", "load_khc_corpus"): "mis_khc_load_corpus",
        ("khc", "constitute_units"): "mis_khc_constitute_units",
        ("khc", "integration_audit"): "mis_khc_integration_audit",
        ("khc", "records_by_stream"): "mis_khc_records_by_stream",
    }
    if (leaf, name) in explicit:
        return explicit[(leaf, name)]

    class_routes: dict[tuple[str, str], dict[str, str]] = {
        ("atoms", "SemanticAtom"): {
            "render": "mis_atom_render",
            "to_payload": "mis_atom_create",
        },
        ("atoms", "AtomRegistry"): {
            "register": "mis_atom_registry_register",
            "get": "mis_atom_registry_get",
            "parse": "mis_atom_registry_parse",
            "atom_ids": "mis_atom_registry_ids",
            "to_payload": "mis_atom_registry_payload",
        },
        ("decision", "LossTable"): {
            "risk": "mis_loss_risk",
            "to_payload": "mis_loss_table_create",
        },
        ("decision", "BayesDecision"): {"to_payload": "mis_bayes_decide"},
        ("exact", "ExactDistribution"): {
            "from_mapping": "mis_distribution_create",
            "uniform": "mis_distribution_uniform",
            "as_mapping": "mis_distribution_mapping",
            "probability": "mis_distribution_probability",
            "update": "mis_distribution_update",
            "to_payload": "mis_distribution_create",
            "from_payload": "mis_distribution_create",
        },
        ("freeze", "FrozenRound"): {
            "create": "mis_frozen_round_create",
            "from_payload": "mis_frozen_round_verify",
            "core_payload": "mis_frozen_round_verify",
            "to_payload": "mis_frozen_round_verify",
            "verify": "mis_frozen_round_verify",
        },
        ("freeze", "OutcomeReceipt"): {
            "create": "mis_outcome_receipt_create",
            "from_payload": "mis_outcome_receipt_verify",
            "core_payload": "mis_outcome_receipt_verify",
            "to_payload": "mis_outcome_receipt_verify",
            "verify": "mis_outcome_receipt_verify",
        },
        ("freeze", "FutureOnlyLedger"): {
            "freezes": "mis_ledger_status",
            "outcomes": "mis_ledger_status",
            "counts_before": "mis_ledger_counts_before",
            "prior_for": "mis_ledger_prior_for",
            "freeze": "mis_ledger_freeze",
            "observe": "mis_ledger_observe",
            "verify": "mis_ledger_verify",
            "to_payload": "mis_ledger_status",
            "from_payload": "mis_ledger_verify",
        },
        ("khc", "KHCDecisionRecord"): {
            "coordinate": "mis_khc_record_validate",
            "to_payload": "mis_khc_record_validate",
            "from_payload": "mis_khc_record_validate",
        },
        ("khc", "MISKHCDecisionUnit"): {
            "constitute": "mis_khc_unit_constitute",
            "core_payload": "mis_khc_unit_verify",
            "to_payload": "mis_khc_unit_verify",
            "from_payload": "mis_khc_unit_verify",
            "sense_form": "mis_khc_unit_sense",
            "explain_form": "mis_khc_unit_explain",
        },
    }
    return class_routes.get((leaf, owner), {}).get(name, "UNCLASSIFIED")


def scan_wheel(path: str | Path) -> dict[str, Any]:
    wheel = Path(path).resolve()
    data = wheel.read_bytes()
    wheel_sha256 = _sha256(data)
    if wheel_sha256 != EXPECTED_WHEEL_SHA256:
        raise ValueError(
            f"MIS wheel custody mismatch: expected {EXPECTED_WHEEL_SHA256}, got {wheel_sha256}"
        )

    members: list[dict[str, Any]] = []
    symbols: list[dict[str, Any]] = []
    with zipfile.ZipFile(wheel) as archive:
        for info in sorted(archive.infolist(), key=lambda item: item.filename):
            member_data = archive.read(info.filename)
            members.append(
                {
                    "path": info.filename,
                    "bytes": info.file_size,
                    "sha256": _sha256(member_data),
                }
            )
            if not info.filename.startswith("mis_v03/") or not info.filename.endswith(".py"):
                continue
            module = info.filename[:-3].replace("/", ".")
            tree = ast.parse(member_data.decode("utf-8"), filename=info.filename)
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                    symbols.append(
                        {
                            "module": module,
                            "symbol": node.name,
                            "kind": "FUNCTION",
                            "signature": _signature(node),
                            "route": _symbol_route(module, node.name, "FUNCTION"),
                        }
                    )
                elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    symbols.append(
                        {
                            "module": module,
                            "symbol": node.name,
                            "kind": "CLASS",
                            "signature": None,
                            "route": _symbol_route(module, node.name, "CLASS"),
                        }
                    )
                    for child in node.body:
                        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            continue
                        if child.name.startswith("_") and child.name not in {"__init__", "__post_init__"}:
                            continue
                        decorators = _decorators(child)
                        method_kind = (
                            "PROPERTY"
                            if "property" in decorators
                            else "CLASS_METHOD"
                            if "classmethod" in decorators
                            else "METHOD"
                        )
                        symbol = f"{node.name}.{child.name}"
                        symbols.append(
                            {
                                "module": module,
                                "symbol": symbol,
                                "kind": method_kind,
                                "signature": _signature(child),
                                "route": _symbol_route(module, symbol, method_kind),
                            }
                        )
                elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                    targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                    for target in targets:
                        if isinstance(target, ast.Name) and target.id.isupper():
                            symbols.append(
                                {
                                    "module": module,
                                    "symbol": target.id,
                                    "kind": "CONSTANT",
                                    "signature": None,
                                    "route": _symbol_route(module, target.id, "CONSTANT"),
                                }
                            )

    symbols.sort(key=lambda item: (item["module"], item["symbol"], item["kind"]))
    unclassified = [f"{item['module']}:{item['symbol']}" for item in symbols if item["route"] == "UNCLASSIFIED"]
    manifest_core = {
        "schema": "kch.mis031.public-surface.v0.2.0",
        "wheel_sha256": wheel_sha256,
        "members": members,
        "symbols": symbols,
        "unclassified": unclassified,
    }
    return {
        **manifest_core,
        "manifest_sha256": _sha256(
            (json.dumps(manifest_core, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        ),
    }
