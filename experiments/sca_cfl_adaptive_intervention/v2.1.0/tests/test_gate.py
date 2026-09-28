import math
from sca_adaptive.model import DEFAULT_ACTIONS,Intervention
from sca_adaptive.policy import run_policy,ROUTE_THRESHOLD,PAIR_THRESHOLD

def test_thresholds(): assert ROUTE_THRESHOLD==80 and PAIR_THRESHOLD==40
def test_interaction_stops_before_second_intervention():
    r=run_policy('INTERACTION',3); assert r['certified']=='INTERACTION' and r['counts']==[15,0]
def test_pair_action_runs_when_needed():
    r=run_policy('X',2); assert r['certified']=='X' and r['counts'][1]>0
def test_safety_hold():
    r=run_policy('X',2,risk_budget=.25); assert r['state']=='HOLD_SAFETY_BOUND' and r['risk']<=.25
def test_authority_hold():
    a0,a1=DEFAULT_ACTIONS; a1=Intervention(a1.intervention_id,a1.cost_per_sample,a1.risk_per_sample,False)
    r=run_policy('X',2,actions=(a0,a1)); assert r['state']=='HOLD_AUTHORITY' and r['counts'][1]==0
def test_familywise_alpha_budget(): assert math.isclose(2/ROUTE_THRESHOLD+1/PAIR_THRESHOLD,.05)
