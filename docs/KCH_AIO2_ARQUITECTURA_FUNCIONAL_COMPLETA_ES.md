# KCH AIO2 — arquitectura funcional completa, defectos que corrige y fronteras reales

## 1. Definición operativa

KwanCode Harness (KCH) es un superarnés reflexivo: gobierna una tarea y también las superficies —modelo, herramientas, hooks, skills, runtimes, almacenamiento y protocolos— usadas para ejecutarla. No sustituye al modelo fundacional ni pretende convertir una inferencia probabilística en una máquina infalible. Su función es hacer que una capacidad estadística potente opere dentro de una arquitectura persistente, verificable, recuperable y explícita respecto de su autoridad.

AIO2 reúne la línea estable R21/R33, KCH Studio 0.3.16, la proyección nativa para Codex, la distribución completa para Cline, el Super MCP federado, custodia recuperable, MIS 0.3.1, los runtimes μ/Transmuter/SCPP y una capa de gobierno adaptable. R34 queda fuera de esta jurisdicción y no fue incorporada ni modificada.

La separación constitucional central es:

```text
capability != support != permission != authority != execution != training
```

- `capability`: el sistema dispone de una función.
- `support`: el host puede materializarla realmente.
- `permission`: el usuario o la plataforma permiten intentarla.
- `authority`: existe base contractual y epistemológica para que gobierne una decisión.
- `execution`: la acción ocurrió y alcanzó un estado terminal verificable.
- `training`: el resultado fue admitido en un proceso de aprendizaje posterior.

Confundir dos de estos ejes es una fuente recurrente de falsas declaraciones de despliegue, aprendizaje o seguridad.

## 2. El defecto recurrente sobre el que opera KCH

Los LLM y los arneses agentic convencionales son muy eficaces para resolver el siguiente paso local. Sin gobierno exterior, esa fortaleza no garantiza coherencia de misión a escala de horas, sesiones, procesos o proyectos. El defecto no es una única “alucinación”; es una familia de discontinuidades sistémicas:

1. **Optimización local frente a misión global.** Una respuesta plausible puede desviar el objetivo de largo plazo, especialmente después de muchas bifurcaciones.
2. **Sesgo de recencia y compacción.** Los últimos turnos dominan y una síntesis corta puede amputar decisiones antiguas todavía gobernantes.
3. **Lectura aparente.** Búsquedas o fragmentos se presentan como lectura completa, aunque no hubo transporte hasta EOF ni verificación de la frontera no leída.
4. **Procesos abandonados.** Un comando, carga, campaña o subida se inicia, pero el agente no reconcilia proceso, log, artefactos y estado terminal hasta que el usuario vuelve a reclamar.
5. **Capacidad confundida con despliegue.** Que exista código, una skill o un MCP se interpreta como si estuviera activado por el host y operando en cada tarea.
6. **Permiso confundido con autoridad.** Una herramienta callable o una autorización genérica termina gobernando decisiones fuera de su jurisdicción.
7. **Historia reescrita por el último éxito.** Un PASS posterior borra el valor causal de un FAIL previo, una abstención o un `NOT_ESTIMABLE`.
8. **Rigidez mal calibrada.** El sistema oscila entre informalidad peligrosa y ceremonialismo paralizante; aplica el mismo rigor a un brainstorming reversible y a una mutación productiva.
9. **Fragmentación por host.** Codex, Cline, Cowork u otro cliente reciben adaptaciones inconexas y dejan de compartir estado, contratos y semántica.
10. **Salida archivística.** La explicación se convierte en inventario de comandos, rutas y hashes sin responder qué cambió, qué significa y qué queda pendiente.

KCH transforma estos fallos repetidos en controles ejecutables: continuidad objetiva, lectura completa tipada, supervisión terminal, contratos de autoridad, evidencia append-only, rollback, perfiles de rigor, adapters host-specific y cierre sustantivo.

## 3. Capas de la arquitectura

### 3.1. Constitución y precedencia

La constitución fija propósito, jurisdicciones, límites negativos y orden de instrucciones. Dentro de su ámbito aplica `HARNESS > AGENTS > RULES`; las restricciones externas de la plataforma conservan precedencia. La constitución no decide resultados científicos: regula cómo pueden ser afirmados, ejecutados, promovidos o revertidos.

### 3.2. Proyección nativa

KCH prioriza la integración más directa que soporte cada host: instrucciones nativas, skills precisas, hooks de lifecycle, reglas de ejecución, herramientas locales y plugin. MCP queda para capacidades externas o una superficie común realmente necesaria. En Codex, AIO2 instala una única proyección coherente con `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PreCompact` y `SessionEnd`. En Cline proyecta ocho eventos equivalentes y conserva configuración previa mediante instalación idempotente y rollback.

### 3.3. Runtime y Super MCP

El Super MCP no es el soberano de KCH; es su plano federado de interoperabilidad. El entrypoint observado `kch-super-mcp-studio` expone 294 herramientas: 154 declaradas de sólo lectura y 140 con potencial de mutación gobernada. El catálogo completo se encuentra en `docs/KCH_AIO2_CATALOGO_COMPLETO_294_HERRAMIENTAS_ES.md`; la forma JSON, con esquemas y anotaciones, está en `benchmarks/KCH_AIO2_HOST_GATES/TOOL_CATALOG_0.3.16.json`.

Codex usa una entrada escalonada: preflight mínimo, bootstrap gobernado y despacho al catálogo completo sólo cuando una llamada lo requiere. Cline puede consumir directamente la superficie federada. Esta diferencia reduce el coste de arranque sin amputar el runtime.

### 3.4. KCH Studio 0.3.16

Studio es la superficie operacional y visual del sistema. Integra estado, gobierno, workbench, evidencia, construcción CSI, recursos, configuración, adaptadores y llamadas MCP. Su interfaz no es autoridad: presenta y acciona contratos del runtime. Incluye workbench estructurado, gobierno de artefactos, portabilidad, proyección de configuraciones, recibos y controles de consentimiento por acción y sesión.

### 3.5. Persistencia y custodia

KCH separa evidencia cruda, información normalizada, estado operativo y memoria de aprendizaje. Los artefactos históricos no se reescriben. Una corrección produce un sucesor enlazado. La persistencia puede abarcar chats, archivos, clipboard, notas, datasets y transcripciones; su existencia no autoriza por sí sola a reinyectar todo en el contexto.

## 4. Las veinte skills de AIO2

1. **`kch-native-governance`**: gobierno general de tareas materiales, límites de autoridad y cierre sustantivo.
2. **`kch-objective-continuity`**: preserva misión, procesos vivos y próximos estados terminales frente a interrupciones y compacción.
3. **`kch-runtime-supervisor`**: supervisa comandos, procesos, campañas, builds, subidas y monitores hasta cierre verificable.
4. **`kch-instruction-governance`**: resuelve ambigüedad, conflicto y versionado de instrucciones sin inventar consentimiento.
5. **`kch-contractual-rigor-fader`**: ajusta rigor por campo y riesgo; mantiene pisos no relajables.
6. **`kch-constitutional-locks`**: protege recursos elegidos y exige autorización exacta de un uso para mutaciones bloqueadas.
7. **`kch-csi-construct`**: construye sucesores versionados de KCH, skills, herramientas, adapters y contratos sin mutar el estable.
8. **`kch-evidence-custody`**: lectura completa, procedencia, resultados adversos, integridad y cierre de cadenas de evidencia.
9. **`kch-data-persistence`**: estructura y preserva información heterogénea con trazabilidad bidireccional.
10. **`kch-virtuous-handoff`**: transfiere proyectos a sesiones frescas mediante lectura íntegra, estructura sistémica y recibo verificable.
11. **`kch-tokenmaster`**: dimensiona razonamiento, tokens, modelos y orquestación; evita fan-out y coste sin valor decisional.
12. **`kch-kwandisk`**: clasifica presión de almacenamiento, duplicados, regenerables y copias local/nube bajo recuperación segura.
13. **`kch-permissions-automation`**: gobierna acciones proactivas, cuentas, automatizaciones y leases finitos de permiso.
14. **`kch-sco-orchestration`**: coordina SuperChats Orchestrators y continuidad multiagente entre diferentes superficies.
15. **`kch-extension-curation`**: descubre y valida plugins, skills, paquetes, adapters y MCP evitando duplicación o autoridad implícita.
16. **`kch-libresource-flush`**: preserva independencia de proveedor, formato y recurso; adjudica compatibilidad y plug-and-play de forma proporcional.
17. **`kch-mis-governance`**: integra Matemática Informacional Semántica 0.3.1 sin degradarla ni inflar su autoridad empírica.
18. **`kch-mu-transmuter-scpp`**: compone μ_EQ, μ_QE, Transformer/Transmuter, octeto y SCPP manteniendo sus soberanías y límites experimentales.
19. **`kch-learning-germination`**: deriva candidatos futuros desde trabajo y fallos verificados, sin promoverlos automáticamente ni reescribir el pasado.
20. **`kch-chatgpt-projection`**: lleva KCH a la capa más nativa realmente soportada por Codex y ChatGPT, declarando brechas del host.

## 5. Operadores y subsistemas principales

### Contractual Rigor Fader

El fader admite perfiles `exploratory`, `balanced`, `strict`, `constitutional` y `adaptive`. Modula, entre otros, formalidad de respuesta, ceremonia documental, libertad de conjetura, exigencia experimental y controles de producción. Nunca puede rebajar estos cuatro pisos: verdad de evidencia, restricciones externas, permiso/autoridad y llaves constitucionales. Relajar formalidad no habilita overclaiming; elevar rigor no autoriza paralizar tareas reversibles.

### KwanDisk

KwanDisk aplica la política cloud-first/local-minimal: observa, clasifica y recomienda; una eliminación material exige copia verificada y objetivo exacto. La versión actual es operativa como herramienta gobernada. Todavía no se afirma que sea un daemon universal activo en cada host ni que pueda borrar automáticamente sin autorización.

### TokenMaster

TokenMaster planifica coste y profundidad, selecciona la mínima configuración suficiente y estructura hasta tres capas de cómputo. La versión actual gobierna decisiones dentro de las tareas KCH; no controla mágicamente el consumo interno de todos los proveedores.

### Virtuous Handoff y continuidad informacional

El traspaso virtuoso no es un resumen. Lee las fuentes declaradas hasta su frontera terminal, reconstruye objetivo, cronología, fases, nodos, contratos, operadores factuales/contrafactuales, artefactos y pendientes, y exige un recibo de destino. Una truncación nativa conmuta a artefacto exacto o segmentación reconciliable; si los bytes no están disponibles, falla sólo el claim de completitud afectado.

### MIS 0.3.1

MIS aporta estados cualitativos tipados, cálculo bayesiano y aprendizaje prospectivo. AIO2 incluye su fuente y evidencia necesaria dentro del árbol vendorizado; el preflight deja de depender de una ruta implícita de la máquina. Esto habilita el runtime, no prueba superioridad general ni concede autoridad ejecutiva.

### μ_EQ, μ_QE, Transmuter, octeto y SCPP

El stack conserva memoria temporal y representaciones conjugadas sin promediarlas. μ_EQ aporta persistencia e histéresis en jurisdicciones temporales; μ_QE trabaja sobre información cosignificativa no parcializable y no debe evaluarse como un competidor destinado a “ganar” el mismo objetivo. Transmuter ofrece procesamiento estructural alternativo; el octeto combina residuos cosignificantes; SCPP bloquea transiciones conformacionalmente inadmisibles antes de deliberar. Su presencia en AIO2 es una integración gobernada; los beneficios end-to-end completos siguen sujetos a validación experimental prospectiva.

### OBL/PHL y aprendizaje hacia adelante

PHL está autorizado arquitectónicamente, pero no entrenado ni ejecutado con feedback real. El aprendizaje admisible crea sucesores futuros; nunca corrige retrospectivamente una decisión congelada. OBL/PHL distingue observación, outcome, adjudicación y promoción.

### Llaves constitucionales

Las llaves son opt-in. Protegen archivos, rutas u operaciones seleccionadas y no pueden ser anuladas por un consentimiento genérico. Una autorización exacta habilita un intento, no una política permanente. Toda propuesta, bloqueo, autorización, consumo y deriva queda registrada.

### Voz, micrófono y transcripción

Studio contiene superficies para audio y transcripción. El micrófono permanece apagado por defecto; el modo de escucha latente requiere activación explícita, visible, revocable y acotada. No se afirma todavía un entrenamiento personal de Whisper desplegado ni una escucha universal en segundo plano.

## 6. Codex y Cline: estado presente

- **Codex**: plugin AIO2 instalado en la fuente servida, dos servidores de entrada gobernada, MIS disponible y preflight real callable. La caché de la aplicación debe recargarse mediante reinicio y tarea fresca antes de afirmar observación nativa completa de AIO2.
- **Cline**: paquete completo con instalador, regla, ocho hooks, Super MCP, conservación de configuración previa, reinstalación idempotente y rollback. Pasó la prueba end-to-end aislada; aún falta la instalación manual del usuario en su VS Code real como evidencia independiente del host.

## 7. Qué demuestra la metrología de integridad

La metrología byte a byte comprueba que el conjunto material producido coincide con su manifiesto: cada archivo esperado existe, conserva tamaño y SHA-256, no aparecen extras silenciosos y el ZIP puede leerse por completo sin error CRC. También comprueba que una reinstalación no duplica proyecciones y que el rollback restaura el estado previo ensayado.

Esto demuestra integridad de transporte, empaquetado y reconstrucción dentro de la jurisdicción probada. No demuestra por sí solo utilidad científica, reducción longitudinal de errores, seguridad industrial ni superioridad sobre otros agentes. Es una condición necesaria, no suficiente.

## 8. Fronteras explícitas

AIO2 no afirma:

- infalibilidad del LLM;
- superioridad universal frente a otros arneses;
- despliegue en hosts todavía no construidos;
- entrenamiento real de PHL o Whisper personalizado;
- autoridad física, clínica, jurídica, financiera o industrial;
- validación independiente multiusuario;
- licencia OSI ya elegida;
- aceptación o preparación formal consumada para JOSS.

La posición correcta es más fuerte y más sobria: ya existe una distribución pública reproducible, operacionalmente verificada en Codex y Cline dentro de fronteras concretas, y diseñada para acumular evidencia sin corromper su historia.