# KCH All-in-One 0.11.33 + Studio 0.3.16 — AIO2

Este sucesor reúne en un único paquete físico recuperable:

- los linajes nativos estables R21 y R33, preservados sin reescritura;
- una única proyección Codex activa, basada en R33, con hooks no duplicados;
- las 19 skills de gobierno R33, el nuevo fader contractual y sus cinco runtimes nativos;
- KCH Studio 0.3.16 y el Super-MCP completo;
- un adaptador Codex y un adaptador Cline para Visual Studio Code;
- wheelhouse offline, instalador transaccional, manifiesto, hashes y rollback.
- correccion verificable de la ruta marketplace a la copia realmente servida por Codex;

No incorpora, inspecciona ni modifica ninguna rama R34. Tampoco desinstala R21 o R33: AIO2 sucede a AIO1 sin reescribirlo y exige validacion en una sesion fresca.

La política es `CLOUD_FIRST_LOCAL_MINIMAL`: en local sólo se instala el runtime necesario y las proyecciones del host; el ZIP sellado es el objeto de custodia y respaldo.

## Construcción

```powershell
C:\Python314\python.exe scripts\build_all_in_one.py
```

## Instalación aislada o real

```powershell
C:\Python314\python.exe install_all_in_one.py --hosts codex cline --runtime-root <ruta> --codex-marketplace <marketplace.json> --cline-settings <cline_mcp_settings.json> --cline-workspace <workspace>
```

El instalador crea copias de seguridad antes de modificar JSON existentes, mezcla claves sin borrar servidores ajenos y puede reejecutarse idempotentemente.

En Windows, `--runtime-root` debe ser una ruta corta (recomendado: `C:\Users\<usuario>\.codex\runtimes\kch-aio1`); el instalador falla antes de crear un entorno parcial si la ruta expandida supera 180 caracteres.

El rollback es primero de solo lectura. Para inspeccionar el plan:

```powershell
python rollback_all_in_one.py --receipt <INSTALLATION_RECEIPT.json>
```

Sólo se aplica con `--apply --ack KCH-AIO2-ROLLBACK`. Restaura las proyecciones del host y conserva el runtime local como evidencia recuperable; nunca lo borra automáticamente.

## Límite Cline/Windows

En Cline para VS Code sobre Windows, las reglas y MCP sí se despliegan. Los hooks de Cline se incluyen como fuente futura, pero no se activan: el host oficial todavía declara Windows no soportado para hooks. La paridad funcional se obtiene por rules + Super-MCP + runtime + custodia, sin fingir paridad nativa inexistente.
