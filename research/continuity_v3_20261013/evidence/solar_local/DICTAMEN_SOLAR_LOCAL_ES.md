# Dictamen solar v1.6: descomposición local exhaustiva

El diagnóstico conserva el resultado congelado `NO_DEVELOPMENT_DOMINANT_LIFT`. H no mejora la identidad en ninguno de los tres HARPs; su NMSE global es un 4,468379% mayor. Aun así, H mejora cuatro transiciones concretas de las doce. G mejora cinco transiciones y pierde al agregar cada uno de los tres HARPs. La heterogeneidad local existe y queda expuesta completa; no basta para definir una regla prospectiva de selección de modelos.

L obtiene la menor NMSE global por un margen de apenas 0,192178% frente a la identidad, con una sola victoria de fold y una NMAE un 1,186546% peor. No alcanza el margen del 5% ni las dos victorias requeridas. Su mejora en HARP 5249 compensa casi exactamente las pérdidas en 401 y 2920. Ninguna de estas observaciones permite promover una topología física.

El hallazgo estructural decisivo es más preciso que una comparación de puntuaciones: el coeficiente de traslación b de H aprende exclusivamente el desplazamiento neto entre extremos de las trayectorias de entrenamiento. Por telescopaje, no aprende su geometría interior. Esta delimitación explica qué operación fue contrastada y evita convertir su resultado negativo en una refutación de toda helicoidalidad.

## Cobertura, procedencia y estatuto

Análisis descriptivo post hoc. Alcance registrado en `PRECALCULATION_SCOPE_ES.md` antes del cálculo diagnóstico y después de conocerse el resultado v1.6. Fuentes reales congeladas: tres HARPs, 15 instantáneas, 12 transiciones y 16 componentes. No hay nuevas observaciones, segmentos FITS ni resultados solares externos. No se cambiaron fechas, selección, fase, normalizadores, parámetros, puntuación ni gate. Las cinco predicciones usan exclusivamente los parámetros y normalizadores de entrenamiento publicados.

Se publican **960 celdas** (3 × 4 × 16 × 5), **1.200 agregaciones**, 96 parámetros H/L, 192 contribuciones por HARP de entrenamiento, 768 sensibilidades por transición de entrenamiento y 60 derivadas analíticas por instantánea. Los recuentos son de auditoría, no tamaños muestrales inferenciales. Las componentes comparten campos, las escalas se solapan y las transiciones comparten extremos. No se calculan p-valores, intervalos de significación ni un número ficticio de réplicas.

Cada escala ordinaria contiene tres componentes; la integral entre escalas es una sola componente y conserva una categoría propia `cross_scale`. La media global pondera las cinco escalas con 3/16 cada una y la integral con 1/16. Las familias HC_SIGNED_MEAN, HC_NORMALIZED y ALPHA_WEIGHTED_PER_MM pesan 5/16 cada una y la integral 1/16. No se promedian sin ponderación las medias de estas seis categorías; tampoco se suman marginals de escala y familia entre sí. Los normalizadores difieren por fold y proceden exclusivamente de los otros dos HARPs.

El verificador stdlib independiente reconstruye las predicciones desde el resultado congelado, sin importar el generador diagnóstico ni el runtime científico. Verifica todas las celdas, todas las agregaciones y las sensibilidades. La reproducción v2 volvió a superar sus 60 comprobaciones numéricas. Además, la auditoría local superó 43924 comparaciones; diferencia absoluta máxima de coma flotante 2.84e-14. Una primera etiqueta de trabajo sumaba erróneamente 1.300 agregaciones; la verificación exhaustiva corrigió el conteo a 1.200, sin cambiar las celdas, métricas o resultados científicos.

## Puntuaciones globales completas

Una ganancia positiva indica menor error que T0. Una negativa indica deterioro. Los cinco rivales operativos son T0 identidad, M inversión de signo, H traslación de deriva, L deriva alternante con fase fija y G ajuste afín condicionado a actividad del extremo.

| Rival | NMSE | NMAE | Ganancia NMSE % | Ganancia NMAE % | Folds mejor que T0 | Transiciones mejor que T0 |
| --- | --- | --- | --- | --- | --- | --- |
| T0 | 0.595157569883 | 0.591468247263 | +0.000000 | +0.000000 | 0 | 0 |
| M | 5.594851754134 | 1.845868748783 | -840.062269 | -212.082476 | 0 | 0 |
| H | 0.621751465448 | 0.610536983161 | -4.468379 | -3.223966 | 0 | 4 |
| L | 0.594013806570 | 0.598486289069 | +0.192178 | -1.186546 | 1 | 7 |
| G | 1.071522606060 | 0.809345902821 | -80.040154 | -36.836746 | 0 | 5 |

Los recuentos anteriores comparan cada rival contra identidad; no son el número de veces que obtiene el mínimo entre los cinco. Los ganadores del fold son T0 en 401 y 2920 y L en 5249. Los conteos por celdas normalizadas son H 82 mejores / 110 peores, L 95 / 97, M 17 / 175 y G 82 / 110; las 192 celdas de cada rival no son observaciones independientes.

## Los tres HARPs, sin descartar ninguno

NMSE completa:

| harp | T0 | M | H | L | G |
| --- | --- | --- | --- | --- | --- |
| 401 | 0.332286664 | 3.831095011 | 0.365638720 | 0.344004953 | 1.181612841 |
| 2920 | 0.256792110 | 4.626089972 | 0.290091112 | 0.256926909 | 0.422712386 |
| 5249 | 1.196393935 | 8.327370279 | 1.209524564 | 1.181109558 | 1.610242592 |

Ganancia de NMSE frente a T0 (%):

| harp | M | H | L | G |
| --- | --- | --- | --- | --- |
| 401 | -1052.948770201 | -10.037133373 | -3.526559993 | -255.600439921 |
| 2920 | -1701.492256006 | -12.967299666 | -0.052493563 | -64.612684525 |
| 5249 | -596.039158404 | -1.097517149 | 1.277537221 | -34.591336880 |

H pierde un 10,037133% en 401, un 12,967300% en 2920 y un 1,097517% en 5249. La media global no oculta una victoria completa de H en una región. Sí oculta victorias dentro de algunas transiciones, detalladas a continuación.

## Las doce transiciones, sin seleccionar victorias

El índice k mantiene el origen y la fase publicados: k=0,1,2,3 dentro de cada HARP; no se desplazó para favorecer L. `TRANSITIONS_ALL_12.csv` incluye las fechas TAI exactas, q en ambos extremos, delta_q y a,c de G.

NMSE completa:

| harp | transition_k | T0 | M | H | L | G |
| --- | --- | --- | --- | --- | --- | --- |
| 401 | 0 | 0.197191628 | 2.968732010 | 0.168850551 | 0.289864949 | 2.779339026 |
| 401 | 1 | 0.288232728 | 6.061773624 | 0.305387989 | 0.189023338 | 1.826777549 |
| 401 | 2 | 0.374883998 | 5.140942159 | 0.451914506 | 0.281814699 | 0.082517898 |
| 401 | 3 | 0.468838304 | 1.152932253 | 0.536401835 | 0.615316826 | 0.037816890 |
| 2920 | 0 | 0.259399221 | 7.619623133 | 0.183565397 | 0.202958711 | 1.212085591 |
| 2920 | 1 | 0.323364238 | 7.405078581 | 0.437849168 | 0.250925327 | 0.217752150 |
| 2920 | 2 | 0.398756008 | 2.448771879 | 0.512381414 | 0.483527076 | 0.085452422 |
| 2920 | 3 | 0.045648971 | 1.030886295 | 0.026568469 | 0.090296524 | 0.175559379 |
| 5249 | 0 | 0.174640720 | 3.733832098 | 0.178656545 | 0.174016880 | 1.312565859 |
| 5249 | 1 | 1.331558935 | 2.956201059 | 1.367659368 | 1.394482991 | 1.032822333 |
| 5249 | 2 | 1.719500703 | 8.796978342 | 1.763635930 | 1.651984076 | 2.058575272 |
| 5249 | 3 | 1.559875383 | 17.822469617 | 1.528146413 | 1.503954284 | 2.037006905 |

Ganancia frente a T0 (%):

| harp | transition_k | M | H | L | G |
| --- | --- | --- | --- | --- | --- |
| 401 | 0 | -1405.506107704 | 14.372353208 | -46.996579641 | -1309.460963407 |
| 401 | 1 | -2003.083042281 | -5.951878236 | 34.419890672 | -533.785608466 |
| 401 | 2 | -1271.342119405 | -20.547825088 | 24.826159318 | 77.988418208 |
| 401 | 3 | -145.912555275 | -14.410838543 | -31.242865772 | 91.933916300 |
| 2920 | 0 | -2837.411723396 | 29.234406931 | 21.758165017 | -367.266472762 |
| 2920 | 1 | -2190.011604257 | -35.404326290 | 22.401645912 | 32.660410723 |
| 2920 | 2 | -514.102816364 | -28.494970193 | -21.258881431 | 78.570248345 |
| 2920 | 3 | -2158.290313988 | 41.798318416 | -97.806262396 | -284.585620075 |
| 5249 | 0 | -2038.007733653 | -2.299478364 | 0.357213282 | -651.580650598 |
| 5249 | 1 | -122.010530740 | -2.711140432 | -4.725592960 | 22.435101771 |
| 5249 | 2 | -411.600741156 | -2.566746656 | 3.926525145 | -19.719361997 |
| 5249 | 3 | -1042.557271533 | 2.034070859 | 3.584972230 | -30.587797370 |

H mejora 401/k0, 2920/k0, 2920/k3 y 5249/k3. Su mayor reducción descriptiva es 41,798318% en 2920/k3; esa transición tiene una NMSE de identidad pequeña, 0,045648971, por lo que una gran reducción porcentual no implica una gran contribución global. G obtiene reducciones de 77,988418% y 91,933916% en 401/k2 y k3, pero sus errores en k0 y k1 anulan estas ventajas. Las fechas o índices de estas victorias se conocen después de evaluar; no constituyen una regla de enrutamiento fuera de muestra.

## Todas las escalas y familias

NMSE por escala, agregando los tres HARPs:

| scale | T0 | M | H | L | G |
| --- | --- | --- | --- | --- | --- |
| 0.0 | 0.617308754 | 4.096243363 | 0.629119627 | 0.611454675 | 0.952920332 |
| 1.0 | 0.612857991 | 3.936437654 | 0.633018415 | 0.606292430 | 1.019477149 |
| 2.0 | 0.510035504 | 4.754432102 | 0.539709885 | 0.512306285 | 0.993224815 |
| 4.0 | 0.397862570 | 4.378704594 | 0.416157825 | 0.401325945 | 0.883596502 |
| 8.0 | 0.879153518 | 11.110871650 | 0.935057169 | 0.878725700 | 1.508275808 |
| cross_scale | 0.470866107 | 4.687559977 | 0.488834685 | 0.473905798 | 1.071877881 |

Ganancia frente a T0 (%):

| scale | M | H | L | G |
| --- | --- | --- | --- | --- |
| 0.0 | -563.564761653 | -1.913284527 | 0.948322690 | -54.366891010 |
| 1.0 | -542.308285614 | -3.289575172 | 1.071302141 | -66.348022584 |
| 2.0 | -832.176694360 | -5.818100952 | -0.445220196 | -94.736407049 |
| 4.0 | -1000.557057891 | -4.598385557 | -0.870495398 | -122.085857864 |
| 8.0 | -1163.814728571 | -6.358804216 | 0.048662523 | -71.560003644 |
| cross_scale | -895.518664725 | -3.816069556 | -0.645553332 | -127.639633787 |

H pierde en las cinco escalas y en la integral; L mejora en sigma 0, 1 y 8, y empeora en sigma 2, 4 y en la integral. M y G pierden en las seis categorías agregadas. Estas seis medias no son seis experimentos independientes.

NMSE por familia:

| family | T0 | M | H | L | G |
| --- | --- | --- | --- | --- | --- |
| HC_SIGNED_MEAN | 0.421537026 | 4.237716477 | 0.446136589 | 0.417819580 | 0.894247102 |
| HC_NORMALIZED | 0.981172785 | 8.453753276 | 1.008023586 | 0.982737030 | 1.474528114 |
| ALPHA_WEIGHTED_PER_MM | 0.407621190 | 4.274543865 | 0.437677578 | 0.405506412 | 0.845721547 |
| SIGNED_HC_LOG_SCALE_INTEGRAL | 0.470866107 | 4.687559977 | 0.488834685 | 0.473905798 | 1.071877881 |

Ganancia frente a T0 (%):

| family | M | H | L | G |
| --- | --- | --- | --- | --- |
| HC_SIGNED_MEAN | -905.301126894 | -5.835682473 | 0.881878964 | -112.139633243 |
| HC_NORMALIZED | -761.596795300 | -2.736602646 | -0.159425966 | -50.282206735 |
| ALPHA_WEIGHTED_PER_MM | -948.655949556 | -7.373607681 | 0.518809828 | -107.477326353 |
| SIGNED_HC_LOG_SCALE_INTEGRAL | -895.518664725 | -3.816069556 | -0.645553332 | -127.639633787 |

L mejora HC_SIGNED_MEAN un 0,881879% y ALPHA_WEIGHTED_PER_MM un 0,518810%; empeora HC_NORMALIZED un 0,159426% y la integral un 0,645553%. H no mejora ninguna de las cuatro familias agregadas. Se retienen todas las componentes, incluidos los resultados que contradicen las ganancias de L.

Ganancia completa por HARP y escala (%):

| harp | scale | M | H | L | G |
| --- | --- | --- | --- | --- | --- |
| 401 | 0.0 | -295.909972426 | 0.840761001 | -0.979057789 | -281.656746359 |
| 401 | 1.0 | -467.075239816 | 0.028980824 | -3.680206166 | -214.822885248 |
| 401 | 2.0 | -837.382120376 | -2.176676798 | -4.658340479 | -216.789763743 |
| 401 | 4.0 | -2585.738746771 | -26.496363583 | -1.917946486 | -377.229398908 |
| 401 | 8.0 | -8468.839618409 | -236.858948526 | -16.241271267 | -731.120182672 |
| 401 | cross_scale | -1025.717674847 | -3.672276514 | -3.409867765 | -187.548331584 |
| 2920 | 0.0 | -957.535202969 | -9.754923377 | 2.451070250 | 25.815470812 |
| 2920 | 1.0 | -1490.225014805 | -12.659921635 | 3.545271425 | -3.090744461 |
| 2920 | 2.0 | -2221.438186264 | -18.450952948 | 1.375825891 | -69.415089515 |
| 2920 | 4.0 | -2580.315331511 | -5.528161869 | -8.861752457 | -255.480728589 |
| 2920 | 8.0 | -2637.566925962 | -75.607134170 | -221.337296255 | -2938.041082813 |
| 2920 | cross_scale | -1733.555031535 | -8.980451986 | 3.176310554 | -79.567116722 |
| 5249 | 0.0 | -528.688538689 | -0.496711005 | 1.069746502 | -12.952833249 |
| 5249 | 1.0 | -169.803412058 | -0.931039114 | 2.440929542 | -17.455803114 |
| 5249 | 2.0 | -53.550085118 | -1.263161836 | 1.423077164 | -25.306810340 |
| 5249 | 4.0 | -378.163224162 | 0.560805700 | 0.684185969 | -41.802233427 |
| 5249 | 8.0 | -1027.746725088 | -1.988865245 | 1.085584322 | -50.081803064 |
| 5249 | cross_scale | -5.224109114 | -0.132570404 | 1.693271474 | -50.318767049 |

Ganancia completa por HARP y familia (%):

| harp | family | M | H | L | G |
| --- | --- | --- | --- | --- | --- |
| 401 | HC_SIGNED_MEAN | -1032.749262175 | -6.938163567 | -1.977100441 | -204.302430622 |
| 401 | HC_NORMALIZED | -919.139403189 | -17.064522533 | -15.831219893 | -474.035664420 |
| 401 | ALPHA_WEIGHTED_PER_MM | -1160.052096092 | -15.388381975 | -0.777480346 | -280.319777814 |
| 401 | SIGNED_HC_LOG_SCALE_INTEGRAL | -1025.717674847 | -3.672276514 | -3.409867765 | -187.548331584 |
| 2920 | HC_SIGNED_MEAN | -1551.874723491 | -12.415302737 | 2.180777251 | -64.902419552 |
| 2920 | HC_NORMALIZED | -1875.836502017 | -17.752982942 | -5.773091154 | -66.991854268 |
| 2920 | ALPHA_WEIGHTED_PER_MM | -1706.751616685 | -11.139597193 | 1.142661817 | -60.041425051 |
| 2920 | SIGNED_HC_LOG_SCALE_INTEGRAL | -1733.555031535 | -8.980451986 | 3.176310554 | -79.567116722 |
| 5249 | HC_SIGNED_MEAN | -464.443122331 | -1.536498903 | 2.992684026 | -46.736266629 |
| 5249 | HC_NORMALIZED | -669.774512232 | -0.897339116 | 1.036795183 | -28.127201414 |
| 5249 | ALPHA_WEIGHTED_PER_MM | -467.317617814 | -1.698187457 | 0.816027548 | -49.851594379 |
| 5249 | SIGNED_HC_LOG_SCALE_INTEGRAL | -5.224109114 | -0.132570404 | 1.693271474 | -50.318767049 |

Ganancia de cada una de las dieciséis componentes, agregando los HARPs (%):

| component | M | H | L | G |
| --- | --- | --- | --- | --- |
| HC_SIGNED_MEAN@sigma=0.0 | -508.951204927 | -1.401356905 | 2.054457271 | -61.705195234 |
| HC_NORMALIZED@sigma=0.0 | -559.351821291 | -1.697209255 | 0.491597812 | -41.679307427 |
| ALPHA_WEIGHTED_PER_MM@sigma=0.0 | -629.760129561 | -2.770602407 | 0.334586434 | -63.247519847 |
| HC_SIGNED_MEAN@sigma=1.0 | -586.317835097 | -2.861741014 | 2.021622301 | -83.162235069 |
| HC_NORMALIZED@sigma=1.0 | -404.657391070 | -2.784022321 | 0.008139601 | -44.050537705 |
| ALPHA_WEIGHTED_PER_MM@sigma=1.0 | -692.443763604 | -4.477542559 | 1.571717273 | -80.208770201 |
| HC_SIGNED_MEAN@sigma=2.0 | -981.808804425 | -5.688355817 | -0.046636342 | -125.117836797 |
| HC_NORMALIZED@sigma=2.0 | -542.356186342 | -4.848245747 | -1.255837573 | -57.802051707 |
| ALPHA_WEIGHTED_PER_MM@sigma=2.0 | -1129.146270562 | -7.482372982 | 0.406589720 | -120.551266287 |
| HC_SIGNED_MEAN@sigma=4.0 | -1742.293123321 | -8.860205199 | -2.720894304 | -214.927825189 |
| HC_NORMALIZED@sigma=4.0 | -553.931596799 | -1.431573706 | -0.364405338 | -61.483165036 |
| ALPHA_WEIGHTED_PER_MM@sigma=4.0 | -1433.661588658 | -8.643707205 | -0.374748272 | -188.477474736 |
| HC_SIGNED_MEAN@sigma=8.0 | -1591.081667335 | -20.565189447 | 0.854707280 | -170.617293005 |
| HC_NORMALIZED@sigma=8.0 | -1095.317538116 | -2.831281721 | -0.030535587 | -49.475877884 |
| ALPHA_WEIGHTED_PER_MM@sigma=8.0 | -1294.595875300 | -19.545521804 | -0.058302344 | -145.743982068 |
| SIGNED_HC_LOG_SCALE_INTEGRAL | -895.518664725 | -3.816069556 | -0.645553332 | -127.639633787 |

La tabla de 960 celdas conserva cada cruce HARP × transición × componente × rival, con predicción, objetivo, normalizador, error con signo, error cuadrático, error absoluto y ambas ventajas. La tabla de 1.200 agregaciones contiene también los cruces completos transición × escala, transición × familia y HARP × componente. No se excluyen celdas desfavorables ni se utiliza selección de características.

## Explicación algebraica de H y L

Para delta=(y−x)/s y corrección c=(predicción−x)/s, con s el RMS del entrenamiento, la ganancia cuadrática respecto a T0 es exactamente:

`ganancia = delta² − (c−delta)² = 2·delta·c − c²`.

El primer término es el crédito de alineación con el cambio observado; el segundo es el coste de introducir la corrección. Se conserva la identidad en cada celda y en cada agregación. La alineación es una descripción del resultado conocido; no una cantidad disponible ex ante.

| HARP | Rival | Crédito alineación | Coste corrección | Ganancia NMSE | Signos b +/− | Medias train opuestas /16 |
| --- | --- | --- | --- | --- | --- | --- |
| 401 | H | -0.017723159242 | 0.015628896451 | -0.033352055693 | 12/4 | 10 |
| 401 | L | +0.003740467553 | 0.015458756124 | -0.011718288571 | 5/11 | 6 |
| 2920 | H | -0.020621245149 | 0.012677757246 | -0.033299002395 | 4/12 | 6 |
| 2920 | L | +0.012231251755 | 0.012366051083 | -0.000134799328 | 6/10 | 4 |
| 5249 | H | -0.012412215093 | 0.000718413515 | -0.013130628608 | 13/3 | 16 |
| 5249 | L | +0.017887614058 | 0.002603236220 | +0.015284377838 | 6/10 | 10 |

En H, el crédito agregado es negativo en los tres folds. Reducir su magnitud a una traslación positiva más pequeña no cambia el signo de ese crédito para estos datos: para una escala positiva lambda, la ganancia sería `lambda·A − lambda²·C`, y A<0, C>0. Esta es una consecuencia algebraica del diagnóstico; no se ajustó lambda, no se evaluó una nueva versión ni se elige ahora una traslación invertida. En L, el crédito es positivo en los tres folds, pero sólo en 5249 supera al coste. Esto distingue desalineación de sobrecorrección dentro del modelo operativo ya fijado.

## Qué aprende cada estimador de los HARPs de entrenamiento

Para dos HARPs A y B y cinco instantáneas por HARP:

`b_H = [(x4−x0)_A + (x4−x0)_B]/8`.

`b_L = [(-x0+2x1−2x2+2x3−x4)_A + (-x0+2x1−2x2+2x3−x4)_B]/8`.

Estas fórmulas se verificaron numéricamente para las 96 combinaciones fold × rival × componente. Para H las derivadas respecto a las instantáneas de cada trayectoria son `[-1,0,0,0,1]/8`: cambiar solamente una instantánea interior, manteniendo los extremos y el normalizador, no cambia su b. Para L son `[-1,2,-2,2,-1]/8`: las instantáneas interiores pesan el doble en magnitud que los extremos, y la fase sigue anclada al primer índice. Las derivadas entre componentes son cero. Las fórmulas se refieren al estimador b, no a toda la evaluación: cambiar datos podría cambiar otros elementos como el RMS. Las tablas de derivadas son resultados analíticos, no observaciones solares añadidas.

Esto permite delimitar el alcance físico: H ensaya transferencia de deriva media entre HARPs; L ensaya transferencia de un contraste temporal alternante fijo. El resultado de H no compara directamente curvas helicoidales reconstruidas ni transportes no lineales dependientes del estado.

## Sensibilidad de entrenamiento, completa y sin reentrenar el gate

Cada contribución individual de una transición es delta/8 para H y s_k·delta/8 para L. Se descompone el coeficiente publicado en las contribuciones de los dos HARPs, y se calcula analíticamente cómo cambiaría b al retirar uno de esos HARPs o una transición. Estos coeficientes diagnósticos no se utilizaron para generar predicciones ni puntuar rivales nuevos. Una transición retirada comparte instantáneas con otras: el cálculo es un diagnóstico de influencia, no una replicación.

| HARP evaluado | Rival | Cambios signo al retirar HARP /32 | Cambios signo al retirar transición /128 | Máximo cambio en la magnitud de b/s al retirar HARP |
| --- | --- | --- | --- | --- |
| 401 | H | 10 | 37 | 0.185138176 |
| 401 | L | 6 | 24 | 0.200836084 |
| 2920 | H | 6 | 28 | 0.235659946 |
| 2920 | L | 4 | 27 | 0.184577006 |
| 5249 | H | 16 | 54 | 0.165521386 |
| 5249 | L | 10 | 55 | 0.078399471 |

En el fold 5249, los dos HARPs de entrenamiento aportan medias de deriva H con signos opuestos en 16/16 componentes. El signo del b resultante depende de qué contribución domina; retirando uno u otro HARP cambia en 16 de los 32 casos componente × HARP retirado. El coeficiente pequeño de ese fold es, en buena parte, una compensación entre regiones. En 401 y 2920 hay oposición en 10/16 y 6/16 componentes. No se infiere de ello la dirección de ningún HARP nuevo.

Para G, los coeficientes c congelados son −0,620686693 en el fold 401, −0,008347054 en 2920 y +0,338955972 en 5249; a vale respectivamente 0,499856023, 0,569202476 y 0,800879535. Los tres diseños conservan rango 18 y números de condición entre 4,455 y 5,763. La heterogeneidad del efecto de actividad no procede de un fallo del umbral de rango publicado. Puesto que G utiliza delta_q hasta el extremo derecho, sus ganancias locales tampoco son evidencia de capacidad predictiva ex ante.

## Conclusiones y límites que conserva el programa integral

1. La falta de dominancia global permanece. L no obtiene un triunfo confirmatorio; H, M y G tampoco.
2. H presenta ganancias en cuatro transiciones, pero pierde en los tres HARPs y en todas las medias por escala y familia. La desalineación de la deriva transferida se verifica mediante una identidad exacta de pérdida.
3. La ganancia de L es pequeña, heterogénea y dependiente de la métrica: menor NMSE global, mayor NMAE. Su única mejora por HARP está en 5249.
4. G tiene ventajas locales grandes y errores grandes en otras transiciones. Su resultado muestra que sería necesario contrastar cualquier futura regla de selección con entradas disponibles antes de conocer el objetivo; elegir retrospectivamente sus cinco victorias fabricaría rendimiento.
5. Los estimadores H y L son mucho más restringidos que una clase general de transportes helicoidales o alternantes. El telescopaje de H revela una limitación representacional concreta y verificable, sin rescatar artificialmente su puntuación.
6. No se extrae una afirmación universal, una topología física, una validación cosmológica ni una negación de otras ramas CEH/ECH. Se incorpora una delimitación operativa y un diagnóstico local completo.

Un eventual sucesor debe plantear y congelar explícitamente qué estado y qué transporte representan la hipótesis, y separar actividad del extremo de un verdadero objetivo ex ante. Estos resultados pueden orientar su diseño, pero cualquier diseño elegido a partir de ellos sigue siendo desarrollo y exige evaluación nueva para promoción. Esta entrega no modifica ningún protocolo ni abre campos nuevos.

## Reproducción y archivos

Desde cualquier directorio, con una copia del repositorio KCH que incluya la evidencia v2 y NumPy disponible:

```bash
python diagnose_solar_v16.py --repo /ruta/al/repo --out /ruta/a/esta/carpeta
python verify_solar_local.py --repo /ruta/al/repo --diagnostic /ruta/a/esta/carpeta
```

El archivo de alcance debe estar previamente presente en la carpeta de salida. El diagnóstico invoca el verificador v2 del propio repositorio, usando el protocolo original v1.6 para verificar el recibo de selección; el verificador local requiere únicamente la biblioteca estándar. El resultado completo es `SOLAR_LOCAL_DIAGNOSTIC.json`, y el recibo independiente es `SOLAR_LOCAL_VERIFICATION.json`. Los hashes de todas las entradas y tablas están registrados.

| Archivo | Cobertura |
| --- | --- |
| CELLS_ALL_960.csv | 960 celdas, todos los rivales y observables |
| AGGREGATES_ALL_1200.csv | 1.200 agregaciones, 11 niveles completos |
| SNAPSHOT_COVERAGE_ALL_15.csv | 15 fechas, máscaras, calidad y reconciliación |
| TRANSITIONS_ALL_12.csv | 12 fechas pareadas, fase, actividad y coeficientes G |
| TRAIN_PARAMETERS_H_L_ALL_96.csv | 96 coeficientes, signos, cancelación y telescopaje |
| TRAIN_HARP_CONTRIBUTIONS_ALL_192.csv | 192 contribuciones y sensibilidades por HARP |
| TRAIN_TRANSITION_INFLUENCE_ALL_768.csv | 768 contribuciones e influencias de transición |
| TRAIN_SNAPSHOT_DERIVATIVES_ALL_60.csv | 60 derivadas analíticas, válidas por componente |
| REEXECUTED_V2_60_CHECKS.json | 60 controles de la reproducción anterior |
