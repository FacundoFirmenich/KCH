# Checkpoint 26 — KCH R19: supervisión terminal efectiva

## Resultado sustantivo

KCH queda mejor posicionado que en R18: la supervisión de procesos ya no confunde un PID aparente, un artefacto presente ni una promesa de seguimiento con éxito terminal. R19 conserva el PID del launcher, obtiene el PID efectivo desde un recibo canónico ligado al mismo `commitment_id` y `request_sha256`, registra la identidad de creación del proceso, espera sin relanzar y sólo adjudica éxito cuando dispone de código de salida y evidencia terminal coherente.

El primer gate instalado R18 fue adverso y se conserva: el proceso objetivo terminó con código 0 y produjo datos correctos, pero el launcher del entorno virtual devolvió PID 12228 mientras el supervisor efectivo selló PID 6644. KCH falló 26/28 porque no podía afirmar identidad gobernada. Ese resultado localizó un defecto real que la suite de fuente no había reproducido.

R19 corrigió causalmente esa frontera. La regresión fuerza `launcher_pid != worker_pid`; 9/9 pruebas específicas pasan. La suite completa pasa 86/86. El gate reproducible vuelve a leer y verificar por hash los cinco archivos de autoridad, comprueba spans exactos, ejecuta la suite bajo el propio monitor y certifica que el manifiesto fuente no cambió durante la prueba. En el runtime instalado, el post-install pasa 19/19 y expone 283 herramientas; el gate `stdio` pasa 29/29 con launcher 6460, worker efectivo 8164, salida 0, hashes independientes coincidentes y ningún relanzamiento.

## Significado técnico, metodológico y epistemológico

Técnicamente, KCH dispone ahora de una primitiva ejecutable para lanzar, observar, recuperar y sellar procesos locales hasta terminalidad. Metodológicamente, el éxito no se deriva del artefacto ni del silencio del proceso: exige una cadena de evidencia coherente entre solicitud, recibo de arranque, identidad, recibo terminal, logs, artefactos y código de salida. Epistemológicamente, el gate adverso R18 no fue borrado ni reinterpretado; fue la evidencia que distinguió éxito físico de éxito gobernado y dio lugar a una regresión nueva.

Esto reduce directamente la clase de fallo recurrente «te dije que monitorizaría, el proceso murió y sólo lo descubrí cuando el usuario preguntó». No demuestra todavía que todo host invoque automáticamente la herramienta, ni que resista reinicios del sistema operativo, cargas prolongadas o todas las plataformas. Tampoco demuestra eficacia industrial ni imposibilidad universal de reincidencia.

## Estado y límites

- Verde: full-read y evidencia semántica 5/5; suite fuente 86/86; Ruff; wheel 0.3.9; instalación portable fresca; composición Super-MCP; supervisión instalada 29/29.
- Adverso preservado: R18 instalado 26/28 por divergencia de PID no gobernada.
- Pendiente: interposición automática real en Codex/Cline/Cowork/OpenCode, prueba prolongada, reinicio del sistema operativo y campañas pareadas frescas.
- PHL: autorizado, pero no entrenado ni ejecutado en esta campaña, conforme a la orden del usuario.

## Artefacto y próxima acción crítica

El sucesor es `KCH_0.11_PRE2G_INTEGRATED_CANDIDATE_R19.zip`, 22.167.341 bytes, SHA-256 `a8f1cf6ffa7f5aafea28a81a3c2bef06b6e6c1f9786379208576be2463da8a08`. R18 permanece intacto como evidencia adversa.

Tras completar custodia remota verificable, la próxima acción crítica es PREPILOT_021: una tarea fresca pareada sobre monitoreo y recuperación de ejecución, con `BASELINE_SIN_KCH` estrictamente sin invocación ni mutación KCH y un brazo asistido que use R19. Ese experimento debe medir fidelidad de misión, detección autónoma del fallo, exactitud terminal, ausencia de relanzamiento y carga impuesta al usuario; no PHL real.
