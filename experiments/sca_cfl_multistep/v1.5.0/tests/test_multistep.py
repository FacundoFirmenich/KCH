from sca_multistep.scenarios import routing_scenario,complementarity_scenario
from sca_multistep.planner import exact_plan
from sca_multistep.adaptive import check,marginal

def test_horizon2_selects_route():
    e,c,a,w=routing_scenario()
    assert exact_plan(e,c,a,w,1)[1][0] in {'critical_A','critical_B'}
    assert exact_plan(e,c,a,w,2)[1][0]=='route'

def test_certification_objective_is_not_adaptive_submodular():
    e,c,a,w=complementarity_scenario(.8)
    r=check(e,c,a,w)
    assert not r['adaptive_submodular']
    assert max(x['gap'] for x in r['violations'])>=.79

def test_positive_control_is_adaptive_submodular():
    e,c,a,w=complementarity_scenario(.8)
    assert check(e,c,a,w,'coverage')['adaptive_submodular']

def test_marginal_increases_after_prerequisite():
    e,c,a,w=complementarity_scenario(.8)
    assert marginal(e,c,a,w,tuple(),'probe_B')==0
    assert abs(marginal(e,c,a,w,(('probe_A','DISTINCT_ROOT'),),'probe_B')-.8)<1e-12
