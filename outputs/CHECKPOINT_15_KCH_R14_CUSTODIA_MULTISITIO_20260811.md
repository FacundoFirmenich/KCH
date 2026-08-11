# CHECKPOINT 15 — KCH 0.11 PRE2G R14: auto-preflight y custodia multisitio

Fecha: 2026-08-11

## Resultado sustantivo

KCH queda mejor posicionado que en R13: R14 ya no intenta exponer automáticamente toda la superficie operativa del arnés. Separa una puerta de preflight estrictamente de sólo lectura, apta para activación automática, de un broker operativo gobernado que conserva aprobación explícita para cualquier despacho con capacidad de mutación.

El prepiloto 011 observó la llamada nativa `kch_governed_preflight` antes de la primera lectura material de la tarea y devolvió `PASS`. Los prepilotos 009 y 010 permanecen como evidencia adversa: el transporte funcionaba, pero el preflight no se activaba automáticamente. La diferencia observada en 011 fue la vinculación conjunta del `AGENTS.md` de proyecto y el servidor MCP monofunción de sólo lectura.

Esto demuestra transporte e invocación automática en una tarea local observada. No demuestra todavía eficacia causal general sobre la calidad de las tareas, recurrencia fiable entre hosts/modelos, validación industrial, ni imposibilidad de reincidencia. PHL está autorizado pero no fue entrenado ni ejecutado realmente.

## Evidencia técnica

- Regresión de fuente: 66/66 pruebas.
- Instalación limpia aislada: 19/19 gates.
- Superficie completa: 277 herramientas.
- Broker de arranque: 5 herramientas.
- Preflight automático: 1 herramienta de sólo lectura.
- Artefacto: `KCH_0.11_PRE2G_INTEGRATED_CANDIDATE_R14.zip`.
- Bytes: 22,114,374.
- SHA-256: `84d0e94de2c25f62b3b3d512239ca0b57f9bb2eeaed073911e9707648de28185`.

## Custodia GitHub

- Repositorio: `FacundoFirmenich/KCH`.
- Visibilidad verificada: `PRIVATE`.
- Rama: `agent/kch-r14-codex-binding`.
- Commit remoto: `570c5867c3e72f51ae54c3cfc5ed6d2c9c276e8b`.
- PR borrador: https://github.com/FacundoFirmenich/KCH/pull/2
- No hubo fusión automática.

## Custodia Google Drive

Carpeta KCH: `1f0vH7T7oLwOh7or5wKs4FoNgnY7quVR3`.

- R14 ZIP: `1SxrDVEDpNypywnZeA3A_y-glxG-nfzfn`, 22,114,374 bytes.
- Checkpoint 14: `1_15YHpa47mysPIB-yIZ3guOS4NlWYbDj`, 2,408 bytes.
- Gate R14: `1OXIaC0yTGWbsHz32d77n2U2ADpTmiT2j`, 1,592 bytes.
- Evaluación 009: `1zCm6YOrZSgaflYCwZTSkJKqEUxslFglm`, 907 bytes.
- Evaluación 010: `16WowWikSd8PyfohxZ3K6Gi3_m-hKj1cv`, 976 bytes.
- Evaluación 011: `1MeJd4_zK5gYEpv_h812ITe5WS7c2de19`, 1,359 bytes.

La lectura remota confirmó ID, nombre, tipo, tamaño y pertenencia a la carpeta KCH. El conector no devolvió checksums remotos; por tanto no se afirma equivalencia criptográfica Drive-local. El SHA-256 local y el commit GitHub son anclas independientes, y la igualdad exacta de tamaño en Drive es evidencia de transporte, no sustituto del hash.

## Defecto menor preservado

El recibo de bootstrap portable genera correctamente `codex.config.toml` y `AGENTS_KCH.md`, pero su inventario `host_adapters` enumera sólo adaptadores JSON por el glob usado. Es un defecto de inventario, no ausencia de los archivos. Debe corregirse en la siguiente revisión sin modificar retrospectivamente R14.

## Próximo gate crítico

Replicar la activación automática en varias tareas nuevas y ejecutar pares históricos comparables con y sin KCH. La condición de avance no será que el MCP aparezca, sino que: (1) el preflight ocurra antes de la primera acción material; (2) sus hallazgos gobiernen la ejecución; (3) los recibos sean criptográficamente reproducibles; y (4) disminuyan fallos concretos predeclarados sin introducir nuevas restricciones inventadas. PHL real permanece para el final.
