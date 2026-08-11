# Checkpoint 19 — reparación prospectiva de `ConstructMode`

Fecha: 2026-08-11
Jurisdicción: candidato vivo posterior a KCH PREPILOT 018
PHL: autorizado; entrenamiento real no ejecutado

## Resultado sustantivo

KCH queda mejor posicionado que al cierre adverso del prepiloto 018 porque se localizó y corrigió la inconsistencia que permitía que un archivo transitorio desapareciera mientras `shutil.copytree` construía el sucesor. La evidencia histórica no se reescribe: el brazo A terminó con 70/70 y el brazo B con 69/70, y el calificativo de «determinista» emitido por B fue un overclaim.

## Cambio técnico

`ConstructMode` usa ahora una única definición de árbol transitorio para:

- calcular hashes;
- excluir rutas de la base estable;
- copiar el candidato al área de construcción;
- promover el sucesor para el siguiente arranque.

La regresión introduce deliberadamente `__pycache__/module.cpython-314.pyc` y `runtime_live_ephemeral/state.bin`; ambos deben quedar fuera del sucesor promovido.

## Verificación

- prueba causal aislada: 1/1 PASS;
- repetición de la prueba causal: 10/10 PASS, cero fallos;
- suite completa posterior: 70/70 PASS en 130,90 s;
- PHL real: no ejecutado.

## Significado y límite de claim

Se eliminó la carrera reproducida en la ruta cubierta y se alinearon identidad y copia del árbol estable. Esto no demuestra ausencia universal de carreras de sistema de archivos, preparación para producción, seguridad operacional ni validación industrial. Tampoco convierte el resultado discordante de 018 en una victoria de ningún brazo.

## Próxima acción crítica

Empaquetar esta reparación junto con el contrato de lectura íntegra ya presente en el candidato, verificar instalación limpia y recibo posinstalación, y sólo entonces sellar una nueva macrorelease portátil.
