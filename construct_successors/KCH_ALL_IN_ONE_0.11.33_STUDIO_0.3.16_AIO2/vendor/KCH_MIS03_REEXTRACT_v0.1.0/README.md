# KCH × MIS v0.3.1 effective integration

Estado previsto tras gate: `LOCAL_VALIDATED_EFFECTIVE_INTEGRATION_CANDIDATE`.

Este paquete integra el MIS v0.3.1 sellado como servicio matemático federado de
KwanCode Harness (KCH). MIS conserva su identidad y calcula estados semánticos,
posteriores racionales exactas, pérdidas, decisiones y certificados. KCH conserva
en exclusiva el gobierno de autoridad, routing, commit y promoción de claims.

No se modifican los bytes de MIS v0.3.1. El bundle contiene copias byte-idénticas
del wheel cualificado, el corpus KHC real de 480 records, el reporte v0.3.1, los
60 ledgers future-only y su manifiesto. El adaptador rehúsa arrancar ante cualquier
hash distinto de los hashes de custodia congelados.

## Superficie integrada

- `describe`: descripción y límites del servicio;
- `audit_historical_khc`: ejecución real sobre 480 records, 60 streams, 480
  freezes y 480 outcomes, con comparación exacta contra el reporte congelado;
- `exact_decide`: actualización bayesiana y decisión por pérdida con fracciones
  canónicas, empates preservados y jurisdicción explícita;
- `verify_certificate`: verificación del certificado sin crear autoridad.

Los cuatro métodos están clasificados `READ_ONLY` en el catálogo KCH. El método
no declarado `authorize_execution` debe ser bloqueado fail-closed antes de que
se invoque ejecutor alguno.

## Frontera de evidencia

El gate puede demostrar integración ejecutable local, custodia, cálculo exacto,
round-trip estructural, replay future-only, adaptación a
`kch.reviewable-decision.v0.2.0`, routing por el control plane y lowering CSI.

No demuestra mejora causal de KCH, superioridad predictiva prospectiva, utilidad
humana, escalado abierto ni ganador global. Las acciones del corpus histórico son
observaciones; no son outcomes causales de calidad. El ejemplo de decisión exacta
es un ejemplo formal congelado, no una estimación empírica.

## Ejecución del gate

El entrypoint `kch-mis-v03-gate` requiere rutas explícitas para el estado KCH de
origen, el control plane, los cinco artefactos MIS, el catálogo, el registry y los
seis outputs. El gate crea una réplica SQLite nueva y se niega a sobrescribir
artefactos existentes. No inicia PHL, no registra feedback y no toca el estado
personal fuente.

