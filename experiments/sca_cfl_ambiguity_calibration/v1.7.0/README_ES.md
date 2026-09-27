# SCA/CFL Ambiguity Calibration v1.7.0

Gate `AMBIGUITY_SET_LEARNING_AND_CALIBRATION_008`.

Capas:
- `BAYES_INNER`: posterior/credible set para routing y propuestas, SHADOW_ONLY.
- `OUTER_CS`: conjunto de confianza anytime-valid, único set calibrado que puede sostener planificación autorizada bajo el contrato `true model in outer family`.
- `CORE`: la familia v1.6, monitorizada por un e-process compuesto; rechazo del core sólo cuarentena el core.
- `FALLBACK`: familia de reserva predeclarada; un rechazo del outer produce HOLD y no activa el fallback sin evento explícito de autoridad.
