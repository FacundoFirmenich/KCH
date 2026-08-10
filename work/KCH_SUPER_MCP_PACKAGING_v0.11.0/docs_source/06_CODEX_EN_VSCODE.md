# Despliegue en Codex, incluido Codex en VS Code

Codex CLI y la extensión IDE comparten la configuración MCP del mismo host. La ubicación de usuario habitual es `~/.codex/config.toml`; un proyecto de confianza puede usar `.codex/config.toml` dentro del proyecto.

## Configuración recomendada por proyecto

1. Ejecute el generador de configuraciones del paquete portable.
2. Abra `generated_configs/codex_config.toml`.
3. Si el proyecto no tiene `.codex/config.toml`, copie el archivo completo.
4. Si ya existe, fusione únicamente las secciones `[mcp_servers.kch_super_mcp]` y `[mcp_servers.kch_super_mcp.env]`. No sobrescriba otros servidores.
5. Marque el proyecto como confiable sólo si conoce su contenido.
6. Reinicie la extensión de Codex o la sesión CLI para recargar MCP.

La configuración mantiene aprobaciones en `prompt`, exige el servidor (`required = true`) y usa un ledger propio de Codex.

## Verificación

Desde Codex, liste o inspeccione los servidores MCP y compruebe que `kch_super_mcp` inicia. Después pida explícitamente una llamada a `kch.super.status`. Si falla, revise stderr/salida del servidor y vuelva a ejecutar `launcher/doctor.py` fuera del cliente.

## Frontera de confianza

Una configuración de proyecto sólo debe usarse en un repositorio confiable. El archivo contiene rutas locales y puede arrancar procesos. Mantenga el runtime fuera de repositorios públicos salvo que su publicación sea deliberada y no incluya estado operativo.

Referencia oficial: https://developers.openai.com/codex/mcp/

