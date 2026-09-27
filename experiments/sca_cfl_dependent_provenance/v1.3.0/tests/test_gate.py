import pytest
from sca_dep.model import *
from sca_dep.robust import *
from sca_dep.rehabilitation import provenance_aware_evidence_gate
from sca_dep.bayes import *
from sca_dep.cartography import *

def ev(n,d=1): return [EvidenceEvent(f"e{i}",f"s{i}",d) for i in range(n)]
def distinct_all(n,authorized=True): return [ProvenanceConstraint(f"e{i}",f"e{j}",Relation.DISTINCT,"attestor",authorized) for i in range(n) for j in range(i+1,n)]
def same_all(n): return [ProvenanceConstraint("e0",f"e{i}",Relation.SAME,"digest",True) for i in range(1,n)]

def test_naive_crosses_robust_blocks(): d=provenance_aware_evidence_gate(ev(8),[]); assert d["naive_e_value"]>20 and d["robust_e_value"]==pytest.approx(1.6)
def test_seven_distinct_crosses(): assert provenance_aware_evidence_gate(ev(7),distinct_all(7))["eligible"]
def test_six_distinct_blocks(): assert not provenance_aware_evidence_gate(ev(6),distinct_all(6))["eligible"]
def test_unauthorized_distinct_ignored(): assert provenance_aware_evidence_gate(ev(8),distinct_all(8,False))["robust_e_value"]==pytest.approx(1.6)
def test_known_copies_collapse(): assert provenance_aware_evidence_gate(ev(8),same_all(8))["robust_e_value"]==pytest.approx(1.6)
def test_source_ids_do_not_prove_independence(): assert provenance_aware_evidence_gate(ev(7),[])["robust_e_value"]==pytest.approx(1.6)
def test_enumeration_limit_fails_closed():
    with pytest.raises(RuntimeError): robust_genealogy_gate(ev(11),[],max_components=10)
def test_copy_posterior_increases_with_similarity():
    p=BetaCopyPrior(); assert copy_posterior(.95,p)>copy_posterior(.55,p)>copy_posterior(.05,p)
def test_hierarchical_prior_updates(): assert BetaCopyPrior().update(8,2).mean>BetaCopyPrior().mean
def test_cartography_does_not_change_gate():
    xs=ev(7); before=provenance_aware_evidence_gate(xs,[])["robust_e_value"]; _=map_unknown_pair(xs,[],"e0","e1",.97); assert provenance_aware_evidence_gate(xs,[])["robust_e_value"]==before
