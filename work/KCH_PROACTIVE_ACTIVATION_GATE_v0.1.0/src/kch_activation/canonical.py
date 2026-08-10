from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", str(value))
    unaccented = "".join(character for character in decomposed if not unicodedata.combining(character))
    collapsed = " ".join("".join(character.lower() if character.isalnum() else " " for character in unaccented).split())
    return collapsed

