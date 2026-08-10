# Despliegue con MCP nativo de Visual Studio Code

VS Code admite un archivo `.vscode/mcp.json` de proyecto con un objeto superior `servers`.

## Instalación

1. Genere `generated_configs/vscode_mcp.json`.
2. Revise las rutas absolutas y el entorno.
3. Si no existe `.vscode/mcp.json`, copie el generado.
4. Si existe, fusione sólo `servers.kchSuperMcp`.
5. Acepte la confianza del servidor únicamente para este runtime verificado.
6. Use **MCP: List Servers** para comprobar estado y **MCP: Show Output** para diagnosticar.

El runtime se inicia por `stdio`, con working directory igual a la raíz extraída y un ledger diferente de Cline y Codex.

## Seguridad específica en Windows

La documentación actual de VS Code indica que el sandbox de servidores MCP no está disponible en Windows. El paquete KCH sigue bloqueando ejecución mutante en su propia capa, pero eso no convierte al host entero en un sandbox. Mantenga el runtime en una ruta confiable, no agregue comandos auxiliares y revise cambios de configuración.

Referencias oficiales:

- https://code.visualstudio.com/docs/agents/reference/mcp-configuration
- https://code.visualstudio.com/docs/agent-customization/mcp-servers

