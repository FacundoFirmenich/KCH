from .core import Hypothesis,Intervention
L=0.142297650131; M=0.5; H=0.860381861575
SEMANTIC_CLASSES=(
    Hypothesis('AND',(L,L),38),
    Hypothesis('X',(L,H),34),
    Hypothesis('INTERACTION',(M,M),1),
    Hypothesis('Z',(H,L),34),
    Hypothesis('OR',(H,H),10),
)
INTERVENTIONS=(
    Intervention('do(x=0,z=1)',1.0,True),
    Intervention('do(x=1,z=0)',1.2,True),
)
def syntax_unresolved_pairs(cells):
    total=0
    for cell in cells:
        n=sum(SEMANTIC_CLASSES[i].multiplicity for i in cell)
        total+=n*(n-1)//2
    return total
