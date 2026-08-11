# KCH 0.11 — enlace gobernado de proyecto Codex

La autoridad KCH se interpreta siempre en el orden `HARNESS > AGENTS > RULES`. Este archivo enlaza la gobernanza instalada con el ciclo nativo de Codex; no sustituye las fuentes completas incluidas en el paquete KCH.

## Arranque obligatorio y verificable

Antes de la primera acción material de cada tarea nueva, llama exactamente una vez a `kch_governed_preflight` del servidor KCH de preflight. No lo reemplaces por una explicación, una inferencia ni una llamada posterior. La herramienta es de sólo lectura y está separada del despachador operativo.

- Si devuelve `PASS`, continúa dentro de su alcance y conserva sus límites de claims.
- Si devuelve `FAIL` o no está disponible, no ejecutes la acción material: registra el gate adverso y su causa exacta.
- No describas la mera configuración, disponibilidad o respuesta manual como activación automática observada.

El servidor bootstrap expone catálogo y despacho. Sus herramientas potencialmente operativas mantienen aprobación y gobierno propios; el preflight automático no concede permiso, autoridad ni ejecución a ninguna de ellas.

PHL está autorizado pero no entrenado. No inicies aprendizaje PHL real salvo feedback genuino del usuario y el protocolo explícito correspondiente.
