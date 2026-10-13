# Continuidad integral KCH · tercer avance · 13 octubre 2026

Esta continuación precisa dos cuestiones que estaban abiertas: cómo planificar adquisiciones sin perder el estado heredado en ECH y qué explica localmente el resultado solar v1.6. Los resultados nuevos son una prueba exacta de planificación finita, una reducción suficiente del estado para esa tarea y un diagnóstico posterior de predicciones solares ya congeladas. No se añadieron observaciones ni se cambió una adjudicación empírica.

El hallazgo de planificación más importante es que los once ahorros encontrados **no requieren adquirir más evidencia en el primer paso**: basta elegir otro mínimo local atendiendo al destino siguiente. El hallazgo solar más importante es que **el coeficiente de traslación de H depende sólo de los extremos de entrenamiento**. Su resultado limita esa deriva compartida; no evalúa todos los transportes posibles de CEH. La evidencia de cada rama conserva su alcance propio.

El registro integral contiene **34 afirmaciones, 34 fuentes y 12 dominios**. Incorpora cuatro afirmaciones y nueve fuentes a la versión anterior, sin borrar ninguna de sus treinta afirmaciones. Sus reservas históricas se conservan en su alcance de origen: la certificación nueva de rutas fijas no convierte en global la optimalidad del planificador, ni verifica recibos históricos. Los artículos V5 y los corpus anteriores permanecen intactos.

## 1. ECH: las 46 rutas fijas tienen óptimos certificados

Se incluyeron las dos rutas de los 23 cuadrados originales antes del cálculo. Cada ruta mantiene su evidencia inicial y sus contratos intermedio/final. En cada etapa sólo se consulta el sensor del destino de esa etapa; se prohíbe readquirir una coordenada tipada. Se minimiza el número total de consultas de las dos etapas, permitiendo inicialmente cualquier reparto factible entre ellas.

Para cada ruta, el testigo entero alcanza el techo de una cota inferior dual racional. El comprobador independiente vuelve a evaluar el kernel y todas las coordenadas originales, sin importar el solver, el productor ni sus matrices agrupadas. Verifica **368.742 desigualdades duales**, **188.412 condiciones de factibilidad por pares**, **90 hashes estructurales** y los **46 comparadores archivados**. Resultado: 46 óptimos exactos, sin brecha.

Once rutas mejoran; 35 conservan coste. La suma descriptiva de costes independientes pasa de 335 a 320; **no es el coste de un único experimento de adquisición compartida**. El máximo ahorro individual es dos consultas. La asimetría de valores óptimos entre las dos rutas persiste en 13 cuadrados, frente a 17 con los testigos históricos. Los cuadrados S06, S07, S10 y S13 igualan sus costes óptimos.

| Cuadrado | Histórico P1 / P2 | Óptimo conjunto P1 / P2 |
| --- | ---: | ---: |
| S01 | 5 / 10 | 5 / 10 |
| S02 | 5 / 13 | 5 / 13 |
| S03 | 5 / 14 | 5 / 14 |
| S04 | 5 / 15 | 5 / 15 |
| S05 | 7 / 7 | 6 / 6 |
| S06 | 8 / 9 | 7 / 7 |
| S07 | 9 / 10 | 8 / 8 |
| S08 | 10 / 10 | 9 / 9 |
| S09 | 2 / 1 | 2 / 1 |
| S10 | 8 / 10 | 8 / 8 |
| S11 | 5 / 6 | 5 / 6 |
| S12 | 3 / 2 | 3 / 2 |
| S13 | 11 / 12 | 10 / 10 |
| S14 | 6 / 7 | 6 / 7 |
| S15 | 4 / 3 | 4 / 3 |
| S16 | 6 / 7 | 6 / 7 |
| S17 | 6 / 7 | 6 / 7 |
| S18 | 6 / 6 | 6 / 6 |
| S19 | 8 / 8 | 8 / 8 |
| S20 | 8 / 8 | 8 / 8 |
| S21 | 8 / 8 | 8 / 8 |
| S22 | 6 / 7 | 6 / 7 |
| S23 | 6 / 8 | 6 / 8 |

Los trece pares de valores óptimos distintos no dependen de cómo se desempaten sus testigos óptimos. Esta invariancia de **valores** no afirma invariancia de conjuntos, identidad de ledgers, cadenas históricas de recibos o una política óptima sobre el grafo entero.

## 2. Auditoría posterior: el mecanismo es el desempate

Treinta testigos devueltos por la optimización no restringida gastaban más que el mínimo en el primer paso. Eso sólo describe soluciones devueltas; no demuestra que ese gasto sea necesario. Para resolverlo, una segunda fase, expresamente **posterior**, fijó las once rutas mejoradas y restringió el primer paso al mínimo ya probado en la versión anterior. No se reescribió el protocolo de las 46 rutas.

En las once se verifica **R = J < A**, donde A es el coste histórico, J el óptimo conjunto no restringido y R el óptimo restringido a un primer paso mínimo. Las 132.090 desigualdades racionales de la segunda comprobación certifican los once casos. No hay ningún caso que requiera sobreadquisición inicial para alcanzar J.

El archivo `evidence/ech_joint/LOCAL_MINIMUM_LOOKAHEAD_CATALOG.json` conserva 35 planes históricos y añade once desempates. Sus **46 planes tienen ambos pasos localmente mínimos y el total óptimo para su ruta fija**. Se vuelven a comprobar 184.250 desigualdades de los mínimos originales del primer paso. La minimalidad del segundo se sigue también de la cota conjunta: abaratarlo desde ese primer testigo contradice el óptimo J.

El catálogo usa ruta y coordenadas heredadas exactas; elegir un desempate puede requerir conocer el siguiente destino. No es una política basada sólo en la etiqueta del contrato ni una solución para estados fuera del catálogo. El dictamen ECH incluye la tabla completa de los once casos y la regla finita de consulta.

## 3. Cociente suficiente de planificación

Para cada coordenada tipada, se calcula su vector completo de separación de los 2.080 pares de 65 clases. Se agrupan sólo coordenadas del mismo sensor con idéntico vector, conservando todos sus miembros y la capacidad real de cada grupo. El estado de planificación guarda contrato/etapa y cuentas adquiridas por grupo.

| Sensor | Coordenadas | Patrones | Capacidad máxima |
| --- | ---: | ---: | ---: |
| EXACT | 4.017 | 3.971 | 3 |
| MODE | 4.017 | 3.300 | 15 |
| ACTIONABLE | 4.017 | 609 | 159 |
| Total | 12.051 | 7.880 | — |

Con kernel fijo, coste unitario, admisibilidad por sensor/etapa y contratos expresados mediante distancias, las cuentas determinan tanto las distancias heredadas como las capacidades restantes. Dos estados reducidos iguales admiten las mismas adquisiciones por grupo, con igual coste y siguiente estado reducido. Por inducción, conservan factibilidad y coste óptimo de cualquier ruta finita fijada dentro de esas reglas.

Es un cociente **suficiente; no se ha probado mínimo**. La verificación reproduce los 204 certificados originales. Tres estados terminales utilizan multiplicidad de patrones: reemplazar un grupo por un simple indicador de presencia perdería información. Los 93 ledgers distintos del archivo dan 93 estados reducidos distintos; no se encontraron colisiones entre esos ledgers.

La reducción preserva la tarea de planificación indicada. No conserva por sí sola etiquetas de respuesta, decodificación, observaciones, identidades de coordenadas, hashes, ruido o autoridad de recibos. El ledger completo sigue siendo necesario para auditoría. Prueba, supuestos y partición íntegra: `evidence/quotient/`.

## 4. Solar: toda la heterogeneidad, sin cambiar el resultado

Se descompusieron las predicciones congeladas de 15 instantáneas reales, tres HARPs, 12 transiciones, 16 componentes y cinco modelos. Se publican **960 celdas**, **1.200 agregaciones**, 96 parámetros H/L, 192 contribuciones por HARP de entrenamiento, 768 sensibilidades por transición y 60 derivadas analíticas. El verificador independiente pasa **43.924 comparaciones numéricas**, con diferencia máxima 2,8422 × 10⁻¹⁴; también reproduce los 60 controles de v1.6.

| Rival | NMSE global | Ganancia NMSE frente a T0 | HARPs mejores que T0 | Transiciones mejores que T0 |
| --- | ---: | ---: | ---: | ---: |
| T0, identidad | 0,595157570 | referencia | — | — |
| H, traslación | 0,621751465 | −4,468379% | 0/3 | 4/12 |
| L, alternancia | 0,594013807 | +0,192178% | 1/3 | 7/12 |
| G, afín con actividad | 1,071522606 | −80,040154% | 0/3 | 5/12 |
| M, cambio de signo | 5,594851754 | −840,062269% | 0/3 | 0/12 |

L gana poco globalmente y pierde un 1,186546% en NMAE. No alcanza el margen de 5% ni las dos victorias de fold exigidas. H pierde en los tres HARPs, las seis categorías de escala y las cuatro familias, aunque gana cuatro transiciones. G gana cinco transiciones y pierde en cada HARP agregado. Cada patrón local queda tabulado, sin convertirlo retrospectivamente en una regla de selección de rivales.

Las agregaciones se solapan y las transiciones comparten instantáneas: no son réplicas independientes. Las cinco escalas ordinarias pesan 3/16 cada una; la componente integral entre escalas pesa 1/16. Las tres familias ordinarias pesan 5/16 cada una, y la integral 1/16. No se promedian categorías como si tuvieran igual peso. G usa actividad del extremo final: su comparación es condicional, no un pronóstico ex ante.

### Qué aprendieron realmente los coeficientes H y L

Para dos HARPs de entrenamiento A y B, con cuatro transiciones cada uno:

- `b_H = [(x4 − x0)_A + (x4 − x0)_B] / 8`.
- `b_L = Σ_{A,B} [−x0 + 2x1 − 2x2 + 2x3 − x4] / 8`, con la fase alternante congelada.

El coeficiente de H cancela por telescopaje las instantáneas interiores; los normalizadores y la evaluación sí pueden depender de ellas. H contrasta una deriva media compartida, no una reconstrucción de geometría helicoidal interior. L conserva un contraste alternante específico, tampoco una prueba general de topología lemniscática.

La mejora cuadrática normalizada se descompone en crédito de alineación menos coste de la corrección. Para H, el crédito medio es negativo en los tres folds: el deterioro no se explica sólo por una penalización de magnitud. Cuando se evalúa HARP 5249, los dos HARPs de entrenamiento tienen derivas medias de signos opuestos en las 16 componentes.

El diagnóstico es **post hoc**, sin nueva selección, ajuste puntuado, observación o confirmación. Se conserva `NO_DEVELOPMENT_DOMINANT_LIFT`. Las tablas completas por HARP, transición, escala, familia y componente están en `evidence/solar_local/DICTAMEN_SOLAR_LOCAL_ES.md` y los CSV, incluidos los marginales cruzados.

## 5. El conjunto y sus obligaciones pendientes

| Dominio | Resultado o estado preservado | Obligación que sigue abierta |
| --- | --- | --- |
| Formal | Artículos V5 completos; separación de observación, retorno, transporte, identificación y paridad | No deducir una hélice literal de toda memoria ni retorno no trivial de M ≠ I |
| CEH | Estado ampliado y relevancia dependiente de la tarea | GF, mapa completo de implementaciones y comparación de todos los rivales |
| ECH | 204 puentes originales; ahora 46 rutas y cociente suficiente | Generador/caché históricos, recibos y política global del grafo |
| Solar | v1.6 evaluable sin dominancia; diagnóstico local completo | Confirmación con observaciones apropiadas y rivales definidos antes de examinarlas |
| Sísmica | Reserva de pertenencia donde corresponde; terminal post-2021 separado; ciego HOLD | Diccionario primario y discrepancias de eventos; independencia histórica reservada |
| MHD galáctica | M33 radial reproducido: p=0,664427; 66 controles y 142 hashes | M33 espacial 2D y 75 sensibilidades fijadas aún sin ejecutar |
| BayME | Informe prospectivo: 8/15 lonjas frente a 7/15 persistencia; aritmética comprobada | Comparación CEH fase frente a fase+fibra/régimen con vintages |
| Cuantorítmica | Intervalos, paquetes y dependencia; especialización sísmica parcial | Unidades, representación, base/redondeo y presupuesto de búsqueda explícitos |
| KCH / KwanBlocks | Dependencias, composición y ejecución cualificada | El alcance del alpha no acredita aislamiento de kernel/red |
| Runtime | Custodia técnica; 12.752 jobs con resultado científico nulo | Evidencia científica específica; los jobs no son observaciones |
| Pluriverse | Programa formal, genealogía y acoplamientos | Discriminación cosmológica frente a rivales de complejidad comparable |
| Banco físico | Preparación histórica documentada | Recepción, calibración y mediciones reales verificables |

La reserva de 3.513 pertenencias históricas no certificadas se propaga a v0.8.2 y v0.9A sísmicos; no se extiende al terminal post-2021 de otra fuente. La continuidad preserva esta separación. Ningún certificado nuevo concede autoridad operativa ni permite trasladar validación entre dominios.

## 6. Reproducción

Desde la raíz del repositorio, con Python 3.12 y NumPy 2.3.5 para la partición. Los verificadores ECH y solar usan sólo la biblioteca estándar. Copiar resultados a una carpeta temporal evita modificar recibos congelados que incluyen tiempos de ejecución.

```bash
mkdir -p /tmp/kch-v3-review
cp -a research/continuity_v3_20261013/evidence/ech_joint /tmp/kch-v3-review/ech-joint
cp -a research/continuity_v3_20261013/evidence/solar_local /tmp/kch-v3-review/solar-local
python research/continuity_v3_20261013/evidence/ech_joint/check_joint_certificates.py --source research/continuity_v2_20261013/evidence/ech --results /tmp/kch-v3-review/ech-joint --catalog /tmp/kch-v3-review/ech-joint/LOCAL_MINIMUM_LOOKAHEAD_CATALOG.json
python research/continuity_v3_20261013/evidence/ech_joint/check_posthoc_local_ties.py --source research/continuity_v2_20261013/evidence/ech --results /tmp/kch-v3-review/ech-joint
python research/continuity_v3_20261013/evidence/solar_local/verify_solar_local.py --repo . --diagnostic /tmp/kch-v3-review/solar-local
python research/continuity_v3_20261013/evidence/quotient/verify_planning_quotient.py --ech research/continuity_v2_20261013/evidence/ech --out /tmp/kch-v3-review/quotient
cmp research/continuity_v3_20261013/evidence/quotient/results/PLANNING_PATTERN_PARTITION.json /tmp/kch-v3-review/quotient/PLANNING_PATTERN_PARTITION.json
python research/continuity_v3_20261013/tools/verify_continuity_v3.py
```

Los productores ECH requieren además SciPy 1.17.0; sus comandos y protocolos separados están en `evidence/ech_joint/README_ES.md`. No se necesita optimizar de nuevo para verificar certificados. `.github/workflows/helical-planning-continuity.yml` repite las comprobaciones y conserva recibos frescos, incluidos los 204 certificados anteriores.

`CLAIM_EVIDENCE_REGISTRY.json` vincula afirmaciones, fuentes, dependencias y reservas. `CORPUS_VERIFICATION.json` registra su comprobación. `DELIVERY_MANIFEST.json` fija cada archivo nuevo y el workflow por SHA-256. El parent remoto es `05a338419267dc81124c31dce18fb8902fc8b0ca`; la continuación es aditiva y no modifica la rama canónica.
