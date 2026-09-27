from dataclasses import dataclass,replace
from enum import Enum
from .generator import CandidateKind
class RegistryState(str,Enum):
    HOLD_MODEL_CLASS_REJECTED="HOLD_MODEL_CLASS_REJECTED"
    CANDIDATE_SHADOW="CANDIDATE_SHADOW"
    CANDIDATE_EVIDENCE_ELIGIBLE="CANDIDATE_EVIDENCE_ELIGIBLE"
    MODEL_CLASS_PATCH_AUTHORIZED="MODEL_CLASS_PATCH_AUTHORIZED"
@dataclass(frozen=True)
class ModelClassRegistry:
    version:int=1; state:RegistryState=RegistryState.HOLD_MODEL_CLASS_REJECTED; patches:tuple[str,...]=(); authority_epoch:int=0
    def register_shadow(self,c):
        if c.state is not CandidateKind.PROTOFORM_REALVIRTUAL_PLUS0: raise ValueError("ONLY_PLUS0_PROTOFORM_CAN_ENTER_SHADOW")
        return self,replace(c,model_class_eligible=False)
    def admit_evidence(self,c,certified):
        if not certified:return self,c
        if c.state is not CandidateKind.PROTOFORM_REALVIRTUAL_PLUS0: raise ValueError("INVALID_CANDIDATE_STATE")
        return replace(self,state=RegistryState.CANDIDATE_EVIDENCE_ELIGIBLE),replace(c,model_class_eligible=True)
    def authorize_patch(self,c,granted):
        if not granted:return replace(self,state=RegistryState.CANDIDATE_EVIDENCE_ELIGIBLE),c
        if not c.model_class_eligible: raise PermissionError("CANDIDATE_NOT_EVIDENCE_ELIGIBLE")
        return replace(self,version=self.version+1,state=RegistryState.MODEL_CLASS_PATCH_AUTHORIZED,patches=self.patches+(c.candidate_id,),authority_epoch=self.authority_epoch+1),c
