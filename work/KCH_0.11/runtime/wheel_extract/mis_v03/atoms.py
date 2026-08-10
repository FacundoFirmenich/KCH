from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class SemanticAtom:
    atom_id: str
    kind: str
    skins: Mapping[str, str]

    def __post_init__(self) -> None:
        if not self.atom_id or "." not in self.atom_id:
            raise ValueError("atom_id must be a stable namespaced identifier")
        if not self.kind:
            raise ValueError("atom kind is required")
        normalized = dict(self.skins)
        if not normalized or any(not key or not value for key, value in normalized.items()):
            raise ValueError("an atom requires non-empty language skins")
        object.__setattr__(self, "skins", MappingProxyType(normalized))

    def render(self, language: str = "canonical") -> str:
        if language in self.skins:
            return self.skins[language]
        if "canonical" in self.skins:
            return self.skins["canonical"]
        raise KeyError(f"no skin {language!r} for {self.atom_id}")

    def to_payload(self) -> dict[str, object]:
        return {"atom_id": self.atom_id, "kind": self.kind, "skins": dict(self.skins)}


class AtomRegistry:
    def __init__(self) -> None:
        self._atoms: dict[str, SemanticAtom] = {}
        self._skins: dict[tuple[str, str], str] = {}

    def register(self, atom: SemanticAtom) -> None:
        if atom.atom_id in self._atoms:
            raise ValueError(f"duplicate atom_id: {atom.atom_id}")
        for language, skin in atom.skins.items():
            key = (language, skin)
            if key in self._skins:
                raise ValueError(f"skin collision {language}:{skin}")
        self._atoms[atom.atom_id] = atom
        for language, skin in atom.skins.items():
            self._skins[(language, skin)] = atom.atom_id

    def get(self, atom_id: str) -> SemanticAtom:
        return self._atoms[atom_id]

    def parse(self, skin: str, language: str = "canonical") -> SemanticAtom:
        return self.get(self._skins[(language, skin)])

    def atom_ids(self, kind: str | None = None) -> tuple[str, ...]:
        atoms = self._atoms.values()
        if kind is not None:
            atoms = (atom for atom in atoms if atom.kind == kind)
        return tuple(sorted(atom.atom_id for atom in atoms))

    def to_payload(self) -> list[dict[str, object]]:
        return [self._atoms[key].to_payload() for key in sorted(self._atoms)]
