import math
from dataclasses import dataclass
@dataclass(frozen=True)
class BetaCopyPrior:
    alpha:float=1.0
    beta:float=4.0
    def update(self,same,distinct): return BetaCopyPrior(self.alpha+same,self.beta+distinct)
    @property
    def mean(self): return self.alpha/(self.alpha+self.beta)

def _log_beta_pdf(x,a,b):
    return (a-1)*math.log(x)+(b-1)*math.log(1-x)-math.lgamma(a)-math.lgamma(b)+math.lgamma(a+b)

def copy_posterior(similarity,prior,same_shape=(9.,2.),distinct_shape=(2.,9.)):
    pi=prior.mean
    ls=math.log(pi)+_log_beta_pdf(similarity,*same_shape)
    ld=math.log(1-pi)+_log_beta_pdf(similarity,*distinct_shape)
    m=max(ls,ld); ps=math.exp(ls-m); pd=math.exp(ld-m)
    return ps/(ps+pd)
