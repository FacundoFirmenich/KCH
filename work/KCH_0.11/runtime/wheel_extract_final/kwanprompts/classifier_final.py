from __future__ import annotations

import re
from typing import Any

from .classifier import FirstSeparator as _FirstSeparator


class FirstSeparator(_FirstSeparator):
    """Final v0.1 separator with interaction-wrapper tolerant continuation rules."""

    def classify_segment(self, raw_text: str) -> dict[str, Any]:
        prepared = re.sub(r"^[\s>*\\/!.]+", "", raw_text)
        return super().classify_segment(prepared)

