+++
schema = "kch.csi-governance-node.v0.1.0"
id = "KCH-RULES"
kind = "RULES"
version = "0.1.0"
title = "KCH semantic rules and routines"
parent = "KCH-AGENTS"
children = ["RULE-AUTHORITY-NONESCALATION", "RULE-GENERATION-STAGED", "RULE-EXTENSION-ACQUISITION", "RULE-RECOMMENDATION-EVIDENCE", "RULE-INTERFACE-TRANSPARENCY", "RULE-HOST-PROJECTION"]
authority_ceiling = ["INSPECT", "DESIGN", "BUILD_STAGED", "VALIDATE", "RECOMMEND", "REQUEST_INSTALL"]
conflict_policy = "MOST_RESTRICTIVE_RULE_WINS"
supersedes = []
+++

# RULES — Reglas, rutinas y subrutinas

`RULES.md` es el plano normativo semántico de KCH. No debe confundirse con los archivos `.rules` de Codex, cuyo alcance nativo se limita a permisos de comandos fuera del sandbox.

Cada regla vive en `rules/*.md` y declara rutinas/subrutinas auditables. El compilador puede proyectar:

- instrucciones semánticas al formato de agentes de un host;
- políticas ejecutables sólo cuando exista un mapeo exacto y verificable;
- recibos de degradación cuando el host no pueda representar una relación CSI.

Una regla no puede conceder autoridad. Ante conflicto de permisos prevalece la opción más restrictiva; ante conflicto semántico se conserva la formulación superior y se solicita adjudicación si no existe especialización válida.
