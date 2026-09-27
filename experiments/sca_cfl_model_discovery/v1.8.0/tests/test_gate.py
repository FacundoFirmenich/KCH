import pytest
from sca_discovery.family import outer_models,reference_null_model,p_one
from sca_discovery.context import KTContextPredictor,UniversalDepthMixture
from sca_discovery.simulate import simulate_sequence
from sca_discovery.monitor import monitor_outer_class,certify_candidate
from sca_discovery.generator import generate_candidate,request_form,CandidateKind,depth_limit
from sca_discovery.contracts import ModelClassRegistry,RegistryState

def test_outer_family_size(): assert len(outer_models())==25
def test_null_reference_is_member(): assert reference_null_model() in outer_models()
def test_kt_probability_direction():
    p=KTContextPredictor(0); h=(); p.update(0,h,1); assert p.predict(0,h)>.5
def test_depth_limit_grows_with_n(): assert depth_limit(64)<=depth_limit(256)<=depth_limit(1024)
def test_null_reference_does_not_generate_structure():
    c,_=generate_candidate(simulate_sequence(600,17,False)); assert c.state is CandidateKind.NULL_0 and c.depth==0
def test_context_dgp_generates_plus0():
    c,_=generate_candidate(simulate_sequence(600,17,True)); assert c.state is CandidateKind.PROTOFORM_REALVIRTUAL_PLUS0 and c.depth==1 and c.posterior_weight>.99
def test_probabilistic_candidate_cannot_be_form1():
    c,_=generate_candidate(simulate_sequence(600,17,True))
    with pytest.raises(TypeError,match='PROBABILISTIC_OBJECT_CANNOT_BE_FORM_1'): request_form(c)
def test_outer_monitor_rejects_context_dgp():
    r,_=monitor_outer_class(simulate_sequence(600,17,True)); assert r.cross_time is not None and r.max_e_value>=20
def test_outer_monitor_reference_seed_not_rejected():
    r,_=monitor_outer_class(simulate_sequence(600,17,False)); assert r.cross_time is None
def test_candidate_requires_fresh_future_data():
    seq=simulate_sequence(1200,17,True); c,_=generate_candidate(seq[:600]); assert certify_candidate(c.depth,seq[600:]).cross_time is not None
def test_depth0_fails_fresh_certification_on_context_dgp():
    seq=simulate_sequence(1200,17,True); assert certify_candidate(0,seq[600:]).cross_time is None
def test_depth3_decoy_fails_reference_seed():
    seq=simulate_sequence(1200,17,True); assert certify_candidate(3,seq[600:]).cross_time is None
def test_registry_does_not_auto_authorize():
    seq=simulate_sequence(1200,17,True); c,_=generate_candidate(seq[:600]); r=certify_candidate(c.depth,seq[600:])
    reg=ModelClassRegistry(); reg,c=reg.register_shadow(c); reg,c=reg.admit_evidence(c,r.cross_time is not None)
    assert reg.state is RegistryState.CANDIDATE_EVIDENCE_ELIGIBLE and reg.authority_epoch==0 and not reg.patches
def test_registry_authority_event_is_separate():
    seq=simulate_sequence(1200,17,True); c,_=generate_candidate(seq[:600]); r=certify_candidate(c.depth,seq[600:])
    reg=ModelClassRegistry(); reg,c=reg.register_shadow(c); reg,c=reg.admit_evidence(c,r.cross_time is not None)
    denied,_=reg.authorize_patch(c,False); assert denied.authority_epoch==0
    accepted,_=reg.authorize_patch(c,True); assert accepted.version==2 and accepted.authority_epoch==1 and c.candidate_id in accepted.patches
def test_authority_before_evidence_fails():
    c,_=generate_candidate(simulate_sequence(600,17,True))
    with pytest.raises(PermissionError): ModelClassRegistry().authorize_patch(c,True)
def test_outer_monitor_mixture_is_normalized():
    u=UniversalDepthMixture(3); assert abs(sum(u.weights)-1)<1e-12
def test_sensor_probabilities_are_strict():
    for m in outer_models():
        for s in range(10): assert 0<p_one(m,s)<1
def test_candidate_remains_plus0_after_authorized_patch():
    seq=simulate_sequence(1200,17,True); c,_=generate_candidate(seq[:600]); r=certify_candidate(c.depth,seq[600:])
    reg=ModelClassRegistry(); reg,c=reg.register_shadow(c); reg,c=reg.admit_evidence(c,True); reg,c=reg.authorize_patch(c,True)
    assert c.state is CandidateKind.PROTOFORM_REALVIRTUAL_PLUS0 and reg.state is RegistryState.MODEL_CLASS_PATCH_AUTHORIZED
