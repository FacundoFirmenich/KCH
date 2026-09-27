from .robust import robust_genealogy_gate

def provenance_aware_evidence_gate(events,constraints,threshold=20.0):
    hard=[c for c in constraints if c.authorized]
    return robust_genealogy_gate(events,hard,threshold=threshold)
