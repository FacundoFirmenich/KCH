# ECH: verificación independiente del atlas finito

Esta entrega reconstruye el problema matemático de puentes de evidencia desde
los tres inputs originales vinculados por SHA-256. Verifica los testigos
archivados y vuelve a demostrar sus costes mínimos. No recupera ni suplanta al
generador o a la caché históricos.

Se certificaron 204 problemas únicos, que cubren 380 aplicaciones de puentes:
96 adyacencias, 192 pasos en los 96 bucles y 92 pasos en los 23 cuadrados.
Son 66 certificados de coste positivo y 138 de coste cero.

## Verificación sin solver

Desde esta carpeta, con Python 3.10 o posterior y sólo biblioteca estándar:

```bash
python tools/check_ech_certificates.py --inputs inputs --results results
```

El verificador independiente no importa el generador ni bibliotecas de
optimización. Vuelve a evaluar el kernel y comprueba factibilidad entera de
todos los testigos, las 264.145 desigualdades duales con aritmética entera,
el cierre de las cotas y los vínculos entre problemas y resultados. Emite
`results/SOLVER_FREE_CERTIFICATE_CHECK.json`.

## Regeneración de los certificados

El entorno ejecutado fue Python 3.12.14, NumPy 2.3.5 y SciPy 1.17.0. Las dos
últimas dependencias sólo se necesitan para proponer certificados mediante LP:

```bash
python tools/verify_ech_finite_bridges.py \
  --inputs inputs \
  --atlas source_archives/ECH_HELICAL_EVIDENCE_MIGRATION_2026-10-12.zip \
  --predecessor source_archives/ECH_EVIDENCE_CARRYING_CONTRACT_MIGRATIONS_2026-10-08.zip \
  --semantics-archive source_archives/ECH_ROBUST_SUCCESSIVE_REFINEMENT_2026-09-28.zip \
  --output results
python tools/check_ech_certificates.py --inputs inputs --results results
```

El optimizador opera en coma flotante, pero sus respuestas no certifican el
resultado: las ponderaciones se convierten a fracciones y se verifica cada
desigualdad exactamente. La optimalidad se acepta sólo cuando el techo entero
de la cota dual coincide con el tamaño de un testigo factible. Otra versión del
optimizador puede proponer un dual distinto y producir bytes diferentes sin
alterar el resultado matemático.

## Insumos y alcance

- `inputs/` contiene los tres originales inalterados: kernel, codebooks y
  adyacencias. La ejecución verifica sus hashes antes del cálculo.
- `source_archives/` preserva el atlas, su predecesor y la fuente primaria que
  define los sensores. ACTIONABLE agrupa APPLY y TOP_2; MODE toma el modo de
  la firma; EXACT conserva la firma completa.
- `results/EXACT_BRIDGE_CERTIFICATES.json` contiene los testigos, las fracciones
  duales y la evidencia heredada de cada uno de los 204 problemas.
- `results/FINITE_ATLAS_REPLAY_DETAIL.json` conserva las comprobaciones de los
  28 codebooks, 784 combinaciones, 96 adyacencias, 96 bucles y 23 cuadrados.
- `results/TIE_INVARIANT_PATH_WITNESSES.json` identifica cuatro cuadrados cuyos
  costes diferentes y conjuntos distintos persisten ante cualquier desempate
  óptimo de los puentes locales.
- `DICTAMEN_ES.md` desarrolla el resultado y sus límites.

Se verifican 238 hashes de conjuntos de coordenadas. No se verifican hashes
de estados completos ni cadenas históricas de recibos. Ningún resultado otorga
autoridad operativa. Los cálculos son consecuencias del kernel finito
archivado, no datos físicos nuevos ni validación del universo real.
