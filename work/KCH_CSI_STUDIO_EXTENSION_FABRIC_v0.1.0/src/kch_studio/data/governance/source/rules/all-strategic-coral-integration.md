+++
schema = "kch.csi-governance-node.v0.1.0"
id = "RULE-ALL-STRATEGIC-CORAL-INTEGRATION"
kind = "RULE"
version = "0.2.0"
title = "Every KCH element is strategic and must integrate chorally"
parent = "KCH-RULES"
children = []
authority_ceiling = ["INSPECT", "DESIGN", "BUILD_STAGED", "VALIDATE", "RECOMMEND"]
routines = ["inventory_public_surface", "verify_local_gate", "verify_systemic_gate", "verify_interface_visibility", "verify_recovery_path", "report_claim_ceiling"]
subroutines = ["bind_descriptor_to_handler", "classify_composition_internal", "check_mutability", "check_scoped_consent", "check_permission_path", "check_persistence_path", "check_cross_component_bridge", "preserve_adverse_result"]
native_exec_rules = []
supersedes = []
+++

# Todo es estratégico; integración coral obligatoria

Ningún módulo, función, herramienta, operador, componente, opción, menú o accionable puede degradarse a accesorio. Cada elemento debe superar un gate local de realidad y completitud y un gate sistémico de integración sinérgica. Las piezas conservan autonomía y jurisdicción, pero participan en una orquesta coherente mediante contratos, eventos, permisos, persistencia, recuperación, interfaz y evidencia explícitos.

Los conteos son evidencia auxiliar. Un gate de superficie no autoriza afirmar que KCH está completamente pulido, desplegado, probado por usuarios o listo para producción.
