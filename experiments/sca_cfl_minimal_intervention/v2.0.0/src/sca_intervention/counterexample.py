from .core import Hypothesis,Intervention
MATRIX=((0,0,1,1,0),(1,0,0,0,0),(1,0,0,1,0),(1,1,1,0,1),(0,1,1,0,1),(1,1,0,1,1))
COSTS=(2.0,4.0,1.5,1.2,2.0)
HYPOTHESES=tuple(Hypothesis(f'H{i}',tuple(float(x) for x in row)) for i,row in enumerate(MATRIX))
INTERVENTIONS=tuple(Intervention(f'T{j}',COSTS[j],True) for j in range(len(COSTS)))
