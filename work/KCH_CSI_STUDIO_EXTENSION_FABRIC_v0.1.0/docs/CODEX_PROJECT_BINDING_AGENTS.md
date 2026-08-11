# KCH 0.11 — enlace gobernado de proyecto Codex

La autoridad KCH se interpreta siempre en el orden `HARNESS > AGENTS > RULES`. Este archivo enlaza la gobernanza instalada con el ciclo nativo de Codex; no sustituye las fuentes completas incluidas en el paquete KCH.

## Arranque obligatorio y verificable

Antes de la primera acción material de cada tarea nueva, llama exactamente una vez a `kch_governed_preflight` del servidor KCH de preflight. No lo reemplaces por una explicación, una inferencia ni una llamada posterior. La herramienta es de sólo lectura y está separada del despachador operativo.

- Si devuelve `PASS`, continúa dentro de su alcance y conserva sus límites de claims.
- Si devuelve `FAIL` o no está disponible, no ejecutes la acción material: registra el gate adverso y su causa exacta.
- No describas la mera configuración, disponibilidad o respuesta manual como activación automática observada.

El servidor bootstrap expone catálogo y despacho. Sus herramientas potencialmente operativas mantienen aprobación y gobierno propios; el preflight automático no concede permiso, autoridad ni ejecución a ninguna de ellas.

PHL está autorizado pero no entrenado. No inicies aprendizaje PHL real salvo feedback genuino del usuario y el protocolo explícito correspondiente.

## Lectura completa y semántica de orden

Cuando el usuario exija lectura completa, lee todos los bytes antes de afirmar comprensión. Las búsquedas y fragmentos no sustituyen esa lectura. Conserva bytes, líneas físicas, SHA-256 y método.

Usa `full_read_file` para archivos UTF-8 dentro de la raíz estable. El gate sólo permite afirmar lectura completa cuando dos lecturas independientes coinciden y todo el contenido fue transportado. Una denegación de permisos, un cambio entre lecturas, un hash esperado discordante, un archivo binario o el límite de transporte conservan un resultado adverso y bloquean ese claim. Los archivos externos requieren permiso explícito.

Para dos o más archivos usa `full_read_batch` en el orden nativo preregistrado y entrega `expected_evidence_spans` literales cuando la misión requiera comprensión de hechos concretos. No reconstruyas a mano hashes, bytes, líneas ni ordinals. Antes de publicar el recibo o usarlo como evidencia, pásalo sin modificaciones a `full_read_verify_batch`: el verificador vuelve a la fuente y una contradicción factual no queda rescatada por un autosellado canónico válido. Una lectura completa sin spans exactos sólo acredita transporte completo; no acredita comprensión semántica específica.

En inventarios derivados preserva por defecto el orden nativo/de fuente. No lo sustituyas por orden alfabético, ranking u otra clave salvo petición expresa o contrato predeclarado, y declara siempre la semántica de orden. Verifica el recibo de forma independiente antes del cierre y conserva cualquier diferencia adversa.
