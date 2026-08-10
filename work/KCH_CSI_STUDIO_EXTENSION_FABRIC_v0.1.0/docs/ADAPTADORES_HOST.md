# Adaptadores de host

`INSTALL_KCH.cmd` crea el runtime en una ruta corta y persistente y escribe las rutas efectivas en `runtime_paths.cmd`. A continuación genera `adapters_runtime/*.json`. Las plantillas de `adapters/` contienen marcadores; los archivos de `adapters_runtime/` son los utilizables.

- **VS Code:** integrar `vscode.mcp.json` como configuración MCP del workspace o del usuario.
- **Cline:** fusionar `cline_mcp_settings.json` dentro de `mcpServers`. `autoApprove` permanece vacío para no saltar los gates KCH ni los del host.
- **OpenCode:** fusionar `opencode.json` bajo `mcp.servers`.
- **Codex:** usar la referencia de plugin y el comando Super‑MCP generados; la activación concreta depende de la superficie Codex instalada.

No se escribe automáticamente en configuraciones externas. No hay claves ni tokens en plantillas, recibos o adaptadores. Las cuentas se solicitan mediante leases finitos y se autentican después por terminal o, sólo si el proveedor lo exige, navegador.

La equivalencia funcional entre hosts no se presume. Cada proyección debe verificar soporte, permisos, transporte, procedencia y límites de autoridad.

Todo adaptador operativo debe arrancar llamando `kch_preflight` y rechazar como condición integral cualquier sustitución por una clase interna. La enumeración completa de chats, la lectura autenticada hasta EOF, la telemetría de cuota y el traspaso/archivo de tareas requieren conectores nativos específicos del host. La minisuite puede custodiar los payloads y preparar packets; no afirma haber ejecutado esas acciones externas sin recibo del conector.

Antes de cada contestación redactada, el adaptador debe llamar `response_mode_contract` con los identificadores disponibles de workspace, SCO, tarea, sesión y mensaje e inyectar la instrucción devuelta. Después de completar la acción debe llamar `response_execution_register` para guardar la ficha Markdown separada y añadir al chat exclusivamente la línea `final_notice`. El adaptador no debe ofrecer esa ficha ni mezclarla con la explicación principal.

La restricción de pantallas y scrolls sólo puede verificarse cuando el host expone dimensiones y altura renderizada. Sin esas métricas, el adaptador debe aplicar el perfil semánticamente y declarar `HOST_RENDERER_MEASUREMENT_REQUIRED`, nunca inventar una medición de viewport.
