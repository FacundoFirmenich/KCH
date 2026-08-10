+++
schema = "kch.csi-governance-node.v0.1.0"
id = "RULE-EXTENSION-ACQUISITION"
kind = "RULE"
version = "0.1.0"
title = "Governed extension acquisition"
parent = "KCH-RULES"
children = []
authority_ceiling = ["INSPECT", "RECOMMEND", "REQUEST_INSTALL"]
routines = ["discover", "inspect", "plan_install", "request_consent"]
subroutines = ["resolve_source", "verify_identity", "enumerate_permissions", "analyze_dependencies", "prepare_isolated_target", "prepare_rollback"]
native_exec_rules = []
supersedes = []
+++

# Adquisición gobernada

Buscar y leer metadatos es distinto de descargar, instalar, habilitar, autenticar y ejecutar. Cada transición requiere un recibo explícito. La fase actual termina en `REQUEST_INSTALL`; no instala globalmente ni modifica un host externo.
