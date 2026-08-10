# Arquitectura y flujo gobernado

## Capas

1. **Cliente MCP**: Cline, Codex o VS Code nativo inicia el proceso local.
2. **Transporte STDIO**: JSON-RPC/MCP circula exclusivamente por stdin/stdout. Los diagnósticos van a stderr.
3. **Servidor Super-MCP**: publica herramientas, recursos y protocolo MCP `2025-06-18`.
4. **Gateway KCH**: aplica sesiones, capacidades, evidencia, controles, autorización, ejecución read-only y auditoría.
5. **Registro federado**: describe los servicios sin fundir sus autoridades.
6. **Adaptadores soberanos**: proyectan estado verificable de PHL, SCO, MIS y otros componentes.
7. **Evidencia portable**: copias selladas por SHA-256 sostienen las verificaciones locales.
8. **Ledger local del cliente**: cada configuración generada usa un archivo SQLite diferente para Codex, Cline y VS Code.

## Flujo completo de una acción gobernada

```text
inspeccionar estado/registro
        |
abrir sesión ligada a objetivo y jurisdicción
        |
admitir evidencia preregistrada
        |
evaluar R01-R28 y compilar contexto
        |
proponer acción (propuesta != autorización)
        |
autorizar sólo si evidencia, controles y autoridad son suficientes
        |
ejecutar una ruta federada READ_ONLY con capacidad de un solo uso
        |
verificar precommit shadow / registrar resultado / exportar auditoría
```

Una propuesta mutante no se transforma en ejecución: KCH 0.11 la bloquea. Un `PASS` de un control tampoco concede autoridad; es un recibo de evaluación de contexto.

## Separación de estados por cliente

El generador produce tres ledgers:

- `runtime/state/cline_kch_011.sqlite3`
- `runtime/state/codex_kch_011.sqlite3`
- `runtime/state/vscode_kch_011.sqlite3`

Esto impide que iniciar el servidor desde dos clientes convierta accidentalmente sus historiales en un solo contexto. Si se desea un ledger compartido, debe configurarse de forma deliberada mediante `KCH_011_STATE`; esa decisión cambia la frontera operacional y debe documentarse.

## Capacidades y secreto HMAC

El lanzador genera por defecto un secreto HMAC efímero por proceso. Las capacidades emitidas no deben tratarse como persistentes entre reinicios. Un secreto persistente sólo debe proporcionarse explícitamente en un entorno de confianza y nunca incrustarse en un ZIP o repositorio.

## Recursos MCP

- `kch://registry/current`
- `kch://controls/28`
- `kch://status/current`
- `kch://audit/current`

Estos recursos son superficies de lectura; no sustituyen las herramientas gobernadas cuando una operación requiere sesión, evidencia o capacidad.

