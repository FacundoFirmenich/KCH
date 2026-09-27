import random
from .family import p_one,reference_null_model

def simulate_sequence(n,seed,context_dependent):
    rng=random.Random(seed); base_model=reference_null_model(); history=[]; out=[]
    for t in range(n):
        sensor=t%10; base=p_one(base_model,sensor)
        if context_dependent:
            prev=history[-1] if history else 0
            p=min(.94,max(.06,base+(.22 if prev else -.22)))
        else: p=base
        y=1 if rng.random()<p else 0
        out.append((sensor,tuple(history),y,p)); history.append(y)
    return out
