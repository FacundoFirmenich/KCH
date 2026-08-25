+++
schema = "kch.csi-governance-node.v0.1.0"
id = "RULE-HOST-PROJECTION"
kind = "RULE"
version = "0.1.0"
title = "Loss-aware host projection"
parent = "KCH-RULES"
children = []
authority_ceiling = ["INSPECT", "BUILD_STAGED", "VALIDATE"]
routines = ["map_capabilities", "compile_projection", "verify_projection", "emit_degradation_receipt"]
subroutines = ["preserve_purpose", "preserve_decision", "preserve_evidence_contract", "preserve_provenance", "verify_transport_integrity"]
native_exec_rules = []
supersedes = []
+++

# Proyección consciente de pérdidas

Cada host recibe únicamente lo que puede representar. El compilador no equipara `HARNESS.md` con un archivo nativo inexistente ni `RULES.md` con `.rules`. Toda pérdida, aplanamiento de agentes o restricción no transportable se declara en un recibo; sin equivalencia suficiente, la proyección queda `SHADOW_ONLY` o `NO_PROMOTION`.
