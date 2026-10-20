# M33: contrato de identificación, fuerza y observación

Fecha: 20 de octubre de 2026. Se conserva el replay radial y su normalización. Esta continuación añade un diagnóstico algebraico del operador archivado y un contrato de interpretación. No agrega observaciones, ajusta parámetros, realiza remuestreo, ejecuta el protocolo 2D ni genera datos sintéticos.

## 1. Resultado local que se conserva

La comparación radial usa 28 bins comunes derivados de 396 filas Hα y 102 H I archivadas. En 1–3 y 3–5 kpc, las medias son −2,7455110461 y −1,3078672795 km/s. Bajo `inclination_plus_corr3_L0p5`, los errores estándar son 3,3232212492 y 3,8840414028 km/s; χ²=0,8176597944 con dos grados de libertad y p=0,6644272437. Es una conclusión condicionada en esa covarianza, no una prueba de residuo exactamente cero.

Las respuestas para norma de coeficiente ≤1 son 0,03032795355 y 0,02583733218 km/s. Las dispersiones entre referencias son 0,64045821997 y 0,45670068351 km/s, es decir 21,11775 y 17,67600 veces las envolventes. La norma mínima 289,9970493 ajusta los estimados puntuales bajo la normalización histórica: conducción 0,1 kpc, escala de helicidad 1 kpc, velocidad de Alfvén 20 km/s y geometría central. No es una exclusión calibrada del parámetro verdadero.

Los ocho escenarios de covarianza quedan conservados en `PHYSICAL_CONTRACT_AUDIT.json`. p varía entre 0,0001530754 y 0,8008336850. No se elige la covarianza por el resultado. El replay histórico verificó 66 comparaciones y 142 hashes; aquí se lee ese recibo, no se vuelve a verificar una transcripción primaria ni a ejecutar esos módulos originales.

## 2. La fuerza radial y el observable son objetos distintos

Con convención radial positiva hacia fuera, densidad ρ y SI,

\[
\mathbf f_B=\mu_0^{-1}(\nabla\times\mathbf B)\times\mathbf B
=\mu_0^{-1}(\mathbf B\cdot\nabla)\mathbf B-\nabla(B^2/2\mu_0)
\]

cuando ∇·B=0. En una idealización estacionaria, axisimétrica y circular, sin aceleración radial adicional,

\[
v_\phi^2=R\,\partial_R\Phi+(R/\rho)\partial_R P-(R/\rho)f_{B,R}.
\]

El término magnético es una contribución firmada a v²; no tiene por qué ser positivo. Para un campo puramente azimutal dentro de esas hipótesis,

\[
\Delta v_B^2={B_\phi\over\mu_0\rho}\,\partial_R(RB_\phi).
\]

Esta identidad fija signo y unidades; no afirma que M33 satisfaga todas esas simplificaciones. La fuerza depende de perfiles, tensión, presión y densidad. Un escalar de helicidad no basta para determinarla. Elstner, Beck y Gressel (2014) desarrolla este contraste físico; la propuesta favorable de Battaner y Florido también depende del perfil radial. [S08, S12]

La diferencia archivada Hα−H I está en km/s, no en aceleración ni v². Para relacionarla con una corrección Δv² sería necesario justificar la linealización Δv≈Δv²/(2v_ref), con referencia no nula y corrección pequeña, o usar la relación no lineal completa. Además, ambos trazadores pueden responder al mismo campo y diferir por densidad, presión, geometría, peso emisivo y estimador de velocidad. Una fuerza común no se convierte automáticamente en su diferencia observada.

Por ello no se declara derivado el kernel del proyecto desde Lorentz: esa equivalencia sigue sin demostrarse con el material recuperado. La formulación anterior es una obligación física estándar que el kernel debe satisfacer o de la que debe distinguirse explícitamente.

## 3. Modelo directo de medición que debe cerrarse

Para cada trazador a, escribir un modelo directo `d_a=O_a[v_a(B,ρ_a,P_a,Φ,geometry),calibration]+ε_a`. El operador O_a debe incluir línea de visión, respuesta espacial/espectral, pesos emisivos, método de extracción, máscara y deproyección. El residuo es la diferencia entre productos ya procesados; no dos mediciones del mismo escalar con igual operador garantizado.

La resolución magnética efectiva citada para M33 es aproximadamente 0,7 kpc [S09], distinta de la resolución cinemática de H I y Hα [S10-S11]. Debe igualarse la respuesta o modelarse explícitamente cada una. Convolucionar e inferir geometría compartida induce dependencias; el número de píxeles o bins no certifica el rango efectivo. La cifra geométrica histórica de áreas de haz tampoco sustituye el rango del problema inverso.

En una linealización local de un modelo directo declarado,

\[
y=K\eta+N\gamma+\epsilon,
\]

K lleva los coeficientes de interés al residuo; N representa variaciones de referencia, geometría y otros mecanismos de confusión, y Σ es la covarianza de ε justificada externamente. Con Σ definida positiva, A=Σ⁻¹ᐟ²K y B=Σ⁻¹ᐟ²N. La información lineal disponible para η tras ajustar nuisance es `Aᵀ(I−BB⁺)A`. Esta es una condición de identificabilidad local regular, no una garantía global. Si alguna dirección de A pertenece al espacio de B, esa dirección puede confundirse con nuisance.

No se calculó aquí esa matriz residualizada: falta especificar y calibrar N y Σ desde el modelo de observación. Tampoco se convierte la sensibilidad de covarianzas histórica en una estimación observada de ellas.

## 4. Diagnóstico nuevo del operador radial real

El recibo `M33_RADIAL_VERIFICATION.json`, campo `deterministic_primary.natural_response.response_matrix_kms_per_eta`, contiene

\[
K=\begin{pmatrix}
0.021648579209053345 & 0.008597515469585624 & -0.019421805074112317\\
0.016004890444171405 & 0.009771788161595461 & -0.017774233383681143
\end{pmatrix}.
\]

Las unidades registradas son km/s por unidad del coeficiente normalizado η. No se asigna a cada factor físico de esos coeficientes una unidad o estimación separada sin recuperar su definición original. Su norma y direcciones se refieren a esa parametrización histórica.

**Obstrucción estructural:** una aplicación lineal de tres coeficientes a dos medias tiene rango a lo sumo dos. Por rango–nulidad, al menos una dirección no puede distinguirse mediante esos dos observables. Esto vale aun si sus errores fueran cero. El resultado es álgebra lineal estándar aplicada al operador real del corpus, no una ley física nueva.

El recibo conserva dos valores singulares no nulos, 0,03974373224 y 0,002790743320; su razón es 14,2412711. El cruce de las dos filas, normalizado y con primera componente positiva, da

\[
n\simeq(0.3333333333333380,\;0.6666666666666619,\;0.6666666666666692).
\]

La comprobación determinista obtiene `max|Kn|=2,6020852×10⁻¹⁸` km/s por unidad de η. Es una igualdad numérica a precisión de los coeficientes almacenados, no una igualdad exacta inferida de datos físicos. La prueba de existencia de un núcleo no trivial procede de la dimensión; el vector aproxima una dirección de ese núcleo para K fijo. La escala de la menor singular no nula está muy por encima del umbral flotante usual `max(m,n) ε σ_max≈2,65×10⁻¹⁷`, lo que respalda rango numérico dos en el operador almacenado.

Así, `η` y `η+t n` producen la misma respuesta radial a la precisión declarada. El ajuste de norma mínima elige un representante de una familia, no identifica por separado los tres coeficientes. Un prior, restricción de signo o regularizador puede seleccionar un representante, pero esa selección incorpora información adicional y debe declararse.

Una presentación identificable puede reportar las dos respuestas `ξ=Kη` o dos coordenadas de su espacio de filas, junto con incertidumbre y nuisance. Esas coordenadas son combinaciones observables del modelo bajo K, no tres parámetros físicos identificados. La dirección aproximada sugiere las combinaciones `η₁−η₃/2` y `η₂−η₃`; cualquier uso exacto de esa simplificación debe derivarse del kernel simbólico original, no de redondear esta matriz.

## 5. Qué adquisición podría resolver la obstrucción

Un nuevo observable con fila de respuesta k₃ sólo ayuda a separar la dirección n si `k₃ n≠0`, y si ese contraste sobrevive a proyección instrumental, covarianza y ajuste nuisance. Añadir más píxeles cuyo patrón pertenezca al mismo espacio de filas no resuelve la degeneración. La próxima pregunta 2D es, por tanto, qué estructura espacial introduce una respuesta independiente del núcleo radial, no simplemente cuántos puntos nuevos pueden producirse.

Este criterio no predice un valor de k₃ ni acredita que los mapas disponibles lo satisfagan. Se necesita el kernel directo sobre los productos reales, máscaras comunes y operadores de cada instrumento. Después debe verificarse rango y sensibilidad residualizados, incluidas perturbaciones justificadas de geometría. La grilla histórica de 75 sensibilidades no se ejecutó ni se modificó aquí.

## 6. Criterios de cierre verificables

| Obligación | Entrada necesaria | Cierre admisible |
|---|---|---|
| Procedencia | Tablas primarias exactas y versiones | Cotejo de transcripción y registros corregidos; el hash local no sustituye este paso. |
| Unidades y fuerza | Definición simbólica del kernel y coeficientes | Correspondencia explícita entre fuerza, velocidad y residuo de trazadores, o reconocimiento de modelo fenomenológico. |
| Identificabilidad radial | Operador K y contrato de parámetros | Reportar espacio identificable y núcleo; no tres coeficientes libres inferidos de dos medias. Cerrado documental y algebraicamente para K archivado. |
| Nuisance y covarianza | Modelo directo, calibración y respuesta instrumental | Familia admisible justificada sin seleccionar por p; rank/perfil de sensibilidad tras nuisance. Pendiente. |
| Discriminación 2D | Mapas exactos, haces, máscaras, geometría | Nueva respuesta no nula sobre la dirección radial perdida y separable de rivales. Pendiente de evaluación real. |
| Comparadores físicos | Lorentz estándar, presión, deformación y diferencias de trazador | Igual información, complejidad y operadores; no atribución causal por descarte incompleto. Pendiente. |

La ganancia científica de esta continuación es localizar una obstrucción que no se cura con más precisión en los mismos dos promedios: existe una dirección de coeficientes que el operador radial no observa. La evidencia es la matriz real archivada y una comprobación determinista, sin ajuste nuevo. La frontera estratégica es diseñar un contraste espacial o una restricción externa que informe esa dirección y separarlo de nuisance; hasta entonces, la norma de ajuste y la compatibilidad con cero deben permanecer como diagnósticos condicionados.

## Fuentes y trazabilidad

Fuente numérica: `research/continuity_20261013/evidence/m33/M33_RADIAL_VERIFICATION.json`, SHA-256 `0dbdc75eade85f1ced260b8d364cc2fe5def50ee17b26691bfab60e1f54053cb`. Interpretación histórica: `DICTAMEN_M33_RADIAL_ES.txt` en el mismo directorio. Código y salida actuales: `audit_physical_contracts.py` y `PHYSICAL_CONTRACT_AUDIT.json`.

S08 Battaner y Florido (2005), preprint: https://arxiv.org/abs/astro-ph/0503657 . S09 Tabatabaei et al. (2008): https://arxiv.org/abs/0809.0419 . S10 Kam et al. (2015): https://arxiv.org/abs/1503.02538 . S11 Koch et al. (2018): https://arxiv.org/abs/1806.11218 . S12 Elstner, Beck y Gressel (2014): https://arxiv.org/pdf/1407.6998 . Las lecturas y límites se registran en `PRIMARY_SOURCES.json`.
