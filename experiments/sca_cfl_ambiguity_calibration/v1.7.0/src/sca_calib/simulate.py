import random
from .family import p_a

def simulate(model,n,seed):
    rng=random.Random(seed)
    for t in range(n):
        sensor=t%10
        y=1 if rng.random()<p_a(model,sensor) else 0
        yield sensor,y
