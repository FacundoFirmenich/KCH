# Frontera del paquete portable

Este paquete inicia el Super-MCP real de KCH 0.11 directamente desde ocho wheels sellados. Incluye fuentes, pruebas, registro, evidencia portable, manifiestos y recibos. No instala dependencias globales ni modifica configuraciones de usuario por sí solo.

El estado operativo nuevo vive en `runtime/state`. El bundle canónico bajo `bundle` debe permanecer inalterado. Cada cliente generado usa su propio ledger.

Techo: despliegue local STDIO, perfil agent-shadow, federación read-only. No prueba PHL real, enforced, mutación, producción, seguridad total ni valor comercial.

