# ECH: rutas fijas de dos etapas y desempates locales

Este paquete conserva separados los dos protocolos: (1) las 46 rutas conjuntas fijadas antes del cálculo y (2) la auditoría posterior de las 11 rutas mejoradas. `DICTAMEN_ES.md` contiene las tablas completas, la formulación, las pruebas y las reservas.

El resultado principal cierra 46 óptimos exactos. La auditoría posterior cierra otros 11 problemas restringidos y prueba que en todos ellos un primer paso localmente mínimo basta. El catálogo reúne 46 planes con ambos pasos mínimos respecto de su estado y coste total óptimo para la ruta fija. Trece de los 23 cuadrados conservan valores óptimos diferentes entre sus dos rutas.

## Verificación sin solver

Los programas `check_joint_certificates.py` y `check_posthoc_local_ties.py` usan exclusivamente Python estándar. El primero verifica además el catálogo si se pasa `--catalog`. No importa ninguno de los productores ni confía en sus agrupaciones.

Desde la carpeta del proyecto:

```bash
python work/continuity_v3/ech_joint/check_joint_certificates.py --source repo/research/continuity_v2_20261013/evidence/ech --results work/continuity_v3/ech_joint --catalog work/continuity_v3/ech_joint/LOCAL_MINIMUM_LOOKAHEAD_CATALOG.json
python work/continuity_v3/ech_joint/check_posthoc_local_ties.py --source repo/research/continuity_v2_20261013/evidence/ech --results work/continuity_v3/ech_joint
```

Los argumentos son rutas explícitas y permiten mover el paquete. El origen debe contener los insumos y resultados congelados del ECH v2. Cada protocolo comprueba sus hashes.

## Recalcular sin sobrescribir evidencia congelada

Requisitos usados: Python 3.12.14, NumPy 2.3.5 y SciPy 1.17.0. Ambos productores aceptan `--time-limit` en segundos por problema MILP; el valor por defecto es 120. El tiempo total de resolución de las 46 rutas en esta ejecución fue aproximadamente 23 segundos, sin promesa de rendimiento en otros entornos.

Para la primera fase, crear una carpeta nueva, copiar sólo `PROTOCOL_FIXED_TWO_STAGE.json` y pasar dicha carpeta mediante `--output` a `solve_joint_routes.py`, junto con `--source` apuntando al ECH v2. Comprobar los nuevos certificados con `check_joint_certificates.py`, sin el argumento de catálogo histórico. Comparar por identidad de ruta los 46 valores óptimos y las brechas; no exigir los mismos desempates.

Para la segunda fase, crear otra carpeta nueva y copiar `PROTOCOL_FIXED_TWO_STAGE.json`, `PROTOCOL_POSTHOC_LOCAL_TIE_AUDIT.json`, `ECH_JOINT_ROUTE_RESULT.json` y `JOINT_ROUTE_CERTIFICATES.json` originales. Ejecutar `solve_posthoc_local_ties.py --source ... --output ...` y luego `check_posthoc_local_ties.py --source ... --results ...`. El productor restringido importa `Kernel` desde `solve_joint_routes.py`, por lo que ambos scripts deben permanecer en el mismo directorio. La segunda fase reejecuta el alcance posterior realmente congelado: su protocolo vincula el resultado original de la primera fase. Un resultado nuevo de la primera fase tiene otra identidad por sus metadatos de entorno/tiempos y no debe hacerse pasar por el original.

Los certificados de una reejecución y su catálogo necesitan referencias de prueba nuevas si cambian los testigos o sus hashes. El catálogo distribuido se verifica contra las pruebas congeladas distribuidas, preservando los recibos originales. La no identidad binaria de logs o testigos no invalida igualdad de costes demostrados.

## Archivos de evidencia

- `PROTOCOL_FIXED_TWO_STAGE.json`: universo completo de 46 rutas, política y hashes de las fuentes.
- `JOINT_ROUTE_CERTIFICATES.json`: testigos binarios y duales racionales exactos por ruta.
- `ECH_JOINT_ROUTE_RESULT.json`, `JOINT_ROUTE_COMPARISON.csv` y `JOINT_SQUARE_COMPARISON.json`: resultados y comparaciones completas.
- `PROTOCOL_POSTHOC_LOCAL_TIE_AUDIT.json`: restricción posterior, 11 rutas y mínimos locales originales.
- `POSTHOC_LOCAL_TIE_CERTIFICATES.json`, `POSTHOC_LOCAL_TIE_RESULT.json` y `POSTHOC_LOCAL_TIE_COMPARISON.csv`: prueba y comparación J/R/A.
- `LOCAL_MINIMUM_LOOKAHEAD_CATALOG.json`: 35 planes históricos y 11 nuevos desempates, todos con coste mínimo local en ambos pasos y óptimo conjunto para su ruta.
- Los dos recibos `SOLVER_FREE_*.json`: resultados de verificaciones independientes.
- Los logs conservan los valores y estados de cálculo. La conclusión de exactitud proviene de los certificados, no del estado del solver.

No se generan observaciones ni datos sintéticos. No se afirma optimalidad de rutas alternativas en el grafo, identidad de ledgers de rutas de igual coste, ni validación física. `permission_granted` permanece false.
