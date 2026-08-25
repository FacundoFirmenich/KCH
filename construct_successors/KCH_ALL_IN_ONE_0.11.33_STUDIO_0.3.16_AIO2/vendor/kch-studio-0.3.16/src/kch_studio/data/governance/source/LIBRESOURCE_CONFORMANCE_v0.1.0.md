# Norma de conformidad LIBRESOURCE v0.1.0

Estado: batería técnica local inicial. La certificación pública, la marca y la auditoría independiente no están establecidas.

## Resultados permitidos por recurso X

- `LIBRESOURCE_ABSENCE_PASS`
- `LIBRESOURCE_INDEPENDENCE_PASS`
- `LIBRESOURCE_DEGRADED_BUT_RECOVERABLE`
- `LIBRESOURCE_FAIL_CONSTITUTIVE_DEPENDENCY`
- `LIBRESOURCE_NOT_ESTABLISHED`

No se convierte `NOT_ESTIMABLE`, un gate no ejecutado o una prueba local en PASS.

## Gates universales de retirada

1. `INVENTORY_COMPLETE`: inventario de dependencias directas y transitivas.
2. `DISCONNECT`: retirada real de X dentro de la jurisdicción ensayada.
3. `INDEPENDENT_BOOT`: arranque por una ruta que no necesita X.
4. `STATE_RECONSTRUCT`: reconstrucción del estado canónico desde exportaciones verificadas.
5. `AUTHORITY_HASH_VERIFY`: autoridad, hashes y trazabilidad preservados.
6. `DEGRADATION_MEASURE`: degradación funcional medida y declarada.
7. `SUBSTITUTE`: sustituto real o ruta alternativa ejecutada.
8. `HISTORY_PRESERVE`: historial y resultados adversos no reescritos.

Antes del flush final deben pasar además:

- `SUCCESSOR_COMPETENCE`: competencia prospectiva, diferencial y adversa del sucesor.
- `FLUSH_PROPORTIONALITY`: el beneficio de retirar X justifica coste, riesgo y pérdida residual.

## Gates plug-and-play por host

`CLEAN_INSTALL`, `AUTODETECT`, `ONE_SHOT_PAIRING`, `CAPABILITY_USE`, `PERMISSION_VISIBILITY`, `UNINSTALL_STATE_PRESERVED`, `ROLLBACK` y `OFFLINE_CORE_CONTINUITY`.

Un paquete, una extensión detectada o una autenticación exitosa no bastan. El claim plug-and-play sólo pertenece al host, versión, sistema y capacidades realmente ejecutados.

## Gates de ultracompatibilidad

- round-trip de datos sin pérdida;
- coexistencia sin interferencia;
- comparación diferencial semántica y operacional;
- negociación de capacidades y extensiones namespaced;
- conservación de permisos y autoridad;
- migración gradual y rollback;
- sustitución del proveedor conservando estado;
- desconexión final con continuidad.

El runtime adjudica por separado las ocho dimensiones y las seis rutas. Un conjunto completo de referencias produce como máximo `PASS_BOUNDED_DECLARED_SCOPE`: sigue necesitando verificación independiente de los recibos y no autoriza generalización.

## Auditoría de dependencias y concentración

El inventario ejecutable clasifica cuentas, navegadores, nubes, bases, formatos, hardware, jurisdicciones, lenguajes, modelos, sistemas operativos, protocolos, proveedores, repositorios, runtimes, SDK, servicios y toolchains. Detecta dependencias constitutivas sin alternativa y autoridad externa declarada. La ausencia de esos defectos sólo significa que no hay un punto único **declarado** en el manifiesto: no prueba retirada, independencia ni ausencia.

## Adjudicación plug-and-play

Cada recibo queda acotado por host, sistema operativo, arquitectura, versión de cliente y capacidades realmente ejercidas. Incluso con ocho gates declarados como `PASS`, KCH mantiene `plug_and_play_established=false` hasta verificar independientemente los recibos de ejecución. Nunca se transfiere el resultado a otro host o versión.

## Niveles locales

- `L0_DECLARED`: contrato y procedencia completos; ninguna independencia probada.
- `L1_PORTABLE`: seis rutas y round-trip local ejecutados.
- `L2_INDEPENDENT`: gates universales pasan para un X y jurisdicción concretos.
- `L3_FLUSH_SEALED`: sucesor competente, retirada proporcionada, X ausente y estado sellado.

Cada resultado debe identificar hardware, sistema operativo, versiones, cuentas, red, fixtures, hashes, timestamps, actor, autoridad, salidas y fallos. La ausencia de una segunda implementación independiente impide claims universales.
