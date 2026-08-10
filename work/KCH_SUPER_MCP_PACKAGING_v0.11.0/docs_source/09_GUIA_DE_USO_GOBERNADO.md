# Guía de uso gobernado

## Nivel 1: inspección segura

Comience por estas operaciones, que no requieren sesión:

1. `kch.super.status`
2. `kch.super.registry`
3. `kch.super.controls`
4. `kch.super.registry.evidence.audit`
5. `kch.component.status`

Use `kch.phl.projection`, `kch.sco.projection` y `kch.mis.certificate.verify` para conocer proyecciones/certificados sellados; no confunda leerlos con ejecutar esos subsistemas.

## Nivel 2: evaluación reflexiva

Invoque un control directo con todos sus campos requeridos o use `kch.super.context.compile` para evaluar un subconjunto explícito. No rellene valores “verosímiles”: si un dato no existe, preserve su ausencia y acepte `ABSTAIN` o `UNAVAILABLE`.

Ejemplo conceptual de R01:

```json
{
  "governing_objective_id": "objetivo-canonico",
  "candidate_objective_id": "objetivo-canonico"
}
```

El `PASS` sólo dice que esos identificadores coinciden bajo ese evaluador; no valida el contenido del objetivo.

## Nivel 3: cadena gobernada de solo lectura

Para ejecutar una ruta adaptada:

1. Defina y selle el contrato de objetivo.
2. Abra una sesión con `kch.super.session.open`.
3. Admita las evidencias esperadas mediante capacidades de un solo uso.
4. Evalúe los controles pertinentes y preserve sus recibos.
5. Proponga una acción `READ_ONLY` para una ruta permitida.
6. Autorice la propuesta con los recibos requeridos.
7. Ejecute exactamente una vez con la capacidad recibida.
8. Registre el resultado, incluso si es adverso.
9. Exporte la auditoría y conserve su hash.

Las capacidades caducan y son de un solo uso. No reutilice un token ni lo incluya en documentación.

## Rutas federadas ejecutables

La herramienta de ejecución sólo acepta rutas de adaptación que el gateway reconozca, entre ellas las superficies de estado/proyección de componentes. Consulte `kch.super.registry` y el código canónico antes de diseñar una campaña; la mera existencia de una herramienta MCP no significa que sea una ruta federada ejecutable a través de `action.execute`.

## Cómo explicar un resultado

Todo cierre material debe distinguir:

- resultado observado;
- comparación con el checkpoint anterior;
- evidencia que lo sostiene;
- significado técnico/metodológico/epistemológico;
- límites y claims no demostrados;
- artefactos cambiados;
- blocker real;
- próxima decisión crítica.

