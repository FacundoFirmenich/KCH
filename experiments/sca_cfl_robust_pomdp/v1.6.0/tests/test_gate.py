from sca_robust.scenario import actions,ambiguity_models,initial_state,nominal_optimistic_model
from sca_robust.model import BeliefState
from sca_robust.pomdp import canonical_models,ExactRobustSolver
from sca_robust.bounds import CertifiedBoundPlanner

def test_dimensions():
    assert len(ambiguity_models())==9 and len(actions())==12

def test_exact_robust_root():
    s=ExactRobustSolver(actions()); v,a=s.value(initial_state(),3)
    assert a=='s3' and abs(v-0.639481865285)<1e-10

def test_nominal_root_differs():
    m=nominal_optimistic_model(); st=BeliefState(canonical_models([m]),(),False)
    s=ExactRobustSolver(actions()); v,a=s.value(st,3)
    assert a=='s2' and abs(v-.665)<1e-12

def test_depth_one_abstains():
    r=CertifiedBoundPlanner(actions()).solve(initial_state(),3,1)
    assert r['root_action']=='s3' and r['decision']=='ABSTAIN_UNCERTIFIED'

def test_depth_two_abstains():
    r=CertifiedBoundPlanner(actions()).solve(initial_state(),3,2)
    assert r['decision']=='ABSTAIN_UNCERTIFIED'

def test_depth_three_certifies():
    r=CertifiedBoundPlanner(actions()).solve(initial_state(),3,3)
    assert r['decision']=='CERTIFY' and r['root_action']=='s3' and r['gap']<1e-12

def test_bound_search_prunes():
    r=CertifiedBoundPlanner(actions()).solve(initial_state(),3,3)
    assert r['stats']['static_pruned']>=500 and r['memo_states']<200

def test_exact_state_space_is_much_larger():
    s=ExactRobustSolver(actions()); s.value(initial_state(),3)
    assert s.calls>4000
