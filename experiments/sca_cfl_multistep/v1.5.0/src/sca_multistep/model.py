from dataclasses import dataclass

@dataclass(frozen=True)
class Action:
    action_id:str
    kind:str
    cost:float
    outcomes:tuple[str,...]
    left:str|None=None
    right:str|None=None
    authorized:bool=True

@dataclass(frozen=True)
class World:
    world_id:str
    probability:float
    outcomes:tuple[tuple[str,str],...]
    def outcome(self,action_id):
        return dict(self.outcomes)[action_id]
