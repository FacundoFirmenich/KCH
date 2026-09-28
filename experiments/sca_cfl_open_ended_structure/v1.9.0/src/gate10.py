from __future__ import annotations
import math, random
from dataclasses import dataclass

@dataclass(frozen=True)
class Obs:
    x:int; z:int; y:int

class KTFeature:
    def __init__(self,name): self.name=name; self.counts={0:[0,0],1:[0,0]}
    def p(self,v):
        n0,n1=self.counts[v]; return (n1+.5)/(n0+n1+1.)
    def update(self,o): self.counts[getattr(o,self.name)][o.y]+=1

def discovery(n=800,seed=7):
    r=random.Random(seed); out=[]
    for _ in range(n):
        x=int(r.random()<.5); z=x; p=.15+.70*x; y=int(r.random()<p); out.append(Obs(x,z,y))
    return out

def intervention(n=400,seed=9,truth='x'):
    r=random.Random(seed); out=[]
    for _ in range(n):
        x=int(r.random()<.5); z=1-x; v=x if truth=='x' else z; p=.15+.70*v; y=int(r.random()<p); out.append(Obs(x,z,y))
    return out

def fit(rows,name):
    m=KTFeature(name)
    for o in rows:m.update(o)
    return m

def predictive_trace(rows,name):
    m=KTFeature(name); ps=[]
    for o in rows:
        ps.append(m.p(getattr(o,name))); m.update(o)
    return ps

def observational_equivalent(rows):
    a=predictive_trace(rows,'x'); b=predictive_trace(rows,'z')
    return max(abs(x-y) for x,y in zip(a,b))==0.0

def distinguishing_probe(rows):
    a=fit(rows,'x'); b=fit(rows,'z'); best=None
    for x in (0,1):
        for z in (0,1):
            g=abs(a.p(x)-b.p(z))
            if best is None or g>best['gap']:best={'x':x,'z':z,'gap':g,'p_x':a.p(x),'p_z':b.p(z)}
    return best

def lr_future(train,future,threshold=20.):
    a=fit(train,'x'); b=fit(train,'z'); loge=0.;cross=None;mx=1.
    for i,o in enumerate(future,1):
        pa=a.p(o.x); pb=b.p(o.z)
        loge+=math.log((pa if o.y else 1-pa)/(pb if o.y else 1-pb))
        e=math.exp(min(700.,loge));mx=max(mx,e)
        if cross is None and e>=threshold:cross=i
    return {'cross_time':cross,'final_e_value':math.exp(min(700.,loge)),'max_e_value':mx}

def reference():
    d=discovery()
    return {
      'equivalent':observational_equivalent(d),
      'probe':distinguishing_probe(d),
      'intervention':lr_future(d,intervention()),
      'continued_observation':lr_future(d,discovery(400,9))
    }

def request_form(probabilistic=True):
    if probabilistic: raise TypeError('PROBABILISTIC_OBJECT_CANNOT_BE_FORM_1')
    return 'FORM_1'
