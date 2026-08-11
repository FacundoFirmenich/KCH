# Checkpoint material — KCH 0.11 R21, llaves constitucionales

Fecha: 2026-08-11  
Estado: `PASS_BOUNDED`

## Resultado sustantivo

KCH queda mejor posicionado que en R20: ya puede ofrecer un modo garantista opcional en el que el usuario bloquea recursos u operaciones modificables y obliga al agente a advertir el bloqueo, explicar el cambio pretendido y esperar una autorización local exacta. La autorización no es un permiso genérico: queda ligada a la llave, el recurso, la operación, la preimagen, los argumentos completos y el resultado pretendido, se consume antes del intento y sólo sirve una vez.

El modo viene apagado. Sólo la frontera local confiable del usuario puede activarlo, crear o desactivar llaves y autorizar propuestas. Esos métodos no están expuestos como herramientas MCP. Un consentimiento ordinario `ALWAYS_THIS_SESSION`, un permiso general, la automatización, RUN o CONSTRUCT no atraviesan una llave activa.

## Integración efectiva

- Motor durable SQLite con llaves `EXACT`, `PREFIX` y `GLOB`, propuestas, autorizaciones de un uso y eventos encadenados por hash.
- Interposición sobre las herramientas mutantes del runtime, las mutaciones directas de UI y las escrituras de CONSTRUCT antes de modificar bytes.
- Pestaña visual **Llaves de bloqueo** para control local, propuestas pendientes, autorización exacta y verificación de deriva.
- Gobernanza compilada `HARNESS > AGENTS > RULES`: 23 nodos, 7 agentes y 13 reglas. El nuevo agente es `AGENT-CONSTITUTIONAL-LOCK-GOVERNOR` y la regla es `RULE-CONSTITUTIONAL-LOCK-KEYS`.
- Detección de deriva externa para archivos exactos con línea base. KCH no afirma impedir una escritura externa que eluda todas sus superficies.

## Evidencia ejecutada

- Suite fuente final: 102/102 pruebas, Ruff PASS, cero relanzamientos y fuente idéntica antes/después. Recibo sellado interno: `5a751abb0c963fdede9a861064959cdef3be04244cce8651baae75cc1f979e7d`.
- Carrera concurrente: exactamente un ganador entre 16 consumos simultáneos de la misma autorización.
- Instalación portable fresca A2: `INSTALL_COMPLETED`, sin configuración externa de hosts, credenciales ni micrófono.
- Gate postinstalación: 22/22, 294 herramientas combinadas, preflight canónico PASS, superficie estratégica PASS, MIS 480 registros/60 ledgers y autoridad experimental no creada.
- Gate funcional instalado: `ALWAYS_THIS_SESSION` quedó bloqueado; una mutación alterada fue rechazada sin consumir; la mutación exacta se ejecutó una vez; el reuso se rechazó; cadena de hashes PASS.
- PHL permanece autorizado, no entrenado y no ejecutado en toda la campaña R21.

## Evidencia adversa preservada

1. El intento integral 01 alcanzó 102 tests aprobados, pero su supervisor no pudo cerrar SQLite porque C llegó a cero bytes libres; Ruff no se ejecutó. Se conserva como `FAIL_SUPERVISOR_STORAGE_EXHAUSTED`, no como PASS. Los intentos posteriores trasladaron monitor y temporales a D sin borrar datos.
2. La primera instalación R21 completó transporte, preflight, workbench y MIS, pero el gate buscó erróneamente `locks` en la raíz del status en vez de `components.locks`. Se conserva como fallo de observabilidad del gate. La fuente se corrigió, se revalidó por completo y se reconstruyó una instalación nueva A2; no se recicló la instalación fallida.

## Candidato canónico y límites

Archivo: `work/KCH_CSI_STUDIO_EXTENSION_FABRIC_v0.1.0/release_build/KCH_0.11_PRE2G_INTEGRATED_CANDIDATE_R21.zip`  
Bytes: `22231435`  
SHA-256: `98ba1faa4c63302f67ec386b9ecf684762e7923febc3039cd8c201a024091b54`

Este checkpoint demuestra regresión local, compilación de gobierno, empaquetado portable, instalación fresca, transporte STDIO y autoridad exacta de llaves en superficies mediadas por KCH. No demuestra prevención de escrituras externas no mediadas, validación humana sostenida, fiabilidad longitudinal, madurez industrial ni beneficio causal general.

## Próxima acción crítica

Custodiar el candidato, su fuente y todos los recibos —incluidos los adversos— en el repositorio privado `FacundoFirmenich/KCH` y en la carpeta KCH de Drive; verificar hashes remotos antes de cualquier limpieza local. Después, el siguiente gate técnico será el uso real de R21 desde un host conectado, manteniendo PHL real para la fase final indicada por el usuario.
