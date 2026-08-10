# START HERE — KCH pre-2G después de integrar MIS v0.3.1

Estado: `KCH × MIS v0.3.1 PASS_BOUNDED`.

## Lectura

1. `CHECKPOINT_05_KCH_MIS_V03_INTEGRACION_EFECTIVA_v0.1.0_20260809.md`.
2. `KCH_MIS_V03_EFFECTIVE_INTEGRATION_RESULT_v0.1.0.json`.
3. `KCH_MIS_V03_HISTORICAL_CERTIFICATE_v0.1.0.json`.
4. `KCH_MIS_V03_REVIEWABLE_DECISIONS_v0.1.0.json`.
5. `KCH_SUPER_MCP_FEDERATED_REGISTRY_v0.6.0.json`.
6. `KCH_MIS_V03_CSI_LOWERING_v0.1.0.json`.
7. `KCH_MIS_V03_BUILD_MANIFEST_v0.1.0.json`.

## Invariantes

- MIS v0.3.1 es una arquitectura matemática federada, no sinónimo de KCH.
- MIS calcula y certifica; KCH gobierna autoridad, routing, commit y claims.
- `capability != permission`; un certificado MIS no autoriza ejecución.
- Se preservan purpose, jurisdicción, provenance, evidencia y future-only.
- Empate MIS no equivale a ganador único.
- El replay histórico de 480 acciones no es evidencia causal ni prospectiva.
- PHL no fue iniciado; no existe feedback humano ni policy activation nuevos.
- La siguiente validación debe ser uso real, no otra campaña artificial.

## Estado ejecutable

- Gate original y reextraído: `21/21 PASS_BOUNDED` cada uno.
- Suite original y reextraída: `7/7 PASS` cada una.
- Registry v0.6.0: 19 filas totales, 18 admitidas, una en cuarentena y MIS una vez.
- Estado integrado: `KCH_CURRENT_INTEGRATION_STATE_v0.6.0.sqlite3`.
- Release: `KCH_MIS_V03_EFFECTIVE_INTEGRATION_v0.1.0.zip`.

## Próximo gate, sólo con uso genuino

Congelar antes del outcome:

1. evidencia KwanDocs exacta;
2. purpose y jurisdicción;
3. estados y acciones semánticas;
4. prior, likelihood y pérdida racional declaradas o `UNAVAILABLE`/abstención;
5. certificado MIS;
6. decisión KCH con autoridad explícita;
7. outcome separado y aprendizaje Z_post future-only.

