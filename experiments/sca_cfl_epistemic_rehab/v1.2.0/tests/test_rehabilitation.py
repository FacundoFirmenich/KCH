from sca_rehab.rehabilitation import *

def test_duplicates_are_not_roots():
    assert evidence_value([1])==1.6

def test_six_not_enough():
    assert not eligible([1]*6)

def test_seven_cross():
    assert eligible([1]*7)

def test_negative_can_reverse():
    assert not eligible([1]*8+[-1])

def test_nine_plus_negative_crosses():
    assert eligible([1]*9+[-1])
