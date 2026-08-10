# Checkpoint 03 — despliegue de KCH SuperChats Orquestadores v0.1.0

Fecha: 2026-08-09  
Estado del gate: `PASS_BOUNDED`  
Comprobaciones de release: `23/23`  
Pruebas unitarias: `21/21`  
Estado KCH: `LOCAL_VALIDATED_INTEGRATION_CANDIDATE`

## Qué se logró realmente

Se implementó una herramienta ejecutable de KCH que registra sesiones nativas como nodos soberanos y las compone mediante un grafo sin fusionar historias, contextos, memorias, herramientas, autoridad ni ciclos de vida.

La superficie operativa incluye:

- ledger SQLite hash-encadenado;
- detección de escritores obsoletos, colisiones e idempotencia;
- selección de referencias nativas Codex, ChatGPT, Cline, Cowork, OpenCode y `CUSTOM`;
- roles, responsabilidades, capacidades, autonomía y autoridad por nodo;
- contratos obligatorios de divulgación acotada;
- aristas tipadas;
- órdenes con dependencias y estados `READY`/`WAITING`;
- recibos `SUCCEEDED`, `FAILED`, `BLOCKED` y `ABSTAINED` sin colapsarlos;
- conflictos preservados y adjudicadores con autoridad explícita;
- retiro no destructivo de nodos;
- sobres de despacho honestos;
- exportación portable sin contenido nativo;
- lowering CSI con primitivas existentes.

## Primer SCO real desplegado

`sco.kch-pre2g-continuation.20260809` contiene:

1. `kch-canonical-lineage-source` → `codex://threads/019fd938-8000-7121-9078-d196bdd15ae4`, fuente cronológica, `OBSERVE_ONLY`.
2. `kch-sco-builder` → `codex://threads/019fe6b4-c2dd-7880-847e-d1fd16ea67a2`, constructor/validador, `EXECUTE_WITHIN_SCOPE`.
3. Arista `SUPPLIES_EVIDENCE` con prohibiciones `FULL_CONTEXT_MERGE`, `NATIVE_MEMORY_COPY` e `IMPLICIT_AUTHORITY_TRANSFER`.
4. Una orden de trabajo real, completada con recibo verificable.

Proyección final: 1 SCO, 2 nodos, 1 arista, 1 orden, 1 recibo, 6 eventos, 6 comandos, 0 conflictos y 0 fusión contextual.

## CSI y KCH

El preset `kch.preset.sco.orchestration` baja únicamente a `OPEN_SESSION`, `SEAL_IDENTITAS`, `ADD_DATUM` y `MODE_ON`. Declara `authority_created=false`, `native_contexts_merged=false`, `native_memories_replaced=false` y `execution_authorized=false`.

El registro federado sucesor v0.5.0 conserva los 17 renglones previos y añade SCO como renglón 18. Eso no equivale automáticamente a “18 de los 28 elementos” porque el registro contiene releases históricas duplicadas y una rama en cuarentena; SCO sí queda propuesto como nuevo elemento KCH, pero el inventario canónico de 28 todavía requiere adjudicación propia.

## Resultado adverso y límite de claims

El sobre de despacho real se generó, pero terminó `HOST_BRIDGE_REQUIRED`: no hubo envío automático. Codex fue observado y sus dos URIs fueron verificadas por el host; el paquete standalone no puede leer ni escribir por sí solo. Cline, Cowork y OpenCode permanecen `UNAVAILABLE_NOT_TESTED` para transporte vivo.

No están demostrados:

- transporte vivo idempotente y recibo ligado a respuesta nativa;
- puentes vivos de otros proveedores;
- adaptación de decisiones SCO a `kch.reviewable-decision.v0.2.0`;
- registro de rutas SCO en Super-MCP;
- operación distribuida o multihost;
- superioridad empírica de resultados frente a Projects.

Por tanto, la superioridad demostrada es arquitectónica —invariantes más fuertes y verificables—, no todavía comparativa en calidad, coste o velocidad.

## Artefactos principales y hashes

- Wheel: `aaecb06da92aa2e47af4b5bc267a799342f56dd5f2bd4dd33ea3092c2a225ad2`.
- Resultado SCO: `ec051c7c93cfe54a1ecf5c426750d34747441b7ed03ae005c0f1aedab55c9bd6`.
- Bundle portable: `d28aa3ba5ffa4c14e474874d4a999731bd768e7f8f1e8179407064ec6043a7b0`.
- Lowering CSI: `58b5a7ec501dc278fdf1afc6aabaae6aa1ec4a63e8a87c2f6699fc09f0e805ad`.
- Registro KCH v0.5.0: `204dd6f069b898d5a263590fe82809aee933c6599bf6df87f500aeaf391dc653`.
- Manifest v0.1.1: `7e493332236bb901ea639cc085b39b57af13c1aab68e3b0db0e01a5641d1f3d8`, 35/35 archivos verificados, 0 discrepancias.

## Próxima decisión crítica

Ejecutar `GATE_SCO_CODEX_LIVE_TRANSPORT_AND_KCH_DECISION_ADAPTER_v0.2.0`. Se necesita que el usuario seleccione una tarea Codex escribible o autorice crear una desechable; la tarea fuente canónica permanecerá sólo lectura. El gate probará descubrimiento, lectura mínima, despacho, recibo nativo, retry idempotente, no fuga contextual, no escalada de autoridad y emisión de decisiones KCH v0.2.0.
