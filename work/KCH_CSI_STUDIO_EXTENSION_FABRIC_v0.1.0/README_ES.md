# KCH 0.11 — candidato integral pre-2G, overlay v0.3.0

Este árbol construye un sucesor candidato de la macrorelease canónica KCH 0.11. La base congelada no se reescribe: el Super‑MCP la compone con CSI Studio, gobernanza integral, SCO, MIS, PHL autorizado, RGG, KwanPrompts, KwanData, persistencia, permisos, recuperación y medios.

## Principio constitucional

`ABSOLUTAMENTE_TODO_ES_ESTRATÉGICO_SIN_EXCEPCIÓN`.

Cada módulo, función, herramienta, operador, menú y accionable debe superar dos gates simultáneos: completitud local verificable e integración sistémica explícita. La cobertura de superficie se audita automáticamente; no se confunde esa cobertura con madurez productiva.

## Instalación portable en Windows

La ruta profunda fue identificada como un fallo real de la primera campaña de dogfooding. La revisión R9 introduce esas defensas y corrige los fallos preservados de creación recursiva del runtime en R6, concatenación del wrapper de check en R7 y dependencia IANA `tzdata` ausente en R8:

1. `EXTRACT_AND_INSTALL_KCH_R9.cmd`, situado junto al ZIP, extrae a una raíz nueva y corta bajo `%LOCALAPPDATA%\KCH\packages` y rechaza rutas inseguras o sobrescrituras.
2. `INSTALL_KCH.cmd` crea el entorno virtual persistente bajo `%LOCALAPPDATA%\KCH\runtimes\<hash>`, no dentro de una ruta de paquete potencialmente profunda.

El bootstrap instala exclusivamente desde el `wheelhouse` incluido, genera `runtime_paths.cmd` y produce adaptadores con rutas absolutas. No modifica automáticamente VS Code, Cline, OpenCode ni Codex.

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
