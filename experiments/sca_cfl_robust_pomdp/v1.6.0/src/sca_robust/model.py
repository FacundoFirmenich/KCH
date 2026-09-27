from dataclasses import dataclass

@dataclass(frozen=True)
class AmbiguityModel:
    q: float
    accuracies: tuple[float,...]

@dataclass(frozen=True)
class BeliefState:
    models: tuple
    used: tuple[str,...]=()
    eligible: bool=False

@dataclass(frozen=True)
class Action:
    action_id: str
    cost: float
    kind: str
    sensor_index: int|None=None
