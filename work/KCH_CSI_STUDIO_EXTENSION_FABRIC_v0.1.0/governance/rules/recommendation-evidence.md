+++
schema = "kch.csi-governance-node.v0.1.0"
id = "RULE-RECOMMENDATION-EVIDENCE"
kind = "RULE"
version = "0.1.0"
title = "Evidence-bounded recommendations"
parent = "KCH-RULES"
children = []
authority_ceiling = ["INSPECT", "RECOMMEND"]
routines = ["normalize_candidates", "evaluate_locally", "explain_tradeoffs"]
subroutines = ["check_host_compatibility", "check_provenance", "check_maintenance", "check_license", "check_security_evidence", "separate_popularity_from_quality"]
native_exec_rules = []
supersedes = []
+++

# Recomendación fundada

No existe un ganador global por número de descargas, estrellas o posición en un marketplace. KCH recomienda condicionalmente para un objetivo, host, riesgo y jurisdicción; muestra evidencia faltante y conserva `NOT_ESTIMABLE` cuando no puede comparar.
