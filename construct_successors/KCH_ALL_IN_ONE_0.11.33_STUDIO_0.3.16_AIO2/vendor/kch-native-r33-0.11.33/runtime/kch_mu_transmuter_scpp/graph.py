from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .canonical import attach_hash
from .layers import LayerByteReceipt


@dataclass(frozen=True, slots=True)
class Relation:
    source: str
    target: str
    relation: str
    authority: str = "NONE"


def rgg_from_layer_byte(receipt: LayerByteReceipt) -> dict[str, Any]:
    nodes = [{"id": f"process:{receipt.process_id}", "kind": "PROCESS"}]
    edges: list[Relation] = []
    for block in receipt.ordered_blocks:
        block_id = f"block:{block}"
        nodes.append({"id": block_id, "kind": "ORDERED_BLOCK"})
        edges.append(Relation(f"process:{receipt.process_id}", block_id, "CONTAINS_ORDERED", "NONE"))
        for layer in (1, 2, 3):
            layer_id = f"layer:{layer}:block:{block}"
            nodes.append({"id": layer_id, "kind": "LAYER_PAIR"})
            edges.append(Relation(block_id, layer_id, "HAS_LAYER", "NONE"))
    return attach_hash({
        "schema": "kch.rgg-layer-byte.v0.1.0",
        "nodes": sorted(nodes, key=lambda item: item["id"]),
        "edges": [asdict(relation) for relation in sorted(edges, key=lambda item: (item.source, item.target, item.relation))],
        "authority_created": False,
        "global_winner": None,
        "claim_boundary": "RGG records relations and order; it does not make scientific relations true or grant authority.",
    })


def rgg_historical_summary(source_sha256: str, coordinates: dict[str, list[str]]) -> dict[str, Any]:
    nodes = [{"id": f"source:{source_sha256}", "kind": "HISTORICAL_EVIDENCE"}]
    edges = []
    for layer, labels in sorted(coordinates.items()):
        nodes.append({"id": f"layer:{layer}", "kind": "HISTORICAL_LAYER"})
        edges.append({"source": f"source:{source_sha256}", "target": f"layer:{layer}", "relation": "REPORTS", "authority": "NONE"})
        for index, label in enumerate(labels):
            node = f"coordinate:{layer}:{index}:{label}"
            nodes.append({"id": node, "kind": "ORDERED_COORDINATE"})
            edges.append({"source": f"layer:{layer}", "target": node, "relation": "ORDERS", "authority": "NONE"})
    return attach_hash({"schema": "kch.rgg-historical-onboarding.v0.1.0", "nodes": nodes, "edges": edges,
                        "authority_created": False, "global_winner": None})
