# Matriz de compatibilidad

| Capacidad | Codex | Cline / VS Code en Windows |
|---|---|---|
| Skills KCH | Nativa, 20 skills | Regla de proyecto equivalente |
| Hooks KCH | Nativos, 6 eventos | Diferido: host no soporta hooks en Windows |
| Studio | MCP de preflight + bootstrap | Super-MCP directo |
| Runtimes R33 | Plugin local | Runtime compartido instalado |
| Custodia y rollback | Sí | Sí |
| Llaves | Nativas mediante hooks | Gobernadas mediante Super-MCP/rules; no se simula interposición nativa |
| PHL | Autorizado, no entrenado | Autorizado, no entrenado |

Referencias de host consultadas durante el diseño:

- https://docs.cline.bot/mcp/configuring-mcp-servers
- https://docs.cline.bot/features/cline-rules
- https://github.com/cline/cline/blob/main/.clinerules/hooks/README.md
