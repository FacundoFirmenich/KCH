from dataclasses import dataclass
from enum import Enum

@dataclass(frozen=True)
class FiniteModel:
    model_id: str
    q: float
    accuracies: tuple[float,...]
    tier: str = "outer"

class ContractState(str, Enum):
    CORE_SHADOW = "C0_CORE_SHADOW"
    CORE_REJECTED = "C1_CORE_REJECTED"
    OUTER_AUTHORITY = "C2_OUTER_AUTHORITY"
    OUTER_REJECTED_HOLD = "C3_OUTER_REJECTED_HOLD"
    FALLBACK_SHADOW = "C4_FALLBACK_SHADOW"
    FALLBACK_AUTHORITY = "C5_FALLBACK_AUTHORITY"
