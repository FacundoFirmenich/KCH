# KCH PREPILOT 001 — adjudicación material

## Resultado

El ensayo no permite estimar superioridad de KCH. El gate comparativo es `INVALID_CONDITION_INTEGRITY`: el brazo arnés usó una clase interna no canónica y su preflight falló. El resultado adverso se conserva; no se rescata mediante la puntuación.

## Diagnóstico descriptivo

- `BASELINE_SIN_KCH`: 95/95 en el rubric observable.
- `KCH_CANDIDATO_CON_ARNES`: 95/95 en el rubric observable.

Ambos brazos calcularon correctamente los bytes, líneas y SHA-256 de los tres archivos y buscaron la convocatoria BIND 11th Edition 2026/2027 en activos oficiales concretos. El brazo KCH preservó mejor su fallo de preflight y sus abstenciones, pero eso no prueba beneficio causal.

## Límite

Esto es un prepiloto local de proceso. No es prueba industrial, no es evidencia de valor para un Venture Client, no es validación humana y no establece readiness de candidatura BIND.

## Próximo gate

Repetir el caso congelado usando exclusivamente `kch_preflight` sobre `StudioMCP`; después incorporar varias clases de fallo histórico, réplicas y un evaluador ciego a la condición.
