# Registro de corrección formal — Paper 1 V5

Fecha: 13 de octubre de 2026. Se corrigió el manuscrito completo, sin reemplazarlo por un resumen o addendum. V4 permanece intacto. No se modificaron datos, protocolos congelados, cohortes, resultados archivados, código ni GitHub. No se generaron muestras ni simulaciones: los contraejemplos son demostraciones analíticas.

## Identidad exacta

- Fuente: `PAPER_1_PROJECTED_RECURRENCE_HELICAL_LIFTS_V4.md`; 25843 bytes, 616 líneas.
- SHA-256 fuente: `43189c1a9f87aefbca49afa675a649942a9603e7329203819cdbcf4087dd8835`.
- Sucesor: `PAPER_1_PROJECTED_RECURRENCE_HELICAL_LIFTS_V5.md`; 46260 bytes, 739 líneas.
- SHA-256 V5: `c561f4dc0d0dd7259eca0c8be1bcef2c0a10305348805b00491c589dded5cc2b`.

## Conservación y comprobaciones

- Las 6 entradas bibliográficas originales permanecen literalmente completas. Se agregan Kullback y Leibler (1951) y Rothenberg (1971).
- Los 9 resultados numerados permanecen, con las correcciones que se detallan abajo. Su número no prueba originalidad.
- Los 9 bloques delimitados de resultados/códigos de V4 permanecen literalmente: esto incluye los dos paneles solares y sus métricas.
- Permanecen las ocho familias rivales, todas las áreas temáticas y las pruebas válidas, con condiciones explicitadas.
- Se reparó numeración duplicada de secciones; se conservaron los identificadores de teoremas/proposiciones.
- Se comprobó equilibrio de delimitadores matemáticos y ausencia de las tres principales afirmaciones invalidadas. No equivale a arbitraje matemático externo.
- Los resultados empíricos se conservaron; no se recalcularon. La reserva v0.8.2 se actualizó leyendo `work/seismic/DICTAMEN_PAPER2_V5_ES_EN.txt`, con la auditoría de pertenencia ya completada por el agente principal. No se atribuye a este subencargo una nueva inspección del código ni repetición del experimento. La continuación solar v1.5 se incorporó a partir de los resultados de ejecución comunicados por el agente principal.

## Correcciones sustantivas

| Asunto | Corrección y efecto |
|---|---|
| R0–R3 | Se retira la implicación universal. Se declaran contratos de transporte, paridad y magnitud física y puentes condicionales. |
| Operador/estado | M no identidad se separa de M(f0) distinto de f0; una reflexión tiene un punto fijo. |
| Monodromía | Se exige transporte definido, invertibilidad, compatibilidad con composición e invariancia por homotopía. Retornos irreversibles se denominan sucesores. |
| Gauge | Se agrega correspondencia de puntos fijos y se restringen invariantes espectrales a similitud lineal. |
| Log-score | Se declaran ley común, dominación e integrabilidad. Se separa identidad óptima poblacional del rendimiento estimado. |
| Datos/procesamiento | Se condiciona la aleatoriedad y se incluyen historia y entrenamiento cuando sean entrada real. |
| Fisher | Se demuestra score eficiente y Schur complement como sensibilidad de primer orden. No se convierte singularidad en imposibilidad universal. |
| Contraejemplo estadístico | Normal de media theta cúbica: identificación por inyectividad, información 9 theta cuarta y consistencia no regular. Ninguna muestra creada. |
| Null space | La imposibilidad lineal se demuestra mediante igualdad de leyes para estados admisibles, no únicamente por rango. |
| Reversión/paridad | Se distinguen inversión de trayectoria, reflexión activa y cambio pasivo de marco. |
| Acumulación | Se añade prueba y condiciones del rival difusivo; se reconoce que una tendencia puede compartir acumulación lineal. |
| Robustez | Se declara medida de estrés y transformación correctora de orientación; no se rechaza un pseudoscalar por su covarianza correcta. |
| Genealogía | El teorema es de recuperación exacta; suficiencia probabilística requiere ley y soporte. Una sucesión no implica hélice literal ni evidencia nueva. |
| Solar | Se conservan las 64 realizaciones históricas como propagación computacional, sin llamarlas mediciones independientes. Acuerdo con índices del mismo campo cualifica cálculo, no instrumento independiente. |
| Hemisferios | Se conserva el negativo; se explicitan independencia y alcance del binomial sin inventar explicación por ciclo. |
| Sismicidad | Se incorpora reserva ev_bl histórica y se mantiene separado el terminal de otra fuente. Cota predictiva no se convierte en cota física. |
| Diccionario | Significado del código y reconciliación exhaustiva con otros catálogos son comprobaciones distintas. |
| Novedad | Se retira el reclamo de nueve teoremas nuevos; se mantiene como propuesta una integración metodológica sujeta a comparación. |

## Contraejemplo físico analítico

Campo estacionario B=(cos z, sin z, 0): divergencia cero, rotacional igual a menos B y densidad de helicidad igual a menos uno. La evolución temporal del campo es identidad. Se demuestra así que helicidad física no implica retorno temporal no trivial. No se presenta este argumento como datos observados ni experimento solar.

## Referencias primarias nuevas y límites de consulta

- Kullback y Leibler (1951), DOI `10.1214/aoms/1177729694`. Registro primario Project Euclid: https://projecteuclid.org/journals/annals-of-mathematical-statistics/volume-22/issue-1/On-Information-and-Sufficiency/10.1214/aoms/1177729694.full . La recuperación HTML no proporcionó todo el artículo. La identidad del manuscrito se deriva en su prueba; no se presenta como cita literal.
- Rothenberg (1971), DOI `10.2307/1913267`. Publicación original: *Econometrica* 39(3), 577–591, https://www.jstor.org/stable/1913267 ; copia indexada: https://pages.stern.nyu.edu/~dbackus/Identification/id/Rothenberg_id_Econometrica_71.pdf . La búsqueda recuperó texto primario del artículo; la apertura del PDF falló y JSTOR no expuso texto completo. No se afirma lectura integral. El teorema V5 se prueba directamente por proyección de scores; la referencia sitúa el criterio de regularidad.

## Mapa de secciones

| V4 / título heredado | V5 |
|---|---|
| 1. Motivation and scope | 1. Motivation and scope |
| 0. Claim distinctions and conditional bridges | 2. Claim distinctions and conditional bridges |
| 1. Observation quotient and lifted state | 3. Observation quotient and lifted state |
| 2. Return operators, gauge covariance, and monodromy | 4. Return operators, gauge covariance, and monodromy |
| 3. Task-relative necessity of a lift | 5. Task-relative necessity of a lift |
| 4. Observation cannot be repaired by postprocessing alone | 6. Observation cannot be repaired by postprocessing alone |
| 5. Local identifiability with nuisance parameters | 7. Local identifiability with nuisance parameters |
| 6. Nontrivial return is not chirality | 8. Nontrivial return is not chirality |
| 7. Additive signed transport and loop reversal | 9. Additive signed transport and loop reversal |
| 8. Representation uncertainty and gauge stress tests | 10. Representation uncertainty and gauge stress tests |
| 9. Append-only recurrence in computational systems | 11. Append-only recurrence in computational systems |
| 10. Falsification architecture | 12. Falsification architecture |
| 11. Domain-specific helicity: magnetic case | 13. Domain-specific helicity: magnetic case |
| 12. Direct physical observability gate in MHD | 14. Direct physical observability gate in MHD |
| 13. Seismic counterexample and the role of negative evidence | 15. Seismic counterexample and the role of negative evidence |
| Discussion: what the negative seismic sequence and direct-field results change | 16. Discussion: what the negative seismic sequence and direct-field results change |
| Conclusion | 17. Conclusion |

## Regiones exactas cambiadas

Los intervalos incluyen líneas en blanco y corresponden a los archivos cuyos hashes figuran arriba. Son todos los bloques no idénticos de una comparación secuencial de líneas (`difflib.SequenceMatcher`, `autojunk=False`). Una inserción se marca como “después de”. Esta tabla permite revisar las regiones concretas sin duplicar todo el manuscrito en el registro.

| Región | Operación | Líneas V4 | Líneas V5 | Sección V5 |
|---|---|---|---|---|
| 1 | replace | 3 | 3 | Título/estado |
| 2 | replace | 7 | 7 | Abstract |
| 3 | replace | 27 | 27 | 1. Motivation and scope |
| 4 | replace | 31 | 31 | 1. Motivation and scope |
| 5 | replace | 33 | 33 | 2. Claim distinctions and conditional bridges |
| 6 | replace | 35 | 35 | 2. Claim distinctions and conditional bridges |
| 7 | replace | 38 | 38 | 2. Claim distinctions and conditional bridges |
| 8 | replace | 44 | 44–46 | 2. Claim distinctions and conditional bridges |
| 9 | replace | 47 | 49 | 2. Claim distinctions and conditional bridges |
| 10 | replace | 50 | 52–53 | 2. Claim distinctions and conditional bridges |
| 11 | replace | 53 | 56 | 2. Claim distinctions and conditional bridges |
| 12 | replace | 56 | 59–60 | 2. Claim distinctions and conditional bridges |
| 13 | replace | 59 | 63 | 2. Claim distinctions and conditional bridges |
| 14 | replace | 62 | 66 | 2. Claim distinctions and conditional bridges |
| 15 | replace | 65 | 69–87 | 2. Claim distinctions and conditional bridges |
| 16 | replace | 69 | 91 | 3. Observation quotient and lifted state |
| 17 | replace | 111 | 133 | 3. Observation quotient and lifted state |
| 18 | replace | 117 | 139 | 3. Observation quotient and lifted state |
| 19 | replace | 121 | 143 | 4. Return operators, gauge covariance, and monodromy |
| 20 | replace | 123 | 145–147 | 4. Return operators, gauge covariance, and monodromy |
| 21 | replace | 129 | 153 | 4. Return operators, gauge covariance, and monodromy |
| 22 | replace | 131 | 155 | 4. Return operators, gauge covariance, and monodromy |
| 23 | replace | 137 | 161 | 4. Return operators, gauge covariance, and monodromy |
| 24 | replace | 140 | 164 | 4. Return operators, gauge covariance, and monodromy |
| 25 | insert | después de 141 | 166–175 | 4. Return operators, gauge covariance, and monodromy |
| 26 | replace | 145 | 179 | 4. Return operators, gauge covariance, and monodromy |
| 27 | replace | 155 | 189–190 | 4. Return operators, gauge covariance, and monodromy |
| 28 | replace | 157 | 192 | 4. Return operators, gauge covariance, and monodromy |
| 29 | replace | 163 | 198 | 4. Return operators, gauge covariance, and monodromy |
| 30 | replace | 167 | 202–204 | 4. Return operators, gauge covariance, and monodromy |
| 31 | replace | 169 | 206 | 4. Return operators, gauge covariance, and monodromy |
| 32 | replace | 173 | 210 | 5. Task-relative necessity of a lift |
| 33 | replace | 181 | 218 | 5. Task-relative necessity of a lift |
| 34 | replace | 194 | 231 | 5. Task-relative necessity of a lift |
| 35 | replace | 198 | 235–236 | 5. Task-relative necessity of a lift |
| 36 | replace | 202 | 240–249 | 5. Task-relative necessity of a lift |
| 37 | replace | 212 | 259 | 5. Task-relative necessity of a lift |
| 38 | replace | 218 | 265 | 5. Task-relative necessity of a lift |
| 39 | replace | 222 | 269 | 6. Observation cannot be repaired by postprocessing alone |
| 40 | replace | 226 | 273 | 6. Observation cannot be repaired by postprocessing alone |
| 41 | replace | 242 | 289 | 6. Observation cannot be repaired by postprocessing alone |
| 42 | replace | 246 | 293 | 7. Local identifiability with nuisance parameters |
| 43 | replace | 264 | 311 | 7. Local identifiability with nuisance parameters |
| 44 | replace | 266 | 313–319 | 7. Local identifiability with nuisance parameters |
| 45 | replace | 272 | 325 | 7. Local identifiability with nuisance parameters |
| 46 | replace | 275 | 328–329 | 7. Local identifiability with nuisance parameters |
| 47 | replace | 278 | 332 | 7. Local identifiability with nuisance parameters |
| 48 | replace | 280 | 334 | 7. Local identifiability with nuisance parameters |
| 49 | replace | 282 | 336 | 7. Local identifiability with nuisance parameters |
| 50 | replace | 284 | 338–340 | 7. Local identifiability with nuisance parameters |
| 51 | replace | 287 | 343 | 7. Local identifiability with nuisance parameters |
| 52 | replace | 290 | 346–372 | 7. Local identifiability with nuisance parameters |
| 53 | replace | 294 | 376 | 8. Nontrivial return is not chirality |
| 54 | replace | 296 | 378 | 8. Nontrivial return is not chirality |
| 55 | replace | 298 | 380–386 | 8. Nontrivial return is not chirality |
| 56 | delete | 302–303 | después de 389 | 8. Nontrivial return is not chirality |
| 57 | insert | después de 304 | 391–394 | 8. Nontrivial return is not chirality |
| 58 | replace | 322 | 412 | 8. Nontrivial return is not chirality |
| 59 | replace | 326 | 416 | 8. Nontrivial return is not chirality |
| 60 | insert | después de 343 | 434–435 | 8. Nontrivial return is not chirality |
| 61 | replace | 346 | 438 | 9. Additive signed transport and loop reversal |
| 62 | replace | 348 | 440 | 9. Additive signed transport and loop reversal |
| 63 | replace | 368 | 460 | 9. Additive signed transport and loop reversal |
| 64 | replace | 370 | 462–464 | 9. Additive signed transport and loop reversal |
| 65 | replace | 374 | 468 | 10. Representation uncertainty and gauge stress tests |
| 66 | replace | 378 | 472 | 10. Representation uncertainty and gauge stress tests |
| 67 | replace | 380 | 474–476 | 10. Representation uncertainty and gauge stress tests |
| 68 | replace | 383 | 479–480 | 10. Representation uncertainty and gauge stress tests |
| 69 | replace | 386 | 483 | 10. Representation uncertainty and gauge stress tests |
| 70 | replace | 388 | 485 | 10. Representation uncertainty and gauge stress tests |
| 71 | replace | 390 | 487 | 10. Representation uncertainty and gauge stress tests |
| 72 | replace | 392–394 | 489 | 10. Representation uncertainty and gauge stress tests |
| 73 | replace | 396 | 491 | 10. Representation uncertainty and gauge stress tests |
| 74 | replace | 400 | 495 | 11. Append-only recurrence in computational systems |
| 75 | replace | 418 | 513 | 11. Append-only recurrence in computational systems |
| 76 | replace | 420 | 515 | 11. Append-only recurrence in computational systems |
| 77 | replace | 422 | 517–519 | 11. Append-only recurrence in computational systems |
| 78 | replace | 426 | 523 | 12. Falsification architecture |
| 79 | replace | 452 | 549–551 | 12. Falsification architecture |
| 80 | replace | 456 | 555 | 13. Domain-specific helicity: magnetic case |
| 81 | replace | 460 | 559 | 13. Domain-specific helicity: magnetic case |
| 82 | insert | después de 464 | 564–565 | 13. Domain-specific helicity: magnetic case |
| 83 | replace | 478 | 579 | 13. Domain-specific helicity: magnetic case |
| 84 | replace | 482 | 583 | 13. Domain-specific helicity: magnetic case |
| 85 | replace | 487 | 588 | 14. Direct physical observability gate in MHD |
| 86 | replace | 516 | 617 | 14. Direct physical observability gate in MHD |
| 87 | replace | 538 | 639 | 14. Direct physical observability gate in MHD |
| 88 | replace | 542 | 643 | 14. Direct physical observability gate in MHD |
| 89 | replace | 562 | 663 | 14. Direct physical observability gate in MHD |
| 90 | replace | 566 | 667 | 15. Seismic counterexample and the role of negative evidence |
| 91 | replace | 568 | 669 | 15. Seismic counterexample and the role of negative evidence |
| 92 | replace | 570 | 671 | 15. Seismic counterexample and the role of negative evidence |
| 93 | replace | 572 | 673 | 15. Seismic counterexample and the role of negative evidence |
| 94 | replace | 585 | 686 | 16. Discussion: what the negative seismic sequence and direct-field results change |
| 95 | replace | 587 | 688 | 16. Discussion: what the negative seismic sequence and direct-field results change |
| 96 | replace | 589 | 690 | 16. Discussion: what the negative seismic sequence and direct-field results change |
| 97 | replace | 591 | 692 | 16. Discussion: what the negative seismic sequence and direct-field results change |
| 98 | replace | 593 | 694 | 16. Discussion: what the negative seismic sequence and direct-field results change |
| 99 | replace | 595 | 696–714 | 16. Discussion: what the negative seismic sequence and direct-field results change |
| 100 | replace | 601 | 720 | 17. Conclusion |
| 101 | insert | después de 616 | 736–739 | References |

## Operaciones editoriales

1. Version status and authority.
2. Abstract scope and nonnovelty.
3. General lift versus literal helix.
4. Seismic reservation in motivation.
5. Universal implication chain replaced.
6. Closure-gap terminology.
7. Transport existence conditions.
8. State-specific nonreturn and literal geometry.
9. Gauge bijection.
10. Gauge invariants and fixed states.
11. Gauge proof.
12. Monodromy assumptions.
13. Log-score assumptions.
14. Oracle versus fitted gain.
15. Conditional sufficiency.
16. Sufficiency is not nonsignificance.
17. Data-processing stochastic condition.
18. History and training input scope.
19. Efficient information corrected and analytic counterexample.
20. Path reversal versus parity.
21. Dilation counterexample parity action.
22. Terminology scope.
23. Realized state and physical sign.
24. Additive functional conditions.
25. Loop scaling proof and rival conditions.
26. Representation measure and pseudoscalar covariance.
27. Lineage deterministic statement.
28. Lineage proof and support qualification.
29. Lineage is not geometry or evidence gain.
30. Gate and upper-bound interpretation.
31. Current helicity density.
32. Units and density versus integral.
33. Solar operator qualification.
34. Solar scope and citations.
35. Historical propagated errors not real replications.
36. No independent instrument validation.
37. Population result and binomial assumptions.
38. Seismic model scope.
39. Predictive bound not physical exclusion.
40. Remove residual hierarchy language.
41. Discussion reconciled across branches.
42. Conclusion separates mathematics and empirical claims.
43. Six original references preserved; two statistical primary references added.
44. Duplicate section numbers repaired; nine result identifiers preserved.

Revisión final: el cierre por pseudométrica exige separación; los invariantes matriciales se limitan a dimensión finita; la prueba de información condicional usa KL sin exigir densidad de la fibra; la dilatación se realiza como acción explícita del grupo fundamental del círculo.

Actualización al cierre: se distingue auditoría sísmica de pertenencia completada de reserva semántica no levantada; se incorporan sus 61.555 seleccionados, 3.513 en código 1 no certificado, 17 contrapartes qb y 16 observables con su partición. La ejecución solar temporal v1.5 queda registrada como soporte insuficiente: seis instantáneas válidas, una trayectoria completa y ninguna comparación de modelos. No se modificaron resultados previos.
