# Área de trabajo, aprendizaje y continuidad

## Función

Esta área es una minisuite de superficie de usuario integrada en KCH. No sustituye KwanData, KwanDocs, OBL, PHL, SCO ni la persistencia: conserva su propia jurisdicción y emite puentes explícitos hacia esos subsistemas sin heredar su autoridad.

Su objetivo es convertir evidencia real de chats, sesiones, workspaces, archivos, experimentos y eventos de herramienta en una organización consultable y, cuando existe evidencia mínima, en protocolos operativos y candidatos de skill trazables.

El nombre de producto permanece abierto a decisión del usuario. El código usa `WorkbenchSuite` sólo como identificador técnico neutral.

## Capas persistentes

1. **Fuente cruda:** bytes originales o texto exacto. Si contiene un secreto, se conserva sólo una versión redactada y el hash del original; el valor secreto no entra en custodia.
2. **Normalización separada:** resolución de dictado o terminología en otro archivo. Nunca reescribe la fuente cruda. La dicción sólo se aplica a `DICTATION` o `AUDIO_TRANSCRIPT`; código, archivos, chats escritos y sesiones se copian sin sustitución. Los acrónimos respetan límites de token y no alteran subcadenas como `permission`.
3. **Candidatos de aprendizaje:** unidades con fuente, ordinal, dominio, clase, detector, hash y estado `DETECTED_CANDIDATE_REQUIRES_EVIDENCE_REVIEW`.
4. **Protocolo fechado:** sólo se genera al superar los umbrales declarados de evidencia, pasos y fallos/correcciones. Incluye pre-hash, casos, decisiones, límites y trazabilidad.
5. **Skill candidata:** contiene `SKILL.md`, `references/PROTOCOL.md`, `references/PROVENANCE.json`, `evals/evals.json` y `MANIFEST.json`. Nace siempre como `STAGED_UNEVALUATED`, no instalada y no activada.
6. **Archivo y grafo:** grupos, subgrupos, rangos, miembros y relaciones tipadas. El grafo añade dimensiones de archivo, workspace, sesión, dominio, artefacto y procedencia; cada nodo visible se resuelve a un registro exacto.
7. **Continuidad:** presupuesto semanal, cadencia, solicitudes de checkpoint y paquetes locales de handoff.
8. **Custodia:** cadena hash de eventos y verificación de fuentes, normalizaciones, protocolos y manifests de skills.

## Dominios y clases detectadas

Los dominios admitidos son teórico, formal, matemático, informático, estadístico, despliegue, experimental, metodológico, epistemológico, protocolar, refinement general y particular. Las clases son fallo, corrección, paso de procedimiento, decisión, invariante, caso, límite de claim y mejora.

La detección actual es determinista y léxica: es operativa para localizar candidatos y automatizar staging, pero no demuestra comprensión semántica completa. Por eso ningún candidato se convierte automáticamente en hecho, norma promulgada o skill activa.

## Presupuesto y cadencia

KCH admite cuentas semanales en tokens, moneda o porcentaje. Cada muestra exige un recibo de fuente. No se infieren precios, límites, consumo ni disponibilidad. Sin telemetría o declaración verificable, el estado es `NOT_ESTIMABLE`.

La política inicial es explícitamente `USER_CUSTOMIZABLE_DEFAULT_NOT_EMPIRICALLY_CALIBRATED`. Un tick persistente de 60 segundos consulta si corresponde mantenimiento; la frecuencia de trabajo real deriva del nivel de presupuesto:

- `NORMAL`: 120 minutos.
- `REFRESH`: 60 minutos.
- `CHECKPOINT`: 30 minutos.
- `HANDOFF`: 10 minutos.
- `CRITICAL`: 2 minutos.

El usuario puede cambiar toda la política. El tick puede desactivarse mediante el scheduler. Un handoff automático prepara un paquete local; crear una tarea real y archivar su predecesora requiere un conector del host y no se afirma sin su recibo.

## Secretos

Los patrones de token, asignación de credencial y bloques completos de clave privada se redactan antes de la persistencia. Se conserva únicamente un `SECRET_REF`, la clase, la longitud y un hash no reversible. Los cuatro últimos caracteres tampoco se guardan.

## Interfaz

La pestaña **Trabajo y aprendizaje** ofrece:

- incorporación de texto y archivos;
- estado visible de fuentes, aprendizajes, protocolos, skills, presupuesto e integridad;
- grupos y subgrupos archivísticos;
- árbol de aprendizajes y artefactos;
- grafo multidimensional clicable;
- mantenimiento manual inmediato.

La pestaña **Orquesta completa** conserva todas las operaciones avanzadas de presupuesto, relaciones, archivo, puentes e integridad.

## Gates y límites

- `kch_preflight` es el único preflight canónico y se ejecuta a través de `StudioMCP`.
- Un `PASS` de integridad prueba hashes y relaciones locales, no utilidad de la skill.
- Un `PASS` de superficie prueba clasificación y binding, no madurez productiva.
- PHL está autorizado pero sigue sin entrenamiento real; esta minisuite no ejecuta PHL.
- KwanData y KwanDocs reciben sólo envelopes hasta que sus conectores ejecuten y devuelvan recibos.
- La enumeración nativa completa de historiales de cada host sigue dependiendo de adaptadores autenticados de Codex, Cline, Cowork, OpenCode u otros.
