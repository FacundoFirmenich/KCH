from __future__ import annotations
from enum import Enum

class QState(str,Enum):
    ABSENT="Q0_ABSENT"
    PRESENT_UNVERIFIED="Q1_PRESENT_UNVERIFIED"
    VERIFIED_NONCURRENT="Q2_VERIFIED_NONCURRENT"
    VERIFIED_CURRENT="Q3_VERIFIED_CURRENT"

def classify(obs,expected_release,expected_digest,parent_digest):
    if obs is None:return {"state":QState.ABSENT.value,"reason":"ABSENT"}
    if not obs.get("verified",False):return {"state":QState.PRESENT_UNVERIFIED.value,"reason":"NOT_VERIFIED"}
    if obs.get("content_digest")!=expected_digest:return {"state":QState.VERIFIED_NONCURRENT.value,"reason":"DIGEST_DIVERGENCE"}
    if obs.get("release")!=expected_release:return {"state":QState.VERIFIED_NONCURRENT.value,"reason":"RELEASE_MISMATCH"}
    if obs.get("parent_manifest_digest")!=parent_digest:return {"state":QState.VERIFIED_NONCURRENT.value,"reason":"PARENT_MISMATCH"}
    return {"state":QState.VERIFIED_CURRENT.value,"reason":"MATCH"}

def adjudicate(observations,expected_release,expected_digest,parent_digest,required=("library","drive","github")):
    states={k:classify(observations.get(k),expected_release,expected_digest,parent_digest) for k in required}
    if any(x["reason"] in {"DIGEST_DIVERGENCE","RELEASE_MISMATCH","PARENT_MISMATCH"} for x in states.values()):
        return {"decision":"HOLD_DIVERGENCE","states":states}
    if all(x["state"]==QState.VERIFIED_CURRENT.value for x in states.values()):
        return {"decision":"PROMOTE_STRONG_3OF3","states":states}
    if any(x["state"]==QState.PRESENT_UNVERIFIED.value for x in states.values()):
        return {"decision":"HOLD_UNVERIFIED","states":states}
    return {"decision":"HOLD_INCOMPLETE","states":states}

def recovery_hint(observations,expected_digest):
    matched=[k for k,v in observations.items() if v and v.get("verified") and v.get("content_digest")==expected_digest]
    return {"matching_verified_surfaces":sorted(matched),"recoverable_hint":len(matched)>=2,"authority":False}
