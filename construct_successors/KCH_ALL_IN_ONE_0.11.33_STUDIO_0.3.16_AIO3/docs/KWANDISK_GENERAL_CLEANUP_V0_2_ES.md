# KwanDisk General Cleanup v0.2 — cierre sustantivo

## Posición

El candidato amplía KwanDisk desde inventario/sincronización acotados hacia una capacidad general de limpieza gobernada para carpetas ad hoc, Documents/Codex, raíces de agentes y tmp/temp.

## Cadena canónica

Google Drive es custodia durable primaria. GitHub replica todo lo compatible dentro de sus límites después del barrido de secretos. Disco local y VPS quedan como excepciones explícitas o indispensables; el VPS no es backup automático.

## Seguridad

La detección y planificación pueden ser proactivas. La eliminación nunca lo es. Sólo se ejecutan candidatos regenerables, transitorios conocidos o materiales con recibos Drive + GitHub + recuperación. Se bloquean estado de agentes, sesiones, bases SQLite vivas, worktrees sucios, secretos, desconocidos, rutas activas y copias únicas.

## Gages

El runtime exige actor USER, ID de autorización exacta, SHA-256 del plan y revalidación del target. Las pruebas cubren descubrimiento, happy path, adversas de autoridad/identidad, protección de agentes, cadena incompleta e idempotencia.

## Autoridad

Este artefacto es candidato en rama y PR borrador. No está promovido, empaquetado ni instalado; capability != activation != execution.
