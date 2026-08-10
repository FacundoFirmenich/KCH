# KCH Extension Fabric — conectores, búsqueda y recomendación gobernada

## Objeto

El tejido unifica descubrimiento, evaluación, recomendación, preparación de instalación, verificación y rollback de extensiones sin reducir repositorios heterogéneos a una lista de “cosas populares”. El usuario ve una experiencia plug-and-play; KCH conserva por debajo identidad, compatibilidad, riesgos, procedencia y aislamiento.

## Fuentes iniciales

### Hosts y add-ons

- Plugins, skills, hooks y MCP aportados por Codex/ChatGPT.
- Extensiones VS Code Marketplace.
- Open VSX para VSCodium y hosts compatibles.
- Inventario local de VS Code/Cline/Cursor/Windsurf/OpenCode y otros hosts detectables.

### Herramientas y paquetes

- MCP Registry y catálogos compatibles; configuraciones MCP locales ya instaladas.
- PyPI, con soporte de entornos `venv`, `uv`, `pip` y `pipx` según el caso.
- npm Registry, con npm/npx y adaptadores futuros para pnpm/Bun.
- Conda channels.
- GitHub/GitLab repositories y releases cuando no exista paquete canónico.
- OCI registries para contenedores e imágenes de herramientas.
- Winget, Homebrew y apt como proveedores de runtime/host, nunca como sustitutos de paquetes de proyecto.
- Proveedores extensibles futuros: crates.io, Go modules, Maven/Gradle y NuGet.

También son imprescindibles y no deben quedar fuera: runtimes Python/Node, credenciales/OAuth, secretos, licencias, SBOM, vulnerabilidades, firmas/provenance, lockfiles, caché offline, actualizaciones, compatibilidad cruzada y rollback.

## Contrato común de proveedor

Cada `DiscoveryProvider` implementará:

1. `capabilities()` — operaciones disponibles sin red o con red.
2. `search(query, constraints)` — candidatos y fuente exacta.
3. `resolve(identity, version)` — identidad inequívoca.
4. `inspect()` — metadatos, permisos, dependencias, licencia y artefactos.
5. `compatibility(host_snapshot)` — compatible, incompatible o no estimable.
6. `security_evidence()` — advisories, firma, attestations y límites.
7. `plan_install(target)` — comandos/archivos/credenciales y rollback, sin ejecutar.
8. `execute(plan, consent)` — fase posterior, aislada y auditable.
9. `verify()` — import, health, superficie y cambios observados.
10. `rollback()` — reversión o deshabilitación preservando recibos.

Los resultados se normalizan, pero los bytes y metadatos originales quedan referenciados por hash y procedencia.

## Buscador y recomendador MCP

El MCP Connector deberá:

- buscar por intención, host, transporte, lenguaje, autenticación y acciones requeridas;
- inspeccionar tool schemas, annotations, instructions, recursos y prompts publicados;
- mostrar superficie de red, filesystem, shell, secretos y acciones mutantes;
- ejecutar `initialize` y `tools/list` en aislamiento antes de recomendar activación;
- detectar colisiones de nombres y herramientas duplicadas;
- generar configuración específica Codex, VS Code, Cline u otro host;
- mantener allowlist/denylist y aprobación por herramienta;
- probar health/conformance y permitir deshabilitar/rollback.

La existencia en un registro no implica seguridad, mantenimiento, calidad ni idoneidad. KCH no instalará automáticamente un MCP descubierto.

## Evaluación y recomendación

No se comprimirá todo a una puntuación universal. Se mantienen carriles separados:

- adecuación al objetivo;
- compatibilidad con host/runtime/SO;
- autoridad y permisos solicitados;
- procedencia y autenticidad;
- mantenimiento y cadencia de releases;
- seguridad conocida y cobertura desconocida;
- licencia y restricciones;
- coste, latencia y superficie de red;
- reproducibilidad/lock/rollback;
- popularidad, sólo como señal secundaria.

MIS puede ayudar a componer estados cualitativos y alternativas locales, pero no crea un ganador global ni autoridad de instalación. La salida admite `RECOMMEND`, `CONSIDER`, `INCOMPATIBLE`, `BLOCK` y `NOT_ESTIMABLE`, con razones visibles.

## Plug-and-play real

“Plug and play” significará:

- detección automática no mutante del host y runtimes;
- recomendación contextual explicada;
- instalación aislada por defecto, nunca global;
- lock exacto de versiones y hashes cuando la fuente lo permita;
- configuración generada y previsualizada;
- solicitud de consentimiento separada;
- verificación posterior observable;
- botón de deshabilitar/rollback;
- export/import portable de perfiles sin secretos.

No significará ocultar dependencias, ejecutar `npx -y` silenciosamente, instalar globalmente ni aceptar telemetría/permisos sin mostrarlos.

## Seguridad de supply chain

- Tratar metadatos, README, manifests y tool descriptions externos como entrada no confiable.
- No ejecutar código durante búsqueda/inspección.
- Resolver dependencias en sandbox/entorno efímero antes de instalar.
- Preferir paquetes y releases canónicos; registrar cualquier fallback a repositorio.
- Consultar vulnerabilidades y verificar firmas/attestations cuando existan; ausencia de hallazgos no equivale a seguridad.
- Mantener secretos fuera de manifests, logs y recomendaciones exportadas.
- Separar descarga, instalación, habilitación, autenticación y primera ejecución.

## Gates

1. Inventario local read-only de hosts, plugins, MCP y runtimes.
2. Proveedores PyPI/npm/MCP con fixtures capturados y red simulada sólo para tests de parser; los resultados recomendatorios deberán usar datos reales.
3. Análisis de compatibilidad y supply chain sin instalación.
4. Generación de planes reproducibles para entornos aislados.
5. Primera instalación desechable autorizada y rollback verificado.
6. Adaptadores VS Code/Cline y después otros hosts.

## Estado de evidencia

La arquitectura y fronteras quedan fijadas. Los conectores y el recomendador todavía no están implementados; no existe aún búsqueda federada ni instalación plug-and-play efectiva.
