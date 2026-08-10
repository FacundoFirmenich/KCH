# Qué es y qué no es Super-MCP

## Definición operacional

Super-MCP es la frontera MCP del sistema nodriza KCH 0.11. Convierte la integración multicomponente en una interfaz auditable para clientes compatibles con MCP. Su núcleo combina:

- un registro federado canónico de 19 servicios admitidos y una entrada en cuarentena;
- una cadena de eventos append-only con verificación de integridad;
- capacidades de un solo uso, ligadas a objetivo, sesión, autoridad y caducidad;
- admisión tipada de evidencia con procedencia, rol y jurisdicción explícitos;
- 28 controles reflexivos con resultados `PASS`, `BLOCK`, `ABSTAIN` o `UNAVAILABLE`;
- adaptadores de inspección para componentes soberanos de KCH;
- recursos MCP de registro, controles, estado y auditoría.

KwanCode/CSI sigue siendo la base composicional: los subsistemas son construcciones preensambladas sobre CSI y KCH las integra y gobierna sin borrar su estructura. Super-MCP no sustituye esa base; es una de sus superficies operacionales.

## Qué preserva

- Identidad y genealogía de cada componente.
- Separación entre capacidad, permiso, soporte, autoridad y ejecución.
- Evidencia adversa, abstenciones y estados no estimables.
- Contextos nativos de SCO: la orquestación no fusiona chats ni sus memorias.
- Jurisdicción local de claims y artefactos.
- Separación entre ciencia, producto y readiness comercial.

## Qué no es

- No es todo KCH: es su gateway MCP federado.
- No es un “proyecto” clásico que vuelca el mismo contexto en todos los chats.
- No es un agente autónomo de segunda generación.
- No es un motor de ejecución mutante en KCH 0.11.
- No es prueba de despliegue productivo, seguridad total, ROI, valor de cliente o autoridad externa.
- No es una sesión PHL ni aprendizaje real por el mero hecho de exponer una proyección PHL.
- No convierte certificados históricos de MIS ni pruebas de paquetes en autoridad KCH nueva.
- No autoriza por sí solo acciones que el usuario, el host o la jurisdicción no hayan autorizado.

## Relación con subsistemas visibles

El runtime incluye adaptadores o paquetes para SCO, MIS 0.3, PHL efectivo, OBL/PHL, KwanPrompts, RGG y MIS Qualitative Bayes, además del wheel principal de KwanCode Harness. La disponibilidad de un paquete significa que puede ser cargado o inspeccionado en esta distribución; no demuestra que todas sus funciones estén expuestas por MCP ni que hayan superado gates externos.

## Techo de autoridad vigente

`agent-shadow`, rutas federadas de solo lectura, auditoría append-only y gobierno observable. El perfil `enforced` permanece prohibido hasta superar los gates correspondientes.

