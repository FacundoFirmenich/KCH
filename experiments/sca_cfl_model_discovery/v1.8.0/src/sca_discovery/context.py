import math
from collections import defaultdict

def logsumexp(xs):
    m=max(xs); return m+math.log(sum(math.exp(x-m) for x in xs))

class KTContextPredictor:
    def __init__(self,depth):
        if depth<0: raise ValueError("NEGATIVE_DEPTH")
        self.depth=depth; self.counts=defaultdict(lambda:[0,0]); self.loglik=0.0
    def key(self,sensor,history):
        return (sensor,tuple(history[-self.depth:]) if self.depth else ())
    def predict(self,sensor,history):
        n0,n1=self.counts[self.key(sensor,history)]
        return (n1+.5)/(n0+n1+1.0)
    def update(self,sensor,history,y):
        p=self.predict(sensor,history)
        self.loglik+=math.log(p if y else 1-p)
        self.counts[self.key(sensor,history)][y]+=1
        return p

def depth_weights(max_depth):
    raw=[2.0**(-(d+1)) for d in range(max_depth+1)]; z=sum(raw)
    return tuple(x/z for x in raw)

class UniversalDepthMixture:
    def __init__(self,max_depth=3):
        self.predictors=[KTContextPredictor(d) for d in range(max_depth+1)]
        self.weights=depth_weights(max_depth)
    def update(self,sensor,history,y):
        for p in self.predictors: p.update(sensor,history,y)
        return self.log_joint()
    def log_joint(self):
        return logsumexp([math.log(w)+p.loglik for w,p in zip(self.weights,self.predictors)])
