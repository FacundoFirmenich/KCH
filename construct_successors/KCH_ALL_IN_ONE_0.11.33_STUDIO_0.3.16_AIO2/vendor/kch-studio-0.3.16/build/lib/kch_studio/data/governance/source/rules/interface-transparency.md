+++
schema = "kch.csi-governance-node.v0.1.0"
id = "RULE-INTERFACE-TRANSPARENCY"
kind = "RULE"
version = "0.1.0"
title = "Visible and prudent interaction"
parent = "KCH-RULES"
children = []
authority_ceiling = ["INSPECT", "DESIGN", "RECOMMEND", "REQUEST_INSTALL"]
routines = ["present_state", "present_choice", "present_consequence", "confirm_transition"]
subroutines = ["render_compact_capsule", "expand_details", "show_permissions", "show_evidence_boundary", "show_rollback"]
native_exec_rules = []
supersedes = []
+++

# Interfaz visible y prudente

Toda opción relevante debe estar a la vista con nombre comprensible, efecto, riesgo, procedencia y reversibilidad. La forma predeterminada es una cápsula compacta, claramente visible y desplegable; los diálogos modales se reservan para decisiones consecuenciales. No se emplean dark patterns ni defaults que aparenten consentimiento.
