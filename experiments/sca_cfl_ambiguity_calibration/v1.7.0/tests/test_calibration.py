from sca_calib.family import outer_models,fallback_models,core_ids
from sca_calib.calibrator import FiniteConfidenceCalibrator,ClassMonitor
from sca_calib.contracts import ModelClassGovernor
from sca_calib.model import ContractState
from sca_calib.simulate import simulate

def test_family_sizes():
    assert len(outer_models())==25
    assert len(fallback_models())==30
    assert len(core_ids())==9

def test_outer_set_is_nested():
    ms=outer_models(); c=FiniteConfidenceCalibrator(ms); prev=set(c.active_ids())
    for s,y in simulate(ms[17],120,17):
        c.update(s,y); cur=set(c.active_ids()); assert cur.issubset(prev); prev=cur

def test_reserve_true_is_retained():
    ms=outer_models(); c=FiniteConfidenceCalibrator(ms)
    for s,y in simulate(ms[24],500,1): c.update(s,y)
    assert c.active_ids()==(24,)

def test_core_rejected_but_outer_authority_remains():
    ms=outer_models(); mon=ClassMonitor(ms,core_ids(ms))
    for s,y in simulate(ms[24],220,1): mon.update(s,y)
    assert mon.cross_time==181
    g=ModelClassGovernor(); assert g.reject_core(181)==ContractState.CORE_REJECTED
    assert g.state==ContractState.OUTER_AUTHORITY

def test_outer_break_is_fail_closed():
    ms=fallback_models(); mon=ClassMonitor(ms,tuple(range(25)))
    for s,y in simulate(ms[26],300,1): mon.update(s,y)
    assert mon.cross_time==269
    g=ModelClassGovernor(); assert g.reject_outer(269)==ContractState.OUTER_REJECTED_HOLD
    assert g.request_fallback()==ContractState.FALLBACK_SHADOW
    assert not g.fallback_authorized

def test_fallback_requires_explicit_authority():
    g=ModelClassGovernor(); g.reject_outer(269)
    assert g.authorize_fallback(False)==ContractState.OUTER_REJECTED_HOLD
    assert g.authorize_fallback(True)==ContractState.FALLBACK_AUTHORITY
