# Operación, diagnóstico y custodia

## Salidas y logs

El protocolo JSON-RPC usa stdout. Cualquier mensaje humano debe ir a stderr; imprimir logs en stdout rompe el transporte. El lanzador incluido no escribe mensajes normales en stdout antes del servidor.

## Diagnóstico por capas

1. **Bytes**: verifique el SHA-256 del ZIP y el manifiesto del paquete.
2. **Bundle**: ejecute `bundle/scripts/verify_bundle.py bundle`.
3. **Runtime portable**: ejecute `launcher/doctor.py`.
4. **Cliente**: revise su panel/output MCP.
5. **Interfaz**: confirme handshake, 49 herramientas y cuatro recursos.
6. **Gobierno**: confirme `agent-shadow`, mutación falsa/prohibida y ledger `PASS`.
7. **Federación**: audite 19 evidencias y siete paquetes.

## Copias y transporte

Archive juntos:

- ZIP completo original;
- archivo `.sha256` o seal;
- ledger operativo que corresponda al cliente;
- exportación `kch.super.audit.export`;
- recibo del doctor y checkpoint de la campaña.

Calcule hashes antes y después del traslado. Transportar bytes intactos conserva identidad, no necesariamente jurisdicción ni autoridad.

## Actualización

No reemplace archivos dentro de un paquete 0.11 ya usado. Extraiga una nueva versión en otra carpeta, valide, migre sólo estado autorizado y conserve la release anterior para reproducibilidad. Toda migración debe recomputar autoridad si cambia evidencia, esquema, jurisdicción o transporte.

## Recuperación

El ledger es append-only en el plano lógico. `kch.super.rollback` agrega una compensación; no borra el evento objetivo ni revierte silenciosamente archivos externos. Si el archivo SQLite se daña, preserve una copia, registre el fallo y restaure desde una copia verificada; no reconstruya eventos inventados.

## Errores relevantes

- `FAIL` de manifiesto: no use el paquete; vuelva al ZIP sellado.
- wheel faltante: la distribución está incompleta.
- evidencia del registro `FAIL`: suspenda el claim relacionado.
- `UNAVAILABLE`: conserve el estado; no lo convierta en `PASS` por narrativa.
- PHL bytes distintos después del doctor: gate fallido; investigar antes de continuar.

