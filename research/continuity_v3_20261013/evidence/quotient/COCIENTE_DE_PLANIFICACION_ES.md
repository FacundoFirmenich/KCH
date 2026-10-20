# Cociente suficiente para planificación de evidencia ECH

Fecha: 13 de octubre de 2026. Aplicación a los inputs originales del atlas ECH, conservados en `research/continuity_v2_20261013/evidence/ech`. Esta construcción formaliza una reducción suficiente bajo condiciones expresas; no afirma minimalidad ni novedad general de la técnica de agregación de estados.

## 1. La pregunta precisa

El atlas muestra que un contrato final puede alcanzarse con distintas evidencias heredadas. La certificación de cada puente resuelve el coste mínimo desde una evidencia concreta, pero no autoriza a sustituir esa evidencia por la etiqueta del contrato. Tampoco exige que toda aplicación conserve, en su estado de planificación, todos los detalles de genealogía que conserva el registro auditable.

Buscamos una representación que preserve exactamente las adquisiciones factibles y sus costes futuros en el problema finito de distancias. Separamos esa representación de la identidad de las coordenadas y de los recibos, que permanecen en el registro original.

## 2. Dominio y definiciones

Sea K el conjunto de las 65 clases funcionales del kernel y P el conjunto de sus pares no ordenados: |P|=2.080. Sea Q_s el conjunto de las 4.017 máscaras admisibles para el sensor s, con s en {EXACT, MODE, ACTIONABLE}. Las máscaras contienen al menos tres bloques de los doce declarados. Una coordenada es tipada: (s,q). Las coordenadas de distintos sensores se consideran distintas aunque utilicen la misma máscara.

El kernel congelado determina una respuesta r_s(c,q) para cada clase c y consulta q. Definimos el vector binario de separación

\[
a_{s,q}(c,c')=\mathbf 1\{r_s(c,q)\ne r_s(c',q)\},\qquad (c,c')\in P.
\]

Para una evidencia heredada E formada por coordenadas distintas, la distancia es

\[
D_p(E)=\sum_{(s,q)\in E}a_{s,q}(p).
\]

Un contrato C=(t,s,d) fija un objetivo t, un sensor permitido para nuevas adquisiciones s y una distancia d. El conjunto I_t contiene los pares de clases distintos bajo el objetivo t, determinado sobre el dominio completo. E satisface el contrato si D_p(E)≥d para todos los p de I_t. El sensor del contrato restringe nuevas adquisiciones; no elimina las contribuciones de evidencia heredada de otros sensores.

## 3. Partición con capacidades

Para cada sensor, agrupamos q y q' si sus vectores a_{s,q} y a_{s,q'} coinciden en TODOS los pares de P. Cada grupo g conserva:

- sensor s(g);
- vector de separación a_g;
- capacidad M_g, igual al número real de coordenadas del grupo;
- miembros originales, para materializar y auditar adquisiciones.

El estado reducido de E es n(E)=(n_g(E))_g, donde n_g cuenta las coordenadas de E pertenecientes a g. La disponibilidad es M_g-n_g, nunca una capacidad artificial igual a uno. La fase de la ruta o el contrato actual se conserva aparte cuando determina qué adquisiciones están permitidas.

Se cumplen exactamente

\[
D_p(E)=\sum_g n_g(E)a_g(p),\qquad
0\le u_g\le M_g-n_g(E),\qquad
\operatorname{coste}(u)=\sum_g u_g.
\]

Una adquisición u sólo puede tener entradas positivas en grupos cuyo sensor esté permitido en esa etapa. El estado siguiente es n'=n+u.

## 4. Proposición de suficiencia y demostración

**Proposición.** Para el kernel fijo, contratos definidos exclusivamente por las distancias anteriores, adquisición sin repetición de coordenadas, coste unitario y admisibilidad dependiente del sensor y de la etapa de la ruta, dos evidencias E y F con n(E)=n(F) tienen los mismos planes futuros factibles por grupos y los mismos costes óptimos en cualquier ruta finita fijada. La identidad del contrato o etapa debe ser la misma en ambos estados.

**Demostración.**

1. La fórmula de D muestra que E y F producen el mismo vector completo de distancias. Por tanto satisfacen exactamente los mismos umbrales contractuales del dominio declarado.
2. Como las capacidades M son propiedades del kernel, n(E)=n(F) implica la misma disponibilidad M-n para cada grupo.
3. Una adquisición concreta A desde E induce el vector u de sus cantidades por grupo. La ausencia de repetición asegura 0≤u≤M-n. La restricción de sensor se conserva porque los grupos son tipados.
4. Desde F puede escogerse exactamente u_g coordenadas aún no adquiridas de cada grupo g. Existen porque la disponibilidad coincide. Esta selección B tiene el mismo coste que A y produce n(E∪A)=n(F∪B)=n+u.
5. El nuevo vector de distancias y la satisfacción del contrato intermedio coinciden. El argumento es simétrico entre E y F.
6. Iterando el paso anterior se empareja cualquier plan de longitud finita con un plan de igual coste y factibilidad. El conjunto de costes alcanzables coincide; por ello coinciden sus mínimos cuando existe un plan factible. La infactibilidad también coincide.

Esto establece una equivalencia de comportamiento para la tarea de planificación declarada. No demuestra que n sea el cociente más pequeño posible, ni que basten sólo D o la etiqueta contractual.

## 5. Compilación de rutas completas

Para una ruta de T etapas y variables enteras u_{k,g}, se puede escribir

\[
\min\sum_{k=1}^{T}\sum_g u_{k,g}
\]

sujeto a

\[
\sum_{j=1}^{k}u_{j,g}\le M_g-n_g(E_0),\quad
u_{k,g}\in\mathbb Z_{\ge0},
\]

\[
\sum_g\left(n_g(E_0)+\sum_{j=1}^{k}u_{j,g}\right)a_g(p)\ge d_k
\quad\text{para }p\in I_{t_k},
\]

más las restricciones de sensor de cada etapa. Cada solución entera se realiza con coordenadas originales distintas; cada plan concreto induce una solución entera de igual coste. Es una reformulación exacta de la ruta fijada. No obliga a minimizar primero cada etapa por separado: permite pagar más antes si reduce el coste total y sigue cumpliendo los contratos intermedios.

El cálculo nuevo de los 23 cuadrados utiliza dos etapas y 46 rutas fijadas. Sus agrupaciones pueden ser más gruesas al considerar sólo los pares activos de cada problema. Para ser exactas deben preservar la contribución a AMBAS etapas, las capacidades disponibles y, si el sensor se repite, el consumo común de esas capacidades. La partición aquí publicada usa todos los pares y sirve como construcción suficiente general para la familia declarada.

## 6. Ejecución sobre los inputs originales

`verify_planning_quotient.py` vuelve a evaluar el kernel, construye la partición y compara las distancias de la representación concreta con la agrupada en los 204 certificados del avance anterior. Revisa también la disponibilidad de cada sensor y la factibilidad de los testigos. Los hashes del kernel, codebooks y certificados se verifican antes del cálculo.

| Sensor | Coordenadas | Patrones sobre todos los pares | Capacidad máxima | Grupos de capacidad mayor que uno |
|---|---:|---:|---:|---:|
| EXACT | 4.017 | 3.971 | 3 | 45 |
| MODE | 4.017 | 3.300 | 15 | 473 |
| ACTIONABLE | 4.017 | 609 | 159 | 317 |
| Total tipado | 12.051 | 7.880 | - | 835 |

Los 204 certificados concordaron; tres evidencias terminales usan multiplicidad dentro de un mismo patrón. Los 93 conjuntos distintos encontrados en esos certificados producen 93 estados reducidos distintos. Por tanto, no se afirma haber encontrado dos ledgers archivados distintos que coincidan en este cociente. La suficiencia proviene de la demostración y de la definición exhaustiva de la partición, no de fabricar un ejemplo de colisión.

La partición enumera todos sus miembros en `PLANNING_PATTERN_PARTITION.json`. Las comprobaciones y los tres ejemplos reales de multiplicidad están en `PLANNING_QUOTIENT_VERIFICATION.json`.

## 7. Fronteras de la afirmación

Este cociente conserva planificación de distancias y costes bajo las condiciones fijadas. No conserva por sí solo:

- el nombre de cada coordenada adquirida ni su hash de conjunto;
- las etiquetas observacionales concretas necesarias para decodificar lecturas;
- cadenas de recibos, tiempos, responsables, permisos o autoridad;
- costes específicos de cada máscara, calidad instrumental desigual, caducidad o ruido;
- kernels que cambian en el tiempo o sensores cuya respuesta depende del historial.

Si alguno de esos atributos interviene en la tarea, debe incorporarse al estado o refinarse la partición; no se presume suficiencia fuera del contrato. Los grupos calculados no autorizan descartarlos del registro auditable. `permission_granted=false` permanece intacto.

## 8. Relación con CEH

La contribución al programa es precisar qué memoria necesita una tarea particular. La etiqueta contractual pierde información relevante para coste; la genealogía completa contiene información adicional que esta tarea no utiliza; el cociente demuestra, bajo supuestos verificables, una representación intermedia suficiente. No deriva una hélice geométrica de esa memoria ni traslada el resultado a datos solares o cosmológicos.

La pregunta CEH queda así operacionalizada para este caso: qué información preserva la capacidad de distinguir futuros planes factibles y sus costes. El transporte entre estos estados reducidos puede estudiarse sin confundirlo con la identidad del estado completo que mantiene el registro.
