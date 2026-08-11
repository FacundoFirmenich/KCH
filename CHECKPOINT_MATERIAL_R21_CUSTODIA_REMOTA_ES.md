# Checkpoint material — KCH 0.11 R21: custodia remota de llaves constitucionales

## Posición del proyecto

KCH queda mejor posicionado que en R20: la nueva capa garantista ya no es solamente un diseño ni código fuente local. R21 fue compilado, sometido a gates de fuente, instalado desde su ZIP en un destino limpio, probado funcionalmente desde esa instalación y respaldado en dos custodias remotas diferenciadas.

## Qué se consiguió

Las llaves constitucionales permiten bloquear recursos modificables mediante reglas `EXACT`, `PREFIX` o `GLOB`. Ante un cambio interceptado por KCH, el agente no puede saltarse el bloqueo por consentimiento general de sesión: debe producir una propuesta exacta que explique motivo, impacto, recurso, operación, hash previo, hash propuesto y payload completo. Sólo una autorización de usuario por interfaz confiable genera una llave de un uso; cambiar argumentos invalida el intento y no consume la autorización legítima.

La capa está integrada transversalmente en el runtime avanzado, el modo Construct, la superficie operacional, la interfaz visual y la jerarquía `HARNESS > AGENTS > RULES`. El modo es opcional y viene apagado: esto conserva la libertad del usuario y evita imponer una política garantista a quien no la active.

## Evidencia ejecutable

- Suite de fuente: 102/102 pruebas y Ruff en estado `PASS`.
- Gobernanza compilada: 23 nodos, 7 agentes y 13 reglas.
- Instalación limpia A2: `PASS_BOUNDED`, 22/22 etapas.
- Superficie instalada: 294 herramientas combinadas; 41 clases estratégicas y 285 métodos públicos clasificados.
- Gate semántico instalado: bloqueo pese a `ALWAYS_THIS_SESSION`, ausencia de autorización por MCP/modelo, rechazo de argumentos alterados, consumo atómico único, rechazo de reutilización y cadena de hashes válida.
- Concurrencia: una única autorización ganadora frente a 16 intentos.
- PHL permanece autorizado pero no entrenado ni ejecutado realmente.

## Custodia

El repositorio `FacundoFirmenich/KCH` fue verificado como `PRIVATE`. Su rama `main` remota coincide con el commit local `7d95a38017cf64a3a272f0a032da5936284cac65`; el árbol quedó limpio tras el push. El manifiesto de custodia cubre 160 archivos y 112.317.779 bytes.

La carpeta KCH de Google Drive contiene el ZIP canónico y ocho piezas de evidencia R21. Drive confirmó nombres, tipos, capacidad de descarga y tamaños exactos; el ZIP remoto mide 22.231.435 bytes y tiene referencia de descarga íntegra. El conector no expuso digest remoto: el SHA-256 `98ba1faa4c63302f67ec386b9ecf684762e7923febc3039cd8c201a024091b54` corresponde a los bytes locales efectivamente entregados al cargador, pero no se presenta fraudulentamente como recomputación independiente dentro de Drive.

## Evidencia adversa preservada

No se borraron los fallos intermedios. Quedan registrados el error inicial de esquema de gobernanza, el bloqueo SQLite anidado en PHL, el conteo obsoleto de pestañas, el agotamiento de almacenamiento del supervisor durante el primer gate completo y el `KeyError` del primer post-install. Cada defecto fue localizado, corregido y revalidado; ninguno se transforma retroactivamente en un pase.

## Límite de claims

R21 demuestra coherencia interna, portabilidad acotada y funcionamiento de la interposición bajo las rutas gobernadas por KCH. No demuestra que pueda impedir escrituras externas que evadan KCH, ni integración real en VS Code/Cline, ni robustez industrial universal, ni eficacia de PHL real.

## Próxima acción crítica

La próxima acción crítica ya no es añadir otra abstracción: es desplegar R21 en un host real VS Code/Cline de forma reversible y acotada, verificar que las mutaciones reales pasan por la interposición constitucional y comprobar la experiencia de propuesta/autorización/ejecución. PHL real continúa reservado para el final.

No se realizó limpieza ni eliminación local.
