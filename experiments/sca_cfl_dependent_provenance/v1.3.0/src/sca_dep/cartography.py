from dataclasses import dataclass,asdict
from .bayes import BetaCopyPrior,copy_posterior
from .model import ProvenanceConstraint,Relation
from .robust import robust_genealogy_gate
@dataclass(frozen=True)
class PairCartography:
    left:str; right:str; similarity:float; p_same:float; e_if_same:float; e_if_distinct:float
    def to_dict(self): return asdict(self)

def map_unknown_pair(events,constraints,left,right,similarity,prior=None):
    prior=prior or BetaCopyPrior(); p=copy_posterior(similarity,prior)
    same=constraints+[ProvenanceConstraint(left,right,Relation.SAME,"SHADOW_MODEL",True)]
    distinct=constraints+[ProvenanceConstraint(left,right,Relation.DISTINCT,"SHADOW_MODEL",True)]
    return PairCartography(left,right,similarity,p,robust_genealogy_gate(events,same)["robust_e_value"],robust_genealogy_gate(events,distinct)["robust_e_value"])
