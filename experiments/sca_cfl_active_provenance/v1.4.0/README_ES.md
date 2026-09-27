# SCA/CFL Active Provenance v1.4.0

Gate `ACTIVE_PROVENANCE_PROBING_AND_VALUE_OF_INFORMATION_005`.

Este directorio es un delta ejecutable sobre `experiments/sca_cfl_dependent_provenance/v1.3.0/`.
La política selecciona qué relación de procedencia investigar según valor esperado para el gate robusto, descontando coste, privacidad y latencia. Las creencias blandas sólo seleccionan sondas; nunca crean restricciones duras.

Ejecución:
```bash
PYTHONPATH=experiments/sca_cfl_dependent_provenance/v1.3.0/src:experiments/sca_cfl_active_provenance/v1.4.0/src \
pytest -q experiments/sca_cfl_active_provenance/v1.4.0/tests
```
