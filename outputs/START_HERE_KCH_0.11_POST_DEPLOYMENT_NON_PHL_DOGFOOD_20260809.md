# START HERE — KCH 0.11 después del despliegue real `agent-shadow`

## Estado canónico inmediato

- Macrorelease: `KCH 0.11`, paquete `0.11.0`.
- MCP de proyecto: `kch_0_11`, habilitado y requerido.
- Transporte activo: Python directo, `stdio` UTF-8.
- Gate directo: 37/37 PASS.
- Validación instalada: 13/13 PASS.
- Bundle canónico: 66/66 PASS.
- Host Codex: descubrimiento y llamada real a `kch.super.status` PASS.
- Perfil: `agent-shadow`; ejecución mutante: falsa; `enforced`: prohibido.
- PHL real: no ejecutado, congelado por decisión del usuario; feedback 0; sesión activa `null`; hash de estado inmutable.

## Leer primero

1. `CHECKPOINT_07_KCH_0.11_DESPLIEGUE_REAL_AGENT_SHADOW_SIN_PHL_20260809.md`.
2. `KCH_0.11_AGENT_SHADOW_EVIDENCE_PACKAGE_SEAL_v0.1.0.json`.
3. `work/KCH_0.11_AGENT_SHADOW_DEPLOYMENT/results/KCH_0.11_REAL_SHADOW_DEPLOYMENT_GATE_RESULT.json`.
4. `work/KCH_0.11_AGENT_SHADOW_DEPLOYMENT/results/CODEX_HOST_TRANSPORT_RECEIPT_v0.3.0.json`.

## Siguiente gate

Ejecutar dogfooding longitudinal **no-PHL** desde nuevas tareas reales de Codex: casos acotados y heterogéneos que usen KCH 0.11 para gobernar rutas SCO, MIS, KwanPrompts y RGG bajo `agent-shadow`, preservando soberanía de cada chat y registrando PASS, BLOCK, ABSTAIN, UNAVAILABLE, coste y defectos de transporte.

No activar PHL, no habilitar `enforced`, no autorizar mutación y no promover controles por mera disponibilidad. La decisión posterior será si la evidencia longitudinal permite ampliar rutas gobernadas; PHL queda para el último gate señalado por el usuario.
