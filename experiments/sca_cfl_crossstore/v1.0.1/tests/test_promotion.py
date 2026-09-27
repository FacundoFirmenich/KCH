from sca_crossstore.promotion import *
E="e"*64;P="p"*64
def o(d=E,r="1.0.1",p=P,v=True):return {"verified":v,"content_digest":d,"release":r,"parent_manifest_digest":p}
def test_all_match_promotes():assert adjudicate({"library":o(),"drive":o(),"github":o()},"1.0.1",E,P)["decision"]=="PROMOTE_STRONG_3OF3"
def test_missing_holds():assert adjudicate({"library":o(),"drive":o()},"1.0.1",E,P)["decision"]=="HOLD_INCOMPLETE"
def test_unverified_holds():assert adjudicate({"library":o(),"drive":o(v=False),"github":o()},"1.0.1",E,P)["decision"]=="HOLD_UNVERIFIED"
def test_one_verified_fork_blocks_majority():assert adjudicate({"library":o(),"drive":o(),"github":o(d="f"*64)},"1.0.1",E,P)["decision"]=="HOLD_DIVERGENCE"
def test_parent_mismatch_blocks():assert adjudicate({"library":o(),"drive":o(),"github":o(p="x"*64)},"1.0.1",E,P)["decision"]=="HOLD_DIVERGENCE"
def test_quaternary_states_are_distinct():
 xs={classify(None,"1.0.1",E,P)["state"],classify(o(v=False),"1.0.1",E,P)["state"],classify(o(d="x"*64),"1.0.1",E,P)["state"],classify(o(),"1.0.1",E,P)["state"]};assert len(xs)==4
def test_recovery_hint_is_not_authority():
 h=recovery_hint({"library":o(),"drive":o(),"github":o(d="x"*64)},E);assert h["recoverable_hint"] and h["authority"] is False
