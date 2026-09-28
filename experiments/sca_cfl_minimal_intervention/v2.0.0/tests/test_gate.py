from sca_intervention.design import exact_min_cost_design,greedy_cost_design,partition_cells
from sca_intervention.v19 import SEMANTIC_CLASSES,INTERVENTIONS,syntax_unresolved_pairs
from sca_intervention.counterexample import HYPOTHESES as CH,INTERVENTIONS as CI
from sca_intervention.core import Intervention

def test_v19_counts():
    assert len(SEMANTIC_CLASSES)==5 and sum(h.multiplicity for h in SEMANTIC_CLASSES)==117
def test_one_intervention_frontier():
    c=partition_cells(SEMANTIC_CLASSES,[0]); assert len(c)==3 and syntax_unresolved_pairs(c)==3502
def test_two_intervention_frontier():
    c=partition_cells(SEMANTIC_CLASSES,[0,1]); assert len(c)==5 and syntax_unresolved_pairs(c)==1870
def test_minimal_full_design():
    r=exact_min_cost_design(SEMANTIC_CLASSES,INTERVENTIONS); assert r['selected_ids']==('do(x=0,z=1)','do(x=1,z=0)') and abs(r['cost']-2.2)<1e-12
def test_authority_frontier():
    ints=(INTERVENTIONS[0],Intervention(INTERVENTIONS[1].intervention_id,1.2,False))
    assert len(exact_min_cost_design(SEMANTIC_CLASSES,ints)['irreducible_pairs'])==2
def test_greedy_counterexample():
    e=exact_min_cost_design(CH,CI); g=greedy_cost_design(CH,CI)
    assert e['selected_ids']==('T0','T3','T4') and abs(e['cost']-5.2)<1e-12
    assert g['selected_ids']==('T3','T2','T0','T4') and abs(g['cost']-6.7)<1e-12
