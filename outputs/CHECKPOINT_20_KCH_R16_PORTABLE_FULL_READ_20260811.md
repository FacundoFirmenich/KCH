# Checkpoint 20 — KCH 0.11 PRE2G R16 portátil

Fecha: 2026-08-11
PHL: autorizado; entrenamiento real no ejecutado

## Posición del proyecto

KCH queda materialmente mejor posicionado que tras R15 y el resultado discordante del prepiloto 018. R16 incorpora la reparación prospectiva de `ConstructMode`, recompila la gobernanza CSI y convierte el contrato de lectura íntegra en una herramienta realmente ejecutable. La suite de fuente terminó 73/73 y una instalación limpia desde el ZIP terminó con gate posinstalación 19/19.

Esto no borra el resultado histórico de 018: A obtuvo 70/70, B obtuvo 69/70 y B calificó indebidamente el fallo observado como determinista. La reparación posterior demuestra que la causa reproducida es reparable; no demuestra que KCH hubiera causado aquel fallo ni que haya eliminado toda carrera posible.

## Nueva capacidad efectiva: `full_read_file`

La herramienta lee dos veces todos los bytes de un archivo UTF-8 de la raíz estable, verifica estabilidad y hash, computa bytes y líneas físicas, y sólo permite el claim de lectura completa cuando transporta todo el contenido. En la instalación R16 leyó y transportó `advanced_runtime.py`: 68.691 bytes, 1.655 líneas y SHA-256 coincidente en ambas lecturas (`d8cb3c36…e6452a7`).

También se verificó el caso adverso: una ruta externa a la raíz estable devolvió `PERMISSION_REQUIRED` y `complete_read_claim_allowed=false`. Un archivo binario, una mutación entre lecturas, un hash esperado discordante o un texto superior al límite de transporte tampoco pueden presentarse como lectura completa.

## Gate portátil

- ZIP R16: 22.130.380 bytes;
- SHA-256: `5868c311ca4be975100cc5fbc45a206aa1c3cfb17a11f9261aab4e614cf6143c`;
- extracción nueva: PASS, 264 archivos;
- instalación offline aislada: PASS;
- gate posinstalación: `PASS_BOUNDED`, 19/19;
- Super-MCP: 278 herramientas combinadas;
- bootstrap: 5 herramientas; preflight automático de sólo lectura: 1;
- configuración externa de hosts: no modificada;
- credenciales incorporadas: no;
- micrófono activado: no;
- PHL real: no ejecutado.

## Límite científico y técnico

R16 establece consistencia local de fuente, portabilidad aislada y ejecución real del lector sobre texto de más de 800 líneas. No establece preparación para producción, seguridad completa, eficacia causal general frente a un control, integración efectiva en VS Code/Cline ni validación industrial. El lector monolítico admite hasta 5 MiB y sólo habilita transporte completo para UTF-8; archivos mayores o binarios requieren una futura lectura paginada con cobertura verificable.

## Próxima acción crítica

Persistir R16 y sus recibos en el GitHub privado y en Drive; después ejecutar un nuevo par fresco, prerregistrado y sin PHL real, sobre una tarea larga multiarchivo que obligue a usar `full_read_file`, preservar orden nativo y seguir una ejecución hasta término. Ese experimento debe medir cumplimiento específico, no declarar un ganador global.
