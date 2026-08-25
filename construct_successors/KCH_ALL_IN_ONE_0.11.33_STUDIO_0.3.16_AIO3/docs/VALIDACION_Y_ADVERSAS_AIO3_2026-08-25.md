# Validación y adversas AIO3 — 2026-08-25

## Resultado sustantivo

AIO3 quedó elegible para promoción gobernada. El contrato de cierre sustantivo y el contrato de persistencia CONSTRUCT se bajaron a las proyecciones soportadas sin modificar los linajes R21/R33 ni el release AIO2. La instalación propagable conserva capacidad de construir, pero no recibe autoridad sobre `FacundoFirmenich/KCH`: sólo puede persistir en la instalación seleccionada, en instalaciones KCH explícitamente registradas o en una rama no predeterminada de un fork GitHub verificado.

El gate cloud real construyó el paquete desde el asset AIO2 fijado por digest, verificó el ZIP, instaló dos veces en hosts aislados Codex y Cline, verificó la proyección marketplace y ejecutó rollback ligado a recibo. Esto acredita construcción, compatibilidad e idempotencia dentro de Windows aislado. No acredita activación observada en una sesión humana, utilidad longitudinal, compatibilidad total con todos los hosts ni autoridad científica u oficial automática.

## Evidencia adversa preservada

1. El primer test local detectó que el segundo lowering Cline cambiaba una línea en blanco. El contenido era equivalente, pero no byte-idempotente. Se corrigió la normalización y la suite posterior pasó 7/7.
2. El primer workflow cloud se ejecutó en Linux y falló al instalar porque el wheelhouse offline AIO2 no contiene una rueda Pillow 12 compatible con esa plataforma. No se incorporaron descargas de red ni se alteró AIO2 para rescatar el gate. Se reubicó la prueba en `windows-latest`, jurisdicción declarada del paquete, y el run posterior pasó.

## Recibos y enlaces

- PR: https://github.com/FacundoFirmenich/KCH/pull/5
- Run adverso fuera de jurisdicción: https://github.com/FacundoFirmenich/KCH/actions/runs/32858747526
- Run Windows terminal PASS: https://github.com/FacundoFirmenich/KCH/actions/runs/32858962998
- Job terminal: https://github.com/FacundoFirmenich/KCH/actions/runs/32858962998/job/97837879974
- Artefacto temporal cloud-first: `kch-aio3-complete`, 184123829 bytes, retención CI de tres días.
- Promoción automática: `false`.
- Escritura upstream desde instalaciones genéricas: `false`.
- Instalación viva del usuario: `false`.
- Activación de host observada en sesión humana: `false`.