# CHECKPOINT 10 — KCH Proactive Activation Gate v0.1.0

Fecha de cierre técnico: 2026-08-10 (Europe/Madrid)

## Posición respecto del checkpoint anterior

KCH queda **mejor posicionado y cualitativamente distinto**. En el checkpoint 09 se había localizado que KCH 0.11 era un MCP pasivo: el modelo podía elegir herramientas, pero KCH no observaba el prompt, no disparaba una consulta propia y no conservaba una política de consentimiento de sesión. Este gate añade un camino efectivo y probado en Codex:

`UserPromptSubmit → regla KCH → bloqueo consultivo → respuesta del usuario → ejecución read-only opcional → reinyección de petición original y evidencia → política confinada a sesión → SessionEnd`.

No se ha reetiquetado KCH 0.11 ni alterado su macrorelease canónica. El nuevo componente es un overlay experimental reversible, versión `v0.1.0`, con versión MCP informativa `0.11.0+activation.gate.1`.

## Contrato vinculante implementado

La consulta admite exactamente cuatro decisiones:

1. **Sí**: autoriza una sola vez la propuesta pendiente actual.
2. **No**: declina una sola vez la propuesta pendiente actual.
3. **Nunca en esta sesión**: suprime futuras coincidencias de la misma regla y herramienta durante esa sesión de host.
4. **Siempre en esta sesión**: ejecuta la propuesta actual y autoejecuta futuras coincidencias de la misma regla y herramienta sólo durante esa sesión.

No existe consentimiento inferido, `AUTO_ALL`, preferencia global ni persistencia intersesión. Una respuesta no reconocida mantiene la propuesta pendiente. `SessionEnd` borra las políticas `Siempre/Nunca`; el historial de auditoría permanece.

## Construcción efectiva

- Catálogo versionado con 7 reglas deterministas, prioridades, exclusiones, TTL, *cooldown* y presupuesto de consultas.
- Allowlist de 10 herramientas KCH exclusivamente *read-only*.
- Ledger SQLite con propuestas, políticas, ejecuciones y cadena de eventos enlazada por SHA-256.
- Consumo atómico previo a la ejecución para impedir replay de una misma autorización.
- Separación explícita entre `EXECUTING`, éxito y `EXECUTION_FAILED`; un fallo nunca queda registrado como ejecución satisfactoria ni instala `Siempre`.
- Minimización del prompt: el texto original se conserva sólo mientras la propuesta está pendiente y se borra al resolver, expirar, omitir o cerrar; el evento conserva su hash.
- Overlay MCP con las 49 herramientas KCH 0.11 más 4 herramientas de activación, total 53.
- Adaptadores Codex reales para `UserPromptSubmit` y `SessionEnd`.
- Configuración de proyecto actualizada para arrancar el overlay y habilitar hooks.

Herramientas nuevas:

- `kch.activation.scan`
- `kch.activation.respond`
- `kch.activation.status`
- `kch.activation.session.close`

## Evidencia y gates

Resultado: **PASS, 11/11 tests**.

La campaña cubrió:

- las cuatro opciones exactas;
- semántica de una sola vez de Sí/No;
- confinamiento de Siempre/Nunca a la misma sesión y regla/herramienta;
- autoejecución posterior bajo Siempre;
- limpieza de políticas en SessionEnd;
- no inferencia de consentimiento inválido;
- bypass explícito de una consulta pendiente cuando llega un prompt nuevo no-respuesta;
- detección de manipulación de la cadena de auditoría;
- fallo de herramienta registrado como FAIL, sin falso éxito ni política Siempre;
- transporte nativo Codex completo: bloqueo, pregunta, respuesta, reinyección de la petición original, ejecución, autoejecución y cierre;
- MCP con 53 nombres únicos, instrucciones consultivas y cero ejecución PHL real.

Resultados adversos preservados y reparados durante el gate:

1. Las conexiones SQLite de lectura finalizaban transacciones pero podían permanecer abiertas hasta el recolector de memoria en Windows. Se introdujo cierre explícito y se repitió el gate.
2. El primer adaptador `SessionEnd` ignoraba una ruta de estado inyectada en prueba y cerraba la ruta productiva fija. Se corrigió para respetar `KCH_ACTIVATION_STATE` y se repitió el gate completo.

## Custodia e invariantes

- ZIP macrorelease KCH 0.11: `a4e08bb2833dffbfe3a3f2036579d1c8e56c20ea67ec94d4685a3618d528ee02` — idéntico.
- Estado PHL/KCH histórico, fuente y réplica desplegada: `d17a982e55203cdce6ffba1a2a2455260bea1df88536ac4456969ae755a07c21` — idéntico.
- Ejecuciones PHL reales en esta campaña: `0`.
- Herramientas mutantes autoejecutables: `0`.
- Manifest overlay: `587fc869105bf14486e0aacb7bafe54a1efd0a136f16af1ebb48a83fa2c8d9a6`.
- Resultado gate: `ed2b5917a736b4d5142f1467c47afb5350138de600109eb44d99457e2a2daa01`.
- Catálogo de reglas: `a8a2cf6069373945fe6330e74c6acf90f1663f158421d0bdd7097d33fa14a181`.
- `.codex/config.toml`: `1334a53a16e313da97d6e914a43c823585831c6d8547147ab56465e64abbc944`.
- `.codex/hooks.json`: `835918ad29e524e5b066b7bcb8367f595b07eaaf64c77dd2d77efdd428d8f98c`.
- ZIP portable overlay: `bf331dd3ffa1b0c1476ad633af1b69e8605b791c0039ca79c702cfdedea58483`; 19 miembros; CRC íntegro.

## Significado técnico, metodológico y epistemológico

El avance real no consiste en que “el modelo quizá llame una herramienta”, sino en que una capa KCH determinista observa un evento de host, formula una consulta explícita, registra la decisión y gobierna su duración. Esto crea por primera vez una política proactiva KCH comprobable en Codex.

El gate no convierte la heurística inicial en un detector semántico universal. Sus reglas son inspeccionables y falsables precisamente porque son léxicas y acotadas. Tampoco demuestra que Siempre sea seguro para acciones mutantes: está técnicamente prohibido fuera de la allowlist read-only. La autorización humana observada es permiso para esa activación; no crea evidencia, soporte científico, autoridad operacional ni validez de claims.

## Techo de claims

Claim máximo vigente:

`LOCAL_CODEX_HOOK_AND_MCP_PROACTIVE_CONSULT_FIRST_GATE_PASS_WITH_READ_ONLY_TARGETS_AND_NO_REAL_PHL_EXECUTION`

No se ha demostrado:

- fiabilidad longitudinal en utilización humana real;
- precisión/recall de activación sobre lenguaje abierto;
- beneficio causal, superioridad o seguridad general;
- adaptadores efectivos para Cline, Cowork, OpenCode u otros hosts;
- autoejecución mutante;
- PHL real ni aprendizaje post hoc a partir de esta sesión.

## Artefactos

- `work/KCH_PROACTIVE_ACTIVATION_GATE_v0.1.0/README.md`
- `outputs/KCH_PROACTIVE_ACTIVATION_GATE_RESULT_v0.1.0.json`
- `outputs/KCH_PROACTIVE_ACTIVATION_GATE_MANIFEST_v0.1.0.json`
- `outputs/KCH_PROACTIVE_ACTIVATION_GATE_v0.1.0.zip`
- `outputs/KCH_PROACTIVE_ACTIVATION_GATE_v0.1.0.sha256`
- `.codex/config.toml`
- `.codex/hooks.json`

## Siguiente acción crítica

La única acción que no puede ejecutar este proceso en nombre del usuario es la confianza del hook. Debe abrirse una tarea nueva o recargarse el proyecto, ejecutar `/hooks`, revisar los dos comandos locales y confiar en su hash. Después debe realizarse el primer uso humano no-PHL con una consulta de estado KCH y las cuatro respuestas. Ese uso es el siguiente gate: validará la ergonomía real, falsos positivos, continuidad de la petición bloqueada y extinción efectiva de Siempre/Nunca al terminar la sesión. No corresponde ampliar aún la autoejecución a mutaciones ni iniciar PHL real.

Soporte normativo técnico consultado: documentación oficial de Codex Hooks, `https://learn.chatgpt.com/docs/hooks` (eventos, configuración, trust por hash, salida `additionalContext`, bloqueo de `UserPromptSubmit` y `SessionEnd`).
