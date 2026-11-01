# KCH Contrastive Effects Observatory — resultado histórico

| Caso | Par admisible | Baseline | KCH | Δ puntos normalizados | Ratio bytes recibo | Gate |
|---|---:|---:|---:|---:|---:|---|
| KCH-PREPILOT-001 | no | 95.0/95.0 | 95.0/95.0 | +0.0 | 0.676× | INVALID_CONDITION_INTEGRITY |
| KCH-PREPILOT-002 | sí | 95.0/95.0 | 95.0/95.0 | +0.0 | 8.983× | PASS_SINGLE_NONRANDOMIZED_PAIR |
| KCH-PREPILOT-003 | sí | 100.0/100.0 | 100.0/100.0 | +0.0 | 0.987× | PASS_SINGLE_NONRANDOMIZED_PAIR |

Pares: 3; admisibles: 2; inválidos: 1; victorias KCH: 0; derrotas: 0; empates: 2.

Posterior direccional P(KCH mejor) = 0.500; intervalo creíble 95% de ventaja condicional = [-0.950, 0.950]. Al no haber pares discordantes, este posterior no aprendió nada respecto del prior.

**Techo de afirmación:** Dos empates descriptivos válidos y un par inválido. No hay mejora de calidad medida, efecto causal, ventaja de coste o tiempo, utilidad humana ni validación industrial.

**Activación automática:** BLOCKED_INSUFFICIENT_EVIDENCE.

Métricas ausentes: wall_clock_latency, provider_input_tokens, provider_output_tokens, provider_reasoning_tokens, provider_cost, user_corrections, task_resolution, human_utility, errors_avoided.

SHA-256 lógico de evidencia compilada: `ddcccff17974a130340668fb6c19fc4332f896683c4a9fc6f69269fa9496aade`
