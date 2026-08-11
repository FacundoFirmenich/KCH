# KCH 0.11 — candidato integral pre-2G, overlay v0.3.3

Este árbol construye un sucesor candidato de la macrorelease canónica KCH 0.11. La base congelada no se reescribe: el Super‑MCP la compone con CSI Studio, gobernanza integral, SCO, MIS, PHL autorizado, RGG, KwanPrompts, KwanData, persistencia, permisos, recuperación y medios.

## Principio constitucional

`ABSOLUTAMENTE_TODO_ES_ESTRATÉGICO_SIN_EXCEPCIÓN`.

Cada módulo, función, herramienta, operador, menú y accionable debe superar dos gates simultáneos: completitud local verificable e integración sistémica explícita. La cobertura de superficie se audita automáticamente; no se confunde esa cobertura con madurez productiva.

## Instalación portable en Windows

La ruta profunda fue identificada como un fallo real de la primera campaña de dogfooding. La revisión R9 introduce esas defensas y corrige los fallos preservados de creación recursiva del runtime en R6, concatenación del wrapper de check en R7 y dependencia IANA `tzdata` ausente en R8:

1. `EXTRACT_AND_INSTALL_KCH_R9.cmd`, situado junto al ZIP, extrae a una raíz nueva y corta bajo `%LOCALAPPDATA%\KCH\packages` y rechaza rutas inseguras o sobrescrituras.
2. `INSTALL_KCH.cmd` crea el entorno virtual persistente bajo `%LOCALAPPDATA%\KCH\runtimes\<hash>`, no dentro de una ruta de paquete potencialmente profunda.

El bootstrap instala exclusivamente desde el `wheelhouse` incluido, genera `runtime_paths.cmd` y produce adaptadores con rutas absolutas. No modifica automáticamente VS Code, Cline, OpenCode ni Codex.

### Puerta gobernada para Codex

Codex recibe dos superficies acotadas. `kch-codex-preflight-mcp` anuncia una sola herramienta estrictamente de lectura y puede aprobarse automáticamente sin conceder despacho operativo. `kch-codex-bootstrap-mcp` anuncia cinco herramientas —estado, búsqueda del catálogo completo, preflight canónico, adjudicación de autoridad de respuesta y despacho exacto— y conserva aprobación gobernada. El Super‑MCP completo permanece detrás del despachador y se materializa sólo cuando una llamada real lo necesita. Esto evita exigir todo el catálogo dinámico de descripciones en el handshake de arranque sin amputar capacidades, fusionarlas ni degradar sus gates. VS Code, Cline y OpenCode conservan la superficie directa completa; el adaptador Codex registra además la ruta explícita del Super‑MCP para auditoría y uso manual.

La cadena de lectura completa R17 separa tres hechos que antes podían confundirse. `full_read_file` transporta un archivo; `full_read_batch` genera por máquina el inventario ordenado, los hashes y los spans exactos preregistrados; `full_read_verify_batch` vuelve a leer la fuente y bloquea un recibo alterado incluso si el agente recalculó correctamente su autosellado. Transportar todos los bytes no autoriza por sí solo una afirmación de comprensión semántica: ésta exige que los spans exactos declarados estén presentes y queden localizados.

La activación probada en Codex requiere dos enlaces complementarios: el servidor de preflight de sólo lectura y una instrucción de proyecto `AGENTS.md` que exija llamarlo una vez antes de la primera acción material. Las instrucciones MCP aisladas demostraron transporte pero no disparo automático; el enlace conjunto sí produjo una llamada nativa anterior a la tarea en el prepiloto local. Esta observación sigue siendo de una tarea y no se promociona a garantía universal del host.

La existencia de esta puerta demuestra únicamente transporte MCP acotado cuando el host la admite. No demuestra que Codex invoque automáticamente el preflight, que intercepte todas sus respuestas ni que KCH tenga eficacia causal o validación industrial; esos gates se adjudican por separado.

Después de instalar:

- `CHECK_KCH.cmd`: ejecuta el gate por STDIO, la auditoría de superficie y el replay MIS acotado.
- `LAUNCH_KCH_UI.cmd`: abre la interfaz visual.
- `LAUNCH_SUPER_MCP.cmd`: inicia el Super‑MCP integrado.
- `adapters_runtime/`: contiene las proyecciones reales para cada host.

## Gobierno efectivo

La precedencia interna es `HARNESS > AGENTS > RULES`. El paquete contiene los tres documentos, sus agentes y reglas, el grafo CSI compilado y un lock de hashes. El runtime verifica tanto el grafo como las fuentes y los artefactos compilados antes de arrancar Studio.

Sobre esa jerarquía, el workspace constitucional CSI pertenece al usuario. El modelo puede leer y proponer, pero no promulgar, editar, desactivar ni degradar cajas. Las mutaciones de la superficie completa usan consentimiento por acción y por sesión con exactamente: `YES`, `NO`, `NEVER_THIS_SESSION` y `ALWAYS_THIS_SESSION`. “Siempre” para una acción no autoriza otras acciones.

La política programada directa está activa por defecto y puede orquestar capacidades cuando una regla del usuario lo ordena. PHL mantiene un gate exclusivo: mientras una sesión PHL está activa, las mutaciones ordinarias quedan bloqueadas.

## Superficie y modos

La UI conserva las superficies guiadas y añade **Orquesta completa**, un catálogo buscable de todas las herramientas Python/MCP. Expone propósito, mutabilidad, esquema, argumentos editables y recibo. Toda plantilla mutante carga `NO` por defecto.

- `PLAN`: crea un plan inspeccionable.
- `RUN`: ejecuta un plan gobernado y conserva originales y recibos.
- `CONSTRUCT`: modifica sólo un sucesor versionado, con copia estable previa, validación, promoción para el próximo arranque y rollback.

### Modos de contestación redactada

La pestaña **Modos de respuesta** contiene tres perfiles canónicos y perfiles custom persistentes:

- **Conciso:** objetivo de una pantalla; máximo de dos pantallas o un scroll.
- **Explicativo:** aproximadamente entre dos y cinco scrolls.
- **Extenso:** tanto espacio como requiera la explicación completa.

La jerarquía de resolución es `GLOBAL < WORKSPACE < SCO < TASK < SESSION < MESSAGE`. Sólo se gobierna la prosa redactada del chat: outputs, código, archivos, tablas de resultados y artefactos no consumen ese presupuesto visual ni se recortan. Toda contestación debe explicar el resultado, su significado, la posición real, los límites y la próxima decisión; un registro archivístico no puede sustituirla.

La ficha técnica de ejecución se guarda automáticamente como Markdown separado, con redacción de campos sensibles. No se ofrece ni se pregunta si el usuario desea verla: una única línea final informa su ruta. La medición estricta de pantallas/scrolls necesita métricas del renderer del host; sin ellas KCH entrega el contrato, pero no afirma una garantía física de viewport.

### Autoridad semántica antes de responder

`ResponseAuthorityGovernor` conserva restricciones explícitas de misión, terminología, procedencia, jurisdicción, linaje experimental, marcos rechazados y conducta de respuesta. El evento programado `response.candidate` ejecuta por defecto su preflight directo. El gate bloquea una respuesta estructurada que contradiga esas restricciones, agregue una jurisdicción local sin autoridad, mezcle experimentos, introduzca clasificaciones ajenas a la misión o prometa vigilancia sin un compromiso activo del monitor. Esta capacidad está verificada dentro del runtime; la interposición física sobre cada respuesta depende del adaptador del host y no se presume.

## Preflight único y trabajo/aprendizaje

`kch_preflight` es el único gate canónico de arranque. Se invoca desde `StudioMCP` y verifica conjuntamente gobierno compilado, superficie estratégica completa, blind spots del launcher y estado PHL. Las clases internas no son entrypoints de preflight.

La pestaña **Trabajo y aprendizaje** incorpora la minisuite de archivo, grafo, presupuesto semanal, continuidad y generación automática de protocolos y skills derivadas de evidencia. Conserva fuente cruda y normalizada por separado, redacta secretos antes de persistir y deja cada skill como `STAGED_UNEVALUATED`, nunca instalada ni activada por generación. Véase `docs/TRABAJO_APRENDIZAJE_CONTINUIDAD.md`.

## PHL, OBL y dicción

PHL está autorizado y operativamente integrado; no está entrenado. Sólo el feedback genuino del usuario puede crear material future‑only. Las pruebas de exclusión abren y cierran sesiones efímeras sin feedback y conservan `training_executed=false`. OBL puede recibir entradas explícitas. Las correcciones de dicción se almacenan como candidatos, nunca se promocionan automáticamente.

## Límites vigentes

- La persistencia local de turnos se verifica por hash, pero un `next_cursor=null` externo sólo produce `EOF_ATTESTED_UNVERIFIED`; la completitud exige un conector nativo autenticado aún no implementado.
- MIS ejecuta matemática exacta y estudios prospectivos freeze‑before‑outcome, pero no crea autoridad ni demuestra mejora causal, superioridad predictiva, utilidad humana o escalabilidad abierta.
- La UI y el catálogo prueban accesibilidad técnica, no ergonomía sostenida.
- Micrófono, autenticación, instalaciones de host y escrituras externas requieren acciones y permisos explícitos. Ninguna credencial se empaqueta.
- La siguiente evidencia crítica viene primero de pares Luna con/sin KCH sobre fallos históricos, corpus congelados y gates de condición. Después corresponde instalación limpia y dogfooding controlado; el uso creativo del usuario no será el detector inicial de defectos básicos. PHL con feedback se reserva para el final por decisión del usuario.
