from dataclasses import dataclass
from enum import Enum

P_LOW=0.142297650131
P_MID=0.5
P_HIGH=0.860381861575
HYPOTHESES=('AND','X','INTERACTION','Z','OR')
PREDICTIONS={
 'AND':(P_LOW,P_LOW),
 'X':(P_LOW,P_HIGH),
 'INTERACTION':(P_MID,P_MID),
 'Z':(P_HIGH,P_LOW),
 'OR':(P_HIGH,P_HIGH),
}
ROUTE_GROUPS={'LOW':('AND','X'),'MID':('INTERACTION',),'HIGH':('Z','OR')}
ROUTE_P={'LOW':P_LOW,'MID':P_MID,'HIGH':P_HIGH}

@dataclass(frozen=True)
class Intervention:
    intervention_id:str
    cost_per_sample:float
    risk_per_sample:float
    authorized:bool=True

DEFAULT_ACTIONS=(
    Intervention('do(x=0,z=1)',1.0,0.01,True),
    Intervention('do(x=1,z=0)',1.2,0.08,True),
)

class PolicyState(str,Enum):
    CERTIFIED='CERTIFIED'
    HOLD_SAFETY_BOUND='HOLD_SAFETY_BOUND'
    HOLD_AUTHORITY='HOLD_AUTHORITY'
    HOLD_MAX_STEPS='HOLD_MAX_STEPS'
