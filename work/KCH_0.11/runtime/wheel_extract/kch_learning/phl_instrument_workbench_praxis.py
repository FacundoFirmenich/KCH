from __future__ import annotations

from .instrument_service import InstrumentLearningService
from .phl_workbench_praxis import PraxisPHLWorkbench


class PraxisPHLInstrumentWorkbench(PraxisPHLWorkbench):
    service: InstrumentLearningService

    def score_interactive(self, decision_id: str, score: str) -> dict:
        print("INSTRUMENT context; must explicitly contain NOT_USER_DATA:")
        context = input().strip()
        print("INSTRUMENT correction path text; empty is permitted:")
        correction = input().strip()
        return self.service.score_phl_instrument(self.session_id, decision_id, score, context, correction)
