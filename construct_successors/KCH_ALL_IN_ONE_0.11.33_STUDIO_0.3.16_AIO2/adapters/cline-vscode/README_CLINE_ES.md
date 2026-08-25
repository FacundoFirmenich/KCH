# KCH AIO2 para Cline en VS Code

Esta proyección usa, en orden nativo: regla persistente, 20 skills bajo demanda, ocho hooks de lifecycle, fader contractual y Super-MCP. No necesita un plugin SDK de Cline para la instalación inicial y no confunde archivos instalados con hooks observados.

## Instalación

Extraiga una sola vez el ZIP AIO2 a una ruta corta, por ejemplo `D:\KCH\AIO2`, y ejecute:

```powershell
python .\install_all_in_one.py `
  --package-root . `
  --runtime-root D:\CodexRuntimes\kch-aio1 `
  --hosts cline `
  --cline-settings "$HOME\.cline\data\settings\cline_mcp_settings.json" `
  --cline-workspace "C:\RUTA\AL\WORKSPACE" `
  --receipt-root D:\CodexRuntimes\kch-aio1-cline-receipts
```

El instalador preserva servidores MCP existentes, respalda antes de reemplazar cada regla, hook o skill homónima y emite un recibo recuperable. No instala ni modifica VS Code o la extensión Cline.

## Prueba del usuario

1. Abra el workspace en VS Code con Cline.
2. Verifique en Cline que aparecen la regla `kch-all-in-one`, las 20 skills y el servidor `kch-all-in-one-super-mcp`.
3. Active hooks si su versión de Cline ofrece ese control.
4. Inicie una tarea fresca. Debe aparecer contexto KCH de `TaskStart` y `UserPromptSubmit`.
5. Pida una lectura simple y compruebe que `PreToolUse` no la bloquea.
6. No autorice entrenamiento PHL ni micrófono: no forman parte de este smoke test.

Hasta completar esos seis pasos, el estado correcto es `PACKAGE_VALIDATED_HOST_ACTIVATION_PENDING_USER`.
