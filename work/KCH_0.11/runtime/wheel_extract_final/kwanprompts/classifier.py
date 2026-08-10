from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Pattern

from .canonical import sha256_text


def normalized(text: str) -> str:
    value = unicodedata.normalize("NFKD", text.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = re.sub(r"\s+", " ", value).strip()
    return value


@dataclass(frozen=True)
class Rule:
    rule_id: str
    branch: str
    subtype: str
    pattern: Pattern[str]
    weight: int


STRATEGIC_RULES = (
    Rule(
        "S01_EXPLICIT_CORRECTION",
        "STRATEGIC_OR_INFORMATIVE",
        "CORRECTION_OR_SUPERSESSION",
        re.compile(r"\b(no es|no se llama|corrijo|correccion|correcto es|queda descartado|no utilizo|no existe|sino que)\b"),
        5,
    ),
    Rule(
        "S02_ARCHITECTURAL_STRUCTURE",
        "STRATEGIC_OR_INFORMATIVE",
        "ARCHITECTURAL_DECISION",
        re.compile(r"\b(arquitectura|sistema nodriza|integr\w*|orquest\w*|gobiern\w*|capas?|niveles?|anidad\w*|subanidad\w*|intraconect\w*|interconect\w*|identitas|modus|csi|kwancode|kch|kwanprompts|kwandocs|super[ -]?mcp)\b"),
        2,
    ),
    Rule(
        "S03_GOVERNING_OBLIGATION",
        "STRATEGIC_OR_INFORMATIVE",
        "INVARIANT_OR_REQUIREMENT",
        re.compile(r"\b(tiene que|tenes que|debe|deben|fundamental|regla|invariante|canon\w*|objetivo|queda prohibido|no se puede)\b"),
        3,
    ),
    Rule(
        "S04_EVIDENCE_OR_STATE",
        "STRATEGIC_OR_INFORMATIVE",
        "EVIDENCE_OR_PROJECT_STATE",
        re.compile(r"\b(ejecutad\w*|pendiente|not_estimable|resultado\w*|evidencia|licencia\w*|version\w*|sha[ -]?256|paso|pass|fallo|failed)\b"),
        3,
    ),
    Rule(
        "S05_AUTHORIAL_PROVENANCE",
        "STRATEGIC_OR_INFORMATIVE",
        "AUTHORIAL_PROVENANCE",
        re.compile(r"\b(yo hago|desde hace|hace largo tiempo|experiencia|llevo [a-z0-9 ]+anos|llevo [a-z0-9 ]+dias)\b"),
        3,
    ),
    Rule(
        "S06_EXPERIMENTAL_ANALOGICAL_HYPOTHESIS",
        "STRATEGIC_OR_INFORMATIVE",
        "03_EXPERIMENTAL_ANALOGICAL_HYPOTHESIS",
        re.compile(r"\b(analoga|analogo|analogia|previsualiz\w*|hipotesis|se me acaba|acaban? de ocurrir)\b"),
        3,
    ),
    Rule(
        "S07_NEW_SYSTEM_COMPONENT",
        "STRATEGIC_OR_INFORMATIVE",
        "NEW_COMPONENT_OR_INTEGRATION",
        re.compile(r"\b(nueva herramienta|nuevo componente|desarrollar|integrar|incorporar|prepaquet\w*|predisen\w*)\b"),
        3,
    ),
    Rule(
        "S08_NAMING_TAXONOMY",
        "STRATEGIC_OR_INFORMATIVE",
        "CANONICAL_NAMING_OR_TAXONOMY",
        re.compile(r"\b(qas|cas|rdss|rds|rgg|kwanforks|kwanprompts|kch|khc|uas)\b"),
        1,
    ),
)


INTERMEDIATE_RULES = (
    Rule(
        "I01_CONTINUATION_SIGNAL",
        "INTERMEDIATE_OR_IRRELEVANT",
        "CONTINUATION_SIGNAL",
        re.compile(r"^(continua|procede|prosigue|dale|segui|sigue|ok|oka|listo)[ >\\/.*!]*$"),
        5,
    ),
    Rule(
        "I02_TRANSIENT_OPERATING_CONTEXT",
        "INTERMEDIATE_OR_IRRELEVANT",
        "TRANSIENT_OPERATING_CONTEXT",
        re.compile(r"\b(ahora mismo|estoy en el ordenador|estaba por remoto|en una hora|por el momento)\b"),
        2,
    ),
    Rule(
        "I03_STATUS_OR_NAVIGATION",
        "INTERMEDIATE_OR_IRRELEVANT",
        "STATUS_OR_NAVIGATION",
        re.compile(r"^(y entonces que|como seguimos|que estas haciendo|en que estado esta|status)[ ?!]*$"),
        3,
    ),
    Rule(
        "I04_EXPLICIT_IRRELEVANCE",
        "INTERMEDIATE_OR_IRRELEVANT",
        "EXPLICITLY_MARKED_IRRELEVANT",
        re.compile(r"\b(esto es irrelevante|ignora este mensaje|sin relacion con la tarea)\b"),
        5,
    ),
)


class FirstSeparator:
    SCHEMA = "kwanprompts.first-separator.v0.1.0"

    @staticmethod
    def segments(raw_text: str) -> list[dict[str, Any]]:
        if not isinstance(raw_text, str) or not raw_text:
            raise ValueError("raw_text must be a non-empty string")
        spans: list[tuple[int, int]] = []
        start = 0
        for match in re.finditer(r"(?:\r?\n\s*){2,}", raw_text):
            left = start
            right = match.start()
            while left < right and raw_text[left].isspace():
                left += 1
            while right > left and raw_text[right - 1].isspace():
                right -= 1
            if left < right:
                spans.append((left, right))
            start = match.end()
        left = start
        right = len(raw_text)
        while left < right and raw_text[left].isspace():
            left += 1
        while right > left and raw_text[right - 1].isspace():
            right -= 1
        if left < right:
            spans.append((left, right))
        return [
            {
                "segment_id": f"seg-{index:04d}",
                "start": left,
                "end": right,
                "raw_text": raw_text[left:right],
                "raw_sha256": sha256_text(raw_text[left:right]),
            }
            for index, (left, right) in enumerate(spans, start=1)
        ]

    def classify_segment(self, raw_text: str) -> dict[str, Any]:
        norm = normalized(raw_text)
        strategic = [rule for rule in STRATEGIC_RULES if rule.pattern.search(norm)]
        intermediate = [rule for rule in INTERMEDIATE_RULES if rule.pattern.search(norm)]
        strategic_score = sum(rule.weight for rule in strategic)
        intermediate_score = sum(rule.weight for rule in intermediate)

        if strategic_score >= 3:
            branch = "STRATEGIC_OR_INFORMATIVE"
            disposition = "CLASSIFIED"
            selected = strategic
            confidence = "RULE_BOUND_HIGH" if strategic_score >= 5 else "RULE_BOUND_MODERATE"
        elif intermediate_score >= 3:
            branch = "INTERMEDIATE_OR_IRRELEVANT"
            disposition = "CLASSIFIED"
            selected = intermediate
            confidence = "RULE_BOUND_HIGH" if intermediate_score >= 5 else "RULE_BOUND_MODERATE"
        else:
            branch = None
            disposition = "REVIEW_REQUIRED"
            selected = strategic + intermediate
            confidence = "UNRESOLVED"

        return {
            "schema": self.SCHEMA,
            "branch": branch,
            "disposition": disposition,
            "subtypes": sorted({rule.subtype for rule in selected}),
            "matched_rules": [rule.rule_id for rule in selected],
            "strategic_score": strategic_score,
            "intermediate_score": intermediate_score,
            "confidence": confidence,
            "irrelevance_inferred": False,
            "claim_boundary": "Deterministic lexical-structural first separator; no semantic canonization or autonomous authority",
        }

    def classify_message(self, raw_text: str) -> dict[str, Any]:
        segments = self.segments(raw_text)
        classified = []
        for segment in segments:
            classified.append({**segment, "classification": self.classify_segment(segment["raw_text"])})
        branches = [item["classification"]["branch"] for item in classified]
        if "STRATEGIC_OR_INFORMATIVE" in branches:
            branch = "STRATEGIC_OR_INFORMATIVE"
            disposition = "CLASSIFIED"
        elif branches and all(item == "INTERMEDIATE_OR_IRRELEVANT" for item in branches):
            branch = "INTERMEDIATE_OR_IRRELEVANT"
            disposition = "CLASSIFIED"
        else:
            branch = None
            disposition = "REVIEW_REQUIRED"
        return {
            "schema": "kwanprompts.message-structure.v0.1.0",
            "raw_sha256": sha256_text(raw_text),
            "branch": branch,
            "disposition": disposition,
            "segments": classified,
            "raw_preserved": True,
            "canonical_promotion": "NOT_REQUESTED",
            "authority_created": False,
        }

