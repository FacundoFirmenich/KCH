import pytest
from sca_misspec.model import L,M,H,LEGAL,SPLICE,DEFAULT_ACTIONS,Intervention
from sca_misspec.policy import run_policy
from sca_misspec.cfl import request_form

def test_reference_splice_breaks():
    r=run_policy((M,L),seed=7)
    assert r['state']=='MODEL_CLASS_BREAK' and r['signature']==('M','L')

def test_legal_centers_certify():
    c={'L':L,'M':M,'H':H}
    for sig,h in LEGAL.items():
        r=run_policy(tuple(c[x] for x in sig),seed=3,risk_budget=200)
        assert r['state']=='CERTIFIED' and r['certified']==h

def test_splice_centers_break():
    c={'L':L,'M':M,'H':H}
    for sig in SPLICE:
        r=run_policy(tuple(c[x] for x in sig),seed=3,risk_budget=200)
        assert r['state']=='MODEL_CLASS_BREAK'

def test_offgrid_not_forced_to_certify():
    assert run_policy((.30,.70),seed=7,risk_budget=200)['state'] in {'MODEL_CLASS_BREAK','HOLD_UNRESOLVED'}

def test_safety_hold():
    assert run_policy((M,L),seed=7,risk_budget=10)['state']=='HOLD_SAFETY_BOUND'

def test_authority_hold():
    a0,a1=DEFAULT_ACTIONS
    a1=Intervention(a1.intervention_id,a1.cost_per_sample,a1.risk_per_sample,False)
    assert run_policy((M,L),seed=7,actions=(a0,a1),risk_budget=200)['state']=='HOLD_AUTHORITY'

def test_counterfactual_has_zero_evidence():
    r=run_policy((M,L),seed=7,risk_budget=200)
    assert all(e.get('evidentiary_weight')==0 for e in r['ledger'] if e['event']=='COUNTERFACTUAL_PARENT_STOP')

def test_probabilistic_object_not_form():
    with pytest.raises(TypeError): request_form(True)
