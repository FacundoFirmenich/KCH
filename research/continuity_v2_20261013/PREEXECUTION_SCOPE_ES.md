# Continuidad integral, segundo avance — congelación previa

Fecha: 2026-10-13. Padre: `11ff8d30bcd7f6d30cd0295e9b49fa3f4a64050d` (PR 31). El corpus de 29 afirmaciones, los dos artículos V5 y sus reservas permanecen inalterados. Este avance añade evidencia verificable.

## Sucesor solar v1.6

El resultado v1.5 `INSUFFICIENT_TEMPORAL_SUPPORT` sigue vigente para su protocolo exacto. La nueva versión cambia la población elegible, por lo que no reemplaza retrospectivamente ese resultado. Los seis campos ya observados y los tres HARPs históricos excluyen presentar esta prueba como confirmación independiente.

Antes de consultar metadatos nuevos se fija, para cada uno de los HARPs 401, 2920 y 5249, una vecindad de inicios de ±6 horas alrededor del inicio v1.5, cada 12 minutos. Son 61 candidatos por HARP; cada candidato contiene cinco registros separados seis horas. Se elige el candidato elegible de menor desplazamiento absoluto; en empate, el anterior. Se permite consultar exclusivamente HARPNUM, T_REC, QUALITY, CMASK y las rutas de los cinco segmentos. Los cinco registros deben existir de forma única, corresponder al HARP, tener QUALITY=0, CMASK≥1000 y rutas de segmentos disponibles. Una ruta disponible no garantiza que la descarga o el soporte multiescala posterior pasen.

Se publicará un artefacto de metadatos inmutable antes del primer acceso a cuerpos FITS. Si falta cualquier trayectoria no se calculan campos. Después de seleccionar no se busca otro candidato ante fallos de descarga, reconciliación, máscara o rango numérico. No se amplía la vecindad. Cada consulta exacta posterior verifica la identidad antes de descargar.

Se conservan el operador v1.4.2, las 16 coordenadas de fibra, el control de actividad, los cinco rivales, el ajuste por dos HARPs y evaluación en el tercero, las normalizaciones exclusivas de entrenamiento y la regla de dominancia. Dieciséis funciones del runtime son idénticas a v1.5 por comparación de AST; los cambios de carga añaden verificación de identidad y los de salida añaden procedencia e interceptos para reproducción. Las versiones del entorno se fijan en el workflow.

El rival G utiliza actividad del extremo final: la comparación es reconstrucción condicional de transiciones, no pronóstico ex ante. Las unidades independientes siguen siendo tres regiones de desarrollo; 12 transiciones ×16 componentes no equivalen a 192 réplicas independientes. Ningún ganador prueba una hélice literal, Möbius, topología, helicidad física o universalidad. No se accede al holdout 2026 ni a resultados de fulguraciones.

Referencia técnica de consultas y rutas de segmentos: https://docs.sunpy.org/projects/drms/en/latest/tutorial.html (consultada 2026-10-13). Esta referencia respalda el uso de la API, no los resultados científicos.

## ECH

Se reconstruye independientemente la satisfacción y optimalidad del problema finito desde el kernel, los codebooks y las adyacencias recuperados con hashes exactos. La identidad binaria del generador y sus 204 cachés originales continúa siendo una afirmación distinta. No se presume recuperada por obtener los mismos costes.

## Conjunto del programa

Esta ejecución no modifica las reservas sísmicas históricas de pertenencia, la fuente terminal separada, el resultado radial de M33, la validación limitada de BayME ni la distinción entre infraestructura Pluriverse y evidencia cosmológica. No autoriza fusión a la rama canónica, promoción ontológica ni comunicaciones externas.
