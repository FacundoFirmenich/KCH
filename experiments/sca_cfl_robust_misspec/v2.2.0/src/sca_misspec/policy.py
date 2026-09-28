import random
from .model import CHECKPOINTS,LEGAL,DEFAULT_ACTIONS
from .cs import mixture_cs_interval,classify_interval

def _draw_block(rng,p,n):
    return sum(1 for _ in range(n) if rng.random()<p)

def run_policy(true_probs,seed=1,actions=DEFAULT_ACTIONS,risk_budget=100.0):
    rng=random.Random(seed); successes=[0,0]; counts=[0,0]; cost=0.0; risk=0.0; ledger=[]; labels=[None,None]
    for a in (0,1):
        action=actions[a]
        if not action.authorized:
            return {'state':'HOLD_AUTHORITY','certified':None,'counts':counts,'cost':cost,'risk':risk,'needed_next':action.intervention_id,'ledger':ledger}
        prev=0; resolved=False
        for n in CHECKPOINTS:
            add=n-prev; add_risk=add*action.risk_per_sample
            if risk+add_risk>risk_budget:
                return {'state':'HOLD_SAFETY_BOUND','certified':None,'counts':counts,'cost':cost,'risk':risk,'needed_next':action.intervention_id,'next_checkpoint':n,'ledger':ledger}
            successes[a]+=_draw_block(rng,true_probs[a],add); counts[a]+=add; cost+=add*action.cost_per_sample; risk+=add_risk
            iv=mixture_cs_interval(successes[a],counts[a]); c=classify_interval(iv)
            ledger.append({'event':'CHECKPOINT','action':action.intervention_id,'n':counts[a],'successes':successes[a],'interval':iv,'classification':c,'evidentiary_weight':1})
            if c['state']=='OUTSIDE_ALL_BANDS':
                return {'state':'MODEL_CLASS_BREAK','break_kind':'OUTSIDE_BANDS','certified':None,'counts':counts,'cost':cost,'risk':risk,'ledger':ledger}
            if c['state']=='CERTIFIED_BAND':
                labels[a]=c['label']; resolved=True; break
            prev=n
        if not resolved:
            return {'state':'HOLD_UNRESOLVED','certified':None,'counts':counts,'cost':cost,'risk':risk,'needed_next':action.intervention_id,'ledger':ledger}
        if a==0 and labels[0]=='M':
            ledger.append({'event':'COUNTERFACTUAL_PARENT_STOP','parent_release':'2.1.0','parent_would_certify':'INTERACTION','reason':'v2.2 requires cross-action closure audit','evidentiary_weight':0})
    sig=tuple(labels)
    if sig in LEGAL:
        return {'state':'CERTIFIED','certified':LEGAL[sig],'signature':sig,'counts':counts,'cost':cost,'risk':risk,'ledger':ledger}
    return {'state':'MODEL_CLASS_BREAK','break_kind':'SPLICE_SIGNATURE','signature':sig,'certified':None,'counts':counts,'cost':cost,'risk':risk,'ledger':ledger}
