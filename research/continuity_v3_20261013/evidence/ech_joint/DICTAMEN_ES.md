# Dictamen ECH: optimización conjunta exacta de rutas fijas de dos etapas

Fecha: 13 de octubre de 2026. Familia finita y fuentes congeladas.

Se ejecutaron las 46 rutas de dos etapas de los 23 cuadrados originales, incluidas todas antes del cálculo. Las 46 tienen óptimo entero demostrado mediante un testigo factible y el techo de una cota dual racional exacta. Once rutas mejoran respecto de la adquisición local archivada y 35 conservan su coste. La suma descriptiva de costes de rutas evaluadas por separado pasa de 335 a 320; no representa una única ejecución que comparte adquisiciones entre rutas.

La optimización conjunta modifica el patrón de costes: 17 cuadrados tenían costes locales archivados diferentes y 13 conservan valores óptimos conjuntos diferentes. Los cuatro que igualan costes son S06, S07, S10 y S13. Esta reducción identifica dependencia de la política de adquisición en una parte de la asimetría histórica. Las diferencias de valor óptimo restantes son invariantes frente a la elección de testigos óptimos dentro de cada ruta fija.

La política es nueva y anticipativa: puede adquirir durante la primera etapa más evidencia que el mínimo necesario inmediatamente, pero únicamente mediante el sensor del contrato intermedio. Toda evidencia heredada se conserva; una coordenada tipada sensor:máscara se adquiere como máximo una vez. El contrato intermedio debe cumplirse tras la primera etapa y el final tras la segunda. No se reemplaza ningún codebook. Se consideran las 4.017 máscaras admisibles por sensor, descontando las coordenadas ya heredadas.

## Formulación y prueba

Para una ruta fija a→b→c, E es exactamente el codebook heredado de a. Las variables binarias x_q y y_q indican nuevas adquisiciones permitidas por los sensores de b y c, respectivamente. Para todo par de clases distinguible por el target de b, la distancia heredada más la contribución de x debe alcanzar d_b. Para todo par distinguible por el target de c, la distancia heredada más x e y debe alcanzar d_c. Si el mismo sensor está permitido en ambas etapas, x_q+y_q≤1. El objetivo es minimizar Σx_q+Σy_q. Los pares que ya cumplen la distancia no requieren restricciones adicionales porque las adquisiciones sólo añaden distancia.

Las columnas con contribución idéntica a todas las restricciones activas se agrupan manteniendo su capacidad entera real. Cuando ambos sensores coinciden, las variables de ambas etapas comparten dicha capacidad. Cada solución agrupada se expande a coordenadas originales distintas y se verifica contra todos los pares relevantes. Agrupar patrones no equivale a reducirlos a una única adquisición.

La relajación usada para la cota inferior permite multiplicidad no negativa sin límites superiores. Es un superconjunto de las soluciones legales. Su dual asigna pesos no negativos a las restricciones de las dos etapas. Para cada coordenada permitida en etapa 1 se verifica que la suma de sus contribuciones duales de ambas etapas es ≤1; para una coordenada permitida en etapa 2, sólo contribuye a los pesos de la segunda. El producto de los pesos racionales por las distancias residuales da L. Cuando ceil(L) coincide con el coste del testigo binario factible, queda probado el óptimo del problema original, incluyendo sus capacidades y acoplamiento.

SciPy propone soluciones y pesos; no se utiliza tolerancia de coma flotante como fundamento de exactitud. Los pesos se convierten a fracciones y todas sus desigualdades se comprueban con enteros. El verificador independiente usa exclusivamente la biblioteca estándar: reconstruye las salidas del kernel, las semánticas EXACT/MODE/ACTIONABLE, las distancias, todos los candidatos originales y los testigos. No importa el productor, SciPy o NumPy ni confía en la agrupación.

La revisión independiente comprobó 368,742 desigualdades duales, 188,412 restricciones de factibilidad por pares y los 90 hashes estructurales de raíces. También volvió a comprobar la factibilidad de los 46 comparadores históricos. Resultado: PASS, 46 óptimos certificados y brecha cero en todas las rutas.

## Las 46 rutas, sin selección posterior

La notación de contratos conserva el archivo: TARGET__SENSOR__dN. «Local» es el coste del testigo histórico. «Etapa 1» y «etapa 2» corresponden al testigo conjunto devuelto; ese reparto temporal no es único ni se afirma mínimo por etapa.

| Ruta | Origen | Intermedio | Destino | Local | Etapa 1 | Etapa 2 | Óptimo conjunto | Ahorro | Cota racional |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| S01P1 | ACTIONABLE__ACTIONABLE__d1 | ACTIONABLE__MODE__d1 | ACTIONABLE__MODE__d2 | 5 | 5 | 0 | 5 | 0 | 33/8 |
| S01P2 | ACTIONABLE__ACTIONABLE__d1 | ACTIONABLE__ACTIONABLE__d2 | ACTIONABLE__MODE__d2 | 10 | 10 | 0 | 10 | 0 | 19/2 |
| S02P1 | ACTIONABLE__ACTIONABLE__d2 | ACTIONABLE__MODE__d2 | ACTIONABLE__MODE__d3 | 5 | 5 | 0 | 5 | 0 | 5 |
| S02P2 | ACTIONABLE__ACTIONABLE__d2 | ACTIONABLE__ACTIONABLE__d3 | ACTIONABLE__MODE__d3 | 13 | 13 | 0 | 13 | 0 | 38/3 |
| S03P1 | ACTIONABLE__ACTIONABLE__d3 | ACTIONABLE__MODE__d3 | ACTIONABLE__MODE__d4 | 5 | 5 | 0 | 5 | 0 | 5 |
| S03P2 | ACTIONABLE__ACTIONABLE__d3 | ACTIONABLE__ACTIONABLE__d4 | ACTIONABLE__MODE__d4 | 14 | 14 | 0 | 14 | 0 | 27/2 |
| S04P1 | ACTIONABLE__ACTIONABLE__d4 | ACTIONABLE__MODE__d4 | ACTIONABLE__MODE__d5 | 5 | 5 | 0 | 5 | 0 | 5 |
| S04P2 | ACTIONABLE__ACTIONABLE__d4 | ACTIONABLE__ACTIONABLE__d5 | ACTIONABLE__MODE__d5 | 15 | 15 | 0 | 15 | 0 | 29/2 |
| S05P1 | ACTIONABLE__EXACT__d1 | MODE__EXACT__d1 | MODE__EXACT__d2 | 7 | 6 | 0 | 6 | 1 | 6 |
| S05P2 | ACTIONABLE__EXACT__d1 | ACTIONABLE__EXACT__d2 | MODE__EXACT__d2 | 7 | 6 | 0 | 6 | 1 | 6 |
| S06P1 | ACTIONABLE__EXACT__d2 | MODE__EXACT__d2 | MODE__EXACT__d3 | 8 | 7 | 0 | 7 | 1 | 7 |
| S06P2 | ACTIONABLE__EXACT__d2 | ACTIONABLE__EXACT__d3 | MODE__EXACT__d3 | 9 | 7 | 0 | 7 | 2 | 7 |
| S07P1 | ACTIONABLE__EXACT__d3 | MODE__EXACT__d3 | MODE__EXACT__d4 | 9 | 7 | 1 | 8 | 1 | 8 |
| S07P2 | ACTIONABLE__EXACT__d3 | ACTIONABLE__EXACT__d4 | MODE__EXACT__d4 | 10 | 8 | 0 | 8 | 2 | 8 |
| S08P1 | ACTIONABLE__EXACT__d4 | MODE__EXACT__d4 | MODE__EXACT__d5 | 10 | 9 | 0 | 9 | 1 | 9 |
| S08P2 | ACTIONABLE__EXACT__d4 | ACTIONABLE__EXACT__d5 | MODE__EXACT__d5 | 10 | 9 | 0 | 9 | 1 | 9 |
| S09P1 | ACTIONABLE__MODE__d1 | MODE__MODE__d1 | MODE__EXACT__d1 | 2 | 2 | 0 | 2 | 0 | 2 |
| S09P2 | ACTIONABLE__MODE__d1 | ACTIONABLE__EXACT__d1 | MODE__EXACT__d1 | 1 | 1 | 0 | 1 | 0 | 1 |
| S10P1 | ACTIONABLE__MODE__d1 | MODE__MODE__d1 | MODE__MODE__d2 | 8 | 8 | 0 | 8 | 0 | 91/12 |
| S10P2 | ACTIONABLE__MODE__d1 | ACTIONABLE__MODE__d2 | MODE__MODE__d2 | 10 | 8 | 0 | 8 | 2 | 91/12 |
| S11P1 | ACTIONABLE__MODE__d1 | ACTIONABLE__EXACT__d1 | ACTIONABLE__EXACT__d2 | 5 | 5 | 0 | 5 | 0 | 5 |
| S11P2 | ACTIONABLE__MODE__d1 | ACTIONABLE__MODE__d2 | ACTIONABLE__EXACT__d2 | 6 | 6 | 0 | 6 | 0 | 66/13 |
| S12P1 | ACTIONABLE__MODE__d2 | MODE__MODE__d2 | MODE__EXACT__d2 | 3 | 3 | 0 | 3 | 0 | 3 |
| S12P2 | ACTIONABLE__MODE__d2 | ACTIONABLE__EXACT__d2 | MODE__EXACT__d2 | 2 | 2 | 0 | 2 | 0 | 2 |
| S13P1 | ACTIONABLE__MODE__d2 | MODE__MODE__d2 | MODE__MODE__d3 | 11 | 10 | 0 | 10 | 1 | 10 |
| S13P2 | ACTIONABLE__MODE__d2 | ACTIONABLE__MODE__d3 | MODE__MODE__d3 | 12 | 10 | 0 | 10 | 2 | 10 |
| S14P1 | ACTIONABLE__MODE__d2 | ACTIONABLE__EXACT__d2 | ACTIONABLE__EXACT__d3 | 6 | 6 | 0 | 6 | 0 | 6 |
| S14P2 | ACTIONABLE__MODE__d2 | ACTIONABLE__MODE__d3 | ACTIONABLE__EXACT__d3 | 7 | 7 | 0 | 7 | 0 | 7 |
| S15P1 | ACTIONABLE__MODE__d3 | MODE__MODE__d3 | MODE__EXACT__d3 | 4 | 4 | 0 | 4 | 0 | 4 |
| S15P2 | ACTIONABLE__MODE__d3 | ACTIONABLE__EXACT__d3 | MODE__EXACT__d3 | 3 | 3 | 0 | 3 | 0 | 3 |
| S16P1 | ACTIONABLE__MODE__d3 | ACTIONABLE__EXACT__d3 | ACTIONABLE__EXACT__d4 | 6 | 6 | 0 | 6 | 0 | 6 |
| S16P2 | ACTIONABLE__MODE__d3 | ACTIONABLE__MODE__d4 | ACTIONABLE__EXACT__d4 | 7 | 7 | 0 | 7 | 0 | 7 |
| S17P1 | ACTIONABLE__MODE__d4 | ACTIONABLE__EXACT__d4 | ACTIONABLE__EXACT__d5 | 6 | 6 | 0 | 6 | 0 | 6 |
| S17P2 | ACTIONABLE__MODE__d4 | ACTIONABLE__MODE__d5 | ACTIONABLE__EXACT__d5 | 7 | 7 | 0 | 7 | 0 | 7 |
| S18P1 | MODE__EXACT__d1 | EXACT__EXACT__d1 | EXACT__EXACT__d2 | 6 | 6 | 0 | 6 | 0 | 6 |
| S18P2 | MODE__EXACT__d1 | MODE__EXACT__d2 | EXACT__EXACT__d2 | 6 | 6 | 0 | 6 | 0 | 6 |
| S19P1 | MODE__EXACT__d2 | EXACT__EXACT__d2 | EXACT__EXACT__d3 | 8 | 8 | 0 | 8 | 0 | 8 |
| S19P2 | MODE__EXACT__d2 | MODE__EXACT__d3 | EXACT__EXACT__d3 | 8 | 8 | 0 | 8 | 0 | 8 |
| S20P1 | MODE__EXACT__d3 | EXACT__EXACT__d3 | EXACT__EXACT__d4 | 8 | 8 | 0 | 8 | 0 | 8 |
| S20P2 | MODE__EXACT__d3 | MODE__EXACT__d4 | EXACT__EXACT__d4 | 8 | 8 | 0 | 8 | 0 | 8 |
| S21P1 | MODE__EXACT__d4 | EXACT__EXACT__d4 | EXACT__EXACT__d5 | 8 | 8 | 0 | 8 | 0 | 8 |
| S21P2 | MODE__EXACT__d4 | MODE__EXACT__d5 | EXACT__EXACT__d5 | 8 | 8 | 0 | 8 | 0 | 8 |
| S22P1 | MODE__MODE__d1 | MODE__EXACT__d1 | MODE__EXACT__d2 | 6 | 6 | 0 | 6 | 0 | 6 |
| S22P2 | MODE__MODE__d1 | MODE__MODE__d2 | MODE__EXACT__d2 | 7 | 7 | 0 | 7 | 0 | 7 |
| S23P1 | MODE__MODE__d2 | MODE__EXACT__d2 | MODE__EXACT__d3 | 6 | 6 | 0 | 6 | 0 | 6 |
| S23P2 | MODE__MODE__d2 | MODE__MODE__d3 | MODE__EXACT__d3 | 8 | 8 | 0 | 8 | 0 | 8 |

## Los 23 cuadrados

| Cuadrado | Costes locales P1/P2 | Óptimos conjuntos P1/P2 | Valores óptimos distintos |
|---|---:|---:|---|
| S01 | 5 / 10 | 5 / 10 | Sí |
| S02 | 5 / 13 | 5 / 13 | Sí |
| S03 | 5 / 14 | 5 / 14 | Sí |
| S04 | 5 / 15 | 5 / 15 | Sí |
| S05 | 7 / 7 | 6 / 6 | No |
| S06 | 8 / 9 | 7 / 7 | No |
| S07 | 9 / 10 | 8 / 8 | No |
| S08 | 10 / 10 | 9 / 9 | No |
| S09 | 2 / 1 | 2 / 1 | Sí |
| S10 | 8 / 10 | 8 / 8 | No |
| S11 | 5 / 6 | 5 / 6 | Sí |
| S12 | 3 / 2 | 3 / 2 | Sí |
| S13 | 11 / 12 | 10 / 10 | No |
| S14 | 6 / 7 | 6 / 7 | Sí |
| S15 | 4 / 3 | 4 / 3 | Sí |
| S16 | 6 / 7 | 6 / 7 | Sí |
| S17 | 6 / 7 | 6 / 7 | Sí |
| S18 | 6 / 6 | 6 / 6 | No |
| S19 | 8 / 8 | 8 / 8 | No |
| S20 | 8 / 8 | 8 / 8 | No |
| S21 | 8 / 8 | 8 / 8 | No |
| S22 | 6 / 7 | 6 / 7 | Sí |
| S23 | 6 / 8 | 6 / 8 | Sí |

## Auditoría posterior: ¿hace falta adquirir más que el mínimo local?

Esta segunda fase fue definida explícitamente después de observar los 46 resultados conjuntos. Incluye las 11 rutas que habían mejorado, sin exclusiones posteriores. Mantiene intacto el protocolo inicial y añade una única restricción: el número de nuevas adquisiciones en la etapa 1 debe ser ≤ al mínimo local original certificado. La factibilidad del contrato intermedio implica simultáneamente ≥ ese mínimo, por lo que se exige exactamente la minimalidad local.

Para cada ruta se compara J, óptimo conjunto sin esa restricción; R, óptimo conjunto con primera etapa localmente mínima y libre elección entre todos sus desempates; y A, coste local archivado. Las once rutas dan R=J<A. Los once óptimos restringidos tienen certificado racional exacto y la verificación independiente PASS comprobó 132.090 desigualdades sobre coordenadas, incluyendo una nueva prueba de los once mínimos originales de primera etapa.

| Ruta | Mínimo etapa 1 | J | R | A | Etapa 1 elegida | Etapa 2 elegida | Cota racional R |
|---|---:|---:|---:|---:|---:|---:|---:|
| S05P1 | 1 | 6 | 6 | 7 | 1 | 5 | 6 |
| S05P2 | 6 | 6 | 6 | 7 | 6 | 0 | 6 |
| S06P1 | 1 | 7 | 7 | 8 | 1 | 6 | 7 |
| S06P2 | 7 | 7 | 7 | 9 | 7 | 0 | 7 |
| S07P1 | 2 | 8 | 8 | 9 | 2 | 6 | 8 |
| S07P2 | 7 | 8 | 8 | 10 | 7 | 1 | 8 |
| S08P1 | 3 | 9 | 9 | 10 | 3 | 6 | 9 |
| S08P2 | 7 | 9 | 9 | 10 | 7 | 2 | 9 |
| S10P2 | 6 | 8 | 8 | 10 | 6 | 2 | 269/35 |
| S13P1 | 3 | 10 | 10 | 11 | 3 | 7 | 10 |
| S13P2 | 7 | 10 | 10 | 12 | 7 | 3 | 10 |

El dual de esta segunda fase incluye un multiplicador λ≥0 para el presupuesto m₁ de primera etapa. La carga dual permitida de cada columna de primera etapa es su contribución a ambas etapas menos λ; debe ser ≤1. Las columnas de segunda etapa conservan su condición anterior. La cota es L=Σbᵢyᵢ−m₁λ. Nuevamente se comprueban fracciones exactas y se compara ceil(L) con un testigo entero factible.

**Resultado interpretativo:** los quince ahorros acumulados entre rutas independientes se consiguen eligiendo mejor entre mínimos locales existentes. En esta familia no hay ningún caso que requiera sobre-adquirir en la primera etapa para alcanzar el óptimo conjunto. La información del destino siguiente permite seleccionar el desempate; no se ha demostrado una regla única que opere ignorando ese destino.

## Corolario: catálogo de planes con ambos pasos localmente mínimos

**Proposición finita.** Para cada una de las 46 rutas congeladas existe un plan cuyos dos pasos son localmente mínimos respecto de su estado heredado y cuyo coste total coincide con el óptimo conjunto de esa ruta.

**Demostración.** En las 35 rutas no mejoradas, el testigo histórico ya tiene coste total A=J y el mínimo del primer paso está certificado. En las otras once, la auditoría posterior construye un primer paso localmente mínimo con coste total R=J. En cualquiera de las 46, si desde ese primer estado existiese un segundo paso factible más barato, se obtendría un plan de la misma ruta con coste total inferior a J, contradiciendo su certificado de optimalidad. Por tanto el segundo paso elegido también es localmente mínimo. Esta demostración no necesita ejecutar nuevas optimizaciones.

`LOCAL_MINIMUM_LOOKAHEAD_CATALOG.json` contiene los 46 planes concretos: 35 testigos históricos y once testigos de la auditoría posterior. Cada entrada incluye estado heredado completo, adquisiciones de ambas etapas, costes y referencias de prueba. El verificador principal, con el argumento `--catalog`, comprueba directamente todas sus adquisiciones y vuelve a demostrar cada mínimo de primera etapa con los certificados originales. La cota conjunta menos el coste fijo de primera etapa certifica el segundo mínimo.

Procedimiento de uso dentro del alcance certificado: identificar la ruta completa origen→intermedio→destino; comprobar que el estado heredado coincide exactamente con el codebook de origen; escoger su entrada; adquirir únicamente las coordenadas de primera etapa y comprobar el contrato intermedio; conservar todo lo heredado y adquirir las de segunda etapa. Cambios del estado, de sensores, del coste, de los contratos o de la ruta requieren otro cálculo. El catálogo no ejecuta observaciones ni confiere autorización.

Este corolario demuestra existencia para estas 46 rutas. No demuestra que cualquier desempate local sea bueno, que una única elección local sirva para todos los destinos futuros, ni que la propiedad se extienda a rutas de tres o más etapas o al grafo completo.

Protocolo posterior SHA-256: `3b9f6476168cde70dc28afbfe8130e5e8582a7eb305f46cc2c69e01c41b5f187`.
Certificados posteriores SHA-256: `44369f886b912d165da207abf95274ee51a68c61f7465498448f8585092afed8`.

## Alcance exacto y reservas

- Se demuestra optimalidad para cada ruta fija de dos etapas. No se resuelve el camino más corto del grafo completo ni una política óptima global.
- Los 11 ahorros comparan contra los testigos locales archivados. La auditoría posterior demuestra que un desempate local adecuado basta en todas esas rutas; no demuestra que cualquier regla local sin información del destino futuro lo encuentre.
- Treinta testigos de la primera optimización adelantaron adquisiciones a la primera etapa. La auditoría posterior y el catálogo demuestran que ese exceso no es necesario para alcanzar ninguno de los 46 óptimos; no debe presentarse aquel conteo como un requisito de planificación.
- Los 13 cuadrados con valores óptimos diferentes tienen dependencia del valor de coste respecto de la ruta dentro de la política especificada. Los 10 con costes iguales no demuestran igualdad de conjuntos finales, de observaciones, de genealogías o de recibos.
- La conservación append-only y las distancias del kernel no constituyen una hélice geométrica ni validación de una tesis física universal.
- Este cálculo es determinista sobre objetos matemáticos archivados. No contiene observaciones nuevas, datos físicos, muestras sintéticas, datos imputados ni lecturas inventadas.
- Los resultados originales de los 204 puentes locales y las 238 coincidencias de hashes continúan siendo válidos para su propio problema. La política conjunta no corrige retrospectivamente ni sustituye la historia de ejecución.
- No se reconstruyen el generador histórico desaparecido, su caché, los recibos completos ni las cadenas de autoridad. permission_granted permanece false.

## Reproducción

Requisitos del productor usados en esta ejecución: Python 3.12.14, NumPy 2.3.5 y SciPy 1.17.0. El verificador sólo necesita Python y la biblioteca estándar. Las rutas siguientes se invocan desde la carpeta del proyecto y pueden adaptarse pasando los dos argumentos explícitos.

```bash
python work/continuity_v3/ech_joint/check_joint_certificates.py --source repo/research/continuity_v2_20261013/evidence/ech --results work/continuity_v3/ech_joint --catalog work/continuity_v3/ech_joint/LOCAL_MINIMUM_LOOKAHEAD_CATALOG.json
python work/continuity_v3/ech_joint/check_posthoc_local_ties.py --source repo/research/continuity_v2_20261013/evidence/ech --results work/continuity_v3/ech_joint
```

Para recalcular con solver, usar una carpeta nueva. La primera fase requiere copiar allí `PROTOCOL_FIXED_TWO_STAGE.json` y ejecutar `solve_joint_routes.py --source RUTA_ECH_V2 --output CARPETA_NUEVA`. La segunda fase se reproduce por separado copiando los dos protocolos y los resultados/certificados conjuntos originales a otra carpeta nueva: el protocolo posterior está ligado expresamente al hash del resultado original, no a un resultado recalculado con tiempos distintos. Ejecutar allí `solve_posthoc_local_ties.py` con los mismos argumentos. El archivo README detalla esta distinción.

El verificador no ejecuta optimización. El productor puede devolver otro testigo óptimo según versiones o desempates del solver; se deben comparar los óptimos, la factibilidad y las pruebas exactas, no exigir identidad de las coordenadas elegidas. No se afirma identidad binaria de logs con tiempos de ejecución.

Protocolo congelado SHA-256: `e4054024e5789f8a82d3ef8bb5c2ee312f291d1954bda28efff4583e53d81db8`.
Certificados SHA-256: `f14655ea2e34c085ac91620a3cf736b39e60dfd7d46fa5c466f471f3004c16f0`.
Resultado canónico SHA-256: `d3215831b7c32a92674592fb5e427d86b0296f7cd3b427f92bc3dd3e3839e1e3`.
