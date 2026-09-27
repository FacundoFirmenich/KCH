from dataclasses import dataclass
from enum import Enum
class Relation(str,Enum):
    SAME="SAME_ROOT"
    DISTINCT="DISTINCT_ROOT"
    UNKNOWN="UNKNOWN"
@dataclass(frozen=True)
class EvidenceEvent:
    event_id:str
    source_id:str
    direction:int
    payload_digest:str|None=None
@dataclass(frozen=True)
class ProvenanceConstraint:
    left:str
    right:str
    relation:Relation
    attestor:str
    authorized:bool=True
