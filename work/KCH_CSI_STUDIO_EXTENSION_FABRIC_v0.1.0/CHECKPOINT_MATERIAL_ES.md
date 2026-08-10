# Checkpoint material — KCH 0.11 pre-2G, R9 estable y sucesor 0.3.0 pendiente de R10

## Posición respecto del checkpoint anterior

KCH está mejor posicionado como candidato local de preproducción: existe una R9 portable instalada desde un ZIP sellado que responde por STDIO y supera 14/14 checks. También está mejor instrumentado para descubrir sus propios fallos. No está validado industrialmente ni se ha demostrado que mejore causalmente a un agente sin KCH.

## Qué cambió

- Se implementó un motor constitucional de modos de contestación redactada con tres presets: Conciso (objetivo una pantalla; máximo dos pantallas/un scroll), Explicativo (dos a cinco scrolls) y Extenso (lo necesario). Los outputs no se contabilizan ni se recortan.
- Los perfiles custom son persistentes y se resuelven por `GLOBAL < WORKSPACE < SCO < TASK < SESSION < MESSAGE`. La medición física del viewport se declara dependiente del renderer del host; no se inventa.
- La corrección posterior del usuario es vinculante: la respuesta principal debe explicar de conjunto y nunca ser una ficha archivística. La ficha técnica se guarda automáticamente como Markdown, no se ofrece ni se pregunta si se desea; sólo se informa su ruta en una línea final.
- La UI incorpora una pestaña específica, el MCP suma diez herramientas operativas y el contrato anti‑orfandad clasifica `ResponseModeManager` completo.
- El gobierno v04 compila 18 nodos y 9 reglas, con hash de grafo `227ac03b4064e04d5cd01e2c70c5bf1d782ce1c021e3066ab47b24f540856586`.
- `kch_preflight` es el único preflight canónico y se ejecuta mediante `StudioMCP`; la clase interna `KCHAdvancedRuntime` ya no puede hacerse pasar por el sistema compuesto.
- La gobernanza compilada contiene 17 nodos y preserva `HARNESS > AGENTS > RULES` y «todo es estratégico».
- La superficie sucesora expone 198 herramientas; el Super‑MCP instalado compone 247 nombres únicos.
- La UI tiene 11 pestañas. **Trabajo y aprendizaje** conserva fuente cruda y normalizada, archivo jerárquico, grafo clicable, presupuesto semanal, handoffs locales y generación de protocolos/skills `STAGED_UNEVALUATED`.
- Un fallo histórico real generó un protocolo y una skill candidata sin instalarla ni activarla. Esto prueba el ciclo local de staging, no la utilidad de la skill.
- El caso 002 reveló que el normalizador de dicción se aplicaba indebidamente a código y podía transformar `permission` en `perMISsion`. Ahora sólo opera sobre `DICTATION` y `AUDIO_TRANSCRIPT`, y las sustituciones respetan límites léxicos.
- La dependencia Windows `tzdata` quedó declarada, hasheada e incluida en el wheelhouse offline.
- El gate portable tiene timeouts por RPC, marcadores de etapa y limpieza del árbol de procesos que él mismo crea.

## Evidencia vigente

- Modos de respuesta + Studio/Super‑MCP dirigidos: 7/7 tests, 74,76 s; Ruff y compilación Python pasan.
- Regresión integral: no adjudicada. El primer intento agotó 7 minutos tras 22 tests; el test 23 aislado pasó en 48,19 s. Un shard posterior obtuvo 21/22 y el último setup falló por `database or disk is full` cuando C: llegó a 0 bytes libres.
- Los basetemps creados en C: quedaron con ACL inaccesibles y no pudieron eliminarse ni mediante el proceso elevado. D: dispone de espacio y `D:\KCH_TESTS_R10` fue creado, pero la revisión de riesgo del host bloqueó ejecutar allí los shards sin una nueva aprobación explícita del usuario.
- Regresión fuente: 36/36.
- Ruff: pasa sobre fuente, tests, scripts y benchmarks cuando se invoca desde sus raíces correctas.
- Prepiloto 001: ambos outputs 95/95 descriptivo, pero condición KCH inválida; efecto `NOT_ESTIMABLE`.
- Prepiloto 002: ambas condiciones válidas, empate 95/95; efecto causal `NOT_ESTIMABLE`.
- Prepiloto 003: ambas condiciones válidas, empate 100/100; el brazo KCH usó y cerró la instalación portable R9, pero el efecto causal sigue siendo `NOT_ESTIMABLE` y `industrial_validation=false`.
- El primer pase literal del evaluador 003 produjo `INVALID_CONDITION_INTEGRITY` porque no reconocía alias contractualmente equivalentes (`actual_sha256`, bloque `live` anidado y `Grupo 6`). Ese resultado se conserva en `evaluation_initial_literal_alias_failure.json`; la corrección no cambió ningún recibo de los brazos ni ningún byte del archivo R9.
- R6: instalación fallida por creación no recursiva de runtime.
- R7: instalación lograda, wrapper `CHECK_KCH.cmd` fallido por separador de ruta.
- R8: instalación lograda, initialize no alcanzado por ausencia de `tzdata` en el venv limpio.
- R9: ZIP de 22.014.573 bytes, SHA‑256 `038d4abff544793253abab3caeb2ff541f09e385c94c3d3d6fd28fb90983ab14`; instalación offline con 16 wheels; gate instalado 14/14 en 53,7 s.
- R9: 247 herramientas; preflight canónico `PASS`; gobierno 17/17; Workbench integrity `PASS`; MIS 480 registros/60 ledgers; autoridad y ejecución falsas.
- PHL está autorizado; `training_executed=false` y `real_feedback_executed=false`.

## Significado técnico y epistemológico

R9 demuestra que los bytes empaquetados pueden instalarse y componer localmente las superficies declaradas en este Windows. Los fallos R6–R8 no se borran: muestran que los tests de source no bastaban para adjudicar portabilidad y justifican el gate limpio.

Los pares Luna todavía no demuestran que KCH reduzca errores: uno fue inválido y los dos pares válidos terminaron empatados. El caso 003 sí mejora la integridad experimental frente al 001 porque usa el `StudioMCP` portable canónico instalado, no una clase interna. También demuestra que el evaluador puede fallar por rigidez de representación; por eso se preservan el pase literal adverso y la justificación de cada alias admitido.

## BIND 2026

El encaje exacto principal es Group 6 / ID36, gestión y transferencia de conocimiento: información dispersa, duplicada u obsoleta; extensiones heterogéneas; captura, organización, clasificación, indexación y reutilización de conocimiento histórico. ID31, ID33 e ID42 son adyacentes. Esto es encaje de problema, no piloto contratado, readiness de mercado ni validación industrial.

## Qué sigue sin validarse

- beneficio causal frente a baseline, utilidad y ergonomía sostenidas;
- completitud autenticada de historiales externos y EOF nativo;
- telemetría real semanal de cuentas y traspaso/archivo automático entre hosts;
- seguridad independiente, compatibilidad amplia y escalabilidad;
- calidad de protocolos/skills autogenerados fuera del caso observado;
- PHL real o entrenado;
- piloto industrial, Venture Client o selección BIND.

## Próxima acción crítica

Obtener autorización explícita para ejecutar los dos shards exhaustivos de pytest usando exclusivamente `D:\KCH_TESTS_R10` como basetemp. Sólo si la unión alcanza 40/40 se construirá e instalará limpiamente el portable R10. R9 permanece intacta y vigente; no se ejecutó PHL real.
