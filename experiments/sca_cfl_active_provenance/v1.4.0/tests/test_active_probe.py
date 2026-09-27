from sca_dep.model import EvidenceEvent, ProvenanceConstraint, Relation
from sca_dep.robust import robust_genealogy_gate
from sca_probe.probe import ProbeAction, evaluate, choose

def scenario():
    events=[EvidenceEvent(f'e{i}',f's{i}',1) for i in range(8)]
    constraints=[]
    for i in range(7):
        for j in range(i+1,7):
            if (i,j)!=(0,1):
                constraints.append(ProvenanceConstraint(f'e{i}',f'e{j}',Relation.DISTINCT,'seed',True))
    actions=[
        ProbeAction('critical_public','e0','e1',.2,.02,.01,.05,1.,True),
        ProbeAction('critical_private','e0','e1',.2,.005,.95,.01,1.,True),
        ProbeAction('critical_unauthorized','e0','e1',.2,0,0,0,1.,False),
        ProbeAction('decoy_entropy','e6','e7',.5,.005,.005,.02,1.,True)
    ]
    return events,constraints,actions

def test_initial_gate():
    e,c,a=scenario()
    assert not robust_genealogy_gate(e,c).eligible

def test_selector_prefers_decision_relevant_probe():
    e,c,a=scenario()
    assert choose(e,c,a,.2)['chosen']['probe_id']=='critical_public'

def test_high_entropy_decoy_has_zero_decision_value():
    e,c,a=scenario()
    x=evaluate(e,c,a[-1],privacy_cap=.2)
    assert x['pair_entropy']>.69 and x['decision_voi']==0

def test_privacy_and_authority_constraints():
    e,c,a=scenario()
    rows=choose(e,c,a,.2)['scored']
    by={x['probe_id']:x for x in rows}
    assert by['critical_private']['reason']=='PRIVACY_CAP'
    assert by['critical_unauthorized']['reason']=='AUTHORITY_DENIED'

def test_attested_distinct_relation_crosses_gate():
    e,c,a=scenario()
    c.append(ProvenanceConstraint('e0','e1',Relation.DISTINCT,'attested',True))
    assert robust_genealogy_gate(e,c).eligible
