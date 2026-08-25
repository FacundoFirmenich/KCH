# KCH AIO2 — metrología byte a byte

## Finalidad

La metrología de KCH AIO2 demuestra que el objeto verificado, el objeto comprimido y el objeto entregado conservan exactamente el mismo conjunto de archivos y bytes dentro de la jurisdicción ensayada. No convierte integridad de transporte en verdad científica, utilidad industrial ni autoridad: un archivo puede llegar intacto y contener una mala decisión. Por eso KCH separa integridad, evidencia, validez, permiso, autoridad y ejecución.

## Artefacto final medido

La unidad sellada es `KCH_ALL_IN_ONE_0.11.33_STUDIO_0.3.16_AIO2` (`0.11.33-aio.2`), construida desde la fuente pública reproducible. Incluye las proyecciones Codex y Cline, Studio 0.3.16, Super MCP, 20 skills, MIS 0.3.1 vendorizado, linajes R21/R33 y custodia recuperable. R34 fue excluido por construcción.

## Cuatro capas de medición

### 1. Fuente y comportamiento

- Suite completa de Studio: **156/156 PASS** en 254,52 segundos.
- El resultado incluye el caso que antes fallaba por `MIS v0.3.1 evidence root unavailable`; la fuente MIS necesaria ya viaja dentro del paquete.
- PHL no fue entrenado ni ejecutado.

### 2. Manifiesto del payload

- Archivos materiales declarados: **446**.
- Bytes materiales declarados: **65.625.584**.
- Por cada archivo se verifica ruta relativa, tamaño y SHA-256.
- Se verifica además igualdad exacta de conjuntos: cero archivos ausentes y cero archivos extra.
- No quedaron directorios `__pycache__`, bytecode ni estado transitorio dentro del payload.
- Gate final del paquete: **1.382/1.382 PASS**.

El `PACKAGE_MANIFEST.json` se genera después de medir el payload y por eso no se cuenta a sí mismo entre los 446 objetos. Sí aparece en el ZIP, que contiene 447 entradas.

### 3. Transporte comprimido

| Distribución | Bytes ZIP | Entradas | Bytes expandidos | Lectura CRC íntegra |
|---|---:|---:|---:|---|
| Universal | 61.444.573 | 447 | 65.720.754 | PASS |
| Codex completa | 61.444.971 | 448 | 65.721.246 | PASS |
| Cline completa | 61.444.978 | 448 | 65.721.300 | PASS |

La distribución Codex agrega únicamente `INSTALL_CODEX.ps1`; la distribución Cline agrega únicamente `INSTALL_CLINE.ps1`. Cada entrada de los tres ZIP fue abierta y descomprimida completamente; no se limitó la comprobación a la existencia del archivo contenedor.

### 4. Superficie funcional observada

- Super MCP: **294 herramientas observadas** mediante `initialize` + `tools/list` sobre el ejecutable servido.
- Clasificación: **154** herramientas de lectura y **140** de mutación gobernada, distribuidas en **89** familias de prefijo.
- Cline: instalación limpia, 8 hooks, 20 skills, fader contractual, 294 herramientas, reinstalación idempotente y rollback que restaura la configuración preexistente.
- Codex: fuente AIO2 desplegada, raíz MIS disponible y preflight 0.3.16 callable con PASS. La recarga del caché de la aplicación sigue requiriendo reinicio y tarea fresca para quedar observada desde el host.

## El FAIL que no se borró

La primera pasada posterior al build obtuvo **1.341/1.342**: el propio auditor importó dos módulos y creó dos archivos `.pyc` después del sellado. El paquete comprimido no estaba corrupto; el auditor había dejado de ser observacionalmente puro. Se corrigió para ejecutar con bytecode desactivado, se reconstruyó desde cero y la segunda pasada produjo **1.382/1.382**, con cero cachés posteriores. El FAIL inicial conserva valor: localizó una mutación producida por la herramienta de validación y endureció el protocolo.

## Qué queda demostrado

Quedan demostradas, en Windows y para los hosts ensayados:

- reproducibilidad del ensamblado desde la fuente y wheelhouse declarados;
- identidad de conjunto, tamaño y hash de cada archivo;
- transporte ZIP íntegro;
- disponibilidad material de MIS;
- comportamiento fuente de Studio;
- proyección funcional de Cline;
- preflight callable de Codex;
- ausencia de R34 y de entrenamiento PHL.

## Qué no queda demostrado

No quedan demostradas todavía:

- superioridad general frente a otros arneses;
- fiabilidad industrial longitudinal;
- funcionamiento equivalente en Linux, macOS o plataformas todavía no portadas;
- autoridad externa, seguridad completa o ejecución autónoma ilimitada;
- recarga efectiva del caché de Codex hasta observar una tarea fresca;
- valor científico o empresarial de cada decisión por el mero hecho de que sus bytes sean exactos.

La metrología byte a byte es una condición de custodia y reproducibilidad, no un sustituto de la evaluación funcional, científica o humana.