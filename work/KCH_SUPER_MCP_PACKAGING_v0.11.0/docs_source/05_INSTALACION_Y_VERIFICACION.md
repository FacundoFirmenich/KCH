# Instalación y verificación

## 1. Extraer sin alterar la estructura

Extraiga `KCH_SUPER_MCP_COMPLETO_PORTABLE_v0.11.0.zip` en una ruta local estable. Evite mover sólo el lanzador: éste resuelve `bundle`, `runtime` y `config_templates` relativamente a la raíz extraída.

Ejemplo PowerShell:

```powershell
Expand-Archive -LiteralPath .\KCH_SUPER_MCP_COMPLETO_PORTABLE_v0.11.0.zip -DestinationPath C:\Tools\KCH-Super-MCP-0.11
```

## 2. Comprobar Python

```powershell
python --version
```

Se requiere Python 3.11 o posterior. El paquete no necesita `pip install` para arrancar.

## 3. Ejecutar el doctor

Desde la raíz extraída:

```powershell
python -X utf8 .\launcher\doctor.py --output .\runtime\doctor_result.json
```

El gate debe terminar en `PASS`. Verifica el manifiesto canónico de 66 archivos, los ocho wheels, el handshake MCP, 49 herramientas, 28 controles, cuatro recursos, siete paquetes soberanos, 19 evidencias del registro, integridad del ledger y la inmutabilidad de la proyección PHL.

Un `PASS` prueba portabilidad local por STDIO bajo esas comprobaciones; no prueba uso real dentro de todos los clientes ni gates externos.

## 4. Generar configuraciones absolutas

```powershell
python -X utf8 .\launcher\generate_client_configs.py --output-dir .\generated_configs
```

El generador no sobrescribe archivos existentes salvo que se suministre `--force`. Revise siempre los tres archivos antes de integrarlos en configuraciones que ya contengan otros servidores.

Valide las configuraciones generadas:

```powershell
python -X utf8 .\launcher\validate_client_configs.py --config-dir .\generated_configs --output .\runtime\client_config_gate.json
```

Este gate arranca el runtime desde los campos de cada archivo y exige 49 herramientas, cuatro recursos, `agent-shadow`, mutación desactivada y tres ledgers distintos. No afirma que los tres hosts hayan realizado ya una llamada real.

## 5. Elegir un cliente

- Cline: `07_CLINE_EN_VSCODE.md`.
- Codex: `06_CODEX_EN_VSCODE.md`.
- MCP nativo de VS Code: `08_VSCODE_MCP_NATIVO.md`.

## 6. Primera verificación dentro del cliente

1. Confirme que aparecen 49 herramientas.
2. Invoque `kch.super.status`.
3. Confirme `profile = agent-shadow`.
4. Confirme que `mutating_execution_authorized = false`.
5. Invoque `kch.super.registry.evidence.audit` y exija 19 `PASS`, 0 `FAIL`, 0 `UNAVAILABLE`.
6. Invoque `kch.phl.projection` sólo para leer; no existe herramienta de inicio PHL.

## 7. Desinstalación reversible

Retire únicamente la entrada `kch-super-mcp`/`kch_super_mcp`/`kchSuperMcp` de la configuración del cliente. El runtime y sus ledgers permanecen en la carpeta extraída hasta que el usuario decida archivarlos o eliminarlos.
