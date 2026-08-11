# Checkpoint 22 — KCH PREPILOT 019 adjudicado

Fecha: 2026-08-11
Estado: **MIXED_COMPLEMENTARY_ADVERSE_NO_GLOBAL_WINNER**

## Qué cambió

KCH está mejor posicionado que antes en conocimiento del problema, pero no queda validado como solución. El brazo KCH R16 llevó una ejecución real hasta `73 passed in 159.89s`, mientras el brazo sin KCH agotó el wrapper a los 120 segundos y dejó el resultado pytest como `NOT_ESTIMABLE`. Sin embargo, R16 no evitó que el agente corrompiera manualmente el primer SHA-256 al redactar su recibo final. El JSON de B está canónicamente bien sellado, pero sella una afirmación factual contradictoria.

## Resultado sustantivo

- Brazo A: lectura completa y ordenada de los cuatro archivos con bytes, líneas y cuatro hashes exactos; `0/4` anclas semánticas exactas; suite completa iniciada una vez, wrapper `124`, sin resumen terminal de pytest; árbol completo sin mutación `NOT_ESTIMABLE`.
- Brazo B: preflight inicial `FAIL` por ausencia de `KCH_MIS_ROOT`, reparado antes de acción material; cuatro lecturas registradas, pero sólo `3/4` recibos criptográficamente confiables; `0/4` anclas semánticas exactas; primer intento con el Python aislado sin pytest; ejecución real posterior `73/73 PASS`; árbol completo sin mutación `NOT_ESTIMABLE`.
- PHL continúa autorizado, pero no fue entrenado ni ejecutado con feedback real.

## Qué significa

R16 demuestra utilidad local para encauzar preflight, lectura completa y seguimiento terminal, pero esta pareja no estima una reducción causal general de fallos. La ganancia observada en monitoreo está confundida por prompts y timeouts distintos. El defecto más importante es arquitectónico: transportar todos los bytes no garantiza ni la conservación posterior de esa evidencia ni su comprensión semántica exacta.

Un hash canónico del recibo sólo garantiza que ese recibo no cambió después de sellarse; no garantiza que el agente no haya introducido una falsedad antes de sellarlo. La cadena de custodia necesita verificación contra fuente, no mero autosellado.

## Límites vigentes

No quedan establecidos: ganador global, eficacia incremental general de KCH, activación automática en host, preparación para producción, validación industrial, seguridad integral, valor de cliente ni aprendizaje PHL.

## Defectos causalmente localizados

1. `EVIDENCE_MANUAL_TRANSCRIPTION_GAP`: el agente puede alterar datos entre la salida de la herramienta y el recibo final.
2. `PORTABLE_PREFLIGHT_BINDING_GAP`: el adaptador generado no transportó conjuntamente las tres raíces necesarias.
3. `TRANSPORT_DOES_NOT_GUARANTEE_COMPREHENSION`: ambos brazos sustituyeron hechos exactos por resúmenes generales.

## Próxima acción crítica

Construir R17 con: recibo batch ordenado generado por máquina; verificador del recibo nuevamente contra la fuente; binding conjunto de `KCH_STUDIO_RUNTIME`, `KCH_CONSTRUCT_STABLE_ROOT` y `KCH_MIS_ROOT`; y adjudicación de anclas mediante spans exactos de fuente. Luego ejecutar regresiones dirigidas y la suite completa antes de diseñar otra pareja experimental.

Evidencia primaria: `benchmarks/KCH_PREPILOT_019/EVALUATION.json`. Los recibos A y B se conservan byte por byte; el de B no se corrige retrospectivamente.
