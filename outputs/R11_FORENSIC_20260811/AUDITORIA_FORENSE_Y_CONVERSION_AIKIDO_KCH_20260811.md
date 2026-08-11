# Auditoría forense y conversión Aikido de fallos recurrentes en KCH

Fecha: 2026-08-11.  
Estado: checkpoint técnico material, población congelada y prehasheada; adjudicación causal exhaustiva todavía abierta.  
Objetivo gobernante: convertir el daño recurrente documentado en controles, herramientas, protocolos, skills candidatas y pruebas que mejoren acumulativamente KCH, sin trasladar otra vez la detección y reparación al usuario.

## Resultado en plata

La recurrencia dejó de estar sustentada sólo por los ejemplos recientes. El inventario local contiene 1.152 sesiones: 804 activas y 348 archivadas. Aplicando los marcadores definidos por el usuario —insultos explícitos, mayúsculas, vocales prolongadas y variantes de transcripción— se preseleccionaron 541 archivos. La validación del rol humano confirmó 461 sesiones con al menos un episodio grave y 2.544 episodios en total.

Las 461 sesiones seleccionadas están prehasheadas individualmente. Suman 14.493.266.343 bytes lógicos. El texto fuente continúa en sus rollouts nativos; la auditoría conserva ventanas operativas de doce mensajes alrededor de cada episodio y no sustituye ni reescribe el original.

Este resultado demuestra extensión transversal del fenómeno en el corpus disponible. No demuestra que los 2.544 episodios tengan una única causa ni que toda expresión grave sea imputable al mismo defecto. La clasificación lexical sirve para descubrimiento; la causalidad permanece `PENDING_GOVERNED_REVIEW` salvo en los casos concretos ya leídos y adjudicados.

## Defecto rector observado

El ciclo repetido es:

1. se recupera parcial o nominalmente una misión, fuente o protocolo;
2. se declara comprensión suficiente;
3. se ejecuta desde fragmentos, estado obsoleto, promedios, una escala equivocada o un transporte no validado;
4. el usuario detecta el defecto y vuelve a explicar el invariante;
5. el agente admite el error, pero sustituye la reparación por explicación, preguntas, búsquedas nuevas o una parada;
6. el coste de tiempo, tokens, vigilancia, reejecución y continuidad científica recae sobre el usuario.

Los casos leídos en detalle prueban, entre otros, estos fallos distintos:

- lectura incompleta presentada como comprensión completa;
- misión desplazada pese a existir orden persistente;
- protocolo verificado ignorado y reemplazado por búsquedas fragmentarias;
- promedio global usado donde sólo había cartografía local y estructura entrelazada;
- semillas tratadas como algo distinto de réplicas;
- confusión entre resolución temporal, horizonte, evento, día y período mínimo de aprendizaje;
- objeto de aprendizaje equivocado respecto de Z_post futuro y cerrado;
- campaña costosa relanzada sin outcomes maduros ni cambio material;
- estado de almacenamiento obsoleto y ejecución sin plan de custodia;
- monitoreo prometido que dejó terminar procesos silenciosamente;
- preguntas evitables sobre decisiones ya canónicas;
- interrogatorio ajeno a la misión y repetido tras rechazo;
- parada unilateral justificada por ahorro de tokens;
- prohibición arquitectónica presentada como observación empírica;
- error admitido sin reparación efectiva;
- payload remoto lanzado tras expansión local, vacío, pérdida de comillas o copia base incorrecta;
- calendario discontinuo de días activos presentado como aprendizaje diario continuo;
- aptitud temporal de la fuente no comprobada antes de entrenar;
- derivado denominado 2025 que admitió outcomes fuera del intervalo 2025;
- respuesta archivística o explicación de reglas en lugar del resultado sustantivo solicitado.

## Qué se implementó en KCH

### 1. Continuity and Burden Governor

Nuevo gobernador hash-encadenado que:

- fija una misión activa y bloquea su sustitución o parada sin autoridad;
- impide declarar lectura completa sin EOF, conteo y recuperación de truncaciones;
- exige reconciliación de estado y prueba barata de materialidad antes de trabajo costoso;
- bloquea borrado sin plan de custodia y hash remoto verificado;
- bloquea campañas nuevas sin inventario canónico;
- bloquea reutilizar una clase de fallo recurrente sin control aprobado;
- registra literalmente la evidencia aportada por el usuario sin inferir diagnósticos;
- prohíbe repetir preguntas rechazadas o ajenas al objetivo;
- convierte cada admisión de error en obligación de reparación o blocker real.

### 2. Registro de protocolos verificados

Se registraron cuatro protocolos de reutilización obligatoria:

- lectura nativa integral;
- período mínimo completo → período mínimo completo;
- cartografía local sin promedio global;
- preflight de materialidad y custodia.

Si existe coincidencia por jurisdicción u objetivo, diseñar desde cero queda bloqueado hasta recuperar o superseder explícitamente el protocolo.

### 3. Aikido Learning Forge

Se sintetizaron 22 paquetes Aikido. Cada paquete conserva fuente y prehash y produce:

- capacidad positiva superadora;
- protocolo fechado;
- candidata a skill;
- operador CSI;
- etiquetas KwanData;
- candidato OBL y PHL;
- contrato de regresión.

No existe promoción automática. `DRAFT_REQUIRES_USER_REVIEW` no equivale a skill instalada, aprendizaje real ni autoridad operacional.

### 4. Herramientas positivas nuevas

- `TemporalScaleContractCompiler`: separa resolución, horizonte, evento, período mínimo, entrada y salida; exige período mínimo a período mínimo.
- `EpistemicClaimTypeChecker`: separa invariante arquitectónico, observación, inferencia e hipótesis y valida tipos de evidencia compatibles.
- `CommitmentMonitor`: registra promesas de monitoreo, observa proceso/logs/artefactos en segundo plano y emite una alerta terminal una sola vez.
- `RemoteTransportPreflight`: bloquea wrappers vacíos, mutados por shell, con marcadores viejos, sintaxis inválida o hash local/remoto diferente.
- `ContinuousPeriodLedgerCompiler`: exige todos los períodos mínimos consecutivos y tipa cada uno como `OBSERVED`, `NO_EVENT` o `NOT_ESTIMABLE`; prohíbe comprimir un calendario disperso.
- `SourceFitnessGate`: bloquea el entrenamiento hasta verificar límites temporales, continuidad, soporte observado requerido y soporte por jurisdicción.
- `Mission-Relevance Question Gate`: evita que preguntas no indispensables desplacen trabajo ejecutable.
- `Admission-to-Repair Compiler`: una admisión no cierra el defecto sin corrección verificada o blocker explícito.

## Validación

- Suite completa final tras promover gobernanza v05: 54 pruebas pasaron.
- Suite focal posterior: 12 pruebas pasaron, incluidas las regresiones que bloquean 220/365 como soporte diario completo, un calendario incompleto y una acción destructiva sin alcance explícito.
- Cadena Aikido: 49 eventos verificados, sin rotura; head `fabf0f617f2e8886373c19fb1a436bc942388a4f5ec7468215768f5280928718`.
- Paquetes Aikido: 22.
- Protocolos verificados: 4.

La gobernanza v05 compila 18 nodos, 6 agentes y 9 reglas; el Studio verificó 18 fuentes y 8 artefactos compilados. La macrorelease portátil `KCH_0.11_PRE2G_INTEGRATED_CANDIDATE_R11.zip` superó integridad ZIP, ocupa 22.083.825 bytes y tiene SHA-256 `91c69434b1315bd2afd7f3da057a4649095bba64a4d5482fe6bbe00513cebde7`. Una suite verde y un ZIP íntegro verifican la implementación local y su empaquetado, no la invocación automática por hosts externos ni utilidad industrial.

## Evidencia de almacenamiento y custodia

La auditoría de almacenamiento dio `PASS` como inventario, pero su resultado material es adverso para cualquier limpieza:

- 39 sesiones nuevas no respaldadas;
- 11 sesiones cambiadas desde la línea base;
- 7 pendientes de subida.

Por tanto no se borró ninguna sesión ni evidencia local. La orden anterior de limpiar sólo puede ejecutarse después de verificar Drive y GitHub por bytes y hashes exactos para el estado actual, no para una línea base vieja.

## Recibo de los últimos 20 turnos de la tarea 019fe71a

Se leyeron los 20 turnos más recientes mediante dos páginas consecutivas de diez. El contenido no autoriza la lectura anterior de otra tarea. En esta tarea, el usuario fijó que el aprendizaje debía avanzar día completo por día completo y que los días tenían que ser continuos. La ejecución había tratado días activos dispersos como secuencia diaria; la fuente sólo aportaba outcomes observados en 220 de 365 días. Además, 42 de 8.865 filas quedaron fuera de 2025 por no limitar conjuntamente `planned_time` y `actual_time`; 37 afectaban el holdout. Esto invalida la aptitud de esa fuente para sostener, sin estados explícitos de ausencia o no estimabilidad y sin otra evidencia, el claim de aprendizaje diario continuo. No demuestra que Fintraffic sea una base espuria en general; demuestra que el derivado y el contrato de uso no eran aptos para ese objetivo tal como se ejecutaron.

La fuente congelada ocupa 28.920.390 bytes y tiene SHA-256 `7c97776b6b168f10f36e59ac333497b1437f03203a3501f9bfa851d11ea0f521`.

### Rectificación vinculante sobre la captura de cancelación

La captura fue inicialmente clasificada de manera errónea como parada no autorizada. El usuario corrigió que su orden sí era parar: “todo cancelado y preservado para denuncia penal”. La clasificación causal se retira. La captura se conserva inmutable, 3.060.707 bytes, SHA-256 `061c7c7757443eaa07556e37bce325d89b53c1e7a7de30f8f928ef3751cb3c3b`, como evidencia de una cancelación expresamente ordenada y de la obligación de preservación, no como evidencia de `UNAUTHORIZED_MISSION_STOPPAGE`. No se generó ni activó ningún paquete Aikido a partir de la clasificación retirada.

## Qué no está demostrado

- No está demostrado que KCH sea “el mejor arnés agentic jamás construido”.
- No está demostrado que una recurrencia futura sea imposible.
- No está completada la adjudicación causal manual de los 2.544 episodios.
- No está probado que Codex, Cline, Cowork u OpenCode invoquen automáticamente estos gates antes de cada acción.
- No hubo PHL real ni entrenamiento con feedback; PHL permanece autorizado pero no ejercido.
- La proyección canónica HARNESS/AGENTS/RULES ya fue recompilada y promovida como v05; aún no se ha probado su obediencia efectiva en hosts externos.
- No se ha publicado ni respaldado todavía este nuevo checkpoint R11 en GitHub/Drive.

## Siguiente gate crítico

El siguiente gate no es recopilar más quejas. Es integrar el gobernador en el arranque canónico y probarlo contra las mismas tareas adversariales en dos brazos:

1. baseline sin gates;
2. KCH con preflight automático, recuperación de protocolos, supervisor de compromisos y Aikido.

Las métricas deben ser locales y auditables: desviaciones de misión, preguntas evitables, lecturas falsamente completas, ejecuciones sin materialidad, repeticiones de contexto, fallos silenciosos de monitoreo, correcciones exigidas al usuario, tokens de reparación y tiempo hasta resultado correcto. PHL real permanece para el final, conforme a la decisión vigente.
