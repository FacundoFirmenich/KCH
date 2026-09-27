from dataclasses import dataclass
import math
from sca_dep.model import ProvenanceConstraint, Relation
from sca_dep.robust import robust_genealogy_gate
from sca_dep.bayes import binary_entropy

@dataclass(frozen=True)
class ProbeAction:
    probe_id:str
    left:str
    right:str
    p_same:float
    cost:float=0.0
    privacy:float=0.0
    latency:float=0.0
    resolution_prob:float=1.0
    authorized:bool=True

def deficit(e,T=20.0):
    return max(0.0, math.log(T/e))

def evaluate(events,constraints,a,T=20.0,privacy_cap=1.0):
    cur=robust_genealogy_gate(events,constraints,threshold=T)
    if not a.authorized:
        return {'probe_id':a.probe_id,'admissible':False,'reason':'AUTHORITY_DENIED'}
    if a.privacy>privacy_cap:
        return {'probe_id':a.probe_id,'admissible':False,'reason':'PRIVACY_CAP'}
    try:
        gs=robust_genealogy_gate(events,constraints+[ProvenanceConstraint(a.left,a.right,Relation.SAME,'probe',True)],threshold=T)
        gd=robust_genealogy_gate(events,constraints+[ProvenanceConstraint(a.left,a.right,Relation.DISTINCT,'probe',True)],threshold=T)
    except ValueError:
        return {'probe_id':a.probe_id,'admissible':False,'reason':'RELATION_ALREADY_CONSTRAINED'}
    d0=deficit(cur.robust_e_value,T)
    ds=deficit(gs.robust_e_value,T)
    dd=deficit(gd.robust_e_value,T)
    after=(1-a.resolution_prob)*d0+a.resolution_prob*(a.p_same*ds+(1-a.p_same)*dd)
    voi=max(0.0,d0-after)
    penalty=.25*a.cost+.50*a.privacy+.05*a.latency
    return {
        'probe_id':a.probe_id,
        'admissible':True,
        'pair_entropy':binary_entropy(a.p_same),
        'decision_voi':voi,
        'net_value':voi-penalty,
        'e_if_same':gs.robust_e_value,
        'e_if_distinct':gd.robust_e_value
    }

def choose(events,constraints,actions,privacy_cap=1.0):
    rows=[evaluate(events,constraints,a,privacy_cap=privacy_cap) for a in actions]
    ok=[r for r in rows if r.get('admissible') and r.get('net_value',0)>0]
    if not ok:
        return {'decision':'ABSTAIN_NO_POSITIVE_VOI','chosen':None,'scored':rows}
    return {'decision':'PROBE','chosen':max(ok,key=lambda r:(r['net_value'],r['decision_voi'],r['probe_id'])),'scored':rows}
