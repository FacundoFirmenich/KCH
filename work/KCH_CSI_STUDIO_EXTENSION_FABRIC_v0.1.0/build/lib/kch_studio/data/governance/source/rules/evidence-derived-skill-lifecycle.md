+++
schema = "kch.csi-governance-node.v0.1.0"
id = "RULE-EVIDENCE-DERIVED-SKILL-LIFECYCLE"
kind = "RULE"
version = "0.1.0"
title = "Evidence-derived protocol, skill and continuity lifecycle"
parent = "KCH-RULES"
children = []
authority_ceiling = ["INSPECT", "DESIGN", "BUILD_STAGED", "VALIDATE", "RECOMMEND"]
routines = ["preserve_raw", "normalize_separately", "detect_candidates", "generate_dated_protocol", "stage_skill", "organize_archive", "adjudicate_budget", "prepare_handoff"]
subroutines = ["redact_secret_value", "retain_secret_reference", "prehash_evidence", "retain_adverse_result", "emit_not_estimable", "verify_hash_chain", "require_host_connector"]
native_exec_rules = []
supersedes = []
+++

# Ciclo de vida de protocolos, skills y continuidad derivados de evidencia

1. Se preservan los bytes crudos y se escribe por separado cualquier normalización o resolución de dictado.
2. La detección automática crea candidatos trazables; no convierte coincidencias léxicas ni inferencias del modelo en hechos.
3. Un protocolo requiere evidencia mínima explícita, pasos, al menos un fallo o corrección, fecha, casos, pre-hash y límites de claim.
4. Toda skill generada queda `STAGED_UNEVALUATED`, con `SKILL.md`, protocolo, procedencia, evals y manifiesto. Generar no equivale a evaluar, instalar, activar ni promover.
5. Los valores secretos no se escriben en fuentes derivadas, logs, protocolos ni skills. Sólo se conservan handles, clase, longitud y hash no reversible.
6. Los resultados adversos y gates fallidos se retienen en su jurisdicción histórica incluso después de reparar la causa.
7. El medidor semanal no infiere precios, límites ni disponibilidad. Sin recibo o telemetría del host devuelve `NOT_ESTIMABLE`.
8. La cadencia puede preparar checkpoints y handoffs locales; crear una tarea o archivar otra exige un conector real y autoridad del host.
