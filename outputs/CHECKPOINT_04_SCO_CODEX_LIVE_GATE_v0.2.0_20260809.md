# Checkpoint 04 — SCO Codex live transport + KCH decision adapter v0.2.0

Fecha: 2026-08-09  
Gate compuesto: `PASS_BOUNDED` — 16/16  
Subgate de decisión: `PASS_BOUNDED` — 8/8  
Pruebas del transport guard: 5/5

## Nueva tarea desechable

- Thread ID: `019fe6f6-076b-7803-b3c3-88c6f29329f0`
- URI: `codex://threads/019fe6f6-076b-7803-b3c3-88c6f29329f0`
- Título: `SCO Gate v0.2 — Nodo Codex desechable`
- Autoridad: `RETURN_BOUNDED_TEXT_RECEIPT`
- Prohibiciones: filesystem, red, contacto con otras tareas y exportación de contexto/memoria.
- Estado final: idle, preservada para inspección; no archivada.

## Resultado observado

El bootstrap devolvió el nonce exacto y no reportó herramientas. Después, SCO registró el nodo, una arista y una orden acotada. El host entregó `SCO-LIVE-DISPATCH-20260809-01`; la tarea devolvió un JSON exacto con `SCO_LIVE_TRANSPORT_OK` en el turno `019fe6fa-b818-7c62-bb0b-d04f0fbb3bb1`.

El texto nativo tiene SHA-256 `e6aa7600f7a9f8fb10d981dca9bf14d8a17f0df5f78dbf46aa3cf2c4dfba8976`. El transport guard lo ligó a dispatch, orden, target, nonce y autoridad. Repreparar el mismo `dispatch_id` produjo `should_send=false`; no se generó un segundo mensaje.

La proyección sucesora de SCO contiene 3 nodos, 2 aristas, 2 órdenes completadas, 2 recibos, 10 eventos y 0 defectos. No se fusionó contenido ni memoria.

## Integración KCH/PHL

SCO fue registrado como `DECISION_EMITTER` en el inventario sucesor de 17 componentes admitidos. Se produjeron dos records estrictamente conformes a `kch.reviewable-decision.v0.2.0`:

1. emisión de `wo.sco-live-transport-01`;
2. abstención de adjudicación porque el ledger contenía 0 conflictos.

Se añadieron 8 métodos SCO al catálogo, que pasa a 25 entradas en la réplica. La réplica conserva integridad, 0 feedback y `PASS_EFFECTIVE_KCH_PHL_INTEGRATION_BOUNDED`. El estado personal original permanece en `a81724487739c37825e251c0de68a9aaf2033e2e14418f9aac8215f6a976527d`.

## Incidencia adversa preservada

El primer intento de copiar el estado v0.1.0 empleó una ruta relativa incorrecta. Se creó una base vacía y las tres operaciones posteriores fueron rechazadas con `unknown sco_id`. La base conserva 0 eventos y 0 comandos; no se tocó el release sellado ni la tarea. El segundo intento usó la ruta absoluta verificada y pasó.

## Límite del claim

Demostrado: un ciclo textual Codex vivo, acotado, con guardia idempotente, receipt-binding y adaptación de decisiones KCH sobre estados sucesores aislados.

No demostrado:

- un segundo target independiente;
- transporte Cline, Cowork, OpenCode o ChatGPT;
- auditoría independiente del sistema operativo del nodo;
- IDs nativos separados para request y response —Codex expuso un turno común—;
- más clases de decisiones SCO;
- desaparición de los 12 contratos históricos `UNAVAILABLE_CONTRACT`;
- superioridad semántica frente a Projects.

## Artefactos y hashes

- Resultado compuesto: `600a7072f0a672a69ebf3ffc6a9c17ac92f3e6b2a07a504749d4ef613602417c`.
- Adapter de decisiones: `b3cd1588c25505229a1a7c802a16efc00c455d223f15105ba64d98cbd23d7bf1`.
- Decisiones KCH: `97770e49d11f2ad7c985eac6a9aebcfad8025ec024c986b331f652160a007fe3`.
- Recibo del host: `a37c319af083c674f0ef436433fe3491d6e074e36a507f8f99801c347c72b67b`.
- Bundle sucesor: `7c707aee65d1816ee0894d985439186ab5108d2d20d2d4f22845213eeda90937`.
- CSI lowering sucesor: `3a704255473d57bd6d37a23bd6e56490bec771ce5e38917c2644324a02b28228`.
- Manifest 24/24: `29f3372d2c698e1eb29df78ce6ef4dd788be06c9cc895ebfbc78289aeb41e8ab`.
- ZIP reextraído 24/24: `aa0af9274681f2ecfeb32ee5acbfdaac93ed5340909dd7607ac92fdfb0b70b4b`.

## Próxima acción crítica

Repetir el transporte sobre un segundo target Codex independiente para cerrar `PASS_FULL_THIS_GATE`, o mantener el nodo actual y abrir el primer puente heterogéneo. Ninguna de esas extensiones debe alterar la fuente histórica ni sustituir las memorias nativas.
