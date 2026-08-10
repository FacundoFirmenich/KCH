from __future__ import annotations

import argparse
import json

from .compiler import compile_governance
from .graph import GovernanceGraph


def main() -> None:
    parser = argparse.ArgumentParser(prog="kch-csi-governance")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("governance")
    explain = subparsers.add_parser("explain")
    explain.add_argument("governance")
    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("governance")
    compile_parser.add_argument("target")
    compile_parser.add_argument("--replace", action="store_true")
    args = parser.parse_args()
    graph = GovernanceGraph.load(args.governance)
    if args.command == "validate":
        result = {"schema": "kch.csi-governance-validation.v0.1.0", "gate": "PASS", **graph.csi_projection()}
    elif args.command == "explain":
        result = graph.csi_projection()
    else:
        result = compile_governance(graph, args.target, replace=args.replace)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
