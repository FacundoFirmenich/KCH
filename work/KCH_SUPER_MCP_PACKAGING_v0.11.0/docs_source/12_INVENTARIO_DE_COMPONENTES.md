# Inventario de componentes del paquete completo

## Wheels sellados

1. `kwancode_harness-0.11.0-py3-none-any.whl`
2. `kch_mis_v03_integration-0.1.0-py3-none-any.whl`
3. `kch_obl_phl_learning_system-0.1.1-py3-none-any.whl`
4. `kch_phl_effective_integration-0.2.0-py3-none-any.whl`
5. `kch_rigor_gradient_governor-0.1.0-py3-none-any.whl`
6. `kch_superchats_orchestrators-0.1.0-py3-none-any.whl`
7. `kwanprompts-0.1.0-py3-none-any.whl`
8. `mis_qualitative_bayes-0.3.1-py3-none-any.whl`

El primero implementa el gateway y servidor MCP; los siete restantes son paquetes soberanos federados o inspeccionados. Un wheel presente no equivale a integración funcional total de todas sus APIs.

## Contenido canónico incorporado

- `bundle/src`: fuentes del runtime KCH 0.11.
- `bundle/tests`: pruebas canónicas.
- `bundle/dist` y `bundle/vendor`: distribución ejecutable.
- `bundle/config`: registro federado canónico.
- `bundle/evidence`: evidencia portable y proyecciones verificables.
- `bundle/results`: resultados de gates canónicos.
- `bundle/scripts`: verificadores de bundle e instalación.
- `bundle/MANIFEST_SHA256.json` y `bundle/SEAL_KCH_0.11.json`: custodia de integridad.
- `bundle/SBOM_CYCLONEDX_v0.11.0.json`: inventario de software.
- licencias, preregistro y contrato de release.

## Capa portable añadida

- `launcher/run_super_mcp.py`: inicio sin instalar wheels globalmente.
- `launcher/doctor.py`: gate del paquete reextraído y transporte MCP.
- `launcher/generate_client_configs.py`: configuraciones con rutas absolutas.
- `config_templates`: plantillas editables y sin autoaprobación.
- `runtime/state`: estado nuevo por cliente; se crea al usarlo.
- `validation_evidence`: recibos del despliegue agent-shadow ya alcanzado.
- `canonical`: copia del ZIP canónico KCH 0.11 para custodia.

