# Dictamen de continuidad ECH — 13 de octubre de 2026

La limitación anterior de reproducibilidad queda superada para los costes de
los puentes, la satisfacción de los contratos de destino y los conjuntos de
evidencia del atlas. Se implementó un evaluador independiente del kernel, se
reconstruyó el problema finito y se obtuvieron certificados racionales nuevos
para sus soluciones archivadas. El generador original y su caché no aparecieron;
esta entrega no afirma haberlos recuperado.

La distinción es material: ahora se dispone de una demostración computacional
verificable de la optimalidad de cada puente y de una reconstrucción de los
conjuntos terminales, en lugar de depender de las declaraciones del informe o
del estado «Optimal» publicado por un solver anterior. La genealogía histórica
de recibos continúa fuera de lo recuperado.

## Corpus preservado y semántica primaria

Los tres inputs conservan exactamente los hashes vinculados por el atlas:

| Archivo | SHA-256 |
|---|---|
| cas_constitutional_kernel_v1.json | 82a9d8b10b90ea1debfeb480ac10e5bcc183e034d0d33a6dbf23b55931053138 |
| compiled_distance_codebooks.json | 9d5ffe66c18b6c764963a484f91eed09ebb064a59be205fc3f7a0681adb81a5b |
| adjacent_contract_migrations.csv | 818beed9111f102a863ad619a6209b27f44026b5adb335ea715814c8d1e3d91d |

Se recuperó además la fuente `successive_refinement_decoder.py`, dentro de
`ECH_ROBUST_SUCCESSIVE_REFINEMENT_2026-09-28.zip`, para resolver una ambigüedad
que los nombres de los sensores, por sí solos, no eliminaban. Su SHA-256 es
`8f579feb5b5bc5279ce0cc57612480ceb9fb38550f8f440bfcb29c87d0fcd1ea`;
el archivo ZIP tiene SHA-256
`a951daaf32d3d2df1661cd3b78fbf176d5da6eb9ef4dfec3726c10d398d0db39`.

EXACT conserva la firma completa. MODE conserva el prefijo previo a los dos
puntos. ACTIONABLE agrupa APPLY y TOP_2; ASK y ABSTAIN quedan en NONACTIONABLE.
Las máscaras admisibles tienen al menos tres bits presentes dentro del universo
de doce bloques. Esas definiciones proceden de la implementación primaria; no
fueron elegidas para hacer coincidir los resultados del atlas.

El kernel tiene 12.423 nodos y 90 jurisdicciones. Se recomputaron los 90 hashes
estructurales y coincidieron todos. Sus 4.017 máscaras admisibles distinguen
65 clases EXACT, 63 MODE y 46 ACTIONABLE. Las clases de destino se establecen
por sus firmas sobre el dominio completo, no únicamente sobre las sondas de
un codebook particular.

## Problema matemático y certificado

Para un ledger heredado E, un contrato de destino de distancia d y cada par
de clases que ese destino exige separar, se calcula la distancia observada.
El déficit b es la parte positiva de d menos esa distancia. Cada nueva
coordenada admisible del sensor de destino aporta un coeficiente A de cero o
uno: indica si sus respuestas distinguen al par.

El puente resuelve la multicobertura:

\[
\min \sum_q x_q,\qquad Ax\ge b,\qquad x_q\in\{0,1\}.
\]

Una coordenada ya heredada no puede contarse como nueva. Dos máscaras distintas
con respuestas iguales siguen siendo dos coordenadas disponibles: no se borra
su multiplicidad mediante una deduplicación de columnas. Esto evita depender
de cómo el generador anterior redujo candidatos.

La factibilidad del testigo archivado se verifica con distancias enteras frente
a todos los pares relevantes. Para la cota inferior se usa la relajación
x≥0, sin límite superior. Su dual exige y≥0 y Aᵀy≤1. El LP propone y; después
se convierte a fracciones y se verifica exactamente cada desigualdad para
todas las coordenadas nuevas admisibles. Si el techo de bᵀy coincide con el
número de coordenadas del testigo, la optimalidad entera queda demostrada.

Este cierre ocurrió en todos los casos. No se acepta como prueba el mensaje
del optimizador ni una tolerancia numérica. Un segundo programa, escrito sólo
con la biblioteca estándar y sin importar el generador, volvió a verificar
los certificados, evaluando otra vez el kernel.

## Resultados ejecutados

| Objeto | Resultado |
|---|---|
| Codebooks iniciales | 28/28 satisfacen su contrato |
| Combinaciones ledger inicial / contrato destino | 784/784 coinciden fila por fila con la matriz archivada |
| Satisfacciones sin consulta adicional | 353/784; 21 perfiles distintos |
| Adyacencias dirigidas | 96/96 factibles y óptimas |
| Bucles de dos pasos | 96/96 reevaluados |
| Bucles con coordenadas nuevas | 34; los otros 62 conservan el mismo conjunto |
| Cuadrados | 23/23; los cuatro pasos de cada cuadrado son factibles y óptimos localmente |
| Cuadrados con coste diferente según el orden | 17/23 |
| Cuadrados con conjunto final diferente | 22/23 |
| Diferencia máxima de coste | 10 consultas |
| Diferencia simétrica máxima entre conjuntos finales | 20 coordenadas tipadas |
| Problemas únicos certificados | 204: 66 positivos y 138 de coste cero |
| Aplicaciones de puentes cubiertas | 380 |
| Desigualdades duales verificadas exactamente | 264.145 |
| Hashes archivados de conjuntos verificados | 238/238 |

También se reprodujo el contraejemplo de sustitución ilegítima de codebook:
el ledger MODE__MODE__d1 deja sin separar exactamente los pares de clases
(11,19) y (55,56) para el objetivo EXACT. Cambiar su etiqueta al contrato
MODE__EXACT__d1 no fabrica las observaciones del codebook canónico de ese
segundo contrato.

## Reconstrucción de los cuadrados y hashes

En 21 cuadrados, los primeros pasos conocidos, las diferencias de conjuntos
publicadas y las cardinalidades determinan ambos conjuntos terminales sin
coordenadas comunes desconocidas. Dos cuadrados dejaban una coordenada común
sin identificar.

Se identificó la serialización que reproduce los hashes publicados:
coordenadas `sensor:máscara` ordenadas, concatenadas con salto de línea, en
UTF-8 y sin salto final. Esa regla coincide con los 192 hashes iniciales y
finales de los bucles y con los 46 hashes terminales de los cuadrados.

Las dos coordenadas ausentes se identificaron enumerando el dominio completo
del sensor de destino. Hubo un único candidato que satisfizo simultáneamente
los dos hashes de su cuadrado:

| Origen | Destino | Coordenada común recuperada |
|---|---|---|
| ACTIONABLE__MODE__d2 | MODE__MODE__d3 | MODE:031 |
| MODE__EXACT__d4 | EXACT__EXACT__d5 | EXACT:08e |

La unicidad indicada es dentro del dominio finito declarado. Esta recuperación
no supone que se haya localizado el generador histórico. Los digests son de
conjuntos de coordenadas; no son hashes de lecturas observacionales completas,
recibos ni estados que incluyan genealogía.

## Dependencia del camino y desempates

Las cuentas 17 y 22 reproducen las elecciones óptimas archivadas. No se ha
demostrado que esas dos cuentas sean invariantes frente a todos los posibles
desempates entre puentes óptimos. Tampoco se ha demostrado que la política
de optimizar cada paso produzca el camino global de coste mínimo.

Sí hay cuatro testigos más fuertes, independientes del desempate óptimo local:

| Estado inicial | Destino | Sensor primero, luego distancia | Distancia primero, luego sensor |
|---|---|---:|---:|
| ACTIONABLE__ACTIONABLE__d1 | ACTIONABLE__MODE__d2 | 5 | 10 |
| ACTIONABLE__ACTIONABLE__d2 | ACTIONABLE__MODE__d3 | 5 | 13 |
| ACTIONABLE__ACTIONABLE__d3 | ACTIONABLE__MODE__d4 | 5 | 14 |
| ACTIONABLE__ACTIONABLE__d4 | ACTIONABLE__MODE__d5 | 5 | 15 |

La primera ruta comienza con un cambio de sensor sin adquisiciones. El ledger
permanece fijado y la cota exacta de la segunda operación es cinco. La segunda
ruta debe pagar su mínimo certificado de refuerzo de distancia; cualquiera de
sus testigos factibles ya satisface el objetivo y la distancia finales, por
lo que el cambio posterior de sensor cuesta cero. Además, una ruta añade
coordenadas MODE y la otra ACTIONABLE: sus conjuntos finales difieren con
independencia de la identidad particular de las sondas óptimas.

Así queda demostrado, en ejemplos del kernel original, que la etiqueta del
contrato no basta para planificar el coste futuro. La evidencia heredada forma
parte del estado necesario del planificador.

## Límites que permanecen

No se recuperaron el generador original, su política de desempate ni la caché
de 204 entradas. El hecho de que la auditoría independiente produzca 204
problemas únicos concuerda con ese recuento histórico, pero no acredita
identidad binaria entre cachés.

Los archivos no contienen las cadenas históricas completas de recibos ni sus
hashes de estado. La regla append-only permite demostrar estructuralmente que
añadir dos recibos impide volver al mismo estado genealógico; esta auditoría
no sustituye esa demostración por una supuesta observación de recibos ausentes.
Tampoco convierte esa propiedad en una hélice geométrica literal.

El resultado es exacto dentro del kernel y de la familia finita congelados.
No añade validación física, cosmológica ni de un sistema operativo desplegado.
No genera lecturas observacionales ni datos sintéticos. La autoridad permanece
ausente y `permission_granted=false` en todos los certificados.

El avance verificable es el cierre de satisfacción, optimalidad local y
conjuntos de evidencia del atlas, con una prueba racional que puede revisarse
sin disponer de ningún solver.
