# SCA/CFL Open-Ended Structure Grammar v1.9.0

Gate `OPEN_ENDED_STRUCTURE_GRAMMAR_AND_ADVERSARIAL_MODEL_SYNTHESIS_010`.

Constructivo: propone una estructura.
Contrapolar: busca otra estructura que produzca la misma traza observable.
Adjudicador: si existe foil indistinguible, devuelve una equivalence class y no una ontología única.
Probe: busca un punto fuera del soporte que maximice la separación predictiva.
Future certifier: congela ambos modelos antes de usar datos interventionales posteriores.

Resultado de referencia: `expr:x` vs `expr:z`, 117 programas observationalmente equivalentes dentro de la grammar depth-2, LR observacional futuro = 1, intervención `x!=z` cruza E=20 en 6 observaciones.

Todo candidato sigue siendo `PROTOFORM_REALVIRTUAL_+0`.
