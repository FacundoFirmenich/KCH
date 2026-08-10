# Checkpoint 06 — KCH 0.11 macrorelease canónica

Fecha: 2026-08-09  
Estado: `SEALED_CANONICAL_PRE2G_MACRORELEASE_LOCAL_BOUNDED`  
Nombre vinculante: **KCH 0.11**  
Versión de paquete: `0.11.0`

## Cambio de posición

KCH queda **sustancialmente mejor posicionado y por primera vez macroconvergido como release ejecutable local**, aunque todavía no es un KCH 2G ni una instalación productiva `enforced`. El checkpoint anterior poseía componentes soberanos validados, un registro federado y un Super-MCP mínimo, pero no una distribución canónica del conjunto. KCH 0.11 aporta esa unidad de instalación, descubrimiento, gobierno, receipts, custodia y ejecución federada de sólo lectura sin fusionar las soberanías internas.

## Resultado alcanzado

1. Paquete canónico `kwancode-harness==0.11.0` y servidor MCP stdio arrancable desde wheel.
2. Doce operaciones estables de orquestación, una operación de catálogo, ocho inspecciones federadas y 28 herramientas directas de control: 49 tools MCP en total.
3. Los controles R01–R28 son contratos ejecutables individuales con salida `PASS`, `BLOCK`, `ABSTAIN` o `UNAVAILABLE`; cada receipt queda ligado por SHA-256 al contexto evaluado y no crea autoridad.
4. Gateway con sesiones vinculadas a objetivo/proyecto/jurisdicción, capability tokens HMAC expirantes y de un uso, admisión tipada de evidencia, propuesta, autorización, ejecución read-only, precommit, outcome, compensación append-only y export de auditoría.
5. Federación read-only efectiva hacia PHL/KCH, SCO, certificado MIS y auditoría del registro. Las acciones mutantes y el perfil `enforced` fallan cerrados.
6. Registro canónico v0.11.0: 19 servicios admitidos —incluido el propio KCH 0.11— y una rama en cuarentena. Las 19 evidencias admitidas poseen copia portable con hash verificado.
7. Bundle offline con ocho wheels: core KCH y siete paquetes soberanos —PHL, SCO, MIS adapter, MIS backend, OBL/PHL, RGG y KwanPrompts— sin herencia de autoridad.
8. SBOM SPDX, inventario de licencias con `NOASSERTION` cuando el wheel no declara licencia, auditoría estática de superficie de red y manifiesto SHA-256.

## Evidencia ejecutada

- 7 suites, 108 tests ejecutados y PASS. Es un total operativo entre suites, no una afirmación de independencia estadística.
- Gate directo desde wheels: `13/13 PASS_KCH_0.11_LOCAL_BOUNDED`.
- Gate desde wheels extraídos: `13/13 PASS_KCH_0.11_LOCAL_BOUNDED`.
- Reextracción del ZIP sellado: `66/66` archivos exactos por manifiesto y nuevo gate `13/13`.
- Smoke MCP real desde la reextracción: versión `0.11.0`, 49 tools, 28 controles directos y schemas corregidos R05/R16.
- Estado PHL/KCH transportado sin mutación: integridad PASS, 63 eventos, 11 decisiones, 29 métodos de mutabilidad, 18 emisores; 4 `DECISION_EMITTER`, 2 `NON_DECISION_SERVICE` y 12 `UNAVAILABLE_CONTRACT`.

Hashes principales:

- ZIP: `a4e08bb2833dffbfe3a3f2036579d1c8e56c20ea67ec94d4685a3618d528ee02`
- wheel core: `1895dfadba8ceea025bd1ff5090fa2f96af66304bf550fe474751186f6799930`
- registro v0.11.0: `170ac6b7a7f442e1baf08b5995dbf774c9cdf4573d7190f8606ad2188c25a9b2`
- estado PHL/KCH v0.6.0: `d17a982e55203cdce6ffba1a2a2455260bea1df88536ac4456969ae755a07c21`
- content-set del manifiesto: `791d3933b3301c3ae0368cba9749583f61c7731982725fb97aea357a11a1f218`

## Resultados adversos preservados

1. La primera suite funcional reveló un handle SQLite no cerrado en Windows: las aserciones pasaban, pero siete limpiezas temporales fallaban con `WinError 32`. Se corrigió con cierre explícito y la implementación fallida quedó preservada.
2. El primer smoke stdio detectó tres tipos JSON Schema incorrectos en R05/R16. Un cliente estricto habría rechazado inputs semánticamente válidos. Se corrigieron, se añadieron tres regresiones y se archivaron fuera de la release el wheel y ZIP pre-fix.

Estos resultados no se borraron ni se convirtieron retrospectivamente en PASS; informaron el diseño final.

## Significado técnico, metodológico y epistemológico

KCH 0.11 resuelve la ausencia de macrorelease: existe ahora un objeto instalable que gobierna composición y evidencia sin borrar la diferencia entre KCH, CSI, KwanForks, QAS, CAS, RDSS, KwanPrompts, RGG, OBL, PHL, SCO y MIS. Los 28 controles dejan de ser sólo una lista prescriptiva y pasan a ser mecanismos invocables y auditables.

La evidencia demuestra coherencia local, integridad de transporte, fail-closed y composición read-only. No demuestra que los 28 controles mejoren causalmente el trabajo real ni que sus umbrales sean óptimos. La distinción es central: implementación contractual no equivale a eficacia empírica.

## Límites vigentes

- KwanForks continúa incompleto.
- CSI conserva cobertura puntual 15/17; OP-01 y OP-03 no se han absorbido artificialmente.
- La adjudicación funcional QAS/CAS y el adapter RDSS histórico permanecen abiertos.
- Doce emisores continúan `UNAVAILABLE_CONTRACT`.
- OBL conserva pendientes adapters nativos Codex/Cline y cero feedback histórico real.
- PHL todavía no posee primera sesión real del usuario; `feedback=0`.
- MIS conserva Luna `NOT_ESTIMABLE` y no crea autoridad.
- SCO no posee dispatch live cross-provider.
- No hay aún campaña pareada future-only, conformance TypeScript 0.11 ni réplica externa Linux de este ZIP.
- `enforced` continúa prohibido; no existe autorización de ejecución mutante.
- El inventario de licencias es evidencia de metadata, no dictamen jurídico.

## Próxima acción crítica

`KCH_0.11_REAL_SHADOW_DEPLOYMENT_GATE`

Instalar el ZIP exacto como servidor MCP local de Codex con un estado nuevo, verificar `initialize/tools/list/resources/list`, y utilizarlo en una tarea real future-only bajo perfil `agent-shadow`. Esa primera utilización debe medir fricción, bloqueos correctos, abstenciones, contaminación entre tareas, coste, completitud de comunicación y utilidad práctica, preservando todo resultado adverso. Sólo después procede decidir si iniciar PHL sobre esa experiencia, ajustar contratos o promover rutas adicionales. No procede activar `enforced`.
