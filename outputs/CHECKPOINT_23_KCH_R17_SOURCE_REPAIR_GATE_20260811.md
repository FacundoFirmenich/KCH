# Checkpoint 23 — R17 cierra en fuente los defectos de PREPILOT 019

Fecha: 2026-08-11
Estado: **SOURCE_REPAIR_GATE_PASS — PORTABLE_GATE_PENDING**

## Posición respecto del checkpoint anterior

KCH está materialmente mejor posicionado. El checkpoint 22 había demostrado que R16 podía transportar archivos completos pero no impedir que el agente corrompiera después los hashes, ni obligarlo a comprender los hechos exactos. R17 añade una cadena ejecutable de evidencia que separa transporte, verdad contra fuente y evidencia semántica.

## Qué se implementó

- `full_read_batch`: lee en el orden entregado, genera ordinals, bytes, líneas, dos hashes, contenido y recibos sin inventario manual.
- `full_read_verify_batch`: vuelve a leer la fuente y contrasta cada campo, el orden, los ordinals, el contenido y los spans.
- `expected_evidence_spans`: una afirmación semántica específica sólo queda autorizada si el texto literal preregistrado aparece y queda localizado. Leer todos los bytes no equivale a comprender un hecho concreto.
- Adaptador Codex fail-closed: tanto preflight como bootstrap reciben conjuntamente `KCH_STUDIO_RUNTIME`, `KCH_MIS_ROOT` y `KCH_CONSTRUCT_STABLE_ROOT`.
- Gobernanza CSI recompilada: 19 nodos, 6 agentes, 10 reglas; grafo `7eb8d424f8865f597b6ead1a6d8cdc3c12b6d4a861425765134bd650c19adb8e`.

## Validación observada

- Ruff: PASS.
- Pruebas dirigidas: 26/26 PASS.
- Suite completa: 78/78 PASS en 129,81 s.
- Batch vivo sobre los cuatro archivos del PREPILOT 019: `PASS`.
- Verificación independiente contra fuente: `PASS_VERIFIED_AGAINST_SOURCE`.
- Anclas literales: todas presentes una vez; claim semántico autorizado.
- Ataque: se reemplazó el primer SHA-256 por ceros y se recalcularon correctamente el sello del recibo y el sello exterior. El autosellado exterior pasó, pero el verificador respondió `FAIL_BATCH_NOT_SOURCE_TRUE` y localizó `sha256`.
- PHL: autorizado; entrenamiento y feedback real no ejecutados.

## Incidente de infraestructura preservado

C: alcanzó cero bytes libres durante un parche grande y el archivo en reemplazo quedó temporalmente en cero bytes. Se eliminó únicamente `release_build`, salida regenerable cuyo ZIP R16 ya estaba verificado en GitHub privado y Drive; no se borraron fuentes ni evidencia. El archivo se restauró byte-exacto desde el worktree Git R16 (`e27fdac0e2127a11cf6b0389797b00738f596ef1cfc2cdb13437f08f05e52c05`) y R17 se reaplicó en parches acotados.

## Qué no está demostrado

Todavía no están demostrados el empaquetado R17, la instalación aislada, la exposición real de las tres herramientas por stdio, el adaptador generado dentro del ZIP, la activación automática de host, la preparación para producción ni la validación industrial.

## Próxima acción crítica

Construir R17, extraerla en una raíz nueva de D:, instalarla en un runtime aislado nuevo y ejecutar: post-install gate, preflight, batch real, verificación contra fuente y rechazo del recibo resealado adulterado. Sólo ese gate autorizará la release portátil.

Evidencia ejecutable: `outputs/KCH_R17_PREPILOT019_REPAIR_GATE.json` (`d28d52bb36ef3ae24c7f66cfbe5ba4d6ff1a524ad4633e24f62f8364f5d452a1`).
