from .model import AmbiguityModel,BeliefState,Action
from .pomdp import canonical_models

SENSOR_COSTS=(.015,.025,.04,.06,.18,.20,.22,.24,.28,.32)
ACCURACY_TEMPLATES=(
    (.58,.68,.78,.88,.95,.95,.95,.95,.95,.95),
    (.62,.72,.82,.90,.97,.97,.97,.97,.97,.97),
    (.55,.75,.85,.92,.90,.92,.94,.96,.98,.99),
)

def actions():
    xs=[Action(f's{i}',c,'sensor',i) for i,c in enumerate(SENSOR_COSTS)]
    xs.extend([Action('critical_A',.25,'critical'),Action('critical_B',.25,'critical')])
    return tuple(xs)

def ambiguity_models():
    return tuple(AmbiguityModel(q,a) for q in (.35,.50,.65) for a in ACCURACY_TEMPLATES)

def initial_state(): return BeliefState(canonical_models(ambiguity_models()),(),False)
def nominal_optimistic_model(): return AmbiguityModel(.5,ACCURACY_TEMPLATES[1])
def ood_model(): return AmbiguityModel(.5,(.5,.5,.5,.5,.99,.99,.99,.99,.99,.99))
