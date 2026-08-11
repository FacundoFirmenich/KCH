# Checkpoint 24 — KCH R17 portátil con cadena de lectura verificable

Fecha: 2026-08-11
Estado: **PASS_BOUNDED — REMOTE CUSTODY PENDING**

## Posición material

KCH queda mejor posicionado que en el checkpoint 23: la reparación ya no vive sólo en fuente. R17 0.3.7 fue empaquetada, extraída e instalada offline en raíces nuevas, arrancó por los ejecutables instalados y superó tanto el post-install general como el caso adverso específico de PREPILOT 019.

## Resultado observado

- ZIP canónico: 22.140.827 bytes; SHA-256 `ab5d71cd1399371f759f58a2cc92d4903d4610ba5d52f7e5abbc58114b393d40`.
- Instalación fresca: `D:\K17PKG_C_20260811\KCH_0.11_PRE2G_R17`; runtime `D:\K17RT_C_20260811`.
- Suite fuente 0.3.7: 79/79 PASS en 130,78 s.
- Post-install: 19/19 PASS_BOUNDED.
- Superficie integrada: 280 herramientas, sin colisiones ni blind spots declarados.
- Preflight 0.5: PASS, incluida la cadena ejecutable `full_read_file` → `full_read_batch` → `full_read_verify_batch`.
- Gobernanza: 19 fuentes verificadas y 8 artefactos compilados; jerarquía HARNESS > AGENTS > RULES intacta.
- MIS: 480 registros y 60 ledgers históricos; sin creación de autoridad ni autorización de ejecución.
- JSON-RPC instalado: UTF-8 estricto PASS usando el entorno generado por el propio adaptador.
- Batch instalado de cuatro archivos: PASS, ordinals 1–4, cuatro gates de spans exactos PASS.
- Reverificación instalada: `PASS_VERIFIED_AGAINST_SOURCE`.
- Ataque resealado: sello hijo y exterior válidos, pero hash factual adulterado; resultado `FAIL_BATCH_NOT_SOURCE_TRUE`.
- PHL: autorizado; entrenamiento y feedback real no ejecutados.

## Adversos preservados y convertidos

R17 necesitó tres iteraciones, sin reescribir su historia:

1. 0.3.5 (`8ce8ffe6…995db`): instalación correcta, pero el gate directo no recuperaba la ruta de runtime persistida. Se conserva en `D:\KCH_R17A_FAILED_POSTINSTALL_20260811`.
2. 0.3.6 (`70991d2a…11d4f`): post-install PASS, pero el stdio usaba la página de códigos local y fallaba ante un cliente UTF-8 estricto en el byte `0xF3`. Se conserva en `D:\KCH_R17B_FAILED_UTF8_STDIO_20260811`.
3. 0.3.7: descubre el runtime desde entorno o `runtime_paths.cmd`, obliga `PYTHONUTF8=1` en adaptadores y valida el transporte con `encoding="utf-8"`.

Esto aporta una lección metodológica concreta: un gate que sólo empareja las codificaciones locales de padre e hijo puede pasar y aun así violar el contrato de transporte del protocolo.

## Qué queda establecido

Queda establecida una instalación portátil local fresca con composición stdio, preflight canónico, MIS histórico acotado y una cadena de lectura multiarquivo que detecta corrupción manual aun cuando el recibo adulterado esté perfectamente resealado. La comprensión específica queda ligada a spans literales, no a resúmenes generales.

## Qué no queda establecido

No quedan establecidos: activación automática en Codex/Cline real, utilización prolongada por el usuario, producción, seguridad integral, reducción general causal de fallos, validación industrial, valor de cliente ni aprendizaje PHL. La lectura sigue limitada a UTF-8 y a un máximo agregado de 5 MiB por batch; paginación transaccional para archivos mayores y formatos binarios sigue pendiente.

## Próxima acción crítica

Subir R17 y toda la evidencia 019 al repositorio privado, custodiar ZIP y recibos en Drive, verificar metadata remota y hashes donde el conector lo permita. No borrar evidencia local.

Recibo de release: `outputs/KCH_R17_RELEASE_RECEIPT.json` (`ddbdb5b4b6e1e40dbef1dbe18ce44ceee29382e033cc52745bd939e03456409a`).
