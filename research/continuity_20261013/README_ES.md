# Continuidad integral KCH / Helical Lift - 13 octubre 2026

Esta revisión realiza correcciones y comprobaciones sobre el corpus completo. Dos manuscritos V5, una auditoría sísmica de pertenencia, una ejecución solar real, la recuperación parcial del ECH y la reproducción radial M33 quedan relacionados en un registro de 29 afirmaciones, 12 dominios y 20 fuentes. Los predecesores y los protocolos congelados permanecen intactos. No se concede nueva autoridad, no se fusiona con la rama canónica y no se generan observaciones sintéticas.

## Resultados nuevos de esta continuidad

| Frente | Trabajo realizado | Resultado y alcance |
|---|---|---|
| Fundamentos | Corrección completa de Paper 1 | Separa retorno observado, retorno de estado, transporte, paridad, helicidad e identificación regular. Conserva referencias y bloques empíricos. |
| Manuscrito sísmico | Corrección completa de Paper 2 | Incorpora reservas de pertenencia y exposición Indio; conserva cifras; cotas predictivas, no físicas. |
| Pertenencia sísmica | Cruce de 61.555 índices contra fuente ciega | 3.513 códigos 1 sin semántica certificada; 17 códigos 0 con contraparte qb, 16 observables, uno en test Parkfield. No se cargaron ángulos. |
| Solar temporal v1.5 | Primera ejecución del runtime y protocolo originales | Seis registros válidos y sólo una trayectoria completa; dos fallos QUALITY impiden la comparación. No hay ganador ni resultado nulo científico. |
| M33 radial | Regeneración determinista sobre tablas archivadas | 396 Hα, 102 H I, 28 bins; p=0,664427; 66 comparaciones y 142 hashes correctos. |
| ECH | Tres inputs exactos recuperados; diferencias recalculadas | 96/96 diferencias de coordenadas coinciden. No se ha regenerado el solver/atlas completo. |
| BayME | Recuperación del informe prospectivo y comprobación de su tabla | 15 lonjas, 8 victorias BayME; MAE 0,96396 frente a 1,15091. No es prueba CEH ni replay del ledger bruto. |

La cohorte sísmica antigua y su análisis de diseño heredan la reserva de selección. El terminal post-2021 utiliza otra fuente y filtro, de modo que esta reserva no se le transfiere automáticamente. Su cierre sigue referido a modelos, observables y umbrales declarados.

## Un solo registro de alcance

`CLAIM_EVIDENCE_REGISTRY.json` no suma los dominios como si fueran réplicas del mismo experimento. Cada entrada declara fuente, estatus, dependencias, reservas e inferencias inadmisibles. `CORPUS_VERIFICATION.json` calcula la propagación de reservas a través de las dependencias reales y comprueba que no se extiendan por mera semejanza de nombres. Conserva CEH, Cuantorítmica, KCH/Fabric, runtime, Pluriverse y banco físico aunque no produzcan un nuevo resultado empírico en esta ejecución.

M33 y el Sol son ramas físicas distintas. El resultado radial galáctico no estaba ausente: había quedado subrepresentado en la recapitulación. Sigue pendiente su inferencia espacial FITS. BayME sí tiene evidencia prospectiva histórica; sigue pendiente la comparación específica fase versus fase más fibra/régimen. En ambos casos, recuperar trabajo existente evita fabricar una carencia o una confirmación.

## Qué significa el resultado solar

Run: https://github.com/FacundoFirmenich/KCH/actions/runs/38381823297

Commit ejecutado: `c31fb9be4f6ddbdce36b25a975246ceffb79dcda`. Protocolo SHA-256: `3f6f7b13a5eb3eed82a3d345116ae5f32f205a12d296ac204d3a916859054b8e`.

- HARP 401: 5/5 registros completados.
- HARP 2920: rechazo del primer registro, QUALITY=70656.
- HARP 5249: primer registro válido; rechazo del segundo, QUALITY=66560.
- El ejecutor abandona cada trayectoria tras su primer rechazo: siete registros restantes no se adjudicaron. No se los etiqueta como inválidos.
- No se ajustaron los rivales ni se produjeron scores. Salida científica: `INSUFFICIENT_TEMPORAL_SUPPORT`; salida de proceso: 31.
- Las siete entradas congeladas coinciden por hash; las seis identidades de registros son exactas; el recibo se valida; los FITS brutos se purgaron.

El control genérico usa actividad del extremo final y, por ello, esta comparación sería condicional a la transición, no pronóstico ex ante. Esa frontera se registró antes de la ejecución en `SOLAR_PREEXECUTION_SCOPE.md`. No se sustituyen fechas para rescatar el resultado. Un sucesor de desarrollo deberá preseleccionar soporte por metadatos, congelar una nueva identidad y conservar este resultado.

## Reproducibilidad

Validación del corpus de esta revisión, desde la raíz del repositorio:

```bash
python research/continuity_20261013/tools/verify_integral_registry.py
```

Las auditorías científicas tienen ejecutores separados y requieren sus fuentes exactas. Sus recibos registran los nombres, hashes y referencias de los archivos originales:

```bash
python research/continuity_20261013/tools/audit_historical_membership.py --source-dir FUENTES_SISMICAS --output-dir SALIDA_SISMICA
python research/continuity_20261013/tools/audit_ech_recovery.py --source-dir FUENTES_ECH --output-dir SALIDA_ECH
python research/continuity_20261013/tools/verify_m33_radial_deterministic.py --source ARCHIVO_MHD_V4_3_EXTRAIDO --output SALIDA_M33
```

El crosswalk exhaustivo de pertenencia se conserva comprimido sin pérdida en `evidence/seismic/SELECTED_MEMBERSHIP_ALL_61555.csv.gz`; `COMPRESSED_CROSSWALK.json` fija hashes tanto comprimido como original. Ningún valor angular está en ese crosswalk.

M33 usa la transcripción Hα y CSV H I archivados: esta continuidad verifica sus bytes y números, pero no vuelve a transcribir las publicaciones primarias. El replay omite deliberadamente el main histórico que ejecuta bootstrap, así como JAX, generadores y FITS. La norma 290 reproduce estimadores puntuales bajo escalas declaradas; no es una cota estadística del coeficiente verdadero.

ECH recupera los tres inputs de SOURCE_BINDING. Sus diferencias utilizan elecciones de puente ya archivadas; todavía faltan el generador original y la caché de 204 entradas para verificar optimalidad y regenerar el atlas entero. Los inputs originales permanecen identificados por sus referencias persistentes y hashes en el recibo.

## Pendientes que conservan su lugar

1. Documentación primaria de códigos y disposición de discrepancias sísmicas. No reabrir como confirmación los tests ya vistos.
2. Crosswalk piloto Indio/global para cuantificar exactamente la exposición a test.
3. Sucesor solar con preflight de soporte anterior a los observables y estimando temporal explícito.
4. Adquisición y verificación del protocolo M33 2D, sin variar sus 75 sensibilidades después de ver píxeles.
5. Generador/caché ECH o implementación independiente declarada como tal.
6. Comparación CEH económica con vintages y freezes originales; completar mapa implementado de rivales y GF.
7. Banco físico: recuperar estado material actual. El paquete histórico del 27 septiembre no registra primer artículo ni datos físicos. Esta revisión no presume compras, calibraciones ni respuestas nuevas.
8. Pluriverse: observables físicos y rivales de complejidad comparable antes de cualquier afirmación cosmológica. El banco o los operadores solares no resuelven esa obligación.
