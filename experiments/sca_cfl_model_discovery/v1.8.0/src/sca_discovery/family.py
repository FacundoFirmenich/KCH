from dataclasses import dataclass

TEMPLATES=(
 (.52,.58,.64,.70,.76,.80,.84,.88,.92,.94),
 (.58,.68,.78,.88,.95,.95,.95,.95,.95,.95),
 (.62,.72,.82,.90,.97,.97,.97,.97,.97,.97),
 (.55,.75,.85,.92,.90,.92,.94,.96,.98,.99),
 (.50,.50,.50,.50,.99,.99,.99,.99,.99,.99),
)
@dataclass(frozen=True)
class MemorylessModel:
    model_id:str; q:float; accuracies:tuple[float,...]

def outer_models():
    return tuple(MemorylessModel(f"q{q:.2f}_t{j}",q,t) for q in (.25,.35,.50,.65,.75) for j,t in enumerate(TEMPLATES))

def p_one(model,sensor):
    r=model.accuracies[sensor]
    return model.q*r+(1-model.q)*(1-r)

def reference_null_model(): return outer_models()[18]
