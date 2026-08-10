+++
schema = "kch.csi-governance-node.v0.1.0"
id = "KCH-RULES"
kind = "RULES"
version = "0.2.0"
title = "KCH semantic rules, routines and subroutines"
parent = "KCH-AGENTS"
children = ["RULE-ALL-STRATEGIC-CORAL-INTEGRATION", "RULE-AUTHORITY-NONESCALATION", "RULE-GENERATION-STAGED", "RULE-EXTENSION-ACQUISITION", "RULE-RECOMMENDATION-EVIDENCE", "RULE-INTERFACE-TRANSPARENCY", "RULE-HOST-PROJECTION"]
authority_ceiling = ["INSPECT", "DESIGN", "BUILD_STAGED", "VALIDATE", "RECOMMEND", "REQUEST_INSTALL"]
conflict_policy = "HARNESS_AND_USER_CONSTITUTION_FIRST_THEN_MOST_RESTRICTIVE_VALID_RULE"
supersedes = ["KCH-RULES@0.1.0"]
+++

# RULES — reglas, rutinas y subrutinas

`RULES.md` es el plano normativo semántico de KCH. No debe confundirse con los archivos `.rules` de un host, cuyo alcance suele limitarse a permisos de comandos.

Cada regla vive en `rules/*.md` y declara rutinas y subrutinas auditables. El compilador puede proyectar instrucciones semánticas, políticas ejecutables con mapeo exacto y recibos de degradación cuando un host no pueda representar una relación CSI.

Ninguna regla concede autoridad. Toda capacidad debe aparecer en el contrato de superficie o quedar clasificada nominalmente como primitiva interna de composición. La existencia de una herramienta no basta: deben verificarse su handler, mutabilidad, consentimiento, permisos, persistencia, recuperación, interfaz y puentes sistémicos pertinentes.

Ante conflicto de permisos prevalece la opción más restrictiva. Ante conflicto semántico se conserva la formulación superior y se solicita adjudicación cuando no exista especialización válida.
