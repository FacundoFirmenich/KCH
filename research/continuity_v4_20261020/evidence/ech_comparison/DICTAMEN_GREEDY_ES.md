# ECH: comparación exacta de un greedy estándar con las rutas archivadas

Fecha: 20 octubre 2026. Protocolo de la regla congelado antes de calcular sus resultados; los óptimos conjuntos anteriores ya eran conocidos. Es una evaluación retrospectiva de una política nueva sobre un corpus existente, no prerregistro confirmatorio ni validación externa. HHC no se utilizó.

**Resultado:** el greedy por etapa es factible en las 46 rutas. Iguala el óptimo conjunto certificado en 15 y necesita entre una y tres consultas adicionales en las otras 31. Las diferencias no se distribuyen uniformemente: MODE→MODE queda por encima en sus ocho rutas, mientras EXACT→EXACT iguala el óptimo en diez de veinticinco. La exactitud conjunta conserva una ventaja local de coste en el corpus, pero esta comparación cambia también la información sobre el destino futuro y no atribuye causalmente todo el ahorro al algoritmo.

## Política fijada y operación efectivamente calculada

Cada etapa recibe sólo la evidencia acumulada y su contrato destino actual: sensor autorizado, par de clases relevante y distancia requerida. No recibe el siguiente contrato, los testigos óptimos ni los históricos. Para un par p, sea d_E(p) la distancia acumulada y r(p) el umbral. La utilidad marginal de una coordenada q es

`g(q | E) = Σ_{p relevante} 1{d_E(p) < r(p)} · 1{q separa p}`.

Esto es la reducción de déficit truncado de un paso; no multiplica el peso de un par por toda su demanda restante. Todos los costes son uno. Se elige máximo g; a igualdad, la máscara numérica menor. Se excluyen coordenadas tipadas ya adquiridas y se para inmediatamente cuando se satisface el contrato actual. La segunda etapa conserva todas las adquisiciones de la primera. La misma máscara bajo otro sensor es otra coordenada.

El protocolo `PROTOCOL_GREEDY_V1.json` fue guardado antes del cálculo y registra todos los hashes de entrada y el hash del productor. El coordinador confirmó su persistencia en el commit `71a5b1ffd605ef12f11ed0a46d574b615ac9a958` antes de autorizar esta ejecución. No se alteró la regla después de observar sus resultados. No se generaron instancias, observaciones ni errores sintéticos. Se evaluó el kernel matemático archivado de 65 clases y 4.017 máscaras admisibles por sensor.

## Jurisdicciones por sensores de las dos etapas

| Sensores etapa 1 → 2 | Rutas | Iguala óptimo | Sobre óptimo | Exceso máximo | Mejor / igual / peor que histórico |
| --- | ---: | ---: | ---: | ---: | ---: |
| ACTIONABLE -> MODE | 4 | 1 | 3 | 2 | 0 / 1 / 3 |
| EXACT -> EXACT | 25 | 10 | 15 | 2 | 1 / 13 / 11 |
| MODE -> EXACT | 9 | 4 | 5 | 2 | 0 / 4 / 5 |
| MODE -> MODE | 8 | 0 | 8 | 3 | 1 / 0 / 7 |

El histórico es una política archivada que elegía mínimos locales exactos, no un greedy. Frente a él, el nuevo greedy mejora dos rutas (S07P2 y S10P2), iguala dieciocho y empeora veintiséis. Las dos mejoras también quedan una consulta por encima del óptimo conjunto: que un greedy mejore un testigo histórico no lo convierte en óptimo. Sus distintas elecciones iniciales cambian el coste posterior, precisamente la razón para conservar evidencia y destino en la formulación.

En doce rutas, el coste de primera etapa supera su mínimo local certificado. En las otras treinta y cuatro alcanza ese mínimo; diecinueve de esas rutas siguen por encima del óptimo conjunto. Alcanzar el mínimo inicial no determina por sí solo el coste total: el contenido de un mínimo y la calidad del completamiento posterior siguen importando. No se suma ese exceso inicial y el exceso total como si fueran causas independientes.

## Tabla íntegra de las 46 rutas

| Ruta | Greedy etapa 1 | Greedy etapa 2 | Greedy total | Histórico | Óptimo conjunto | Exceso total | Exceso etapa 1 sobre mínimo local |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| S01P1 | 0 | 6 | 6 | 5 | 5 | 1 | 0 |
| S01P2 | 10 | 0 | 10 | 10 | 10 | 0 | 0 |
| S02P1 | 0 | 6 | 6 | 5 | 5 | 1 | 0 |
| S02P2 | 15 | 0 | 15 | 13 | 13 | 2 | 2 |
| S03P1 | 0 | 6 | 6 | 5 | 5 | 1 | 0 |
| S03P2 | 15 | 0 | 15 | 14 | 14 | 1 | 1 |
| S04P1 | 0 | 6 | 6 | 5 | 5 | 1 | 0 |
| S04P2 | 17 | 0 | 17 | 15 | 15 | 2 | 2 |
| S05P1 | 1 | 7 | 8 | 7 | 6 | 2 | 0 |
| S05P2 | 6 | 2 | 8 | 7 | 6 | 2 | 0 |
| S06P1 | 1 | 7 | 8 | 8 | 7 | 1 | 0 |
| S06P2 | 7 | 2 | 9 | 9 | 7 | 2 | 0 |
| S07P1 | 2 | 7 | 9 | 9 | 8 | 1 | 0 |
| S07P2 | 7 | 2 | 9 | 10 | 8 | 1 | 0 |
| S08P1 | 3 | 8 | 11 | 10 | 9 | 2 | 0 |
| S08P2 | 7 | 4 | 11 | 10 | 9 | 2 | 0 |
| S09P1 | 2 | 0 | 2 | 2 | 2 | 0 | 0 |
| S09P2 | 0 | 1 | 1 | 1 | 1 | 0 | 0 |
| S10P1 | 2 | 9 | 11 | 8 | 8 | 3 | 0 |
| S10P2 | 6 | 3 | 9 | 10 | 8 | 1 | 0 |
| S11P1 | 0 | 6 | 6 | 5 | 5 | 1 | 0 |
| S11P2 | 6 | 0 | 6 | 6 | 6 | 0 | 0 |
| S12P1 | 3 | 0 | 3 | 3 | 3 | 0 | 0 |
| S12P2 | 0 | 2 | 2 | 2 | 2 | 0 | 0 |
| S13P1 | 3 | 9 | 12 | 11 | 10 | 2 | 0 |
| S13P2 | 8 | 5 | 13 | 12 | 10 | 3 | 1 |
| S14P1 | 0 | 6 | 6 | 6 | 6 | 0 | 0 |
| S14P2 | 8 | 0 | 8 | 7 | 7 | 1 | 1 |
| S15P1 | 4 | 0 | 4 | 4 | 4 | 0 | 0 |
| S15P2 | 0 | 3 | 3 | 3 | 3 | 0 | 0 |
| S16P1 | 0 | 6 | 6 | 6 | 6 | 0 | 0 |
| S16P2 | 9 | 0 | 9 | 7 | 7 | 2 | 2 |
| S17P1 | 0 | 7 | 7 | 6 | 6 | 1 | 0 |
| S17P2 | 8 | 0 | 8 | 7 | 7 | 1 | 1 |
| S18P1 | 0 | 7 | 7 | 6 | 6 | 1 | 0 |
| S18P2 | 7 | 0 | 7 | 6 | 6 | 1 | 1 |
| S19P1 | 1 | 7 | 8 | 8 | 8 | 0 | 0 |
| S19P2 | 7 | 1 | 8 | 8 | 8 | 0 | 0 |
| S20P1 | 1 | 7 | 8 | 8 | 8 | 0 | 0 |
| S20P2 | 8 | 1 | 9 | 8 | 8 | 1 | 1 |
| S21P1 | 1 | 7 | 8 | 8 | 8 | 0 | 0 |
| S21P2 | 8 | 1 | 9 | 8 | 8 | 1 | 1 |
| S22P1 | 0 | 6 | 6 | 6 | 6 | 0 | 0 |
| S22P2 | 9 | 0 | 9 | 7 | 7 | 2 | 2 |
| S23P1 | 0 | 7 | 7 | 6 | 6 | 1 | 0 |
| S23P2 | 9 | 0 | 9 | 8 | 8 | 1 | 1 |

Las sumas descriptivas son 365 consultas greedy, 335 históricas y 320 óptimas. **Son costes de rutas independientes, no un único experimento de adquisición compartida.** No se usa esa suma para ocultar empates, mejoras locales del greedy o el reparto por sensores.

## Qué prueba el comprobador independiente

El productor usa NumPy; el comprobador usa exclusivamente biblioteca estándar e implementa coberturas mediante bitsets enteros. Reconstruye el DAG original y verifica sus 90 hashes de raíces. No importa el productor ni un solver ni acepta sus matrices agrupadas. Repite cada máximo greedy y desempate: 346 pasos distintos, con 1,383,265 evaluaciones de ganancias candidatas. Los inputs de etapa repetidos se comprueban como iguales y no se presentan como nuevas réplicas.

También vuelve a comprobar factibilidad por etapas, dominios, sensores, no readquisición, costes de testigos y comparadores históricos. Revalida los 46 óptimos conjuntos mediante sus desigualdades duales racionales y testigos enteros, así como 39 mínimos iniciales distintos. La comprobación abarca 524,911 desigualdades de coordenadas duales y 376,824 controles de pares por etapa. CSV, jurisdicciones y resumen deben coincidir con lo recalculado. Estado final: **PASS**, en `GREEDY_INDEPENDENT_CHECK.json`.

Estos conteos describen obligaciones computacionales. No son tamaño muestral ni una réplica científica independiente. Un verificador escrito aparte tampoco equivale a una demostración mecanizada de su propio código o del significado físico de entradas.

## Tiempos y recursos: sólo descripción de ejecución

El productor tardó 11.699973 s: 11.587332 s en reconstruir el kernel y 0.031129 s acumulados en 85 inputs distintos de etapa; siete de las 92 invocaciones usan caché de un input ya calculado. El comprobador independiente tardó 7.304100 s. Python 3.12.14, NumPy 2.3.5. El resto del tiempo del productor incluye comparación y serialización. No se midió memoria máxima ni se igualaron hardware, calentamiento, caché y repeticiones con un solver; no se formula una superioridad temporal.

## Relación con la literatura y alcance de la contribución

La regla es un greedy de cobertura residual por coste, una referencia estándar de diseño de pruebas/multicover. El antecedente más cercano identificado en la revisión es Abbas, Sela Perelman, Amin y Koutsoukos (2017), *Resilient Sensor Placement for Fault Localization in Water Distribution Networks*, ICCPS, DOI 10.1145/3055004.3055020; su formulación une sensores multivaluados, corrección por distancia y multicover. Este experimento implementa la regla especificada aquí: no pretende ser una reproducción íntegra de sus experimentos ni importar su garantía teórica.

Referencia primaria: https://cs.vuse.vanderbilt.edu/koutsoxd/www/Publications/p165-abbas.pdf . La revisión y profundidad de lectura están en el paquete bibliográfico del 20 octubre. No se reivindica novedad para el greedy, ni una razón de aproximación que no se haya probado bajo estas etapas y capacidades.

La comparación cierra un pendiente concreto: ya existe un baseline no óptimo y reproducible sobre todas las rutas reales archivadas. Todavía faltan una comparación con igual información futura para separar algoritmo de anticipación, kernels externos para transferencia, y medidas de tiempo/memoria bajo un diseño comparable si se quiere afirmar rendimiento. La prueba finita no debe usarse para declarar esas obligaciones cerradas.

## Reproducción sin modificar el registro congelado

Copiar este directorio a una carpeta de salida separada y ejecutar desde la raíz del repositorio:

```bash
python research/continuity_v4_20261020/evidence/ech_comparison/run_greedy_baseline.py --repo . --out /ruta/a/copia/ech_comparison
python research/continuity_v4_20261020/evidence/ech_comparison/check_greedy_baseline.py --repo . --out /ruta/a/copia/ech_comparison
```

El productor requiere NumPy; el comprobador sólo Python. Los tiempos de una repetición cambian y, por ello, los hashes de artefactos que incluyen tiempos también cambian. El protocolo y el productor congelados deben mantenerse idénticos. El resultado del productor conserva `COMPUTED_PENDING_INDEPENDENT_CHECK` como estado de su fase; la adjudicación posterior válida está en el recibo independiente PASS, que enlaza por hash ese resultado. No se reescribe retroactivamente su estado.

## Explicación científica

El mecanismo de la pérdida del greedy es que la cobertura marginal del contrato actual no representa por sí sola el valor de la evidencia para una continuación. Además, incluso dentro de una etapa, maximizar la reducción inmediata de déficits no garantiza el mínimo número de consultas. Ambas limitaciones aparecen en el corpus: doce primeras etapas exceden mínimos locales y los treinta y un excesos de ruta incluyen situaciones con primera etapa mínima. Las dos rutas donde el greedy mejora el histórico muestran, a su vez, que el contenido de las adquisiciones puede importar tanto como su número.

La evidencia exacta establece estas diferencias para las 46 rutas, sus sensores, sus evidencias heredadas y el kernel congelado; no identifica todavía qué proporción de cada exceso se debe a falta de información futura, heurística o desempate. El avance para el conjunto es disponer de una referencia algorítmica estándar y de su mapa local de fallos y aciertos. La frontera siguiente es una comparación con información equiparada o un resultado estructural que explique cuándo la suficiencia del estado y la selección anticipatoria realmente aportan una ventaja, sin trasladar este cálculo a validación física ni autoridad operativa.
