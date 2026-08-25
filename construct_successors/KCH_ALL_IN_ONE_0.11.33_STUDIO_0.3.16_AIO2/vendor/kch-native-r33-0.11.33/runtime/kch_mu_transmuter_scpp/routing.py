from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical import attach_hash
from .contracts import OperatorLineage


@dataclass(frozen=True, slots=True)
class LocalRoute:
    jurisdiction_id: str
    operator: str
    authority_evidence: tuple[str, ...]
    policy_hash: str


class LocalAbstainingRouter:
    def __init__(self, lineages: dict[str, OperatorLineage], routes: tuple[LocalRoute, ...] = ()) -> None:
        self.lineages = dict(lineages)
        self.routes = {item.jurisdiction_id: item for item in routes}

    def route(self, jurisdiction_id: str) -> dict[str, Any]:
        route = self.routes.get(jurisdiction_id)
        if route is None:
            return attach_hash({"jurisdiction_id": jurisdiction_id, "status": "ABSTAIN", "operator": None,
                                "reason": "NO_PREDECLARED_LOCAL_AUTHORITY", "global_winner": None})
        lineage = self.lineages.get(route.operator)
        if lineage is None:
            return attach_hash({"jurisdiction_id": jurisdiction_id, "status": "ABSTAIN", "operator": None,
                                "reason": "UNKNOWN_OPERATOR_LINEAGE", "global_winner": None})
        if lineage.authority != "LOCAL_OPERATIONAL":
            return attach_hash({"jurisdiction_id": jurisdiction_id, "status": "SHADOW_ONLY", "operator": route.operator,
                                "reason": f"LINEAGE_AUTHORITY_{lineage.authority}", "global_winner": None})
        if not route.authority_evidence:
            return attach_hash({"jurisdiction_id": jurisdiction_id, "status": "ABSTAIN", "operator": None,
                                "reason": "EMPTY_AUTHORITY_EVIDENCE", "global_winner": None})
        return attach_hash({"jurisdiction_id": jurisdiction_id, "status": "ROUTE_LOCAL", "operator": route.operator,
                            "authority_evidence": route.authority_evidence, "policy_hash": route.policy_hash,
                            "global_winner": None})

