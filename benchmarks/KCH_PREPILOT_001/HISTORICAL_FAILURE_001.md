# HISTORICAL FAILURE 001 — preflight no canónico y comparación inválida

- Fecha de observación: 2026-08-10.
- Caso: `KCH-PREPILOT-001`.
- Baseline Luna: tarea `019fecfe-cfde-7f81-b29d-4da9a0d8dfc4`; recibo SHA-256 `74ad8f52e27813713b654598b0bbad4d941ac43cdbb4c08a7e3aea0b5e6f5198`.
- Brazo KCH Luna: tarea `019fecff-08ef-7e53-85dc-53fde6705acf`; recibo SHA-256 `b7c606929f857ed79e1b0c6b2dbb8bca65f79872735a2664ca837bb6dfd8ebe8`.

Fallo observado: el protocolo del brazo KCH ordenó instanciar `KCHAdvancedRuntime`, que es un componente interno, en vez de arrancar el Super-MCP canónico mediante `StudioMCP`. La auditoría interna aplicó por error el alcance completo y devolvió `FAIL` por herramientas que sólo pertenecían a la composición host.

Corrección vinculante: ningún ensayo con arnés puede comenzar mediante una clase interna elegida ad hoc. Tiene que invocar primero la herramienta única `kch_preflight` del entrypoint canónico y conservar el recibo completo.

Primero, congela y hashea el corpus, el prompt común, el rubric y la asignación de condiciones antes de despachar ninguna tarea.

Segundo, arranca el brazo KCH exclusivamente por `kch_studio.mcp_server:StudioMCP`, llama `kch_preflight` y detén la ejecución si el gate no es `PASS`.

Después, ejecuta ambos brazos con el mismo modelo, intensidad, corpus, red y límites de salida; la única diferencia admitida es la condición KCH predeclarada.

Luego, persiste ambos recibos sin reescribir resultados adversos y evalúalos con un script determinista ciego a la narrativa de los agentes.

Finalmente, declara `NOT_ESTIMABLE` para el efecto de KCH si falla la integridad de condición, falta una réplica o el evaluador no está cegado. Una puntuación superior no rescata un gate experimental fallido.

Decisión: `KCH-PREPILOT-001` se conserva como prepiloto descriptivo adverso. No se promueve a evidencia causal ni a validación industrial, aun después de reparar el entrypoint.

Este caso no demuestra superioridad de KCH, valor humano, escalabilidad, seguridad abierta, selección BIND, contrato Venture Client ni validación industrial.
