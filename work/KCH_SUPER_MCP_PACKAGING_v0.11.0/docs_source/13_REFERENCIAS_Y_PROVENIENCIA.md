# Referencias y proveniencia

## Fuentes técnicas locales canónicas

El paquete explicativo se derivó de la macrorelease canónica KCH 0.11, en particular:

- `README.md` y `RELEASE_CONTRACT_v0.11.0.md`;
- `src/kwancode_harness/mcp_server_base.py`;
- `src/kwancode_harness/gateway.py`;
- `src/kwancode_harness/controls.py`;
- `config/KCH_REGISTRY_v0.11.0.json`;
- manifiesto, seal, SBOM, resultados y evidencia portable.

La entrega completa conserva esos archivos dentro de `bundle`, de modo que la explicación pueda contrastarse con el runtime real.

## Documentación oficial de clientes

- Codex MCP: https://developers.openai.com/codex/mcp/
- Cline MCP: https://docs.cline.bot/mcp/mcp-overview
- Configuración MCP de VS Code: https://code.visualstudio.com/docs/agents/reference/mcp-configuration
- Servidores MCP en VS Code: https://code.visualstudio.com/docs/agent-customization/mcp-servers

Estas fuentes sostienen la forma de las configuraciones de cliente. No sostienen claims propios de KCH.

## Regla de precedencia

Para comportamiento ejecutable, prevalecen el código, los esquemas MCP, el registro y los artefactos sellados de KCH 0.11. Esta documentación explica la release, pero no debe usarse para ampliar su autoridad ni para corregir retrospectivamente evidencia histórica.

