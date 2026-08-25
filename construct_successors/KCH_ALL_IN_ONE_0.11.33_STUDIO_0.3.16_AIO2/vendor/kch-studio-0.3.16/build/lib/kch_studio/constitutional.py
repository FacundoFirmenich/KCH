from __future__ import annotations

import json
import uuid
from copy import deepcopy
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from .contracts import sha256_json
from .recovery import RecoveryVault


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


class Actor(StrEnum):
    USER = "USER"
    MODEL = "MODEL"
    KCH_SYSTEM = "KCH_SYSTEM"


class ConstitutionalAuthorityError(PermissionError):
    pass


class ConstitutionalWorkspace:
    """User-sovereign ranked/nested graph. Models may read and propose, never enact."""

    SCHEMA = "kch.csi-constitutional-workspace.v0.1.0"

    def __init__(self, root: str | Path, workspace_id: str = "default"):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.vault = RecoveryVault(self.root / "recovery")
        self.workspace_id = workspace_id
        self.key = f"constitutional/workspaces/{workspace_id}.json"
        try:
            self._load()
        except KeyError:
            self._initialize()

    @staticmethod
    def _require_user(actor: Actor) -> None:
        if actor is not Actor.USER:
            raise ConstitutionalAuthorityError(
                "constitutional mutation denied: only an explicit USER action may enact or alter this workspace"
            )

    def _initialize(self) -> None:
        box_id = f"BOX-{uuid.uuid4()}"
        state = {
            "schema": self.SCHEMA,
            "workspace_id": self.workspace_id,
            "title": "",
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "authority": {
                "enact": [Actor.USER.value],
                "amend": [Actor.USER.value],
                "model_can_read": True,
                "model_can_propose": True,
                "model_can_mutate": False,
                "model_can_downgrade": False,
            },
            "planes": [{"plane_id": "main", "label": "", "orientation": "VERTICAL", "rank": 1}],
            "boxes": [
                {
                    "box_id": box_id,
                    "plane_id": "main",
                    "parent_box_id": None,
                    "rank": 1,
                    "content": "",
                    "active": True,
                    "constitutional": True,
                    "tags": [],
                    "created_at": utc_now(),
                    "updated_at": utc_now(),
                }
            ],
            "connections": [],
            "first_box_id": box_id,
            "revision": 1,
        }
        self.vault.save_json(
            self.key,
            state,
            kind="CSI_CONSTITUTION",
            actor=Actor.KCH_SYSTEM.value,
            operation="INITIALIZE_EMPTY_FIRST_BOX",
        )

    def _load(self) -> dict[str, Any]:
        value = self.vault.latest(self.key, decode=True)
        state = json.loads(str(value["content"]))
        self._validate(state)
        return state

    def _commit(self, state: dict[str, Any], *, operation: str) -> dict[str, Any]:
        state["updated_at"] = utc_now()
        state["revision"] = int(state.get("revision", 0)) + 1
        self._validate(state)
        receipt = self.vault.save_json(
            self.key, state, kind="CSI_CONSTITUTION", actor=Actor.USER.value, operation=operation
        )
        return {"state": deepcopy(state), "custody": receipt}

    def _validate(self, state: dict[str, Any]) -> None:
        if state.get("schema") != self.SCHEMA:
            raise ValueError("unsupported constitutional workspace schema")
        if state.get("authority", {}).get("model_can_mutate") is not False:
            raise ValueError("model mutation prohibition is missing")
        planes = {item["plane_id"] for item in state.get("planes", [])}
        boxes = state.get("boxes", [])
        ids = [item["box_id"] for item in boxes]
        if not planes or not boxes or len(ids) != len(set(ids)):
            raise ValueError("constitutional workspace requires unique planes and boxes")
        by_id = {item["box_id"]: item for item in boxes}
        if state.get("first_box_id") not in by_id:
            raise ValueError("first box cannot be removed")
        sibling_slots: set[tuple[str, str | None, int]] = set()
        for box in boxes:
            if box["plane_id"] not in planes:
                raise ValueError(f"box references unknown plane: {box['box_id']}")
            parent = box.get("parent_box_id")
            if parent is not None and parent not in by_id:
                raise ValueError(f"box references unknown parent: {box['box_id']}")
            if int(box["rank"]) < 1:
                raise ValueError("box ranks must be positive")
            slot = (box["plane_id"], parent, int(box["rank"]))
            if slot in sibling_slots:
                raise ValueError(f"duplicate sibling rank: {slot}")
            sibling_slots.add(slot)
            seen = {box["box_id"]}
            cursor = parent
            while cursor is not None:
                if cursor in seen:
                    raise ValueError("box nesting cycle detected")
                seen.add(cursor)
                cursor = by_id[cursor].get("parent_box_id")
        connection_ids: set[str] = set()
        for edge in state.get("connections", []):
            if edge["connection_id"] in connection_ids:
                raise ValueError("duplicate connection id")
            connection_ids.add(edge["connection_id"])
            if edge["source_box_id"] not in by_id or edge["target_box_id"] not in by_id:
                raise ValueError("connection endpoint does not exist")

    def state(self) -> dict[str, Any]:
        return deepcopy(self._load())

    def add_plane(
        self, *, label: str, orientation: str, rank: int | None = None, actor: Actor
    ) -> dict[str, Any]:
        self._require_user(actor)
        state = self._load()
        orientations = {"VERTICAL", "HORIZONTAL", "DIAGONAL", "FREEFORM"}
        orientation = orientation.upper()
        if orientation not in orientations:
            raise ValueError(f"orientation must be one of {sorted(orientations)}")
        rank = rank or max(int(item["rank"]) for item in state["planes"]) + 1
        if any(int(item["rank"]) == rank for item in state["planes"]):
            raise ValueError("plane rank already exists")
        plane_id = f"PLANE-{uuid.uuid4()}"
        state["planes"].append(
            {"plane_id": plane_id, "label": label, "orientation": orientation, "rank": rank}
        )
        return self._commit(state, operation="ADD_PLANE")

    def add_box(
        self,
        *,
        plane_id: str = "main",
        parent_box_id: str | None = None,
        rank: int | None = None,
        content: str = "",
        tags: list[str] | None = None,
        constitutional: bool = True,
        actor: Actor,
    ) -> dict[str, Any]:
        self._require_user(actor)
        state = self._load()
        siblings = [
            item
            for item in state["boxes"]
            if item["plane_id"] == plane_id and item.get("parent_box_id") == parent_box_id
        ]
        rank = rank or (max((int(item["rank"]) for item in siblings), default=0) + 1)
        box_id = f"BOX-{uuid.uuid4()}"
        timestamp = utc_now()
        state["boxes"].append(
            {
                "box_id": box_id,
                "plane_id": plane_id,
                "parent_box_id": parent_box_id,
                "rank": rank,
                "content": content,
                "active": True,
                "constitutional": bool(constitutional),
                "tags": sorted(set(tags or [])),
                "created_at": timestamp,
                "updated_at": timestamp,
            }
        )
        result = self._commit(state, operation="ADD_BOX")
        result["box_id"] = box_id
        return result

    def update_box(self, box_id: str, content: str, *, actor: Actor) -> dict[str, Any]:
        self._require_user(actor)
        state = self._load()
        box = next((item for item in state["boxes"] if item["box_id"] == box_id), None)
        if box is None:
            raise KeyError(box_id)
        box["content"] = content
        box["updated_at"] = utc_now()
        return self._commit(state, operation="UPDATE_BOX_CONTENT")

    def set_box_active(self, box_id: str, active: bool, *, actor: Actor) -> dict[str, Any]:
        self._require_user(actor)
        state = self._load()
        box = next((item for item in state["boxes"] if item["box_id"] == box_id), None)
        if box is None:
            raise KeyError(box_id)
        box["active"] = bool(active)
        box["updated_at"] = utc_now()
        return self._commit(state, operation="SET_BOX_ACTIVE")

    def connect(
        self,
        source_box_id: str,
        target_box_id: str,
        *,
        relation: str,
        label: str = "",
        directed: bool = True,
        actor: Actor,
    ) -> dict[str, Any]:
        self._require_user(actor)
        if not relation.strip():
            raise ValueError("relation is user-defined but cannot be empty")
        state = self._load()
        connection_id = f"EDGE-{uuid.uuid4()}"
        state["connections"].append(
            {
                "connection_id": connection_id,
                "source_box_id": source_box_id,
                "target_box_id": target_box_id,
                "relation": relation,
                "label": label,
                "directed": bool(directed),
                "created_at": utc_now(),
            }
        )
        result = self._commit(state, operation="CONNECT_BOXES")
        result["connection_id"] = connection_id
        return result

    def propose(self, proposal: dict[str, Any], *, actor: Actor = Actor.MODEL) -> dict[str, Any]:
        if actor is Actor.USER:
            raise ValueError(
                "user changes should be enacted directly, not stored as model proposals"
            )
        proposal_id = f"PROPOSAL-{uuid.uuid4()}"
        value = {
            "schema": "kch.csi-constitutional-proposal.v0.1.0",
            "proposal_id": proposal_id,
            "workspace_id": self.workspace_id,
            "actor": actor.value,
            "status": "PROPOSED_NOT_ENACTED",
            "proposal": proposal,
            "created_at": utc_now(),
        }
        receipt = self.vault.save_json(
            f"constitutional/proposals/{proposal_id}.json",
            value,
            kind="CSI_CONSTITUTIONAL_PROPOSAL",
            actor=actor.value,
            operation="PROPOSE_NO_MUTATION",
        )
        return {**value, "custody": receipt}

    def effective_mandates(self) -> dict[str, Any]:
        state = self._load()
        plane_rank = {item["plane_id"]: int(item["rank"]) for item in state["planes"]}
        by_id = {item["box_id"]: item for item in state["boxes"]}

        def path(box: dict[str, Any]) -> tuple[int, ...]:
            values = [int(box["rank"])]
            cursor = box.get("parent_box_id")
            while cursor is not None:
                parent = by_id[cursor]
                values.append(int(parent["rank"]))
                cursor = parent.get("parent_box_id")
            return tuple(reversed(values))

        mandates = [
            {
                "box_id": box["box_id"],
                "plane_id": box["plane_id"],
                "plane_rank": plane_rank[box["plane_id"]],
                "rank_path": list(path(box)),
                "content": box["content"],
                "tags": box["tags"],
                "constitutional": box["constitutional"],
            }
            for box in state["boxes"]
            if box["active"] and box["content"].strip()
        ]
        mandates.sort(key=lambda item: (item["plane_rank"], item["rank_path"], item["box_id"]))
        return {
            "schema": "kch.csi-effective-constitution.v0.1.0",
            "workspace_id": self.workspace_id,
            "source_revision": state["revision"],
            "source_hash": sha256_json(state),
            "mandates": mandates,
            "model_mutation_authorized": False,
        }
