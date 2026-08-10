# CHECKPOINT 07 — KCH 0.11 desplegado realmente en Codex bajo `agent-shadow`, sin PHL real

Fecha: 2026-08-09  
Estado: `PASS_BOUNDED_REAL_PROJECT_SCOPED_MCP_DEPLOYMENT`  
Posición respecto del checkpoint 06: **mejor posicionada**.

## Resultado sustantivo

KCH 0.11 ya no es solamente una macrorelease sellada y reextraíble. Quedó instalado como servidor MCP de alcance de proyecto, reconocido por Codex y consumido por una instancia real de Codex. El servidor opera exclusivamente en `agent-shadow`, con federación de sólo lectura, sin promoción automática, sin perfil `enforced` y sin autoridad de ejecución mutante.

El gate directo sobre el transporte MCP terminó `PASS` con 37/37 aserciones. Una prueba host→MCP posterior terminó con exit code 0 y una única llamada `kch.super.status` del servidor `kch_0_11`. La respuesta observada fue: release `KCH 0.11`, package `0.11.0`, perfil `agent-shadow`, modo `SHADOW_AND_READ_ONLY_FEDERATION`, 28 controles, 7 paquetes federados disponibles, 0 no disponibles, ledger `PASS` y `mutating_execution_authorized=false`.

Esto establece **despliegue local real, descubrimiento por Codex y una ejecución MCP acotada en sombra**. No establece producción, autoridad mutante, eficacia causal, superioridad, seguridad del perfil `enforced` ni completitud total de KCH.

## Evidencia ejecutada

- ZIP canónico verificado nuevamente: 66/66 entradas exactas.
- Validación instalada post-despliegue: 13/13 checks, `PASS_KCH_0.11_LOCAL_BOUNDED`.
- Handshake MCP: protocolo `2025-06-18`; servidor `kwancode-harness` versión `0.11.0`.
- Superficie MCP: 49 herramientas, de ellas 28 controles directos, y 4 recursos.
- Auditoría de evidencia del registro: 19 PASS, 0 FAIL, 0 UNAVAILABLE.
- Paquetes federados: 7 AVAILABLE, 0 UNAVAILABLE.
- Proyecciones y probes no mutantes: SCO disponible; certificado MIS disponible; KwanPrompts, RGG y OBL/PHL importables.
- Cinco controles sobre el contexto efectivo de despliegue: R01, R02, R03, R27 y R28; composición 5 PASS, 0 BLOCK, 0 ABSTAIN, 0 UNAVAILABLE.
- Sesión KCH gobernada con tres evidencias preregistradas y admitidas: ZIP canónico, configuración MCP del proyecto y congelación PHL.
- Propuesta `kch.component.status`, clase `READ_ONLY`, autoridad pedida `READ`.
- Autorización: `ALLOW_READ_ONLY`.
- Ejecución: realizada, sólo lectura, 7/7 paquetes disponibles.
- Precommit: `ALLOW_SHADOW_PRECOMMIT`; promoción automática falsa; ejecución mutante falsa.
- Ledger KCH final: 30 eventos, 4 sesiones, 12 evidencias, 4 propuestas, integridad `PASS`.
- Host Codex: configuración descubierta con `codex mcp list/get` y una llamada real exitosa a `kch.super.status`.

## PHL: exclusión vinculante y evidencia de no uso

La orden del usuario de reservar PHL real para el final quedó convertida en un contrato explícito: `PHL_REAL_SESSION_FREEZE_v0.1.0.json`.

Durante todo el gate:

- no se expuso ninguna herramienta MCP de inicio, feedback, cierre o commit PHL;
- no se invocó `START_PHL`, no se creó feedback y no se activó aprendizaje;
- sólo se leyó la proyección existente y se verificó su integridad;
- feedback antes: 0; feedback después: 0;
- sesión PHL activa antes: `null`; después: `null`;
- cabeza lógica PHL antes y después: idéntica;
- SHA-256 físico del estado PHL antes y después: `d17a982e55203cdce6ffba1a2a2455260bea1df88536ac4456969ae755a07c21`.

Por tanto, este checkpoint **no es una sesión PHL**, no produce aprendizaje post hoc y no reduce el gate pendiente de primera utilización real por el usuario.

## Resultados adversos preservados y qué significan

1. Dos probes iniciales del launcher se detuvieron antes de iniciar el servidor porque Windows PowerShell 5 carece de APIs criptográficas estáticas modernas. Se sustituyeron por variantes compatibles; no tocaron KCH ni PHL.
2. El primer gate completo se detuvo porque el observador esperaba un campo `gate` inexistente en la auditoría registral. La respuesta real era 19 PASS, 0 FAIL, 0 UNAVAILABLE. Se corrigió el observador, no el resultado.
3. Dos sesiones KCH emitieron `CONTROL_RECEIPT_INTEGRITY_FAILURE` y `BLOCK`: Python entregaba JSON MCP en CP1252 (`F3`) en vez de UTF-8 (`C3 B3`), alterando nombres firmados como `autorización`. La localización inicial en PowerShell fue corregida al reproducir el defecto con Python directo. El bootstrap activo fuerza `-X utf8` y reconfigura `stdin/stdout` en UTF-8.
4. Un intento posterior completó autorización, ejecución, precommit y outcome, pero el observador final buscó integridad dentro de `audit.export`; el contrato real la expone en `status.ledger`. El resultado sustantivo exitoso se preservó y el observador pasó a verificar tanto el gate del ledger como el hash del export.
5. El primer comando host combinó flags incompatibles (`--approve-for-me` y sandbox explícito); la CLI lo rechazó antes de crear sesión. El reintento válido terminó exit code 0.

Los BLOCK de recibos alterados constituyen evidencia local de fail-closed frente a corrupción de transporte. No demuestran por sí solos eficacia general de R01–R28 ni seguridad de producción.

## Cambios materiales

- `.codex/config.toml`: registro MCP de proyecto `kch_0_11`, habilitado y requerido, aprobación `prompt`.
- `run_kch_011.py`: bootstrap directo con ocho wheels selladas, secreto HMAC efímero, estado separado y UTF-8 obligatorio.
- `runtime/state/kch_011_agent_shadow.sqlite3`: ledger append-only del despliegue y sus intentos adversos.
- `OBJECTIVE_CONTRACT_KCH_0.11_REAL_SHADOW_DEPLOYMENT_v0.1.0.json`: objetivo, jurisdicción, autoridad y límites.
- `PHL_REAL_SESSION_FREEZE_v0.1.0.json`: prohibición ejecutable y auditable de PHL real durante este gate.
- `KCH_0.11_REAL_SHADOW_DEPLOYMENT_GATE_RESULT.json`: resultado final 37/37.
- Cuatro resultados de intentos fallidos preservados, sin reescritura retrospectiva.
- `CODEX_HOST_TRANSPORT_RECEIPT_v0.3.0.json` y mensaje final host hasheado.

## Hashes principales

- Macrorelease canónica: `a4e08bb2833dffbfe3a3f2036579d1c8e56c20ea67ec94d4685a3618d528ee02`.
- Gate real shadow: `ce0192b201293a1dff818110d355a3ac2c05b37b34e385ea108f5363dae236f5`.
- Configuración MCP de proyecto: `a8a285bf8c23bda32529bf559ab548373e96f7e4e4c3fe795af41e2265209d55`.
- Bootstrap Python: `aa7216feb531e03886551ea5bd969ad7afdf23c524bce7fd4c3aa8ad294d23c6`.
- Contrato de objetivo: `e0dcaf359ea29b16c7469dd2f190a627931cb1bffc2164c8cc700b5b0dbf1987`.
- Congelación PHL: `1934042b4aa97233efa15188f051554a6cdd3f964cba823675741e8a36ebe7c8`.
- Estado PHL inmutable: `d17a982e55203cdce6ffba1a2a2455260bea1df88536ac4456969ae755a07c21`.
- Validación instalada: `9a4460e05a7c10627922ec8f28b4dfca1060f3875ec3bc2cae152f45bab351d6`.
- Recibo del host Codex: `56e5871992313fa3ce3b9d4f8a905f05977db6ad5f7dd2148fd11244f3094272`.
- Mensaje final del host Codex: `5bfbba8feb0a1ebdf9b36ee15ff440573f1e1ddc2adcbfd3313b016b226c3ecd`.
- Ledger KCH desplegado al cierre: `c35f43f1da0d738d1ddbcb0d075dc730fe14e3007d71cd045ce873a9c1a01168`.

## Límite vigente de claims

Claim admisible: `REAL_LOCAL_PROJECT_SCOPED_MCP_DEPLOYMENT_AND_BOUNDED_AGENT_SHADOW_EXECUTION_WITHOUT_PHL_REAL_USE`.

No demostrado:

- despliegue productivo o multihost;
- ejecución mutante o gobernanza `enforced` segura;
- eficacia real de los 28 controles en diversidad de tareas;
- mejora causal, superioridad o ROI;
- estabilidad longitudinal;
- orquestación SCO viva entre proveedores;
- PHL con feedback humano real;
- completitud de KwanForks, CSI 17/17 o Luna/MIS.

## Siguiente acción crítica, manteniendo PHL para el final

El siguiente gate no debe ser más empaquetado ni otra prueba sintética. Debe ser una campaña corta de **dogfooding longitudinal no-PHL**: utilizar KCH 0.11 desde nuevas tareas Codex reales para gobernar una secuencia acotada de trabajos heterogéneos, invocando de manera trazable rutas SCO, MIS, KwanPrompts y RGG bajo `agent-shadow`; medir disponibilidad, abstenciones, BLOCK, errores de transporte, coherencia de objetivos, evidencia y coste operacional. Cada caso debe conservar su autoridad local y no fusionar chats.

Sólo después de obtener consistencia real suficiente se decidirá si ampliar rutas gobernadas o si algún control puede optar a promoción. PHL seguirá congelado hasta el último gate indicado por el usuario.

Nota operativa: la nueva configuración fue consumida por una nueva instancia CLI. La tarea de escritorio que ya estaba en ejecución no puede incorporar dinámicamente una superficie MCP añadida durante su propio turno; para verla interactivamente hace falta abrir una nueva tarea en este proyecto o recargar la aplicación.
