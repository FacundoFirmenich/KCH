# CSI Studio — arquitectura vinculante previa a implementación visual

## Naturaleza

CSI Studio no será un editor de texto decorado ni una colección de formularios. Será el entorno de composición, inspección, generación, validación y promoción de construcciones KwanCode/CSI. Todo artefacto deberá poder verse simultáneamente como:

- objeto humano comprensible;
- nodo/ensamblaje CSI;
- archivos materiales;
- grafo de dependencias y autoridad;
- diff respecto del estado instalado;
- candidato inactivo, validado o promovido.

## Arquitectura de referencia

### Motor Python soberano

Un servicio Python local, sin dependencia de la vista, expondrá API tipada y eventos para:

- cargar y compilar `HARNESS.md > AGENTS.md > RULES.md`;
- editar el grafo CSI;
- generar artefactos en staging;
- ejecutar validadores específicos;
- mantener catálogos, hashes, linaje, permisos y recibos;
- preparar instalación, actualización y rollback sin ejecutarlos sin autorización.

El estado será portable y auditable. La UI nunca decidirá autoridad por sí misma; solicitará transiciones al motor.

### Cliente visual Python principal

Se propone **PySide6/Qt** como cliente de escritorio inicial por sus paneles acoplables, árbol, inspector, menús, diálogos, ventanas flotantes, accesibilidad y empaquetado Windows/macOS/Linux. La dependencia y sus obligaciones de distribución deberán auditarse antes de congelarla. El motor conservará una frontera que permita clientes alternativos.

### Adaptadores de host

- Codex/ChatGPT: herramientas MCP y, cuando proceda, componentes MCP Apps versionados.
- VS Code/Cline: panel Webview delgado conectado al servicio Python local.
- CLI/headless: automatización y gates reproducibles.
- Navegador local opcional: cliente web del mismo API, no una segunda lógica.

La lógica permanece Python; las vistas específicas del host son adaptadores de presentación.

## Sistema visual

### Cápsula KCH prudente

Elemento persistente, visible y compacto que muestra:

- estado general y perfil;
- acción o recomendación pendiente;
- riesgo/autoridad por color, texto e icono redundantes;
- evidencia faltante;
- botón de expansión.

Al desplegarse muestra por qué se sugiere algo, qué cambiaría, qué permisos requiere, procedencia, alternativas y rollback. Nunca cubre contenido ni interrumpe para avisos informativos.

### Interacciones

- **Desplegables** para selección reversible y exploratoria.
- **Inspector lateral** para identidad, versión, hash, procedencia, autoridad y compatibilidad.
- **Ventanas flotantes/acoplables** para grafo, consola, tests y diff.
- **Pop-ups/modales** sólo para instalación, publicación, credenciales, mutación o pérdida de datos.
- **Paleta de comandos** con búsqueda por intención y artefacto.
- **Tour guiado opcional** que puede abandonarse y retomarse sin ocultar el modo experto.

Todas las decisiones deben ofrecer explicación corta visible y detalle expandible. No habrá opciones críticas escondidas en menús profundos, defaults silenciosos ni recomendación única sin alternativas.

## Editor CSI guiado

### Tipos de artefacto

1. Skill.
2. Herramienta o función.
3. Servidor/herramienta MCP.
4. Operador CSI.
5. Agente y subagente.
6. Regla, rutina y subrutina.
7. KwanFork.
8. Mod.
9. Plugin/paquete de integración.
10. Adaptador de host.
11. Recurso, catálogo o preset KwanPrompts.

### Flujo transaccional

`intención → tipo → objetivo/jurisdicción → entradas/salidas → autoridad → dependencias → topología CSI → preview → diff → generación completa en staging → tests → revisión → sello candidato → decisión separada de instalación`.

Cada pantalla admite tres grados de guía:

- **Guiado completo**: una decisión clara por paso, ejemplos contextualizados y recomendación explicada.
- **Asistido**: formulario completo con validación y sugerencias no vinculantes.
- **Experto**: grafo, archivos y contratos editables directamente con feedback inmediato.

### Generación de skills

El generador deberá seguir el contrato material real del host. Para Codex: carpeta con `SKILL.md`, frontmatter mínimo válido, `agents/openai.yaml` cuando corresponda y únicamente `scripts/`, `references/` o `assets/` necesarios. Debe usar el inicializador/validador oficial disponible, ejecutar pruebas de scripts y rechazar TODOs o recursos de ejemplo sin sustituir. La instalación en el catálogo de skills es una transición posterior.

### Generación de otros artefactos

Cada tipo tendrá un `ArtifactProvider` con:

- esquema de especificación;
- preguntas guiadas;
- materializador;
- validadores;
- detector de placeholders;
- prueba mínima real;
- proyección CSI;
- plan de instalación y rollback.

Un proveedor ausente produce `UNAVAILABLE_PROVIDER`; CSI Studio no fabrica una implementación genérica y la llama completa.

## Estados

`DRAFT → SPECIFIED → GENERATED_STAGED → VALIDATED → SEALED_CANDIDATE → INSTALL_REQUESTED → INSTALLED → ENABLED`.

Las transiciones `INSTALLED` y `ENABLED` no pertenecen a esta fase. Un fallo genera `VALIDATION_FAILED` preservando artefactos y logs; una revisión crea una nueva versión/branch, no reescribe evidencia.

## Gates del Studio visual

1. Backend de contratos y grafo validado sin UI.
2. Prototipo visual conectado al backend real, sin botones simulados.
3. Generación completa de una skill y una herramienta MCP en staging.
4. Test de accesibilidad, escalado, teclado y recuperación de sesión.
5. Empaquetado portable en entorno limpio.
6. Uso humano guiado por el usuario antes de afirmar ergonomía o inspiración efectiva.

## Estado de evidencia

Este documento fija arquitectura y requisitos. El compilador de gobierno ya constituye el primer backend real; **CSI Studio visual todavía no está implementado** y no debe mostrarse como disponible.
