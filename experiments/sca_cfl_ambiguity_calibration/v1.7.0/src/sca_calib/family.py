from .model import FiniteModel

TEMPLATES = (
    (.52,.58,.64,.70,.76,.80,.84,.88,.92,.94),
    (.58,.68,.78,.88,.95,.95,.95,.95,.95,.95),
    (.62,.72,.82,.90,.97,.97,.97,.97,.97,.97),
    (.55,.75,.85,.92,.90,.92,.94,.96,.98,.99),
    (.50,.50,.50,.50,.99,.99,.99,.99,.99,.99),
)

def outer_models():
    out=[]
    for q in (.25,.35,.50,.65,.75):
        for j,t in enumerate(TEMPLATES):
            out.append(FiniteModel(f"q{q:.2f}_t{j}",q,t,"outer"))
    return tuple(out)

def core_ids(models=None):
    models=models or outer_models()
    return tuple(i for i,m in enumerate(models) if m.q in (.35,.50,.65) and m.accuracies in TEMPLATES[1:4])

def fallback_models():
    out=list(outer_models())
    for j,t in enumerate(TEMPLATES):
        out.append(FiniteModel(f"q0.85_t{j}",.85,t,"fallback"))
    return tuple(out)

def p_a(model,sensor):
    r=model.accuracies[sensor]
    return model.q*r+(1-model.q)*(1-r)
