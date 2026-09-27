from dataclasses import dataclass
from .model import ContractState

@dataclass
class ModelClassGovernor:
    state: ContractState = ContractState.OUTER_AUTHORITY
    core_rejected_at: int|None = None
    outer_rejected_at: int|None = None
    fallback_authorized: bool = False
    def reject_core(self,t):
        self.core_rejected_at=t
        return ContractState.CORE_REJECTED
    def reject_outer(self,t):
        self.outer_rejected_at=t
        self.state=ContractState.OUTER_REJECTED_HOLD
        return self.state
    def request_fallback(self):
        return ContractState.FALLBACK_SHADOW
    def authorize_fallback(self,granted:bool):
        if not granted:
            self.state=ContractState.OUTER_REJECTED_HOLD
            return self.state
        self.fallback_authorized=True
        self.state=ContractState.FALLBACK_AUTHORITY
        return self.state
