# Cierre sustantivo — custodia Âqhâw y KwanDisk general

Fecha: 2026-08-27  
Estado: candidatura validada y custodiada; no promovida; ningún borrado real autorizado ni ejecutado.

## Objetivo gobernante

Aplicar en los proyectos Codex/ChatGPT la cadena de almacenamiento indicada por el usuario —Google Drive primero; GitHub después, dentro de sus límites; disco local o VPS sólo por orden explícita o necesidad indispensable— y convertir en una capacidad general de KwanDisk la limpieza gobernada de carpetas ad hoc, `Documents/Codex`, carpetas de agentes y `tmp/temp`.

## Resultado real

- Âqhâw: 58 archivos y 24.255.723 bytes verificados en Drive. Repositorio privado nuevo `FacundoFirmenich/aqhaw-startup`, commit `25ce0cd43a7e3bdfbe8a58e3651ee0233273c1f4`; 58 archivos de proyecto más el README generado por GitHub.
- KwanDisk: candidatura implementada en `FacundoFirmenich/KCH`, rama `codex/kwandisk-general-cleanup-v0.2`, commit validado `9db6ac7c03ccca57b00e9c0ec96a87acb0c54bf6`, PR borrador #6.
- Drive KCH: 8/8 archivos de la candidatura, 49.210 bytes, descargables y no compartidos públicamente, en `KCH_0.11.33_DRIVE_FIRST_STORAGE_POLICY_CANDIDATE_20260827`.
- Validación: tres módulos compilados y 5/5 pruebas formales superadas. El primer gate detectó una sintaxis inválida real en el ensamblador AIO3; fue corregida y revalidada.
- Transporte: la carpeta temporal exacta `C:\tmp\kwandisk-drive-20260827-9db6ac7c` fue eliminada después de la verificación remota; no contenía originales del usuario.

## Significado técnico y metodológico

KwanDisk puede descubrir y planificar candidatos en cuatro jurisdicciones sin inferir que todo lo viejo o voluminoso sea basura. Sólo clasifica como eliminable material regenerable conocido, transitorio conocido o custodia replicada con Drive, GitHub y recuperación verificados. La ejecución requiere identidad `USER`, autorización exacta, SHA-256 exacto del plan y revalidación de la huella del origen. Sesiones, memorias, skills, plugins, reglas, AGENTS, autenticación/configuración, `.git`, worktrees, bases SQLite/WAL, rutas activas y material desconocido quedan protegidos.

## Límites y blocker real

La PR es una candidatura, no una versión promovida ni instalada globalmente. La política global de AGENTS sigue bajo llave constitucional y requiere un gesto exacto del usuario en terminal confiable; la propuesta anterior queda superada porque expresaba un orden de almacenamiento ya corregido. No se verificó hash remoto de Drive porque el conector no lo expone. No se ejecutó limpieza sobre datos reales, no se modificó el VPS y no se ejecutó entrenamiento PHL.

## Próxima acción crítica

Autorizar por llave constitucional la política global corregida y, por separado, generar un plan de limpieza real con objetivos exactos, bytes recuperables y gates de recuperación. Sólo después podrá decidirse qué candidatos concretos eliminar.
