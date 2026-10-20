# Continuidad v4: implementación de la revisión crítica

Fecha: 20 de octubre de 2026. Continuación aditiva del commit `3d50f0ae68affbc747d73eb855863ead02d02782`. Rama de revisión: `continuity/review-implementation-20261020`. [PR 37](https://github.com/FacundoFirmenich/KCH/pull/37), todavía borrador. No se utiliza HHC.

La revisión se convirtió en dos manuscritos V6 completos, una comparación algorítmica nueva sobre las 46 rutas ECH archivadas, un módulo estructural y contratos físicos verificables. Los 108 archivos de las tres entregas precedentes quedan intactos. No se obtuvieron nuevas observaciones físicas ni se reabrieron adjudicaciones terminales. La implementación mejora precisión conceptual, comparación y trazabilidad; no transforma automáticamente esas mejoras en novedad científica o confirmación física.

## Resultado nuevo en ECH

Se fijaron y guardaron protocolo y productor antes de ejecutar una política greedy de cobertura marginal, con desempate por máscara numérica ascendente, parada inmediata al satisfacer el contrato y sin acceso al destino de la siguiente etapa. Se conservaron las 46 rutas, sin selección posterior. Es un protocolo de desarrollo retrospectivo: los óptimos conjuntos ya eran conocidos; no es un prerregistro ciego ni una validación externa.

| Jurisdicción de sensores | Rutas | Greedy igual al óptimo conjunto | Greedy por encima | Exceso máximo de consultas |
|---|---:|---:|---:|---:|
| ACTIONABLE → MODE | 4 | 1 | 3 | 2 |
| EXACT → EXACT | 25 | 10 | 15 | 2 |
| MODE → EXACT | 9 | 4 | 5 | 2 |
| MODE → MODE | 8 | 0 | 8 | 3 |
| **Conjunto finito archivado** | **46** | **15** | **31** | **3** |

Las sumas de costes de ejecuciones independientes son 365 para greedy, 335 para la selección local histórica y 320 para los óptimos conjuntos. No son el coste de un experimento compartiendo adquisiciones entre rutas. Frente a la selección histórica, greedy mejora dos rutas, empata dieciocho y empeora veintiséis. Sus primeras etapas exceden el mínimo certificado en doce rutas. De las otras treinta y cuatro, diecinueve todavía tienen coste total subóptimo: alcanzar el mínimo inicial no basta para garantizar el mejor completamiento.

El checker independiente reconstruye el DAG original, las respuestas de los tres sensores y cada decisión greedy. Comprueba las 46 rutas, 346 decisiones únicas, 1.383.265 ganancias candidatas y 524.911 desigualdades racionales; recertifica los 46 óptimos conjuntos y 39 mínimos iniciales distintos sin importar productor, NumPy, solver o matrices agrupadas. El resultado del productor conserva su estado histórico `COMPUTED_PENDING_INDEPENDENT_CHECK`; la adjudicación posterior está en `GREEDY_INDEPENDENT_CHECK.json`, que vincula por hash ese resultado y registra `PASS`.

Los tiempos de una ejecución (11,70 segundos para el productor, 7,30 para el checker original) son descriptivos y declaran reutilización de etapas idénticas. No justifican una ventaja de velocidad. La comparación greedy–óptimo conjunto cambia tanto la regla de decisión como el conocimiento del contrato siguiente. Por eso no identifica causalmente cuánto ahorro se debe a anticipar, desempatar o resolver exactamente.

El resultado estructural separa esas cuestiones. Sean A el coste histórico, J el óptimo conjunto y R el mejor total restringido a primeras etapas de coste mínimo. Entonces A−J=(A−R)+(R−J): elección entre mínimos iniciales y posible beneficio de gastar más primero son componentes distintos. En las 46 rutas ya certificadas, R=J; los once ahorros frente al histórico pueden alcanzarse eligiendo mejor entre mínimos iniciales. Esa igualdad pertenece a este catálogo, no a cualquier problema de cobertura. El módulo `theory/ECH_STRUCTURAL_CONTRIBUTION.md` explicita condiciones, pruebas y alcance.

## Manuscritos conservados y corregidos

**PAPER 1 V6**, en inglés, sitúa la suficiencia de estado respecto de una tarea junto a estados causales, representaciones predictivas y abstracciones decisionales. Conserva literalmente 53 ecuaciones, nueve pruebas, nueve bloques de código o métricas y nueve encabezados numerados de V5. Las adiciones se delimitan; siete cambios editoriales son reversibles; título, abstract y metadatos previos quedan en el historial. El cuerpo V5 se puede reconstruir exactamente. La especialización ECH conserva costes y factibilidad bajo sus hipótesis; no demuestra minimalidad de representación, aceleración o una teoría física universal.

**PAPER 2 V6**, también en inglés, presenta primero el terminal y define el estimando: ganancia de log-score de una marca axial, condicionada en un evento y sus metadatos, sobre la red congelada. No es una prueba de predicción de ocurrencias. Los 38.476 bytes de V5 se conservan completos en un apéndice exacto, con catorce bloques verificables. El terminal de Bay Area y Parkfield permanece negativo bajo su regla anterior: efectos aproximados +0,000227 y −0,000611 nats por hijo; cotas superiores marginales 97,5% ≈0,001187 y 0,0000559, por debajo del margen 0,02. La interpretación simultánea requiere la cobertura marginal declarada; el manuscrito no convierte la aritmética de Bonferroni en una nueva demostración de cobertura del bootstrap.

El segundo manuscrito distingue la literatura próxima de los comparadores efectivamente ejecutados. Permanecen pendientes la recuperación de la densidad realmente usada, normalización, política numérica, pérdidas pareadas y configuración reproducible del bootstrap. La corrección editorial define esas obligaciones, pero no sustituye su auditoría computacional.

## Solar: contratos temporales y victorias locales

La cronología completa es v1.5 (soporte insuficiente, cero comparaciones), v1.6 (15 registros, 12 transiciones, comparación de desarrollo completada), v3 (diagnóstico local) y v4 (auditoría de disponibilidad temporal). La conclusión `NO_DEVELOPMENT_DOMINANT_LIFT` no cambia. H/L/G/M conservan respectivamente 4/7/5/0 victorias descriptivas frente a T0 en doce transiciones.

| Región evaluada | Años de las regiones de entrenamiento | Lectura admisible |
|---|---|---|
| HARP 401, 2011 | 2013 y 2015 | Transferencia retrospectiva; ajuste con datos posteriores |
| HARP 2920, 2013 | 2011 y 2015 | Transferencia retrospectiva; ajuste con datos posteriores |
| HARP 5249, 2015 | 2011 y 2013 | Orden de observación compatible; desarrollo retrospectivo en 2026 |

La fórmula H o L puede utilizar entradas del instante de emisión si los parámetros ya estaban disponibles. Eso no prueba que este ajuste existiera entonces. G incorpora actividad del extremo final y su contrato actual es reconstrucción. Además, seleccionar ventanas que completan cinco snapshots de buena calidad usa metadatos futuros y no define una regla de elegibilidad online. Son límites de interpretación del protocolo retrospectivo, no una acusación de haber incumplido ese protocolo.

La búsqueda de DAVE4VM inspeccionó los 108 archivos recuperados y los miembros de tres ZIP, con inventario y coincidencias auditables. No recuperó el código original v1.3. Esta ausencia está limitada al corpus inspeccionado. La diferencia entre derivadas internas del estimador y un mosaico de velocidades, pertinente a la literatura DAVE4VM de 2026, exige recuperar aquella implementación antes de adjudicar un nuevo balance de inducción. No se inventó una reparación ni un resultado de flujo.

## M33: sensibilidad, incertidumbre e identificación

La matriz archivada K tiene dimensión 2×3 y rango dos. Su espacio nulo es unidimensional, con dirección unitaria aproximadamente (1,2,2)/3. El verificador integra una comprobación racional exacta para los decimales archivados, además del residuo numérico del contrato. Para ese operador fijo, η y η+t·n generan el mismo vector de dos anillos. Esta afirmación algebraica sobre el operador no prueba su equivalencia con un kernel físico de Lorentz.

Se preservan el p=0,664427 de la covarianza primaria, las ocho sensibilidades de covarianza y la norma mínima puntual ≈289,997. Esta última no es una cota estadística de amplitud. Las referencias radiales difieren unas 18–21 veces la respuesta natural. Un contraste 2D útil debe aportar una dirección de respuesta independiente del espacio ya observado y separar parámetros físicos de nuisance; reunir más puntos con la misma proyección no elimina por sí solo la degeneración. El protocolo 2D y sus 75 sensibilidades siguen sin ejecución adjudicada.

## Conjunto de doce ramas

| Rama | Evidencia que se conserva | Acción que permitiría avanzar |
|---|---|---|
| Formal | Argumentos corregidos y V6 íntegra | Demostrar un resultado diferencial frente al antecedente más cercano |
| ECH | Certificados exactos, cociente suficiente, catálogo y greedy real | Comparación con información equiparada y validación en otro kernel real |
| Sísmica | Terminal negativo; auditoría histórica acotada | Recuperar y comprobar densidades, pérdidas y bootstrap ejecutados |
| Solar | Campos observados, comparación retrospectiva y ganancias locales | Replay cronológico con procedencia temporal de parámetros y código DAVE original |
| MHD galáctica | Replay radial M33 y geometría M31 | Resolver el puente físico y rango efectivo con nuisance antes de ejecutar 2D |
| BayME | Informe prospectivo histórico: 8/15 lonjas; MAE 0,9640 vs 1,1509 | Replay de vintages y contraste específico fase frente a fase+fibra/régimen |
| CEH | Representación de fase, vuelta, fibra y demás componentes | Instancia identificada y comparadores completos; GF sigue incompleta |
| Cuantorítmica | Programa de intervalos, paquetes, marcas y dependencia | Especialización medible adicional; sísmica no cubre todo el programa |
| KCH fabric | Arquitectura de dependencias y ejecución con lease | Calificar aislamiento real y contratos de composición |
| Runtime | Custodia y 12.752 jobs técnicos | Mantener separado `scientific_result=null` del rendimiento operativo |
| Pluriverse | Programa formal de no-clausura y acoplamientos | Puente observable y prueba discriminante; sin validación cosmológica |
| Banco físico | Preparación de firmware y metrología histórica | Primer artículo, calibración y datos físicos con procedencia |

El registro v4 conserva sin cambios las 34 afirmaciones previas y sus dependencias, y añade afirmaciones con fuentes y reservas explícitas. Las reservas se transmiten por dependencias efectivas; compartir vocabulario o una región geográfica no contamina automáticamente otra rama. Las fuentes bibliográficas son las de la revisión crítica, con profundidades de lectura declaradas: no se reclama haber leído exhaustivamente toda la literatura mundial.

## Verificación y estado de despliegue

`tools/verify_continuity_v4.py` comprueba hashes del corpus de entrada, retención de ambos manuscritos, fuentes y dependencias del registro, aritmética de la comparación, cronología solar, rango y nulidad de M33 y manifiesto de entrega. Vuelve a ejecutar el checker ECH en un directorio temporal sin reutilizar su recibo anterior. La integración continua produce recibos nuevos; ningún `PASS` constituye validación física ni permiso operativo.

Este despliegue corresponde a una rama y PR de investigación en borrador. Las afirmaciones históricas permanecen accesibles, pero las precisiones v4 gobiernan su interpretación actual. El libro de correcciones distingue implementaciones terminadas de obligaciones documentadas y bloqueos por fuente ausente. No se reclama cierre de los pendientes físicos ni preparación automática para una revista determinada.

El mecanismo común que ahora queda mejor delimitado es la suficiencia de la información para una tarea: en ECH puede certificarse qué evidencia conserva un coste óptimo; en solar importa qué información existía al emitir una predicción; en M33 una proyección puede borrar una combinación de parámetros; en sísmica una mejora condicional de marcas no identifica un mecanismo físico. Estas relaciones permiten integrar las ramas sin convertirlas en equivalencias.

La evidencia nueva es finita y computacional, acompañada de correcciones documentales y una comprobación algebraica sobre un operador real archivado. La frontera estratégica consiste en resolver la comparación ECH con información equiparada, recuperar las implementaciones empíricas ausentes y diseñar nuevas observaciones que rompan ambigüedades identificadas. Ese paso requiere conservar los resultados negativos y las victorias locales, no reetiquetarlos como una confirmación global.
