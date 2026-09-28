import pytest
from gate10 import discovery,intervention,observational_equivalent,distinguishing_probe,lr_future,reference,request_form

def test_observational_equivalence():
    assert observational_equivalent(discovery())

def test_probe_breaks_support_equivalence():
    p=distinguishing_probe(discovery())
    assert p['x']!=p['z'] and p['gap']>.6

def test_intervention_crosses():
    assert lr_future(discovery(),intervention())['cross_time']==6

def test_continued_observation_stays_one():
    r=lr_future(discovery(),discovery(400,9))
    assert r['cross_time'] is None and r['final_e_value']==pytest.approx(1.0)

def test_probabilistic_candidate_cannot_be_form1():
    with pytest.raises(TypeError): request_form(True)
