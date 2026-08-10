# CHECKPOINT 08 — Super-MCP KCH 0.11: documentación y runtime portable para VS Code/Cline

## Cambio de posición

KCH queda **mejor posicionado** que en el checkpoint 07: el Super-MCP ya no sólo está desplegado en el host Codex del proyecto, sino empaquetado en dos distribuciones separadas, explicables, verificables y transportables. La portabilidad se construyó desde el ZIP canónico KCH 0.11 sellado, no desde directorios operativos susceptibles de contener estado local.

## Entregables

### 1. Paquete explicativo e instructivo

`KCH_SUPER_MCP_DOCUMENTACION_Y_USO_v0.11.0.zip`

- 19 archivos de payload verificados; 21 entradas totales contando manifiesto y seal.
- Arquitectura, taxonomía, catálogo de 49 herramientas y cuatro recursos.
- Gobierno, seguridad, autoridad, evidencia y límites de claims.
- Instalación, diagnóstico, custodia, actualización y troubleshooting.
- Guías específicas para Cline, Codex y MCP nativo de VS Code.
- Plantillas de configuración para los tres clientes.
- SHA-256: `cde9cc103b1dfe7ec4dac5dd3fcd17b856e57508cbfd586f90a90fdb4dd78f63`.

### 2. Super-MCP completo portable

`KCH_SUPER_MCP_COMPLETO_PORTABLE_v0.11.0.zip`

- 106 archivos de payload verificados; 108 entradas totales contando manifiesto y seal.
- Bundle canónico KCH 0.11 íntegro: 66/66 archivos y SHA-256 de origen `a4e08bb2833dffbfe3a3f2036579d1c8e56c20ea67ec94d4685a3618d528ee02`.
- Ocho wheels sellados: KCH más siete componentes soberanos.
- Fuentes, pruebas, registro, evidencia portable, resultados, SBOM, licencias, manifiesto y seal.
- Lanzador STDIO sin instalación global de wheels.
- Doctor portable, exportador de interfaz viva, generador y validador de configuraciones.
- Ledgers separados para Cline, Codex y VS Code.
- Documentación completa incorporada bajo `docs/full`.
- Evidencia del despliegue agent-shadow previo.
- SHA-256: `4790f768fef54c7449b748e7cbbde5b7ebb3f929be4b5a6d8df2f91c37cce19b`.

## Gates observados

1. Construcción y reextracción de ambos ZIP: `PASS`.
2. Manifiesto documental: 19/19 payloads íntegros.
3. Manifiesto runtime: 106/106 payloads íntegros.
4. Doctor desde reextracción limpia: 18/18 `PASS`.
5. Handshake MCP: servidor `kwancode-harness` 0.11.0, protocolo `2025-06-18`.
6. Interfaz viva: 49 herramientas, incluidas 28 R01–R28, y cuatro recursos.
7. Componentes: 7 disponibles, 0 no disponibles.
8. Evidencia del registro: 19 `PASS`, 0 `FAIL`, 0 `UNAVAILABLE`.
9. Perfil: `agent-shadow`; mutación no autorizada; `enforced` prohibido.
10. Configuraciones generadas: Cline, VS Code y Codex arrancaron el runtime directamente desde sus campos, 3/3 `PASS`; estados explícitos y distintos.
11. Cline conserva `autoApprove: []`; Codex conserva aprobación `prompt`.
12. Lanzador Windows `.cmd`: handshake y 49 herramientas, `PASS`.
13. PHL: sólo proyección read-only; feedback 0; sesión activa nula; bytes históricos antes/después idénticos (`d17a982e55203cdce6ffba1a2a2455260bea1df88536ac4456969ae755a07c21`).

## Resultados adversos preservados y reparación

### Longitud de rutas Windows

Dos intentos de build se cerraron antes de promoción porque una evidencia con nombre SHA-256 superó el límite de ruta al combinarse con un staging demasiado profundo. No se renombró ni alteró el artefacto. La reparación fue usar un staging corto y repetir desde cero construcción, reextracción y hashes. Consecuencia operacional: extraer el ZIP runtime en una ruta local estable y relativamente corta.

### CLI de Cline 3.0.39

El probe `cline mcp add ... -- python -X ...` rechazó `-X` como opción propia aun después de `--`. Un segundo probe con el `.cmd` no produjo un recibo verificable dentro del directorio aislado. Por ello la CLI no forma parte del gate promovido. La vía documentada y óptima es fusionar `cline_mcp_settings.json` mediante la interfaz **MCP Servers → Configure MCP Servers**; conserva argumentos, entorno, ledger propio y cero autoaprobaciones.

## Significado técnico, metodológico y epistemológico

Técnicamente existe una distribución portable real y autoauditable, no un template. Metodológicamente la portabilidad se validó desde reextracción limpia y las tres configuraciones se ejecutaron como especificaciones, separando estado por cliente. Epistemológicamente se preserva la diferencia entre integridad de bytes, disponibilidad de capacidad, permiso, autoridad y ejecución: pasar estos gates no demuestra operación dentro de cada host ni amplía la jurisdicción de los componentes.

La separación de ledger por cliente es material: evita que Cline, Codex y VS Code fusionen accidentalmente sus historiales operativos. Puede elegirse un estado compartido de forma explícita, pero no es el default y cambia la frontera de gobierno.

## Claim máximo vigente

Distribución local portable de KCH 0.11 Super-MCP validada por STDIO directo en perfil agent-shadow, con federación read-only y configuraciones ejecutables preparadas para Cline, Codex y VS Code.

## No demostrado

- Primera invocación realizada por el host Cline o por el host MCP nativo de VS Code.
- PHL real, aprendizaje post hoc efectivo o promoción.
- Ejecución mutante o perfil enforced.
- Gate Linux integral.
- Producción, VPS, multiusuario, operación remota, alta disponibilidad o seguridad total del host.
- Integración funcional completa de todas las APIs internas de los siete componentes.
- Valor comercial, pilotaje, adopción, ROI o autoridad externa.

## Próxima acción crítica

Extraer el ZIP portable en una ruta corta y estable de la máquina objetivo; ejecutar `launcher/doctor.py`; generar configuraciones absolutas; fusionar el JSON de Cline desde su interfaz; y observar dos llamadas reales: `kch.super.status` y `kch.super.registry.evidence.audit`. El gate exige perfil `agent-shadow`, mutación falsa, 49 herramientas y auditoría 19/0/0. Esta prueba no inicia PHL real.
