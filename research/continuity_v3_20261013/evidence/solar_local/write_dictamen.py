from pathlib import Path
import csv,json,math,platform,sys
import numpy
p=Path(__file__).parent;d=json.loads((p/'SOLAR_LOCAL_DIAGNOSTIC.json').read_text());v=json.loads((p/'SOLAR_LOCAL_VERIFICATION.json').read_text());a=list(csv.DictReader((p/'AGGREGATES_ALL_1200.csv').open()));models=['T0_TRIVIAL_IDENTITY','M_MOBIUS_SIGN','H_HELICAL_TRANSLATION','L_LEMNISCATIC_ALTERNATING','G_ACTIVITY_AFFINE'];short={m:m.split('_')[0] for m in models}
def table(header,rows):return '| '+' | '.join(header)+' |\n| '+' | '.join(['---']*len(header))+' |\n'+'\n'.join('| '+' | '.join(str(x) for x in r)+' |' for r in rows)+'\n'
def pivot(level,dims,metric,chosen=models):
 rr=[r for r in a if r['level']==level];groups={}
 for r in rr:groups.setdefault(tuple(r[k] for k in dims),{})[r['model']]=r
 return table(dims+[short[m] for m in chosen],[list(k)+[f'{float(q[m][metric]):.9f}' for m in chosen] for k,q in groups.items()])
s='''# Dictamen solar v1.6: descomposición local exhaustiva

El diagnóstico conserva el resultado congelado `NO_DEVELOPMENT_DOMINANT_LIFT`. H no mejora la identidad en ninguno de los tres HARPs; su NMSE global es un 4,468379% mayor. Aun así, H mejora cuatro transiciones concretas de las doce. G mejora cinco transiciones y pierde al agregar cada uno de los tres HARPs. La heterogeneidad local existe y queda expuesta completa; no basta para definir una regla prospectiva de selección de modelos.

L obtiene la menor NMSE global por un margen de apenas 0,192178% frente a la identidad, con una sola victoria de fold y una NMAE un 1,186546% peor. No alcanza el margen del 5% ni las dos victorias requeridas. Su mejora en HARP 5249 compensa casi exactamente las pérdidas en 401 y 2920. Ninguna de estas observaciones permite promover una topología física.

El hallazgo estructural decisivo es más preciso que una comparación de puntuaciones: el coeficiente de traslación b de H aprende exclusivamente el desplazamiento neto entre extremos de las trayectorias de entrenamiento. Por telescopaje, no aprende su geometría interior. Esta delimitación explica qué operación fue contrastada y evita convertir su resultado negativo en una refutación de toda helicoidalidad.

## Cobertura, procedencia y estatuto

Análisis descriptivo post hoc. Alcance registrado en `PRECALCULATION_SCOPE_ES.md` antes del cálculo diagnóstico y después de conocerse el resultado v1.6. Fuentes reales congeladas: tres HARPs, 15 instantáneas, 12 transiciones y 16 componentes. No hay nuevas observaciones, segmentos FITS ni resultados solares externos. No se cambiaron fechas, selección, fase, normalizadores, parámetros, puntuación ni gate. Las cinco predicciones usan exclusivamente los parámetros y normalizadores de entrenamiento publicados.

Se publican **960 celdas** (3 × 4 × 16 × 5), **1.200 agregaciones**, 96 parámetros H/L, 192 contribuciones por HARP de entrenamiento, 768 sensibilidades por transición de entrenamiento y 60 derivadas analíticas por instantánea. Los recuentos son de auditoría, no tamaños muestrales inferenciales. Las componentes comparten campos, las escalas se solapan y las transiciones comparten extremos. No se calculan p-valores, intervalos de significación ni un número ficticio de réplicas.

Cada escala ordinaria contiene tres componentes; la integral entre escalas es una sola componente y conserva una categoría propia `cross_scale`. La media global pondera las cinco escalas con 3/16 cada una y la integral con 1/16. Las familias HC_SIGNED_MEAN, HC_NORMALIZED y ALPHA_WEIGHTED_PER_MM pesan 5/16 cada una y la integral 1/16. No se promedian sin ponderación las medias de estas seis categorías; tampoco se suman marginals de escala y familia entre sí. Los normalizadores difieren por fold y proceden exclusivamente de los otros dos HARPs.

El verificador stdlib independiente reconstruye las predicciones desde el resultado congelado, sin importar el generador diagnóstico ni el runtime científico. Verifica todas las celdas, todas las agregaciones y las sensibilidades. La reproducción v2 volvió a superar sus 60 comprobaciones numéricas. Además, la auditoría local superó '''+str(v['numeric_comparisons_passed'])+''' comparaciones; diferencia absoluta máxima de coma flotante '''+f"{v['max_absolute_float_difference']:.3g}"+'''. Una primera etiqueta de trabajo sumaba erróneamente 1.300 agregaciones; la verificación exhaustiva corrigió el conteo a 1.200, sin cambiar las celdas, métricas o resultados científicos.

## Puntuaciones globales completas

Una ganancia positiva indica menor error que T0. Una negativa indica deterioro. Los cinco rivales operativos son T0 identidad, M inversión de signo, H traslación de deriva, L deriva alternante con fase fija y G ajuste afín condicionado a actividad del extremo.

'''
s+=table(['Rival','NMSE','NMAE','Ganancia NMSE %','Ganancia NMAE %','Folds mejor que T0','Transiciones mejor que T0'],[[short[g['model']],f"{g['nmse']:.12f}",f"{g['nmae']:.12f}",f"{g['relative_nmse_gain_percent']:+.6f}",f"{100*g['nmae_gain_vs_identity']/g['identity_nmae']:+.6f}",sum(r['model']==g['model'] and r['nmse_gain_vs_identity']>1e-12 for r in d['harp_scores']),sum(r['model']==g['model'] and r['nmse_gain_vs_identity']>1e-12 for r in d['transition_scores'])] for g in d['global_scores']])
s+='''
Los recuentos anteriores comparan cada rival contra identidad; no son el número de veces que obtiene el mínimo entre los cinco. Los ganadores del fold son T0 en 401 y 2920 y L en 5249. Los conteos por celdas normalizadas son H 82 mejores / 110 peores, L 95 / 97, M 17 / 175 y G 82 / 110; las 192 celdas de cada rival no son observaciones independientes.

## Los tres HARPs, sin descartar ninguno

NMSE completa:

'''+pivot('harp',['harp'],'nmse')+'\nGanancia de NMSE frente a T0 (%):\n\n'+pivot('harp',['harp'],'relative_nmse_gain_percent',models[1:])
s+='''
H pierde un 10,037133% en 401, un 12,967300% en 2920 y un 1,097517% en 5249. La media global no oculta una victoria completa de H en una región. Sí oculta victorias dentro de algunas transiciones, detalladas a continuación.

## Las doce transiciones, sin seleccionar victorias

El índice k mantiene el origen y la fase publicados: k=0,1,2,3 dentro de cada HARP; no se desplazó para favorecer L. `TRANSITIONS_ALL_12.csv` incluye las fechas TAI exactas, q en ambos extremos, delta_q y a,c de G.

NMSE completa:

'''+pivot('transition',['harp','transition_k'],'nmse')+'\nGanancia frente a T0 (%):\n\n'+pivot('transition',['harp','transition_k'],'relative_nmse_gain_percent',models[1:])
s+='''
H mejora 401/k0, 2920/k0, 2920/k3 y 5249/k3. Su mayor reducción descriptiva es 41,798318% en 2920/k3; esa transición tiene una NMSE de identidad pequeña, 0,045648971, por lo que una gran reducción porcentual no implica una gran contribución global. G obtiene reducciones de 77,988418% y 91,933916% en 401/k2 y k3, pero sus errores en k0 y k1 anulan estas ventajas. Las fechas o índices de estas victorias se conocen después de evaluar; no constituyen una regla de enrutamiento fuera de muestra.

## Todas las escalas y familias

NMSE por escala, agregando los tres HARPs:

'''+pivot('scale',['scale'],'nmse')+'\nGanancia frente a T0 (%):\n\n'+pivot('scale',['scale'],'relative_nmse_gain_percent',models[1:])
s+='''
H pierde en las cinco escalas y en la integral; L mejora en sigma 0, 1 y 8, y empeora en sigma 2, 4 y en la integral. M y G pierden en las seis categorías agregadas. Estas seis medias no son seis experimentos independientes.

NMSE por familia:

'''+pivot('family',['family'],'nmse')+'\nGanancia frente a T0 (%):\n\n'+pivot('family',['family'],'relative_nmse_gain_percent',models[1:])
s+='''
L mejora HC_SIGNED_MEAN un 0,881879% y ALPHA_WEIGHTED_PER_MM un 0,518810%; empeora HC_NORMALIZED un 0,159426% y la integral un 0,645553%. H no mejora ninguna de las cuatro familias agregadas. Se retienen todas las componentes, incluidos los resultados que contradicen las ganancias de L.

Ganancia completa por HARP y escala (%):

'''+pivot('harp_scale',['harp','scale'],'relative_nmse_gain_percent',models[1:])
s+='\nGanancia completa por HARP y familia (%):\n\n'+pivot('harp_family',['harp','family'],'relative_nmse_gain_percent',models[1:])
s+='\nGanancia de cada una de las dieciséis componentes, agregando los HARPs (%):\n\n'+pivot('component',['component'],'relative_nmse_gain_percent',models[1:])
s+='''
La tabla de 960 celdas conserva cada cruce HARP × transición × componente × rival, con predicción, objetivo, normalizador, error con signo, error cuadrático, error absoluto y ambas ventajas. La tabla de 1.200 agregaciones contiene también los cruces completos transición × escala, transición × familia y HARP × componente. No se excluyen celdas desfavorables ni se utiliza selección de características.

## Explicación algebraica de H y L

Para delta=(y−x)/s y corrección c=(predicción−x)/s, con s el RMS del entrenamiento, la ganancia cuadrática respecto a T0 es exactamente:

`ganancia = delta² − (c−delta)² = 2·delta·c − c²`.

El primer término es el crédito de alineación con el cambio observado; el segundo es el coste de introducir la corrección. Se conserva la identidad en cada celda y en cada agregación. La alineación es una descripción del resultado conocido; no una cantidad disponible ex ante.

'''
s+=table(['HARP','Rival','Crédito alineación','Coste corrección','Ganancia NMSE','Signos b +/−','Medias train opuestas /16'],[[x['held_out_harp'],short[x['model']],f"{x['mean_alignment_credit']:+.12f}",f"{x['mean_correction_cost']:.12f}",f"{x['mean_nmse_gain']:+.12f}",f"{x['frozen_b_positive_components']}/{x['frozen_b_negative_components']}",x['opposite_training_harp_means_components']] for x in d['H_L_diagnostics']])
s+='''
En H, el crédito agregado es negativo en los tres folds. Reducir su magnitud a una traslación positiva más pequeña no cambia el signo de ese crédito para estos datos: para una escala positiva lambda, la ganancia sería `lambda·A − lambda²·C`, y A<0, C>0. Esta es una consecuencia algebraica del diagnóstico; no se ajustó lambda, no se evaluó una nueva versión ni se elige ahora una traslación invertida. En L, el crédito es positivo en los tres folds, pero sólo en 5249 supera al coste. Esto distingue desalineación de sobrecorrección dentro del modelo operativo ya fijado.

## Qué aprende cada estimador de los HARPs de entrenamiento

Para dos HARPs A y B y cinco instantáneas por HARP:

`b_H = [(x4−x0)_A + (x4−x0)_B]/8`.

`b_L = [(-x0+2x1−2x2+2x3−x4)_A + (-x0+2x1−2x2+2x3−x4)_B]/8`.

Estas fórmulas se verificaron numéricamente para las 96 combinaciones fold × rival × componente. Para H las derivadas respecto a las instantáneas de cada trayectoria son `[-1,0,0,0,1]/8`: cambiar solamente una instantánea interior, manteniendo los extremos y el normalizador, no cambia su b. Para L son `[-1,2,-2,2,-1]/8`: las instantáneas interiores pesan el doble en magnitud que los extremos, y la fase sigue anclada al primer índice. Las derivadas entre componentes son cero. Las fórmulas se refieren al estimador b, no a toda la evaluación: cambiar datos podría cambiar otros elementos como el RMS. Las tablas de derivadas son resultados analíticos, no observaciones solares añadidas.

Esto permite delimitar el alcance físico: H ensaya transferencia de deriva media entre HARPs; L ensaya transferencia de un contraste temporal alternante fijo. El resultado de H no compara directamente curvas helicoidales reconstruidas ni transportes no lineales dependientes del estado.

## Sensibilidad de entrenamiento, completa y sin reentrenar el gate

Cada contribución individual de una transición es delta/8 para H y s_k·delta/8 para L. Se descompone el coeficiente publicado en las contribuciones de los dos HARPs, y se calcula analíticamente cómo cambiaría b al retirar uno de esos HARPs o una transición. Estos coeficientes diagnósticos no se utilizaron para generar predicciones ni puntuar rivales nuevos. Una transición retirada comparte instantáneas con otras: el cálculo es un diagnóstico de influencia, no una replicación.

'''
s+=table(['HARP evaluado','Rival','Cambios signo al retirar HARP /32','Cambios signo al retirar transición /128','Máximo cambio en la magnitud de b/s al retirar HARP'],[[x['held_out_harp'],short[x['model']],x['sign_changes_removing_one_training_harp_cases_of_32'],x['sign_changes_removing_one_training_transition_cases_of_128'],f"{x['max_absolute_normalized_parameter_change_removing_harp']:.9f}"] for x in d['H_L_diagnostics']])
s+='''
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

'''
s+=table(['Archivo','Cobertura'],[['CELLS_ALL_960.csv','960 celdas, todos los rivales y observables'],['AGGREGATES_ALL_1200.csv','1.200 agregaciones, 11 niveles completos'],['SNAPSHOT_COVERAGE_ALL_15.csv','15 fechas, máscaras, calidad y reconciliación'],['TRANSITIONS_ALL_12.csv','12 fechas pareadas, fase, actividad y coeficientes G'],['TRAIN_PARAMETERS_H_L_ALL_96.csv','96 coeficientes, signos, cancelación y telescopaje'],['TRAIN_HARP_CONTRIBUTIONS_ALL_192.csv','192 contribuciones y sensibilidades por HARP'],['TRAIN_TRANSITION_INFLUENCE_ALL_768.csv','768 contribuciones e influencias de transición'],['TRAIN_SNAPSHOT_DERIVATIVES_ALL_60.csv','60 derivadas analíticas, válidas por componente'],['REEXECUTED_V2_60_CHECKS.json','60 controles de la reproducción anterior']])
(p/'DICTAMEN_SOLAR_LOCAL_ES.md').write_text(s)
(p/'EXECUTION_ENVIRONMENT.json').write_text(json.dumps({'python':sys.version,'platform':platform.platform(),'numpy':numpy.__version__,'local_verifier_dependencies':'Python standard library only','diagnostic_dependencies':'numpy plus original v2 replay'},indent=2)+'\n')
print(len(s), 'characters')
