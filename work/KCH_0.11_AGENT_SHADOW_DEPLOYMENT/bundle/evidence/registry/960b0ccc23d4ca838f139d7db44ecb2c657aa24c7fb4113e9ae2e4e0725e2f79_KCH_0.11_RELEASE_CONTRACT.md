# Contrato canónico de macrorelease — KCH 0.11

Fecha: 2026-08-09  
Identidad arquitectónica: **KCH 0.11**  
Versión de distribución: `0.11.0`  
Clase: `CANONICAL_PRE2G_FEDERATED_MACRORELEASE`

## Objeto gobernante

KwanCode Harness (KCH) es el sistema nodriza de integración, orquestación y gobierno multicapas/multiescala. KwanCode/CSI aporta la representación composicional tipo MIDI; las herramientas KCH son construcciones preensambladas en esa representación, pero no pierden por ello su jurisdicción, estado, memoria ni techo de claims.

KCH 0.11 fija una macrorelease ejecutable común sin convertir la federación en una fusión monolítica.

## Inclusión efectiva

1. Super-MCP canónico `kwancode-harness==0.11.0` con transporte MCP stdio.
2. Doce operaciones estables: status, registry, session, evidence, context, propose, authorize, execute, precommit, rollback, outcome y audit.
3. Veintiocho controles reflexivos invocables individualmente, con receipts deterministas y estados `PASS`, `BLOCK`, `ABSTAIN` o `UNAVAILABLE`.
4. Tokens HMAC locales, acotados por objetivo, jurisdicción, operación y binding; expirantes y de un solo uso.
5. Ledger SQLite append-only con encadenamiento SHA-256, replay detectable y export verificable.
6. Rutas federadas reales de sólo lectura hacia el estado efectivo PHL/KCH, SCO, el certificado MIS v0.3.1 y el registro de evidencia.
7. Wheels soberanos de PHL, SCO, MIS, OBL/PHL, RGG y KwanPrompts transportados sin herencia implícita de autoridad.
8. Censo federado con genealogía, estados, jurisdicciones, cuarentena y copias portables de la evidencia referenciada.

## Estados preservados

- KwanForks continúa incompleto; sus releases históricos no se reinterpretan como subsistema terminado.
- CSI Operator Suite conserva cobertura puntual 15/17; OP-01 y OP-03 no se inventan dentro de esta release.
- QAS y CAS siguen siendo distintos; la rama derivada de transcripción permanece en cuarentena hasta adjudicación funcional.
- RDSS es la denominación moderna, aunque servicios históricos puedan exponer `rds.*` bajo adapter futuro.
- OBL conserva cero feedback real de usuario en su evidencia histórica y adapters nativos Codex/Cline pendientes.
- PHL conserva pendiente su primera sesión real con el usuario; su integración técnica no demuestra utilidad humana.
- MIS conserva Sol y Terra ejecutados y Luna `NOT_ESTIMABLE`; su exactitud matemática no crea autoridad KCH.
- SCO conserva `live_cross_provider_dispatch=false`; organiza chats soberanos sin fusionarlos.
- Objective Lineage y checkpoint/replay siguen siendo líneas shadow candidatas, no autoridad canónica automática.
- Los doce emisores históricos con `UNAVAILABLE_CONTRACT` permanecen explícitos.

## Perfiles y autoridad

- `minimal`: gateway, registro, ledger y controles.
- `research`: añade servicios instalados, siempre sin promoción automática.
- `agent-shadow`: añade observación y rutas read-only; es el perfil predeterminado.
- `enforced`: `PROHIBITED_UNTIL_GATES_PASS`.

KCH 0.11 no ejecuta acciones mutantes. `action.execute` sólo admite rutas read-only preregistradas, después de sesión, evidencia, controles y autorización. `rollback` registra una compensación append-only; no reescribe historia ni modifica archivos silenciosamente.

## Claim máximo admisible

`CANONICAL_PRE2G_MACRORELEASE_WITH_BOUNDED_EXECUTABLE_INTEGRATION`

Quedan fuera del claim: KCH 2G, integración completa de todo endpoint histórico, eficacia causal sobre trabajo real, superioridad frente a un control, utilidad humana general, despliegue productivo enforced, réplica externa Linux vigente, conformance TypeScript actual y dispatch live cross-provider.

## Gates de promoción aún externos

1. Primera utilización real de PHL por el usuario.
2. Campaña pareada control vs KCH 0.11 shadow sobre tareas reales future-only.
3. Réplica externa Linux del bundle exacto.
4. Conformance Python↔TypeScript y stdio↔loopback de la macrorelease 0.11.
5. Cobertura efectiva de los emisores actualmente `UNAVAILABLE_CONTRACT`.
6. Adjudicación de OP-01/OP-03, QAS/CAS y cierre real de KwanForks.
7. Validación separada antes de cualquier perfil `enforced`.
