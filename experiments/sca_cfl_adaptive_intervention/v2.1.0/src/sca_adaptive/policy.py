import math, random
from .model import HYPOTHESES,PREDICTIONS,ROUTE_GROUPS,ROUTE_P,DEFAULT_ACTIONS,PolicyState
ALPHA_ROUTE=.025
ALPHA_PAIR=.025
ROUTE_THRESHOLD=2/ALPHA_ROUTE
PAIR_THRESHOLD=1/ALPHA_PAIR
STATIC_PARENT_N_EACH=11

def inc(p,y): return math.log(p if y else 1-p)
def route_cert(ll):
    t=math.log(ROUTE_THRESHOLD)
    for g in ('LOW','MID','HIGH'):
        if all(ll[g]-ll[h]>=t for h in ('LOW','MID','HIGH') if h!=g): return g
def pair_cert(ll,pair):
    a,b=pair; t=math.log(PAIR_THRESHOLD)
    if ll[a]-ll[b]>=t:return a
    if ll[b]-ll[a]>=t:return b

def counterfactual(actions,counts,cost,risk,cancelled):
    sc=11*actions[0].cost_per_sample+11*actions[1].cost_per_sample
    sr=11*actions[0].risk_per_sample+11*actions[1].risk_per_sample
    return {'parent_static_plan':{actions[0].intervention_id:11,actions[1].intervention_id:11},
            'actual_counts':{actions[0].intervention_id:counts[0],actions[1].intervention_id:counts[1]},
            'cancelled_unexecuted':cancelled,'static_cost':sc,'actual_cost':cost,
            'cost_difference_static_minus_actual':sc-cost,'static_risk':sr,'actual_risk':risk,
            'risk_difference_static_minus_actual':sr-risk,
            'epistemic_rule':'Counterfactual/cancelled interventions never update likelihoods or evidence.'}

def run_policy(true_hypothesis,seed=1,actions=DEFAULT_ACTIONS,risk_budget=10,max_per_stage=200):
    rng=random.Random(seed); counts=[0,0]; cost=risk=0.; trace=[]; cancelled=[]
    a0,a1=actions
    if not a0.authorized:return {'state':'HOLD_AUTHORITY','certified':None,'counts':counts,'cost':cost,'risk':risk}
    ll={g:0. for g in ROUTE_P}; route=None
    for t in range(1,max_per_stage+1):
        if risk+a0.risk_per_sample>risk_budget:return {'state':'HOLD_SAFETY_BOUND','certified':None,'stage':'ROUTE','needed_next':a0.intervention_id,'counts':counts,'cost':cost,'risk':risk}
        y=int(rng.random()<PREDICTIONS[true_hypothesis][0]); counts[0]+=1; cost+=a0.cost_per_sample; risk+=a0.risk_per_sample
        for g,p in ROUTE_P.items():ll[g]+=inc(p,y)
        route=route_cert(ll)
        if route:break
    if route is None:return {'state':'HOLD_MAX_STEPS','certified':None,'counts':counts,'cost':cost,'risk':risk}
    if route=='MID':
        cancelled=[{'action':a1.intervention_id,'reason':'IDENTIFICATION_SUFFICIENT_AFTER_ROUTE','parent_static_samples_avoided':11}]
        return {'state':'CERTIFIED','certified':'INTERACTION','route':route,'counts':counts,'cost':cost,'risk':risk,'counterfactual':counterfactual(actions,counts,cost,risk,cancelled)}
    pair=ROUTE_GROUPS[route]
    if not a1.authorized:return {'state':'HOLD_AUTHORITY','certified':None,'route':route,'needed_next':a1.intervention_id,'counts':counts,'cost':cost,'risk':risk}
    ll2={h:0. for h in pair}
    for t in range(1,max_per_stage+1):
        if risk+a1.risk_per_sample>risk_budget:return {'state':'HOLD_SAFETY_BOUND','certified':None,'route':route,'needed_next':a1.intervention_id,'counts':counts,'cost':cost,'risk':risk}
        y=int(rng.random()<PREDICTIONS[true_hypothesis][1]); counts[1]+=1; cost+=a1.cost_per_sample; risk+=a1.risk_per_sample
        for h in pair:ll2[h]+=inc(PREDICTIONS[h][1],y)
        pred=pair_cert(ll2,pair)
        if pred:return {'state':'CERTIFIED','certified':pred,'route':route,'counts':counts,'cost':cost,'risk':risk,'counterfactual':counterfactual(actions,counts,cost,risk,cancelled)}
    return {'state':'HOLD_MAX_STEPS','certified':None,'counts':counts,'cost':cost,'risk':risk}
