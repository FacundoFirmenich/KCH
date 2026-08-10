from __future__ import annotations

from .classifier_final import FirstSeparator
from .ledger import KwanPromptsLedger
from .service import KwanPromptsService as _KwanPromptsService


class KwanPromptsService(_KwanPromptsService):
    def __init__(self, ledger: KwanPromptsLedger):
        super().__init__(ledger)
        self.separator = FirstSeparator()

