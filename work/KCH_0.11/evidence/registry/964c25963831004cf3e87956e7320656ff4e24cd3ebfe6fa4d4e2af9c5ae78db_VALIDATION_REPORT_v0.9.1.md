# Validation report KwanCode Microcosmic Harness v0.9.1

## Estado

VALIDATED_SOFTWARE_AND_RETROSPECTIVE_REPLAY

## Controles ejecutados

- Suite completa: 120/120 pruebas aprobadas.
- Wheel: kwancode_microcosmic_harness-0.9.1-py3-none-any.whl.
- Instalacion aislada: aprobada.
- Smoke MCP instalado: version 0.9.1, 27 herramientas, sin error.
- Replay futuro-only sobre factorial v0.4.1: ejecutado sobre 204 payloads estimables.
- Historia preservada: v0.4.0, v0.4.1 y v0.9.0 no fueron reescritas.

## Resultado del replay

| Brazo | N estimable | Committable | Bloqueado | Residuos numericos limpiados | Consultas propuestas | Consultas auto-committed |
|---|---:|---:|---:|---:|---:|---:|
| A control | 102 | 96 | 6 | 12 | 6 | 0 |
| B KHC | 102 | 96 | 6 | 0 | 6 | 0 |

Los seis bloqueos por brazo corresponden a D5: no habia pregunta en el
payload. El gate no invento la pregunta. La politica adquisitiva produjo una
propuesta separada a partir de fundamentos explicitos future-only.

C3 conserva 12 filas NOT_ESTIMABLE por correspondencia terminologica
subdeterminada.

## Limite de evidencia

El replay valida implementacion y transferencia retrospectiva sobre respuestas
ya observadas. No es un nuevo A/B prospectivo y no demuestra utilidad
industrial, cero alucinacion universal ni generalidad fuera de contratos
cerrados.


## Sello final

- Suite final: 120/120 aprobadas en 6.57 s.
- Wheel final SHA-256: 3cac69af12f7d0b46ba7ba66475d938b2bf9176adb84ee7bcde8b0d90bc9a62b.
- Smoke aislado: gate=BLOCK, query=QUERY_PROPOSED, release_authorized=false.
