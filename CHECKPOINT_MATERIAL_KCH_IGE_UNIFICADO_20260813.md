# Checkpoint material — integración unificada IGE/KCH

Fecha: 2026-08-13  
Estado: **mejor posicionado; sucesor CSI ejecutable y compuesto localmente con KCH R21, todavía no promovido a estable**.

## Resultado sustantivo

Los dos adjuntos contienen una contribución real: modelar la ambigüedad de instrucciones mediante conjuntos credales, conservar la incomparabilidad, abstenerse ante riesgo y preguntar de manera adaptativa. No son, sin embargo, una implementación directamente integrable en KCH: convierten autoridad en una variable probabilística, separan persistencia y ledger en commits distintos, colapsan el posterior a una envolvente intervalar para actualizaciones posteriores, usan una fidelidad 0.8 no calibrada, desempatan lexicográficamente, exponen una API sin autenticación y presentan T1–T7 «cubiertos» con evidencia exclusivamente unitaria y declarativa.

KCH R21 ya tenía las capas que IGE trataba de recrear: `HARNESS > AGENTS > RULES`, constitución user-sovereign, políticas programadas, permisos, llaves, continuidad, response-authority y ledgers con límites de claim. Por eso la integración superadora no es una segunda constitución: es una capa credal subordinada que sólo opera dentro de una autoridad dura previamente atestada.

## Fuentes leídas y contrastadas

- Adjunto IGE v0.1: 32.405 bytes, 842 líneas físicas, SHA-256 `3e97d2f20eb4f6753e67bb91b38b07a2d6ca438e8054e707d0d8b37599361bc3`.
- Adjunto IGE v0.2: 37.044 bytes, 915 líneas físicas, SHA-256 `421e4bcf00d289eeec64f0a0174fb833a5738e7ec375229c9ed75d1e51d9c649`.
- Trece archivos vigentes de KCH 0.11, CSI Studio y proyección nativa R21 fueron inspeccionados y hasheados. El inventario exacto está en `construct_successors/KCH_IGE_UNIFIED_v0.3.0/EVIDENCE_MANIFEST.json`.

## Integración construida

El sucesor `KCH_IGE_UNIFIED_v0.3.0` implementa:

1. Precedencia determinista externa/KCH que la inferencia credal no puede alterar.
2. Instrucciones versionadas con autoridad atestada, jurisdicción, scopes, recursos, operaciones, excepciones, dependencias, supersesión, vigencia, lifecycle, procedencia y evidencia.
3. Un espacio credal de 100 celdas reinterpretado como fuerza del mandato, alcance y riesgo dentro de una misma capa dura.
4. Condicionamiento generalizado exacto respecto del politopo base mediante Charnes–Cooper; las cotas marginales son sólo proyecciones de reporte.
5. Resoluciones tipadas: `APPLY`, `BLOCK`, `ASK_USER`, `ABSTAIN`, `NOT_APPLICABLE`, `NOT_ESTIMABLE`, `CONFLICT_SET`.
6. Elicitación sin likelihoods inventadas: sin calibración queda `NOT_ESTIMABLE`; con calibración se usa contracción minimax de imprecisión decisional por coste.
7. Store, evento y recibo idempotente en una única transacción SQLite `BEGIN IMMEDIATE`, con verificación de cadena y reconstrucción de proyecciones.
8. Contexto compilado sólo desde un `APPLY`, transportado como JSON marcado como datos y sin claim de inmunidad a prompt injection.
9. Composición nativa pre-start mediante `extra_handlers`/`extra_tools`; el bind posterior se prohíbe para no eludir PHL ni llaves.
10. Un clasificador conservador READ/MUTATE que resuelve el falso positivo observado: una lectura simple protegida no es una mutación; comandos compuestos o desconocidos siguen cerrando en modo seguro.

## Gates ejecutados

- Pytest: **30/30 PASS**.
- Ruff: **PASS**.
- Compilación Python: **PASS**.
- Wheel: construido e instalado de forma aislada, **PASS**.
- Smoke del wheel: `WHEEL_RELEASE_SMOKE_PASS 0.3.0 7`.
- Composición con `kch_studio.advanced_runtime.KCHAdvancedRuntime`: **PASS**.
  - 7/7 operadores presentes.
  - 3/3 operadores mutantes envueltos por llaves.
  - PHL catalogó las capacidades; entrenamiento PHL ejecutado: `false`.
  - Capacidades sueltas del launcher: ninguna.
  - MCP usado: `false`.
- SHA-256 del wheel final: `0bf7cbb9aa3ad41dde316749caddbdb716bd159afd70dcfb3a21300f3755dc11`.
- SHA-256 lógico del manifiesto: `4c3c758f2d8f584b56512e49f2fd02fcdaf27cd3eeea6d7dee4485bd90edfa53`.

## Evidencia adversa preservada

1. La primera suite dio 5 PASS y 12 errores de setup porque el directorio temporal global de Pytest no era accesible. El relanzamiento con `--basetemp` local ejecutó toda la suite; no se reetiqueta el primer resultado como éxito.
2. `python -m build` no estaba disponible. Se construyó con `pip wheel --no-deps --no-build-isolation`, sin red; la ausencia del módulo queda registrada como `UNAVAILABLE`.
3. La proyección nativa de llaves bloqueó una lectura de una skill protegida. La causa está localizada: el hook compara recursos protegidos sin distinguir operación de lectura frente a mutación. El candidato añade clasificación conservadora y diez pruebas específicas, pero la corrección estable aún no se ha promovido.

## Qué queda demostrado y qué no

Queda demostrado un kernel local ejecutable, transaccional, instalable y composable durante el arranque real de KCH R21. Quedan refutados o rebajados los claims de IGE sobre atomicidad separada, append-only físico, posterior intervalar exacto para secuencias, EIG estándar y cobertura industrial T1–T7.

No queda demostrado: promoción estable; recepción nativa emitida por Codex/Cline; eficacia longitudinal; seguridad multiusuario; anclaje externo de ledger; calibración empírica de likelihoods; inmunidad a prompt injection; prevención universal de perjuicios. PHL continúa autorizado pero no entrenado ni ejecutado realmente.

## Próxima acción crítica

La próxima acción es una promoción exacta gobernada por llaves, no más diseño abierto. El contrato está en `construct_successors/KCH_IGE_UNIFIED_v0.3.0/PROMOTION_CONTRACT.json`: injertar el paquete en CSI Studio, componerlo antes de PHL/locks, corregir READ/MUTATE en el hook nativo y ejecutar una tarea desechable con recibos reales de `SessionStart -> UserPromptSubmit -> PreToolUse(read permitido) -> PreToolUse(mutación bloqueada) -> PostToolUse -> Stop/SessionEnd`.

La promoción requiere el gesto local exacto del usuario para cada mutación protegida. No se ha solicitado ni simulado esa autorización y la versión estable permanece intacta.
