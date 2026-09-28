from dataclasses import dataclass

@dataclass(frozen=True)
class Intervention:
    intervention_id:str
    cost:float
    authorized:bool=True
    privacy:float=0.0
    risk:float=0.0

@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id:str
    predictions:tuple[float,...]
    multiplicity:int=1
