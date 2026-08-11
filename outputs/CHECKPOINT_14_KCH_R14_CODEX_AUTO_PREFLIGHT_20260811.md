# Checkpoint 14 — KCH R14: ingreso Codex y preflight automático acotado

KCH queda mejor posicionado que en el checkpoint anterior. El Super‑MCP integral ya funcionaba localmente, pero su superficie monolítica de 277 herramientas agotaba el handshake de Codex y no existía evidencia de preflight automático. R14 resuelve el transporte mediante dos frontales sin amputar la superficie: uno de cinco herramientas para catálogo y despacho gobernado, y otro de una única herramienta de sólo lectura para el preflight automático.

La secuencia adversa fue informativa. Los prepilotos 009 y 010 arrancaron sin timeout y completaron la tarea, pero no llamaron automáticamente al preflight; por tanto, las instrucciones MCP aisladas no bastaban. El prepiloto 009 añadió un hash autocanónico inválido, preservado como fallo. El 010 controló la contaminación por historia heredada, produjo un hash válido y volvió a fallar sólo el disparo automático.

El prepiloto 011 añadió el enlace de proyecto `AGENTS.md` y separó el preflight de sólo lectura del despachador operativo. Ante un prompt que no nombraba KCH, Codex llamó nativamente a `kch_governed_preflight` antes de leer la tarea fuente. La llamada duró 18,478 s y devolvió `PASS`; luego se ejecutó la lectura pedida, se corrigió un control de conteo y se selló un recibo cuyo hash independiente coincide.

La evidencia técnica de R14 es consistente: 66/66 pruebas de fuente, ZIP de 22.114.374 bytes con SHA‑256 `84d0e94de2c25f62b3b3d512239ca0b57f9bb2eeaed073911e9707648de28185`, instalación limpia aislada y post‑install 19/19. El Super‑MCP conserva 277 herramientas, MIS conserva 480 registros y 60 ledgers, y PHL sigue autorizado pero no entrenado.

Esto demuestra una integración local operativa de arranque en una tarea Codex, no una garantía universal del host, eficacia causal, reducción de fallos históricos, validación industrial ni imposibilidad de recurrencia. El próximo gate crítico es repetir el enlace en varias tareas nuevas y, después, comparar casos históricos con/sin KCH bajo condición íntegra. PHL real continúa reservado para el final.

Defecto menor conservado: el bootstrap genera `codex.config.toml` y `AGENTS_KCH.md`, pero su array de inventario enumera sólo adaptadores JSON. Los archivos existen y funcionan; el inventario se corregirá en el siguiente sellado sin reescribir R14.
