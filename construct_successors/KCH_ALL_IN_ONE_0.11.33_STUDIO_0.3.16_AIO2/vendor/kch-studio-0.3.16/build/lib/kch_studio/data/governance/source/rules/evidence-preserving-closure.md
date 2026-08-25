+++
schema = "kch.csi-governance-node.v0.1.0"
id = "RULE-EVIDENCE-PRESERVING-CLOSURE"
kind = "RULE"
version = "0.1.0"
title = "Evidence-preserving mechanical closure"
parent = "KCH-RULES"
children = []
authority_ceiling = ["INSPECT", "BUILD_STAGED", "VALIDATE"]
routines = ["retain_original_receipts", "project_without_transcription", "verify_by_regeneration", "fail_closed_on_missing_terminal_status"]
subroutines = ["verify_source_seals", "retain_transported_content", "copy_exact_unicode_spans", "bind_os_exit_code", "seal_projection_independently", "preserve_adverse_outcomes"]
native_exec_rules = []
supersedes = []
+++

# Clausura mecánica que preserva la evidencia

Una evidencia correcta no puede degradarse al redactar la contestación final. Las rutas, bytes, líneas físicas, hashes, spans literales, identidades de proceso y códigos de salida se proyectan mecánicamente desde recibos fuente verificados; el agente no los reconstruye, resume ni transcribe a mano.

La proyección conserva íntegros los recibos originales y sus contenidos transportados. Nunca se elimina contenido de un recibo para presentarlo después bajo el sello anterior. Una reducción legítima utiliza un esquema derivado explícito, procedencia completa y sello propio, mientras el original permanece disponible e inalterado.

El verificador regenera la clausura desde el sobre fuente retenido. Un cambio de Unicode, hash, orden, línea, span, PID, artefacto o salida terminal falla aunque la clausura alterada posea un autosellado internamente válido. El texto emitido por el proceso no sustituye al código de salida del sistema operativo y la presencia de artefactos no rescata un estado terminal adverso.

La clausura sólo acredita fidelidad de representación dentro de la jurisdicción de sus fuentes. No crea autoridad, permiso, éxito científico, equivalencia experimental, validación industrial ni preparación productiva. PHL conserva por separado sus estados de autorización, entrenamiento y ejecución real.
