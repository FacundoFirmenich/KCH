# KCH CSI Self-Governance v0.1.0

Fundación ejecutable preinstalación para gobernar KCH mediante la jerarquía `HARNESS.md > AGENTS.md > RULES.md` y compilarla a un grafo KwanCode/CSI y proyecciones conscientes de pérdidas para hosts concretos.

Esta capa no modifica KCH 0.11, no instala extensiones, no habilita perfiles enforced y no ejecuta PHL real.

## Comandos

```powershell
$env:PYTHONPATH='work\KCH_CSI_SELF_GOVERNANCE_v0.1.0\src'
python -m kch_self_governance validate work\KCH_CSI_SELF_GOVERNANCE_v0.1.0\governance
python -m kch_self_governance compile work\KCH_CSI_SELF_GOVERNANCE_v0.1.0\governance work\KCH_CSI_SELF_GOVERNANCE_v0.1.0\dist
```

La salida Codex aplana los agentes en un `AGENTS.md` de host, pero conserva el grafo soberano por separado. `RULES.md` no se traduce indebidamente a `.rules`: sólo reglas de comandos declaradas de forma exacta pueden entrar en ese subconjunto.

El Studio visual y Extension Fabric están especificados en `docs/`; aún no están implementados.
