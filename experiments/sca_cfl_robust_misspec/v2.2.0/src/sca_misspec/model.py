from dataclasses import dataclass
L=0.142297650131
M=0.5
H=0.860381861575
ETA=0.10
CHECKPOINTS=(25,50,100,200,400,800,1200)
ALPHA_TOTAL=0.05
BANDS={'L':(L-ETA,L+ETA),'M':(M-ETA,M+ETA),'H':(H-ETA,H+ETA)}
LEGAL={('L','L'):'AND',('L','H'):'X',('M','M'):'INTERACTION',('H','L'):'Z',('H','H'):'OR'}
SPLICE={('L','M'):'SPLICE_LM',('M','L'):'SPLICE_ML',('M','H'):'SPLICE_MH',('H','M'):'SPLICE_HM'}

@dataclass(frozen=True)
class Intervention:
    intervention_id:str
    cost_per_sample:float
    risk_per_sample:float
    authorized:bool=True

DEFAULT_ACTIONS=(Intervention('do(x=0,z=1)',1.0,.01,True),Intervention('do(x=1,z=0)',1.2,.08,True))
