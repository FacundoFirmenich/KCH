# Roadmap multiplataforma KCH y SuperAgentic Assistant 3G — Q4 2026

## Propósito

KCH no debe multiplicar forks inconexos para cada cliente. La estrategia es mantener un núcleo constitucional y semántico común, más adapters delgados y verificables. Codex, Cline, CLI, OpenCode, Cowork, Claude Code, Copilot Agents, VS Code y Antigravity deben interpretar los mismos contratos de misión, evidencia, consentimiento, autoridad, estado y recuperación.

Este documento es una hoja de ruta de desarrollo para el último trimestre de 2026. No afirma que las superficies futuras ya estén construidas ni garantiza fechas externas que dependan de APIs o permisos de terceros.

## Estado de partida

AIO2 cierra las dos primeras distribuciones completas:

- Codex: proyección nativa, lifecycle, skills, preflight/bootstrap y despacho federado.
- Cline: paquete VS Code autónomo, ocho hooks, regla, Super MCP, instalación idempotente y rollback.

Ambas comparten R21/R33, Studio 0.3.16, MIS, fader de rigor, custodia, KwanDisk, TokenMaster, handoff y contratos de autoridad. R34 permanece fuera de esta línea.

## Idioma común

La interoperabilidad no dependerá de copiar prompts. Cada host proyectará un mismo Statistical/Constitutional Intermediate Representation con, al menos:

```text
Mission
Jurisdiction
InstructionGraph
ManeuverNode
EvidenceClaim
AuthorityConformation
PermissionLease
ExecutionReceipt
Outcome
FutureOnlyUpdate
RecoveryPoint
```

Cada objeto tendrá identidad estable, versión, procedencia, tiempo, host de origen y reglas de traducción. La capa visible podrá ser Markdown, JSON, comandos CLI, UI o voz; la semántica gobernante será la misma.

El intercambio mínimo seguirá esta cadena:

```text
intención humana
→ contrato normalizado
→ adjudicación local
→ plan host-specific
→ ejecución supervisada
→ recibo común
→ outcome separado
→ aprendizaje future-only
```

## Ola 1 — base portable y desarrolladores

### CLI

Objetivo: una distribución sin interfaz gráfica capaz de instalar, inspeccionar, exportar, verificar, hacer preflight, iniciar handoffs y operar el Super MCP. Debe funcionar en Windows y Linux, con configuración explícita y salida machine-readable.

Gate: instalación limpia, help completo, cero rutas personales embebidas, rollback, compatibilidad de recibos Codex/Cline y documentación de shell.

### VS Code genérico

Objetivo: separar el adapter base de VS Code de la lógica específica de Cline. Debe ofrecer MCP, tareas, panel de estado, comandos y visualización de nodos sin conceder autoridad a la UI.

Gate: workspace con y sin Cline, configuración reversible, ausencia de colisión con settings existentes y paridad semántica de eventos.

### OpenCode y Claude Code

Objetivo: adapters nativos para sus reglas, hooks y herramientas, recurriendo a MCP sólo cuando el host no ofrezca una capa más directa.

Gate: misma misión transferida entre Codex, Cline y cada host; recibos equivalentes; ninguna degradación silenciosa de permisos o locks.

## Ola 2 — colaboración y agentes de plataforma

### Cowork

Objetivo: continuidad de proyectos, colaboración humana y transferencia de tareas conservando autoridad por jurisdicción y visibilidad de nodos de maniobra.

### Copilot Agents

Objetivo: proyectar KCH sobre agentes de repositorio, issues, pull requests y automatizaciones sin confundir permisos del repositorio con autoridad para promover cambios.

### Antigravity

Objetivo: adapter experimental sujeto a las capacidades reales del host. Ningún claim de compatibilidad se emitirá antes de disponer de API, lifecycle y pruebas reproducibles.

Gate común: corpus de tareas pareadas, export/import exacto, recuperación tras interrupción, preservación de FAIL/ABSTAIN y medición de coste y latencia.

## Ola 3 — SuperAgentic Assistant de tercera generación

La tercera generación propuesta se sitúa en la línea de los asistentes tipo Jarvis que operan de forma persistente desde un VPS o PC dedicado, pero busca superar sus límites arquitectónicos en cinco frentes. La palabra “superar” expresa objetivo de diseño; todavía requiere comparación experimental contra OpenClaw, harness agents y alternativas contemporáneas.

### 1. Fiabilidad temporal

El asistente no vive sólo en una ventana de contexto. Mantiene un grafo externo de misión, estados, compromisos, procesos vivos, artefactos y recovery points. Una compacción o cambio de modelo no redefine la tarea.

### 2. Coherencia de muy largo plazo

La memoria distingue presente, obsoleto, recurrente, todavía no readmitido y residuo contrafactual. Recuperar una pieza no le concede autoridad. Los cambios producen sucesores, no reescrituras retrospectivas.

### 3. Protocolarización universal multiagéntica

Todos los agentes intercambian los mismos objetos semánticos. Codex puede iniciar una misión, Cline continuar el código y Cowork coordinar una revisión sin traducciones ad hoc ni pérdida de las fronteras de permiso.

### 4. Operación persistente sobre VPS o PC dedicado

El sistema podrá supervisar procesos, backups, colas y automatizaciones con leases finitos, health checks y fail-closed. La ejecución remota estará separada de la autorización humana y del aprendizaje. KwanDisk mantendrá el principio cloud-first/local-minimal; los secretos permanecerán en vaults externos y nunca en el ledger.

### 5. Interacción multimodal gobernada

Texto, voz, micrófono opcional, archivos, navegador, interfaces visuales y notificaciones compartirán misión y contratos. La escucha latente será opt-in, visible y revocable. Ninguna modalidad tendrá privilegio constitucional por sí misma.

## Componentes 3G previstos

- Mission Graph persistente y temporal.
- Universal Handoff Bus entre hosts.
- Authority Conformation de seis ejes y transiciones tipadas.
- Runtime Supervisor distribuido.
- KwanDisk multiinstancia local/nube.
- TokenMaster multinivel y selección de modelos.
- SCO para orquestación multiagente.
- Studio/KwanTau como interfaz amigable no soberana.
- Adaptadores LIBRESOURCE para sustituir modelos, proveedores y formatos.
- Construcción CONSTRUCT recuperable y promoción pareada contra el estable.
- OBL/PHL future-only con feedback humano real.

## Secuencia de despliegue Q4 2026

1. Congelar AIO2 público y completar la observación Codex post-reinicio y la instalación Cline del usuario.
2. Cerrar licencia y política de contribución pública.
3. Extraer el adapter VS Code común y publicar CLI.
4. Incorporar OpenCode y Claude Code mediante pruebas pareadas.
5. Abrir Cowork, Copilot Agents y Antigravity sólo cuando sus superficies reales estén documentadas.
6. Ejecutar el primer handoff multihost end-to-end con la misma misión y recibos reconciliados.
7. Desplegar un prototipo 3G en VPS/PC dedicado sin autoridad irreversible.
8. Medir fiabilidad longitudinal, coste, latencia, recovery y reducción de fallos frente a baseline sin KCH y alternativas externas.

## Gates para declarar tercera generación

No bastará una demo. La denominación 3G requerirá:

- continuidad demostrada durante tareas largas y múltiples hosts;
- recuperación reproducible tras crash, compacción y cambio de cliente;
- ausencia de promoción automática;
- permisos y autoridad preservados entre adapters;
- proceso vivo supervisado hasta terminal;
- tareas pareadas con y sin KCH;
- reducción estadísticamente defendible de fallos relevantes;
- costes y latencias publicados;
- red-team de secretos, locks y acciones irreversibles;
- documentación de instalación y desinstalación por un tercero.

## Relación con JOSS

El roadmap es más amplio que el primer paper. Una eventual presentación a JOSS debe congelar un objeto científico acotado: probablemente el núcleo de gobierno portable, su representación intermedia, la reproducción Codex/Cline y el benchmark de continuidad. Las capacidades futuras se citarán como roadmap, no como resultados.