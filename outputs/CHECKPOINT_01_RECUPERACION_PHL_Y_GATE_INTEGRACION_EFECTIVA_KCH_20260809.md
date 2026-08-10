# Checkpoint 01 — recuperación PHL y gate de integración efectiva KCH

Fecha: 2026-08-09  
Jurisdicción: `KCH_PRE2G_SCIENTIFIC_ARCHITECTURAL_NONCOMMERCIAL`  
Posición: `PHL_INSTRUMENT_VALIDATED_EFFECTIVE_KCH_INTEGRATION_NOT_YET_DEMONSTRATED`

## Resultado sustantivo

La tarea nativa `codex://threads/019fd938-8000-7121-9078-d196bdd15ae4` fue leída íntegramente, paginando hasta `hasMore=false`. La conversación, y no el handoff, gobierna la interpretación. El handoff técnico fue leído después y sus 29 artefactos fueron verificados de forma independiente.

KwanCode Harness (KCH) es el sistema nodriza de integración, registro, composición, intraconexión, interconexión, orquestación y gobierno multicapas/multiescala. KwanCode/CSI es el sustrato composicional tipo MIDI. Las herramientas KCH son construcciones funcionales CSI preensambladas, descomponibles y recompilables; Super-MCP es una fachada federada, no KCH entero ni una fusión de servicios.

La ontología activa conserva KCH, KwanForks, QAS, CAS, RDSS, KwanPrompts, RGG, OBL, PHL, Z_post y Super-MCP con jurisdicciones separadas. El censo `17/23→27/9/39/14+9/28` contiene ejes taxonómicos y momentos históricos distintos. Los 28 son especificaciones de control reflexivo, no 28 endpoints ya ejecutados. Sol y Terra fueron ejecutados; Luna permanece `NOT_ESTIMABLE_RUNTIME_MODEL_UNAVAILABLE`.

## Evidencia PHL revalidada

La primera campaña autónoma PHL sigue siendo `PASS 30/30`.

- Los scores instrumentales `000`, `050` y `100` están tipados `MODEL_TEST_OPERATOR`, `NOT_USER_DATA` y `training_eligible=false`.
- El paquete admitió cero ejemplos y excluyó los tres registros instrumentales.
- Inventario, filtros, búsqueda, orden, página, cola y cursor sobrevivieron a la reconstrucción del workbench.
- El lock PHL bloqueó las tres operaciones mutantes de Super-MCP v0.1 y se liberó al cerrar.
- El estado personal original permanece en 7 decisiones, 0 feedback y 0 sesiones PHL activas.
- SHA-256 observado del estado: `a81724487739c37825e251c0de68a9aaf2033e2e14418f9aac8215f6a976527d`.
- Wheel canónica: versión interna `0.1.1`, entrada `kch-phl = kch_learning.phl_workbench_praxis:main` y SHA-256 `3887df03e896d5779e8815b6a52f2213ae557e4a92045f9216dde3e61552e141`.
- Manifiesto auxiliar: 29/29 artefactos coinciden en existencia, tamaño y SHA-256; cero discrepancias.
- SHA-256 observado del manifiesto de 29 artefactos: `ceda3cf07263185c086a8d8b5e1161e91be47953e4efc38abc949e0e5130d914`.

## Qué demuestra y qué no

La evidencia demuestra que PHL es un instrumento/control plane ejecutable, persistente, reanudable y resistente a contaminación instrumental dentro del corte ensayado. También demuestra lowering CSI acotado y binding completo de la superficie mutante de Super-MCP v0.1.

No demuestra aprendizaje de preferencias, mejora de política, ajuste de pesos, integración nativa Codex/Cline, instrumentación de todos los emisores KCH, routing de todos los servicios, lock global de actuadores ni recompilación CSI universal.

## Brecha causal localizada en código

1. El ledger usa SQLite WAL, proyecciones y cadena hash, pero no posee un protocolo explícito multi-cliente con `request_id`, `expected_head_hash`, control optimista o réplica con conflictos detectables.
2. El workbench sí persiste filtros, búsqueda, orden, página, cola y cursor.
3. `LearningAwareGateway` protege sólo `open_session`, `admit_evidence` y `precommit_verify`; un método mutante futuro o no clasificado puede quedar fuera si no existe un catálogo fail-closed.
4. El registro v0.4 admite 16 filas y conserva una en cuarentena, pero registro no equivale a routing ni emisión de decisiones.
5. `register_decision` preserva cualquier record JSON, pero todavía no exige el sobre superinformado común que permita comparar decisiones heterogéneas sin perder evidencia, reglas, propósito, autoridad o techo de claims.

## Siguiente gate congelado

`GATE_PHL_EFFECTIVE_KCH_INTEGRATION_v0.2.0`

Objetivo: demostrar, sin producir scores sintéticos, que Codex y Cline pueden operar sobre un único estado personal mediado; que las decisiones KCH llegan a PHL mediante un contrato completo y verificable; y que toda operación ruteada clasificada como mutante queda bloqueada durante PHL, con fallo cerrado para mutabilidad no clasificada.

### Fronteras del gate

1. **Ledger único multi-cliente**
   - Un único escritor mediado por servicio o una sincronización explícita hash-linked.
   - Cada mutación porta `request_id`, identidad de cliente y `expected_head_hash`.
   - Reintentos son idempotentes; una cabeza obsoleta produce conflicto explícito.
   - Ningún cliente copia y muta un SQLite independiente.

2. **Contrato reviewable-decision**
   - Todo emisor bajo prueba produce identidad, tiempo, componente, objetivo, propósito, jurisdicción, tipo, input/procedencia, evidencia, reglas, alternativas, rationale, confianza declarada sin inventar escala, riesgo, autoridad concedida/ejercida, techo de claims, consecuencia, reversibilidad y condiciones de parada.
   - Ausencias materiales se representan como `UNAVAILABLE` y bloquean promoción del emisor; no se rellenan con valores plausibles.
   - Igual `decision_id` con contenido distinto falla; reemisión byte-equivalente es idempotente.

3. **Catálogo de mutabilidad y lock PHL**
   - Cada método ruteado se clasifica `READ_ONLY` o `MUTATING` con evidencia de implementación.
   - PHL activo permite lectura y bloquea toda mutación antes del efecto.
   - Método sin clasificación falla cerrado.
   - Cierre o reanudación no puede perder ni duplicar el lock.

4. **Cobertura de emisores KCH**
   - Las 16 filas admitidas del registro v0.4 se adjudican como `DECISION_EMITTER`, `NON_DECISION_SERVICE` o `UNAVAILABLE_CONTRACT` mediante inspección real.
   - El PASS pleno exige conformidad de todo emisor admitido identificado.
   - Un corte parcial sólo puede recibir `PASS_BOUNDED`; nunca “todos los emisores KCH”.

5. **Round-trip Codex↔Cline**
   - Dos procesos/clientes sobre el mismo servicio observan la misma cabeza y proyección.
   - Se prueban escritura concurrente, reintento, cabeza obsoleta, caída/reanudación, tamper y colisión de identidad.
   - No se solicita ni registra feedback del usuario en esta campaña de infraestructura.

## Estados de decisión

- `PASS_EFFECTIVE_KCH_PHL_INTEGRATION_FULL`: ledger, catálogo, lock y todos los emisores admitidos identificados cumplen.
- `PASS_EFFECTIVE_KCH_PHL_INTEGRATION_BOUNDED`: la infraestructura y un subconjunto congelado cumplen; cobertura global sigue prohibida.
- `NOT_ESTIMABLE_EMITTER_INVENTORY_INCOMPLETE`: no puede determinarse qué servicios emiten decisiones.
- `FAIL_LOST_UPDATE_OR_SILENT_CONFLICT`: cualquier escritura se pierde o sobrescribe sin conflicto explícito.
- `FAIL_UNGUARDED_MUTATION`: una mutación ruteada atraviesa PHL.
- `FAIL_DECISION_CONTRACT_DIVERGENCE`: una decisión pierde objetivo, evidencia, procedencia, autoridad o propósito.
- `FAIL_LEDGER_OR_PROJECTION_INTEGRITY`: cadena o proyección diverge.

## Condición para la primera praxis humana

La primera sesión PHL real se habilita sólo cuando el gate alcance al menos `PASS_EFFECTIVE_KCH_PHL_INTEGRATION_BOUNDED` sobre un inventario explícito y cuando Codex/Cline compartan realmente el mismo ledger o servicio. Después podrá entrar feedback humano real. El learner ordinal y channel-aware continúa prohibido hasta que exista suficiente evidencia humana cronológica y se congele un dataset separado por lineage.

## Consecuencia para el objetivo rector

KCH está mejor posicionado que al inicio de esta tarea porque su estado PHL fue recuperado desde la fuente nativa y revalidado byte a byte, y porque la próxima brecha quedó localizada en mecanismos concretos. No ha ganado todavía capacidad de aprendizaje personal. El próximo trabajo de ingeniería ya no es otro self-test PHL: es implementar el servicio de ledger multi-cliente, el contrato común de decisión y el catálogo fail-closed de mutabilidad, comenzando por un corte pareado KwanPrompts + RGG + Super-MCP antes de ampliar al universo admitido.

