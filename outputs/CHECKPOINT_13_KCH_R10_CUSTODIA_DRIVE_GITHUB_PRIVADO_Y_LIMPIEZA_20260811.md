# CHECKPOINT 13 — KCH 0.11 R10: custodia Drive, GitHub privado y limpieza local

Fecha: 2026-08-11  
Estado: **CUSTODIA DOBLE VERIFICADA EN SU JURISDICCIÓN; LIMPIEZA MATERIAL PARCIAL CON RESIDUOS ACL BLOQUEADOS**

## Resultado sustantivo

KCH queda mejor posicionado que en el checkpoint anterior: el candidato integrado R10 ya no depende de una única copia local y existe una rama canónica privada utilizable para continuidad de ingeniería. La mejora es de custodia, trazabilidad y recuperabilidad; no amplía por sí sola la validación funcional o industrial del arnés.

## Estado técnico validado antes de la custodia

- Regresión local exhaustiva dividida: 40/40 pruebas superadas.
- Instalación portable limpia en D: y gate postinstalación: 14/14, `PASS_BOUNDED`.
- Candidato portable R10: `KCH_0.11_PRE2G_INTEGRATED_CANDIDATE_R10.zip`.
- SHA-256 R10: `90069c91fe8d57aca44b19d515fa7fad0664395c06e5ab99dfd0803ab39c67ea`.
- Superficie estratégica: 31 clases, 232 métodos públicos, 205 herramientas expuestas y 27 métodos internos.
- PHL permanece autorizado arquitectónicamente, pero no entrenado ni validado con uso real.
- MIS conserva integración portable acotada; no se convierte por ello en autoridad automática ni validación industrial.

## Custodia Google Drive

Carpeta creada en Mi unidad: `KCH`  
ID: `1f0vH7T7oLwOh7or5wKs4FoNgnY7quVR3`

El respaldo integral tuvo que dividirse por el límite de 100 MiB del conector:

1. `KCH_CANONICAL_BACKUP_20260811.zip.part001`
   - ID Drive: `1Sc1Dmp2Ihtr_nIPLnOT-xdI5LNC5k6wZ`
   - 94.371.840 bytes
   - SHA-256 local: `3205c2678819cf3fd4b744ba9e1bea1420c5d81c3dc6adab0e77b986713201cb`
2. `KCH_CANONICAL_BACKUP_20260811.zip.part002`
   - ID Drive: `1el6nhCqscJupgJxr9jBRiskwBX5iQeqt`
   - 87.002.190 bytes
   - SHA-256 local: `a6c7e6f38a5604fdd5d9fa4feee977df772bf2e90a37a59e4a6713b4e0f694af`

ZIP recompuesto esperado:

- 181.374.030 bytes
- SHA-256: `983ea61138c280108c67d9b0290d373ed2ae3b6bfdd13b6688ea2ba7cc7fb140`

También se cargaron el manifiesto de partes, el manifiesto SHA-256 por archivo y el recibo local. Drive confirmó presencia, carpeta padre, nombres y tamaños exactos. El conector no devolvió checksums remotos; por rigor, no se afirma una verificación criptográfica remota de descarga.

## Custodia GitHub

Repositorio: `https://github.com/FacundoFirmenich/KCH`  
Visibilidad consultada después del push: **PRIVATE**  
Rama: `main`  
Commit canónico inicial: `bc4ecc5b5fef868d1fb62522f74cdd5d29c1ad98`

El SHA de `refs/heads/main` remoto coincidió exactamente con el HEAD local. GitHub conserva código, documentación, evidencia, resultados adversos, releases y manifiestos; excluye 69 archivos regenerables, todos contenidos bajo `.pytest_tmp`. Drive conserva además esos derrames en el respaldo integral.

## Limpieza local

Eliminado:

- `D:\KCH_TESTS_R10` (~236,8 MB de pruebas, instalación y runtimes desechables).
- `...\KCH_CSI_STUDIO_EXTENSION_FABRIC_v0.1.0\.pytest_tmp` (~2,6 MB).
- El espacio libre de C: pasó de ~1,8 MB en el incidente a ~3,60 GB.

No eliminado por ACL de Windows, pese a borrado forzado, `takeown` e `icacls`:

- `...\KCH_CSI_STUDIO_EXTENSION_FABRIC_v0.1.0\.pytest_response_modes`
- `C:\Users\User\Documents\Codex\pytest-kch-full-r10-20260811-a`
- `C:\Users\User\Documents\Codex\pytest-kch-r10-shard-a`
- `C:\Users\User\Documents\Codex\pytest-kch-r10-shard-b`
- `C:\Users\User\Documents\Codex\pytest-kch-response-20260811-a`

Son residuos de pytest ya respaldados; no se afirma que la limpieza haya sido total. El workspace canónico y los artefactos R10 no fueron borrados.

## Límite epistemológico

Este checkpoint prueba continuidad de custodia, réplica privada de ingeniería, integridad local por hashes y coincidencia del commit remoto. No prueba superioridad general, seguridad integral, robustez industrial, valor longitudinal del usuario, aprendizaje PHL real ni cierre completo de MIS.

## Próxima acción crítica

Cerrar los cinco residuos ACL desde una sesión de Windows realmente elevada o tras reinicio, sin ampliar el blanco. Después, la siguiente acción de producto sigue siendo el prepiloto industrial comparativo con KCH frente a baseline sobre fallos históricos reales; PHL real permanece postergado por decisión del usuario.

