"""KCH instruction-governance candidate.

This package is a CSI successor candidate.  It does not alter the stable KCH
release and creates no authority merely by being imported.
"""

from .credal import ConditionedCredalSet, LinearCredalSet, StateSpace
from .integration import KCHInstructionGovernance
from .models import (
    DecisionState,
    GovernanceContext,
    GovernanceLayer,
    Instruction,
    InstructionEffect,
    LifecycleState,
)

__all__ = [
    "ConditionedCredalSet",
    "DecisionState",
    "GovernanceContext",
    "GovernanceLayer",
    "Instruction",
    "InstructionEffect",
    "KCHInstructionGovernance",
    "LifecycleState",
    "LinearCredalSet",
    "StateSpace",
]

__version__ = "0.3.0"
