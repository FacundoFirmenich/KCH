# Despliegue en Cline dentro de Visual Studio Code

## Método visual recomendado

1. Abra Cline en VS Code.
2. Pulse el icono **MCP Servers**.
3. Elija **Configure MCP Servers**.
4. Abra `generated_configs/cline_mcp_settings.json` producido por el generador.
5. Fusione el objeto `kch-super-mcp` dentro del objeto `mcpServers` existente. No reemplace otros servidores.
6. Guarde el archivo y reinicie el servidor desde la interfaz de Cline si no se recarga automáticamente.
7. Verifique que la herramienta figure como conectada y que Cline descubre 49 herramientas.

La plantilla usa `autoApprove: []`. Manténgalo vacío hasta haber observado y entendido las llamadas reales. `disabled: false` habilita el servidor, pero no autoaprueba sus herramientas.

## Por qué se recomienda el JSON y no `cline mcp add`

La CLI de Cline 3.0.39 observada ofrece `cline mcp add`, pero su parser rechazó el argumento Python `-X` incluso después del separador `--`, y un segundo probe con el `.cmd` no produjo un recibo verificable de configuración dentro del directorio aislado. Por rigor, ese camino no forma parte del gate de esta entrega.

Use la interfaz visual y fusione el JSON generado. Esa forma conserva `args`, `env`, el ledger propio de Cline y `autoApprove: []`. Una aceptación sintáctica tampoco bastaría: el gate empírico pendiente es observar desde Cline una llamada real a `kch.super.status`.

## Prueba inicial en Cline

Pida a Cline que invoque únicamente `kch.super.status` y muestre el resultado sin ejecutar otras herramientas. Confirme el perfil `agent-shadow`, la prohibición de mutación y el gate del ledger. Luego ejecute la auditoría del registro.

## Fallos frecuentes

- **Server disconnected**: ejecute `launcher/doctor.py`; revise ruta de Python y del lanzador.
- **No tools found**: reinicie el servidor/extensión y confirme que stdout no está siendo usado para logs.
- **Ruta inválida después de mover la carpeta**: regenere configuraciones; contienen rutas absolutas.
- **Estado inesperadamente compartido**: compruebe `KCH_011_STATE` y use el ledger específico de Cline.
- **Aprobaciones silenciosas**: verifique que `autoApprove` siga vacío.

Referencia oficial: https://docs.cline.bot/mcp/mcp-overview
