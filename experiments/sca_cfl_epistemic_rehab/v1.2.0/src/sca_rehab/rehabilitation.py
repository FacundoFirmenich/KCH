from enum import Enum

class RehabState(str,Enum):
    QUARANTINED="R0_QUARANTINED"
    EVIDENCE_ELIGIBLE="R1_EVIDENCE_ELIGIBLE"
    SHADOW_REHABILITATED="R2_SHADOW_REHABILITATED"
    ACTIVE_REHABILITATED="R3_ACTIVE_REHABILITATED"

def root_factor(direction,p0=.5,p1=.8):
    if direction==1:return p1/p0
    if direction==-1:return (1-p1)/(1-p0)
    raise ValueError("direction")

def evidence_value(root_directions):
    e=1.0
    for d in root_directions:e*=root_factor(d)
    return e

def eligible(root_directions,threshold=20,min_roots=7):
    return len(root_directions)>=min_roots and evidence_value(root_directions)>=threshold
