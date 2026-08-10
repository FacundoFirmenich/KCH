# CHECKPOINT 09 — Activación proactiva y function calling en KCH 0.11

## Adjudicación

La observación del usuario es fundamental y parcialmente correcta:

- El usuario no tiene que nombrar manualmente cada herramienta. Un cliente MCP con modelo agente puede descubrirlas y seleccionarlas automáticamente según el prompt y el contexto.
- Sin embargo, el Super-MCP KCH 0.11 no contiene un motor propio que detecte cuándo corresponde utilizar una herramienta, proponga su activación ni consulte proactivamente al usuario.
- La selección eventual del modelo cliente no equivale a activación proactiva gobernada por KCH.

## Evidencia del runtime actual

`mcp_server_base.py` sólo declara `tools` y `resources`, espera líneas en stdin, procesa `initialize`, `tools/list`, `resources/*` y `tools/call`, y responde. No hay scheduler, watcher, trigger engine, notificaciones proactivas, `instructions`, sampling ni elicitation.

La configuración Codex vigente usa `default_tools_approval_mode = "prompt"`. Por tanto, Codex puede decidir que una herramienta es pertinente, pero debe solicitar aprobación antes de invocarla. Eso es aprobación del host, no detección/consulta producida por KCH.

## Cinco funciones que no deben confundirse

1. **Exposición**: el servidor publica una herramienta. Existe.
2. **Selección**: el modelo decide que podría necesitarla. Puede ocurrir hoy, pero no está garantizado por KCH.
3. **Consulta**: se pregunta al usuario si debe lanzarse. Hoy depende del host; KCH no formula esa propuesta.
4. **Autorización**: se emite permiso acotado. KCH sí posee capacidades y gates, pero después de que el cliente haya iniciado la cadena.
5. **Ejecución**: se llama la herramienta o ruta. Nunca ocurre espontáneamente en el runtime actual.

## Decisión vinculante introducida por el usuario

La política por defecto para la futura capa de activación será `CONSULT_FIRST`:

1. KCH detecta una condición de activación.
2. KCH construye una propuesta explicando herramienta, motivo, evidencia, argumentos previstos, utilidad, riesgo, efectos y coste.
3. KCH consulta directamente al usuario.
4. Sólo una aceptación explícita genera una capacidad de ejecución de un solo uso.
5. La ejecución automática sólo se permite cuando exista configuración contraria, explícita, acotada, revocable y auditable.

No se admite un `AUTO_ALL` implícito.

## Arquitectura requerida

### Núcleo KCH independiente del cliente

- Catálogo de reglas de activación con versión y jurisdicción.
- Motor determinista de detección y puntuación.
- Ledger de propuestas, consultas, aceptaciones, rechazos, cancelaciones y expiraciones.
- Deduplicación, cooldown, agrupación y presupuesto de interrupciones.
- Tokens de consentimiento ligados a regla, herramienta, argumentos, objetivo y TTL.
- Separación estricta entre recomendación, autorización y ejecución.

### Modos de política

- `CONSULT_FIRST`: default general.
- `MANUAL_ONLY`: nunca propone ni ejecuta automáticamente.
- `AUTO_PREAUTHORIZED`: sólo para combinación exacta de regla, herramienta, clase de acción, jurisdicción, límites y vigencia previamente autorizada.
- `PROHIBITED`: ni consulta ni ejecuta cuando un gate duro lo impide.

Las decisiones `siempre para esta regla` y `nunca para esta regla` son cambios explícitos de configuración, no inferencias de KCH.

### Adaptadores del host

- En Codex, hooks deterministas de ciclo de vida pueden ejecutar el detector en `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse` y `Stop`.
- Las `instructions` MCP deben explicar al modelo cuándo solicitar el scan y cómo respetar su resultado.
- Elicitation MCP puede permitir que el servidor pida entrada al usuario durante una interacción si el cliente declara esa capacidad; no debe asumirse soporte sin gate real.
- Cline, OpenCode, Cowork y otros clientes necesitan adaptadores equivalentes y gates específicos.

### Activación fuera de turno

Un servidor STDIO que espera stdin no puede despertar por sí solo un cliente cerrado o inactivo. La proactividad entre turnos exige un daemon/event broker persistente, hooks/scheduled tasks del host o transporte remoto con canal de eventos. Debe separarse del primer gate de proactividad dentro del turno.

## Afinación necesaria para evitar un sistema molesto

Cada propuesta debe incluir `trigger_id`, evidencia, confianza, novedad, severidad, coste, riesgo, motivo de oportunidad y fingerprint de deduplicación. Deben existir umbral mínimo, cooldown por regla, límite de consultas por turno/intervalo, agrupación de propuestas relacionadas y supresión explicable. El silencio también debe dejar recibo cuando una regla fue evaluada pero no alcanzó umbral.

## Cambio de posición

KCH queda **diferentemente posicionado**: el Super-MCP 0.11 sigue siendo correcto dentro de su claim de gateway MCP federado y read-only, pero se identifica una carencia arquitectónica crítica para convertirse en sistema proactivo. No es una simple opción de autoaprobación; exige una nueva capa de detección, consulta, consentimiento y adaptadores de host.

## Límites

- No se ha implementado todavía esta capa.
- No está demostrado que Codex, Cline u otros clientes soporten elicitation de igual modo.
- Los hooks de Codex permiten automatización dentro del ciclo del cliente, pero no convierten al Super-MCP en servicio autónomo fuera de turno.
- La macrorelease KCH 0.11 congelada no debe reescribirse; la funcionalidad pertenece a un sucesor versionado y nuevamente sellado.
- PHL real sigue fuera de ejecución.

## Próxima acción crítica

Construir el primer gate de activación proactiva **dentro del turno**: motor de reglas + herramienta de scan de activación (nombre canónico todavía abierto) + propuesta `CONSULT_FIRST` + consentimiento de un solo uso + hook Codex `UserPromptSubmit`, usando inicialmente sólo herramientas read-only y sin PHL real. Después se valida el adaptador Cline y, en una fase separada, la proactividad fuera de turno.
