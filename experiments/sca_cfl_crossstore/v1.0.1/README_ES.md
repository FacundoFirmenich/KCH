# SCA/CFL Cross-Store Continuity v1.0.1

Gate de persistencia cruzada entre Biblioteca de ChatGPT, Google Drive y GitHub.

Principio: **persistencia ≠ vigencia ≠ autoridad**.

## Ejecutar
```bash
PYTHONPATH=src pytest -q -p no:cacheprovider
PYTHONPATH=src python -m sca_crossstore.cli verify .
```

La promoción fuerte requiere coincidencia verificada 3/3. Una divergencia verificada bloquea promoción. Dos copias coincidentes pueden orientar recuperación, nunca decidir autoridad por mayoría.
