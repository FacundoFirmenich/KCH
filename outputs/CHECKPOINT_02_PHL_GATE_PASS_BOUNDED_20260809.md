# Checkpoint 02 — gate efectivo PHL↔KCH v0.2.0

Fecha: 2026-08-09  
Estado: `PASS_BOUNDED`  
Comprobaciones: `16/16`

## Posición respecto del checkpoint anterior

KCH queda mejor posicionado. PHL ya no es sólo un instrumento local con una campaña autónoma y una primera sesión real de usuario pendiente: existe una ruta transaccional sucesora, probada sobre una réplica exacta, que media escrituras de clientes múltiples y hace efectiva la exclusión PHL.

## Resultado observado

- El estado fuente arrancó con 7 decisiones, 7 eventos, 0 feedback y 0 sesiones activas.
- Se registraron 17 métodos como `READ_ONLY` o `MUTATING` con evidencia explícita.
- Se inventariaron los 16 renglones admitidos del registro KCH v0.4.0.
- Una escritura de un segundo cliente con head obsoleto fue rechazada.
- La repetición del mismo request fue idempotente y no duplicó eventos.
- Con PHL activo, `Super-MCP.open_session` quedó bloqueado antes de ejecutar el callable.
- Con PHL activo, `RGG.resolve_profile` siguió disponible como lectura.
- La cadena final cerró con 46 eventos, 39 solicitudes, 9 decisiones —7 originales y 2 sondas instrumentales—, 0 feedback y 0 defectos.
- El estado personal fuente permaneció byte a byte idéntico: `a81724487739c37825e251c0de68a9aaf2033e2e14418f9aac8215f6a976527d`.

## Significado

Técnicamente, queda demostrada una ruta local de escritor único, concurrencia optimista, idempotencia, contrato estricto de decisiones y exclusión efectiva. Metodológicamente, la prueba evita alterar el estado personal y distingue sondas instrumentales de decisiones sustantivas. Epistemológicamente, un `PASS_BOUNDED` no se promueve a cobertura global.

## Límite vinculante

El inventario adjudica 2 emisores (`RGG`, `KwanPrompts`), 2 servicios no emisores (`OBL`, `PHL`) y 12 contratos `UNAVAILABLE_CONTRACT`. No se ejecutó una sesión PHL con el usuario, no hubo notas `000..100`, paquete de entrenamiento ni activación de política. Tampoco se demostró despliegue distribuido.

## Artefactos y hashes

- Resultado del gate: SHA-256 `792fe7af5a8e07cd331e2ed81b708d29458e01b82e519b2d64dc210302ebd0c9`.
- Réplica preservada: SHA-256 `5ced75b2950c202ad32cecd338ea1c7bd30a150dfd37ea1ee11a62863938057d`.

## Consecuencia para el objetivo KCH

El gate pendiente dejó de bloquear la incorporación de nuevas herramientas. SCO puede construirse sobre una base que ya distingue lectura, mutación, autoridad y decisión revisable. La cobertura deberá ampliarse al registro v0.5.0, donde SCO entra como candidato con contrato emisor todavía no implementado.
