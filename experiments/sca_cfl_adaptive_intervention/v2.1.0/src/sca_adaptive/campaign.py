import statistics
from .model import HYPOTHESES,DEFAULT_ACTIONS,Intervention
from .policy import run_policy

def monte_carlo(episodes_per_class=5000,seed_offset=100000):
    per={}; errors=0
    for h in HYPOTHESES:
        rows=[run_policy(h,seed_offset+i) for i in range(episodes_per_class)]
        err=sum(r.get('certified')!=h for r in rows); errors+=err
        per[h]={'error_rate':err/episodes_per_class,
                'mean_samples':statistics.mean(sum(r['counts']) for r in rows),
                'mean_cost':statistics.mean(r['cost'] for r in rows),
                'mean_risk':statistics.mean(r['risk'] for r in rows),
                'mean_do01':statistics.mean(r['counts'][0] for r in rows),
                'mean_do10':statistics.mean(r['counts'][1] for r in rows)}
    ac=statistics.mean(x['mean_cost'] for x in per.values())
    ar=statistics.mean(x['mean_risk'] for x in per.values())
    static_cost=24.2; static_risk=.99
    return {'episodes_per_class':episodes_per_class,'total_episodes':episodes_per_class*len(HYPOTHESES),
            'per_class':per,'overall_error_rate':errors/(episodes_per_class*len(HYPOTHESES)),
            'mean_cost_uniform_classes':ac,'mean_risk_uniform_classes':ar,
            'cost_reduction_vs_parent_static':(static_cost-ac)/static_cost,
            'risk_reduction_vs_parent_static':(static_risk-ar)/static_risk,
            'formal_error_bound':.05}

def reference():
    return run_policy('INTERACTION',3)

def safety():
    return run_policy('X',2,risk_budget=.25)

def authority():
    a0,a1=DEFAULT_ACTIONS
    return run_policy('X',2,actions=(a0,Intervention(a1.intervention_id,a1.cost_per_sample,a1.risk_per_sample,False)))
