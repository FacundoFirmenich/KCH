from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np

AMBIGUITY_RATIO = 1.10
MAX_DISTANCE_KM = 20.0


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location("kch_terminal_prepare_base", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def aki_richards_p_axis(strike_deg, dip_deg, rake_deg):
    strike = np.deg2rad(np.asarray(strike_deg, dtype=float))
    dip = np.deg2rad(np.asarray(dip_deg, dtype=float))
    rake = np.deg2rad(np.asarray(rake_deg, dtype=float))
    normal = np.stack(
        [
            -np.sin(dip) * np.sin(strike),
            np.sin(dip) * np.cos(strike),
            -np.cos(dip),
        ],
        axis=1,
    )
    slip = np.stack(
        [
            np.cos(rake) * np.cos(strike) + np.sin(rake) * np.cos(dip) * np.sin(strike),
            np.cos(rake) * np.sin(strike) - np.sin(rake) * np.cos(dip) * np.cos(strike),
            -np.sin(rake) * np.sin(dip),
        ],
        axis=1,
    )
    normal /= np.linalg.norm(normal, axis=1)[:, None]
    slip /= np.linalg.norm(slip, axis=1)[:, None]
    axis = slip - normal
    axis /= np.linalg.norm(axis, axis=1)[:, None]
    return axis


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--network-root", type=Path, required=True)
    parser.add_argument("--directional-root", type=Path, required=True)
    parser.add_argument("--fault-geojson", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    module = load_module(args.script)
    module.p_axis = aki_richards_p_axis

    class AmbiguityAwareOracle:
        instances: list["AmbiguityAwareOracle"] = []

        def __init__(self, graph, positions, node_map):
            self.graph = graph
            self.positions = positions
            self.node_map = node_map
            self.path_cache: dict[tuple[str, str], tuple[float, ...]] = {}
            self.query_count = 0
            self.accepted_count = 0
            self.distance_cutoff_count = 0
            self.ambiguous_count = 0
            self.no_path_count = 0
            AmbiguityAwareOracle.instances.append(self)

        def two_lengths(self, left: str, right: str) -> tuple[float, ...]:
            key = tuple(sorted((left, right)))
            if key in self.path_cache:
                return self.path_cache[key]
            if left == right:
                self.path_cache[key] = (0.0,)
                return (0.0,)
            lengths: list[float] = []
            try:
                generator = nx.shortest_simple_paths(self.graph, left, right, weight="weight")
                for _ in range(2):
                    path = next(generator)
                    length = float(sum(self.graph[a][b]["weight"] for a, b in zip(path, path[1:])))
                    lengths.append(length)
            except (nx.NetworkXNoPath, StopIteration):
                pass
            result = tuple(lengths)
            self.path_cache[key] = result
            return result

        def distance(self, left_fault: int, left_along: float, right_fault: int, right_along: float) -> float | None:
            self.query_count += 1
            candidates: list[float] = []
            if left_fault == right_fault:
                candidates.append(abs(left_along - right_along))
            for left_node, left_cost in module.anchors(left_fault, left_along, self.positions, self.node_map):
                for right_node, right_cost in module.anchors(right_fault, right_along, self.positions, self.node_map):
                    for middle in self.two_lengths(left_node, right_node):
                        candidates.append(float(left_cost + middle + right_cost))
            if not candidates:
                self.no_path_count += 1
                return None
            unique = []
            for value in sorted(candidates):
                if not unique or abs(value - unique[-1]) > 1e-6:
                    unique.append(value)
            best = unique[0]
            if best > MAX_DISTANCE_KM:
                self.distance_cutoff_count += 1
                return None
            if len(unique) > 1:
                second = unique[1]
                if best <= 1e-9:
                    ambiguous = second <= 1e-6
                else:
                    ambiguous = (second / best) < AMBIGUITY_RATIO
                if ambiguous:
                    self.ambiguous_count += 1
                    return None
            self.accepted_count += 1
            return best

    module.Oracle = AmbiguityAwareOracle
    sys.argv = [
        str(args.script),
        "--network-root", str(args.network_root),
        "--directional-root", str(args.directional_root),
        "--fault-geojson", str(args.fault_geojson),
        "--protocol", str(args.protocol),
        "--out", str(args.out),
    ]
    try:
        return_code = int(module.main())
    except SystemExit as exc:
        return_code = int(exc.code or 0)
    totals = {
        "queries": sum(instance.query_count for instance in AmbiguityAwareOracle.instances),
        "accepted": sum(instance.accepted_count for instance in AmbiguityAwareOracle.instances),
        "abstained_ambiguous_multiple_paths": sum(instance.ambiguous_count for instance in AmbiguityAwareOracle.instances),
        "rejected_distance_cutoff": sum(instance.distance_cutoff_count for instance in AmbiguityAwareOracle.instances),
        "rejected_no_path": sum(instance.no_path_count for instance in AmbiguityAwareOracle.instances),
        "cached_anchor_node_pairs": sum(len(instance.path_cache) for instance in AmbiguityAwareOracle.instances),
    }
    receipt = {
        "format": "KCH_SEISMIC_PATH_AMBIGUITY_IMPLEMENTATION_RECEIPT_V1_1",
        "locked_criterion": "SECOND_PATH_TO_FIRST_PATH_LENGTH_RATIO_BELOW_1_10_IMPLIES_ABSTENTION",
        "ambiguity_ratio": AMBIGUITY_RATIO,
        "maximum_network_distance_km": MAX_DISTANCE_KM,
        "topology_changed": False,
        "scientific_threshold_changed": False,
        "directional_values_used_to_choose_paths": False,
        "statistics": totals,
        "authority_ceiling": "NONE",
    }
    receipt["receipt_id"] = "s11path:" + hashlib.sha256(canonical(receipt)).hexdigest()
    receipt_path = args.out / "PATH_AMBIGUITY_IMPLEMENTATION_RECEIPT.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    convention_receipt = {
        "format": "KCH_SDR_TO_PRINCIPAL_AXIS_CONVENTION_RECEIPT_V1_1",
        "coordinate_system": "NORTH_EAST_DOWN",
        "fault_normal": "[-sin(dip)sin(strike), sin(dip)cos(strike), -cos(dip)]",
        "slip_vector": "[cos(rake)cos(strike)+sin(rake)cos(dip)sin(strike), cos(rake)sin(strike)-sin(rake)cos(dip)cos(strike), -sin(rake)sin(dip)]",
        "p_axis": "NORMALIZED_SLIP_MINUS_NORMAL",
        "source_convention": "AKI_RICHARDS_NED",
        "previous_materialization_result_used_for_scientific_adjudication": False,
        "scientific_threshold_changed": False,
        "authority_ceiling": "NONE",
    }
    convention_receipt["receipt_id"] = "s11sdr:" + hashlib.sha256(canonical(convention_receipt)).hexdigest()
    (args.out / "SDR_AXIS_CONVENTION_RECEIPT.json").write_text(
        json.dumps(convention_receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    report_path = args.out / "SEISMIC_TERMINAL_INPUT_MATERIALIZATION_V1_1.json"
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["path_ambiguity_receipt_id"] = receipt["receipt_id"]
        report["path_ambiguity_statistics"] = totals
        report["sdr_axis_convention_receipt_id"] = convention_receipt["receipt_id"]
        report["materialization_id_before_wrapper_receipts"] = report.get("materialization_id")
        report.pop("materialization_id", None)
        report["materialization_id"] = "s11mat:" + hashlib.sha256(canonical(report)).hexdigest()
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    print(json.dumps(convention_receipt, indent=2, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
