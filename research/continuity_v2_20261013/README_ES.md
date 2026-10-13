# Continuidad integral KCH / CEH / Helical Lift - segundo avance

13 de octubre de 2026. Continuación del corpus `research/continuity_20261013`, conservado íntegro. PR incremental: https://github.com/FacundoFirmenich/KCH/pull/32.

Se cerraron dos pendientes verificables: ECH pasó de reproducción parcial a certificación exacta del problema finito; solar pasó de soporte insuficiente en v1.5 a una comparación completa en v1.6, sin rival dominante. Estos resultados tienen alcances distintos y se registran por separado.

## Solar: comparación completada, sin dominancia

El protocolo de selección se publicó en `3328788851c832ec06c905e19693aef7c2a13c9e`. El primer workflow no creó jobs por una referencia de contexto inválida; la corrección operativa se publicó en `7b82281d24fb4d1ab0de7cddd1e788ed27bce6cb`, sin cambiar protocolo, rivales ni umbrales. El run https://github.com/FacundoFirmenich/KCH/actions/runs/38390362532 terminó correctamente.

Se consultaron únicamente los cuatro metadatos de selección y las rutas de segmentos. De 61 ventanas candidatas por HARP fueron elegibles 43, 56 y 22. La regla seleccionó desplazamientos de 0, -12 y -12 minutos para 401, 2920 y 5249. El artefacto de selección quedó publicado antes del acceso a campos; no se eligieron ventanas a partir de scores.

Los 15 registros pasaron; se evaluaron las 12 transiciones mediante tres folds, cada uno con una región completa fuera del ajuste. No hubo fallo de rango ni de condición numérica.

| Rival operativo | NMSE medio | NMAE medio | Folds ganados |
|---|---:|---:|---:|
| L: deriva alternante | 0,594014 | 0,598486 | 1/3 |
| T0: identidad | 0,595158 | 0,591468 | 2/3 |
| H: traslación helicoidal | 0,621751 | 0,610537 | 0/3 |
| G: afín condicionado por actividad | 1,071523 | 0,809346 | 0/3 |
| M: cambio de signo | 5,594852 | 1,845869 | 0/3 |

Resultado congelado: **NO_DEVELOPMENT_DOMINANT_LIFT**. El menor NMSE corresponde a L, pero su margen sobre T0 es 0,192178%, frente al 5% exigido, y no alcanza las dos victorias requeridas. El campo técnico `global_winner` sólo identifica el mínimo numérico: no equivale a pasar la regla de dominancia. H presenta 4,468379% más NMSE que T0. La identidad gana además la métrica secundaria global.

La reproducción independiente recalculó la selección, ajustes, normalizaciones, scores por transición, resultados globales y regla final: 60 controles numéricos concordantes, diferencia absoluta máxima 1,7764e-15. Los datos crudos fueron purgados; quedan agregados y hashes de origen.

El resultado v1.5 permanece **INSUFFICIENT_TEMPORAL_SUPPORT** para sus fechas originales. v1.6 cambia la población a ventanas elegibles cercanas. Son tres HARPs históricos de desarrollo, con parte de sus campos ya conocida. G usa actividad del extremo final, de modo que la comparación es condicional, no pronóstico ex ante. No se midió helicidad magnética volumétrica ni se demostró o refutó una topología física.

## ECH: cierre exacto de satisfacción, optimalidad local y evidencia

Se conservaron los tres inputs originales y se recuperó la semántica primaria de EXACT, MODE y ACTIONABLE. Un evaluador nuevo recorrió las 4.017 máscaras admisibles del kernel: 65 clases EXACT, 63 MODE y 46 ACTIONABLE. Coincidieron los 90 hashes estructurales.

Los 204 problemas únicos de puente quedaron certificados: 66 positivos por duales racionales y 138 con testigo factible de coste cero. Las cotas se verifican exactamente, sin depender del mensaje ni de las tolerancias de un optimizador. El segundo verificador, sólo con biblioteca estándar, comprobó 264.145 desigualdades duales.

Se reconstruyeron 96 adyacencias, 96 bucles y 23 cuadrados, que contienen 380 aplicaciones de puentes. Coincidieron 238 hashes de conjuntos. Hay 34 bucles con evidencia nueva, 17 cuadrados con costes diferentes y 22 con conjuntos terminales diferentes para las elecciones óptimas archivadas.

Cuatro cuadrados proporcionan una afirmación más fuerte: su diferencia persiste para cualquier desempate óptimo local. Los costes de las rutas son 5 frente a 10, 13, 14 y 15 consultas. En una ruta cambia primero el sensor; en la otra se aumenta primero la distancia exigida. El contrato final es el mismo, pero el coste y la evidencia heredada difieren. Por tanto, la etiqueta del contrato no basta para representar el estado necesario para planificar futuras adquisiciones.

El generador, su caché original y las cadenas históricas de recibos siguen sin recuperarse. Se verifican hashes de conjuntos de coordenadas, no de estados completos. La optimalidad es local por puente; no se afirma óptimo global del planificador ni invariancia de las cuentas 17/22 bajo todo desempate. Ninguno de estos cálculos añade validación física o cosmológica.

## Estado del conjunto

El registro v2 contiene **30 afirmaciones, 25 fuentes y 12 dominios**. Su verificador conserva las dependencias y reservas del corpus previo.

| Dominio | Estado integrado y límite vigente |
|---|---|
| Formal | Artículos V5 completos; recurrencia observada, retorno del estado, monodromía, identificabilidad y paridad diferenciados. |
| CEH | Estado ampliado conservado; comparación completa de rivales y formulación GF pendientes. |
| ECH | Certificación finita exacta y cuatro testigos de dependencia del camino; recibos históricos y política global siguen abiertos. |
| Solar | v1.6 evaluable sin dominancia; v1.5 conserva su fallo de soporte; física y confirmación externa pendientes. |
| Sísmica | Resultados históricos conservados con reserva de pertenencia; cierre terminal post-2021 separado; continuación ciega sigue HOLD. |
| MHD galáctica | M33 radial reproducido: p=0,664427, 66 comparaciones y 142 hashes concordantes; M33 2D y 75 sensibilidades aún no ejecutadas. |
| BayME | Informe prospectivo y aritmética recuperados; contraste específico fase frente a fase+fibra/régimen pendiente. |
| Cuantorítmica | Programa de intervalos, paquetes y dependencia preservado; sísmica cubre sólo una especialización. |
| KCH / KwanBlocks | Arquitectura de dependencias y ejecución cualificada; no equivale a aislamiento de kernel/red. |
| Runtime | Custodia y ejecución técnica; 12.752 jobs no son observaciones científicas. |
| Pluriverse | Programa formal articulado; sin validación cosmológica. |
| Banco físico | Preparación histórica documentada; no se han establecido aquí nuevas mediciones físicas. |

La continuidad conceptual se fortalece donde se prueba que el estado observado o su etiqueta omiten información relevante para la tarea. La forma matemática concreta del transporte exige su propia comparación: el resultado solar no permite privilegiar el rival helicoidal. Las capas formal, computacional, empírica y operativa conservan obligaciones de prueba distintas.

No se amplían ahora ventanas, ajustan rivales ni reabren tests direccionales para obtener un resultado favorable. Los pendientes sustantivos son evidencia aún no adjudicada: membresía e independencia sísmicas donde corresponda; M33 espacial; vintages para la comparación BayME/CEH; implementación de los rivales CEH faltantes; mediciones del banco físico y pruebas cosmológicas propias. Sus fuentes, condiciones y límites siguen en el registro.

## Reproducción

Desde la raíz del repositorio:

```bash
python .github/helical_v16/run_successor.py check
python research/continuity_v2_20261013/tools/verify_solar_v16.py \
  --metadata research/continuity_v2_20261013/evidence/solar/METADATA_SELECTION.json \
  --result research/continuity_v2_20261013/evidence/solar/TEMPORAL_LIFT_DEVELOPMENT_RESULT_V1_6.json \
  --protocol .github/helical_v16/TEMPORAL_PROTOCOL_V1_6.json \
  --output /tmp/SOLAR_V16_INDEPENDENT_REPLAY.json
python research/continuity_v2_20261013/evidence/ech/tools/check_ech_certificates.py \
  --inputs research/continuity_v2_20261013/evidence/ech/inputs \
  --results research/continuity_v2_20261013/evidence/ech/results
python research/continuity_v2_20261013/tools/verify_continuity_v2.py
```

El replay solar requiere NumPy. El verificador ECH sin solver y el integrador sólo requieren Python estándar. La regeneración de certificados ECH, con sus fuentes completas, está documentada en `evidence/ech/README_ES.md`.
