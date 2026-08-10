# Checkpoint 05 — integración efectiva de MIS v0.3.1 en KCH

Fecha: 2026-08-09  
Estado: `PASS_BOUNDED · LOCAL_VALIDATED_EFFECTIVE_INTEGRATION_CANDIDATE`

## Resultado sustantivo

KwanCode Harness (KCH) queda mejor posicionado. La sospecha del usuario era
correcta: MIS estaba descrito como candidato transversal y existía la regla
«MIS calcula; KCH gobierna autoridad y commit», pero no había un adaptador
ejecutable MIS v0.3.1 → KCH, routing real por el control plane, catálogo de
mutabilidad, contrato de decisión revisable ni lowering CSI específico.

Ahora MIS v0.3.1 está integrado como **servicio matemático federado**. No ha
sido absorbido ni renombrado como parte nativa de KCH. MIS conserva su identidad
y calcula átomos semánticos, posteriores racionales exactas, pérdidas,
decisiones y certificados. KCH conserva en exclusiva la autoridad, el routing,
el commit y la promoción de claims. La pertenencia a la federación no transmite
autoridad.

## Qué se ejecutó realmente

El gate `GATE_KCH_MIS_V03_EFFECTIVE_INTEGRATION_v0.1.0` pasó `21/21`:

- cargó el wheel MIS v0.3.1 sellado, SHA-256
  `be03cb2b594e22f662da5b74d8689384de8c1bde3d466fe18772dedbf0c89157`;
- ejecutó el adaptador sobre los 480 registros reales del corpus histórico cuyo
  identificador congelado conserva `KHC_TWO_BATTERY_COMPARATIVE_8x8_v2.0.7`;
- obtuvo 480 coordenadas y 480 unidades MIS únicas;
- rehidrató y verificó 60 ledgers, 480 freezes y 480 outcomes;
- reprodujo exactamente el audit y el replay cualificados de MIS v0.3.1;
- verificó la interfaz racional contra el ejemplo formal congelado, sin
  presentarlo como estimación empírica;
- registró cuatro métodos KCH `READ_ONLY`: `describe`,
  `audit_historical_khc`, `exact_decide` y `verify_certificate`;
- bloqueó fail-closed `authorize_execution`, método no declarado, antes de
  llamar al ejecutor;
- registró `kch.mis.v03.adapter` como emisor federado;
- incorporó dos records conformantes con `kch.reviewable-decision.v0.2.0`:
  admisión estructural y abstención causal/global;
- emitió lowering CSI con separación MIS-cálculo / KCH-autoridad;
- creó el registry v0.6.0 con una sola fila MIS nueva. El registry contiene 19
  filas totales: 18 admitidas y una rama histórica en cuarentena.

La proyección KCH pasó de 51 a 63 eventos, de 9 a 11 decisiones, de 25 a
29 métodos clasificados y de 17 a 18 emisores inventariados. El ledger verificó
`PASS` sin defectos. PHL permaneció inactivo y el feedback humano siguió en
cero.

## Custodia y no mutación

El baseline KCH mantuvo el mismo SHA-256 antes y después:

`1027fa8da1a583b107521bb5298a3f5774e1abbeb887a3772cea70c4e1c969a8`

Los cinco artefactos MIS conservaron sus hashes. El certificado histórico tiene
identidad canónica interna:

`66d400e747fa35bc8f3eba5e521d23b538b98c1cffb9405c30fa20cc86f4deed`

El JSON que lo transporta tiene SHA-256:

`1bbe2885eed1dd53618f9b0af9c21cee3d0bfdde1aace48dbfcf9b56e9bd775a`

El primer hash identifica el core canónico; el segundo, los bytes JSON
formateados. El nuevo estado KCH de continuación es una réplica sucesora, no una
mutación del estado personal.

## Hallazgo adverso preservado

La primera suite falló 3 de 7 tests porque el runtime devolvía `ledgers: null`
con `include_ledgers=False`, mientras el reporte omitía ese campo. No había
diferencia matemática, numérica ni cronológica. El adaptador normaliza sólo ese
campo de transporte nulo y, separadamente, rehidrata los 60 ledgers completos.
El fallo inicial no se borró ni se presentó como éxito ex ante.

## Portabilidad

Desde el ZIP reextraído en otra raíz pasaron:

- manifiesto: `PASS`, 0 defectos, 40 entradas;
- suite: `7/7 PASS`;
- replay: misma identidad canónica;
- segunda ejecución completa: `21/21 PASS_BOUNDED`.

Release: `KCH_MIS_V03_EFFECTIVE_INTEGRATION_v0.1.0.zip`  
SHA-256: `b084cd49f9df41ef848aa3a002d2a494d47898e255dadef5cff10342de64b9d8`

Wheel: `kch_mis_v03_integration-0.1.0-py3-none-any.whl`  
SHA-256: `81037cd2881516e537701d3b720f15bcc8694c4ccdc70514726c0348254e49ae`

## Evidencia y límites

Queda demostrada localmente, sobre una réplica, la invocación de MIS por el
control plane KCH, representación sin pérdida de 480 records, cálculo racional
exacto, empates preservados, persistencia y future-only, adaptación de decisiones
KCH, fallo cerrado y portabilidad local.

No queda demostrada mejora causal, superioridad prospectiva, utilidad humana,
escalado abierto, ganador global, validación externa independiente ni producción.
El `PASS_BOUNDED` es sustantivo: la integración es real, pero doce servicios
históricos siguen `UNAVAILABLE_CONTRACT` y el corpus MIS es histórico.

## Próxima acción crítica

No corresponde otra campaña artificial. La próxima validación informativa será
el primer uso real `KwanDocs → MIS → KCH → outcome → Z_post` sobre una decisión
genuina del usuario, con evidencia, jurisdicción y tabla de pérdida congeladas
antes de conocer el outcome. Una acción MIS seguirá siendo consejo certificado,
nunca permiso implícito.

