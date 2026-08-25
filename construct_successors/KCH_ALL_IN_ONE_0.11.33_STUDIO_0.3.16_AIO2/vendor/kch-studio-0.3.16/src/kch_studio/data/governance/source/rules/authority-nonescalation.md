+++
schema = "kch.csi-governance-node.v0.1.0"
id = "RULE-AUTHORITY-NONESCALATION"
kind = "RULE"
version = "0.1.0"
title = "Authority non-escalation"
parent = "KCH-RULES"
children = []
authority_ceiling = ["INSPECT", "DESIGN", "BUILD_STAGED", "VALIDATE", "RECOMMEND", "REQUEST_INSTALL"]
routines = ["resolve_authority", "intersect_capabilities", "record_abstention"]
subroutines = ["verify_parent_ceiling", "verify_user_consent", "verify_host_policy"]
native_exec_rules = []
supersedes = []
+++

# No escalamiento de autoridad

Toda autoridad efectiva es la intersección del techo HARNESS, la asignación AGENT, las restricciones RULE, la política del host y el consentimiento vigente. Un conjunto vacío produce `ABSTAIN`, no una autorización implícita.
