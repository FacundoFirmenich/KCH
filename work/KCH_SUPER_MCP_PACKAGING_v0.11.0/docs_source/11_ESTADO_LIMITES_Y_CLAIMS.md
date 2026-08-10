# Estado, límites y claims de KCH 0.11 Super-MCP

## Demostrado en la release canónica y su despliegue shadow

- Bundle canónico KCH 0.11 sellado y verificable.
- Servidor MCP local por `stdio`.
- 49 herramientas y cuatro recursos declarados.
- 28 controles reflexivos individualmente invocables.
- Registro federado de 19 servicios admitidos más una entrada en cuarentena.
- Ocho wheels transportables: KCH y siete componentes.
- Perfil `agent-shadow` con mutación prohibida.
- Ejecución federada limitada a rutas read-only autorizadas.
- Cadena local append-only con gate de integridad.
- Proyecciones read-only de PHL y SCO y verificación del certificado MIS.
- Despliegue real previo en el host Codex del proyecto, con estado PHL inalterado.

## Lo que este empaquetado añade

- Portabilidad sin instalación global de wheels.
- Diagnóstico reproducible desde una extracción nueva.
- Configuraciones con rutas absolutas para Cline, Codex y VS Code.
- Separación de ledger por cliente.
- Documentación de despliegue, uso, gobierno, custodia y límites.

## No demostrado

- Una sesión PHL real, aprendizaje post hoc efectivo o promoción derivada.
- Integración funcional completa de todas las APIs internas de cada componente.
- Ejecución mutante gobernada.
- Perfil `enforced`.
- Seguridad completa del host/IDE/modelo/extensiones.
- Operación en producción, VPS, multiusuario, remota o de alta disponibilidad.
- Validación de cliente Cline en todas sus versiones y sistemas; una configuración aceptada no equivale a uso empírico prolongado.
- Gate Linux completo.
- Valor comercial, ROI, pilotaje, adopción o autoridad institucional.
- Agente autónomo de segunda generación.

## Claim máximo responsable del ZIP portable

“Distribución local portable de KCH 0.11 Super-MCP, validada por transporte STDIO directo en perfil agent-shadow, con federación read-only y configuraciones preparadas para Cline, Codex y VS Code.”

No añada “productivo”, “autónomo”, “seguro”, “enforced”, “aprende” o “desplegado en Cline” sin la evidencia específica correspondiente.

## Próximo gate empírico

Después de extraer en la máquina objetivo: ejecutar el doctor, integrar una configuración en el cliente elegido, observar una llamada real a `kch.super.status` y una auditoría del registro, y conservar sus recibos. PHL real permanece fuera de ese gate.

