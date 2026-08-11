# CHECKPOINT 16 — KCH R15 prospectivo: recibo portable completo

Fecha: 2026-08-11

## Qué cambió

Se corrigió prospectivamente el único defecto de inventario conocido de R14. El bootstrap portable ya no enumera sólo `*.json`: el contrato declara explícitamente y verifica seis adaptadores (`AGENTS_KCH.md`, `cline_mcp_settings.json`, `codex-plugin-reference.json`, `codex.config.toml`, `opencode.json` y `vscode.mcp.json`). Si falta cualquiera, la instalación falla cerradamente en vez de producir un recibo incompleto.

R14 no fue modificado. La corrección vive en la rama `agent/kch-r15-portable-receipt`, commit `0ba011f`.

## Verificación

- Gate focal: 11/11 pruebas.
- Regresión completa: 68/68 pruebas en 210.88 s.
- Artefacto construido: `KCH_0.11_PRE2G_INTEGRATED_CANDIDATE_R15.zip`.
- Bytes: 22,115,016.
- SHA-256: `c6818fa4e62bb52697b30360db20b7859586b75ca1abeb81c67f13b869fed403`.
- Extracción limpia: 259 archivos; hash estructural `c22f46e7247964ad6404544ca0061c92878b2a0f6b65817728023b3c805af1c9`.
- Instalación aislada: `INSTALL_COMPLETED`.
- Postinstall integral: 19/19 gates, 277 herramientas completas, broker de 5 y preflight de sólo lectura de 1.
- El recibo instalado enumera exactamente los seis adaptadores declarados.
- Advertencia no funcional: pytest no pudo escribir su caché local; no afectó ninguna prueba.
- Dos corridas previas en temporales administrados por el sandbox fallaron en setup/ACL y se preservan como incidencias de infraestructura, no como fallos del producto.
- Una corrida intermedia ejecutó 10/11 y falló transitoriamente en el preflight integrado bajo el árbol con ACL defectuosa; la inspección directa devolvió `PASS` y la corrida limpia corta aprobó 11/11 y después 68/68.

## Significado y límites

La mejora elimina una discrepancia entre archivos realmente generados y archivos declarados por el recibo, aumentando trazabilidad y capacidad de recuperación. No añade una nueva capacidad operativa, no valida hosts externos y no cambia el techo de claims de R14. No hubo PHL real.

## Próxima acción crítica

R15 queda sellable como candidato portable local. La próxima acción crítica es el gate multi-tarea de replicación del auto-preflight y los pares históricos con/sin KCH. La condición no es que el MCP aparezca: debe gobernar la ejecución y reducir fallos concretos predeclarados sin introducir restricciones inventadas. PHL real continúa reservado para el final.
