import math
from dataclasses import dataclass
from enum import Enum
from .context import KTContextPredictor,depth_weights,logsumexp
class CandidateKind(str,Enum):
    PSEUDOFORM_STATISTICAL="PSEUDOFORM_STATISTICAL"
    PROTOFORM_REALVIRTUAL_PLUS0="PROTOFORM_REALVIRTUAL_+0"
    COUNTERPOLAR_MINUS1="COUNTERPOLAR_-1"
    FORM_1="FORM_1"
    NULL_0="NULL_0"
@dataclass(frozen=True)
class StructureCandidate:
    candidate_id:str; depth:int; posterior_weight:float; log_code_gain_vs_depth0:float; state:CandidateKind; probabilistic:bool=True; model_class_eligible:bool=False

def depth_limit(n): return max(0,int(math.log2(max(2,n)))-6)

def generate_candidate(seq,posterior_gate=.95):
    D=depth_limit(len(seq)); ps=[KTContextPredictor(d) for d in range(D+1)]
    for sensor,history,y,_ in seq:
        for p in ps:p.update(sensor,history,y)
    ws=depth_weights(D); scores=[math.log(w)+p.loglik for w,p in zip(ws,ps)]
    z=logsumexp(scores); post=[math.exp(x-z) for x in scores]; best=max(range(D+1),key=lambda d:(post[d],-d)); gain=scores[best]-scores[0]
    if best==0 or post[best]<posterior_gate:
        c=StructureCandidate("candidate:none",0,post[0],0.0,CandidateKind.NULL_0,True,False)
    else:
        c=StructureCandidate(f"context_depth_{best}",best,post[best],gain,CandidateKind.PROTOFORM_REALVIRTUAL_PLUS0,True,False)
    return c,{"depth_limit":D,"weights":ws,"log_scores":scores,"posterior":post,"selected_depth":best,"selected_probability":post[best],"log_code_gain_vs_depth0":gain}

def request_form(candidate):
    if candidate.probabilistic: raise TypeError("PROBABILISTIC_OBJECT_CANNOT_BE_FORM_1")
    return StructureCandidate(candidate.candidate_id,candidate.depth,candidate.posterior_weight,candidate.log_code_gain_vs_depth0,CandidateKind.FORM_1,False,candidate.model_class_eligible)
