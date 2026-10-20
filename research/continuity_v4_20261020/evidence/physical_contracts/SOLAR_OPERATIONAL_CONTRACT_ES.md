# Contrato operacional solar: información, operador y evidencia

Fecha: 20 de octubre de 2026. Continuación aditiva; no modifica v1.3, v1.5, v1.6 ni el diagnóstico v3. No se adquirieron observaciones, ajustaron modelos o generaron datos. HHC excluido. El contrato distingue tres niveles: el resultado archivado, su interpretación corregida y las condiciones de una ejecución futura.

## 1. Qué observamos y qué no identificamos

La fibra archivada tiene 16 componentes: `HC_SIGNED_MEAN`, `HC_NORMALIZED` y `ALPHA_WEIGHTED_PER_MM` en cinco escalas de suavizado de 0, 1, 2, 4 y 8 píxeles, más `SIGNED_HC_LOG_SCALE_INTEGRAL`. Esas escalas son parámetros del operador sobre el mapa; no nuevas regiones físicas independientes.

`Bz Jz` es una contribución vertical de helicidad de corriente. Hay que explicitar la convención de `Jz`: corriente eléctrica en SI y componente de `curl B` difieren por μ₀. Las unidades nativas del producto y sus conversiones deben acompañar cada transformación. No se declara que este proxy sea toda `B·curl B`, que sea `A·B`, ni que mida helicidad relativa de un volumen coronal. Reconciliar índices SHARP con los mismos campos comprueba consistencia computacional, no una segunda medición instrumental independiente. [S01, S04]

La helicidad volumétrica exige un volumen, campo de referencia y condiciones de contorno apropiados. El flujo de helicidad exige además inferir campos de velocidad o eléctricos; esa inversión tiene grados de libertad que la evolución de la componente normal por sí sola no determina. La rama de flujo y la rama de transporte de la fibra observada tienen obligaciones distintas. Un resultado de una no cierra la otra. [S02-S04]

## 2. PREDICT, TRACK y RECONSTRUCT

Sea τ la hora de emisión y A(τ) la información realmente disponible entonces, incluidos tiempos de publicación y versiones. El tiempo de medición no basta: un producto definitivo publicado después de τ no pertenecía a A(τ).

| Tarea | Blanco y acceso permitidos | Obligación verificable |
|---|---|---|
| PREDICT | Estimar un estado o resultado con tiempo objetivo posterior a τ utilizando sólo A(τ). | Todos los predictores, parámetros, normalizadores, selección y regla de activación estaban disponibles antes de emisión; el objetivo posterior no interviene. |
| TRACK | Actualizar una estimación del estado presente a medida que llegan observaciones, con latencia declarada. | Registrar secuencia, latencia y revisiones. No introducir información que sólo llega después de la actualización evaluada. |
| RECONSTRUCT | Inferir una transición o un estado pasado condicionado en datos de ambos extremos o posteriores. | Declarar exactamente qué extremos y productos se usan; no presentar el error como rendimiento de pronóstico. |

La evaluación retrospectiva fuera de región es un diseño de análisis, no una cuarta operación física. Puede evaluar ecuaciones potencialmente aptas para PREDICT sin demostrar que la ejecución histórica haya sido prospectiva. La taxonomía no altera los números: impide transportar una garantía temporal que no se verificó.

## 3. Los cinco operadores realmente implementados

Se conserva el identificador histórico y se añade una descripción operacional. `x_k` es la fibra inicial; `s_k=(-1)^k` tiene fase fijada, no ajustada; `z=x/scale` usa RMS de objetivos de entrenamiento.

| ID histórico | Operación | Parámetros ajustados | Uso del extremo final del test |
|---|---|---:|---|
| T0_TRIVIAL_IDENTITY | `ŷ=x` | 0 | No en la ecuación; sí para evaluar error. |
| H_HELICAL_TRANSLATION | `ŷ=x+b_H`, con `b_H=mean_train(y−x)` | 16 | No en la ecuación; el tiempo del entrenamiento sigue siendo una obligación separada. |
| L_LEMNISCATIC_ALTERNATING | `ŷ=x+s_k b_L`, con `b_L=mean_train[s_k(y−x)]` | 16 | No en la ecuación. La fase debe estar disponible y definida antes de emisión. |
| M_MOBIUS_SIGN | `ŷ=−x` | 0 | No en la ecuación. No representa toda alternativa geométrica. |
| G_ACTIVITY_AFFINE | `ẑ_y=a z_x+b_component+c Δq` | 18 | Sí: `Δq=q_{k+1}−q_k` usa actividad del extremo final; RECONSTRUCT condicional. |

La actividad `q` promedia cuatro componentes transformadas con logaritmo y normalizadas con media/desvío de entrenamiento: helicidad de corriente no firmada, proxy de energía magnética, RMS de Jz y energía de gradiente. El protocolo fija sigma=2 píxeles. Normalización sólo en TRAIN evita contaminación por el fold de test, pero no demuestra cronología operacional del entrenamiento.

H y L son traslación y alternancia. Para dos HARPs de entrenamiento, cada uno con cuatro transiciones:

`b_H = [(x4−x0)_A+(x4−x0)_B]/8`.

`b_L = Σ_{A,B}(−x0+2x1−2x2+2x3−x4)/8`.

El coeficiente de H cancela el interior por telescopaje; normalizadores y evaluación sí pueden depender del interior. No es una prueba de toda geometría helicoidal. Las denominaciones lemniscática y Möbius tampoco acreditan por sí mismas una topología física.

## 4. Auditoría temporal nueva del diseño archivado

El análisis deja una región fuera y entrena en las otras dos. Eso mantiene separación de región, pero no orden temporal en dos de los tres folds. `PHYSICAL_CONTRACT_AUDIT.json` reconstruye esta tabla directamente desde los identificadores y horas TAI del resultado v1.6; no modifica la selección ni repite el ajuste.

| HARP evaluado | Año del test | HARPs y años de entrenamiento | Fuente posterior al inicio del test |
|---|---:|---|---|
| 401 | 2011 | 2920 (2013), 5249 (2015) | Ambas |
| 2920 | 2013 | 401 (2011), 5249 (2015) | HARP 5249 |
| 5249 | 2015 | 401 (2011), 2920 (2013) | Ninguna de esas observaciones |

Por tanto, H/L/G en los dos primeros folds no son un replay cronológico de un predictor que existiera en 2011 o 2013. Es un ensayo retrospectivo legítimo de transferencia entre regiones. El tercer fold tampoco constituye confirmación prospectiva: fue diseñado y ejecutado después de los datos, dentro de un programa de desarrollo con exposición anterior. T0/M no ajustan esos coeficientes, pero la selección del panel y su interpretación siguen siendo retrospectivas.

Además, la selección de cada ventana exigió que las cinco instantáneas futuras cumplieran QUALITY=0, CMASK≥1000 y disponibilidad de segmentos. Esa selección previa a leer campos evita escoger por sus valores, pero condiciona el estimando en soporte completo conocido al final de la ventana. Una operación online no puede garantizar a la emisión la calidad de las cuatro adquisiciones siguientes. Debe registrar fallos y cobertura, en lugar de reconstruir retrospectivamente una población siempre completa.

Estas observaciones refuerzan una reserva ya existente: v1.6 es desarrollo. No invalidan la aritmética, no convierten el estudio en fraudulento y no alteran `NO_DEVELOPMENT_DOMINANT_LIFT`.

## 5. Toda la competencia local sigue presente

`SOLAR_LOCAL_PRESERVED.csv` conserva las 12 transiciones y los cuatro contrastes frente a T0, con NMSE absoluto de ambos modelos, diferencia absoluta y ganancia relativa. H mejora 4, L 7, G 5 y M 0. No se seleccionaron sólo casos positivos.

Por ejemplo, en HARP 2920/k3, T0 tiene NMSE 0,04564897118 y H 0,02656846885: ganancia absoluta 0,01908050233 y relativa 41,7983184%. Es un resultado descriptivo situado del panel. Aún no se mostró que una política pudiera reconocer ese régimen antes del desenlace.

El balance global archivado permanece: T0 0,595157570; H 0,621751465; L 0,594013807; G 1,071522606; M 5,594851754. L mejora NMSE 0,192178% y empeora NMAE 1,186546%; H empeora NMSE 4,468379%. Las transiciones comparten instantáneas y los agregados se solapan: su número no es un tamaño muestral independiente.

## 6. Gate de flujo v1.3: bloqueo material preciso

Se inspeccionaron los nombres y texto de los 108 archivos del corpus recuperado v1/v2/v3, y los 51 miembros de los tres ZIP incluidos. `DAVE_SOURCE_SEARCH.json` contiene inventario, hashes, patrón, coincidencias y límites; ningún archivo de código coincidió con DAVE4VM, inducción o flujo de helicidad. Las coincidencias útiles remiten al estado histórico en registros; la mención a inducción matemática de PAPER 1 no es el gate físico.

No se recuperó una implementación suficiente del gate v1.3. Esta ausencia vale para esos bytes locales, no para todos los archivos remotos del proyecto. El estado correcto es `BLOCKED_MISSING_ORIGINAL_GATE_IMPLEMENTATION`; no `BUG_CONFIRMED` y no `FLUX_RESCUED`.

Liu et al. (2026), sección II.2, distingue derivadas internas de la solución por ventana de operaciones diferenciales sobre el mosaico de velocidades. Esa distinción crea una obligación de inspección concreta para nuestro gate, no una prueba de que lo implementara mal. También advierte sensibilidad a componentes no inductivos y Doppler. [S07]

Para resolver el bloqueo hacen falta: versión exacta del estimador; fuente del gate; pares de registros y máscaras; unidades y sistema de coordenadas; paso temporal/espacial; tamaño de ventana; derivadas exportadas o coeficientes locales; criterio de balance; tratamiento de bordes; umbrales originales y recibo del resultado. Con esos materiales podrá comprobarse si se evaluó la misma ecuación local ajustada o un residual del mosaico con interpretación distinta. La calidad de una inversión no quedaría validada sólo por pasar ese control.

## 7. Condiciones concretas de continuación

1. Publicar separadamente comparación retrospectiva de T0/H/L/M y reconstrucción condicionada G. No convertir su orden actual en ganador de pronóstico.
2. Antes de nuevos objetivos, fijar hora de emisión, latencia, productos/vintages, grupos de regiones, ventana de entrenamiento que termine antes de τ y definición de datos faltantes. Registrar cobertura y abstención.
3. Fijar una pregunta local: por ejemplo, transferencia bajo derivas inicialmente compatibles. Sus rasgos deben ser observables en A(τ); las condiciones descubiertas con este panel sólo pueden orientar decisiones futuras.
4. Comparar con persistencia, deriva local regularizada, un autorregresivo y transporte de complejidad comparable. No atribuir a este documento resultados de esos rivales todavía no ejecutados.
5. Mantener intactos el gate anterior, el panel de desarrollo y las regiones ya expuestas. Una corrección técnica o una hipótesis nueva crea una versión y un estimando nuevos; no convierte el pasado en test virgen.

La mejora material es un contrato de información comprobable: separa causalidad de la ecuación, cronología del ajuste y selección de las observaciones. El archivo muestra exactamente dónde el diseño conserva transferencia entre regiones y dónde no permite reclamar disponibilidad temporal. Su frontera es una evaluación con emisión y datos realmente disponibles documentados, o la recuperación del gate de flujo para resolver su objeción técnica; ninguna queda simulada como completada.

## Fuentes primarias y corpus

S01 Bobra et al. (2014), SHARP: https://arxiv.org/abs/1404.1879 . S02 Schuck (2008), DAVE4VM: https://arxiv.org/abs/0803.3472 . S03 Welsch y Fisher (2008), espacio nulo: https://arxiv.org/abs/0710.0546 . S04 Berger y Field (1984), helicidad relativa: https://doi.org/10.1017/S0022112084002019 . S06 Leka et al. (2019), comparación de pronósticos: https://arxiv.org/abs/1907.02905 . S07 Liu et al. (2026): https://arxiv.org/html/2604.16098v1 . Profundidad de lectura y límites bibliográficos: `PRIMARY_SOURCES.json`.

Corpus exacto: `research/continuity_v2_20261013/evidence/solar/SELECTED_PROTOCOL_V1_6.json`, `TEMPORAL_LIFT_DEVELOPMENT_RESULT_V1_6.json`, `research/continuity_v2_20261013/tools/verify_solar_v16.py`, y `research/continuity_v3_20261013/evidence/solar_local/`. Sus huellas efectivamente usadas están en `PHYSICAL_CONTRACT_AUDIT.json`.
