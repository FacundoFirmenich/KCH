# Lifecycle Cline/VS Code

AIO2 instala ocho wrappers PowerShell en `.cline/hooks`: `TaskStart`, `TaskResume`, `TaskCancel`, `TaskComplete`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse` y `PreCompact`. Cada wrapper adapta el contrato JSON de Cline al lifecycle KCH y devuelve el contrato Cline `cancel/contextModification/errorMessage`.

La lógica constitucional no se bifurca: el bridge reutiliza `kch_native_hook.py`, `kch_native_state.py` y `kch_r33_runtime.py` de la proyección estable R33 incluida en AIO2. `PreToolUse` falla cerrado si el bridge no puede verificar una operación; los hooks informativos fallan visibles pero abiertos para no inutilizar Cline.

La documentación de Cline ha coexistido con dos layouts históricos. AIO2 usa `.cline/hooks`, que es el layout general vigente de configuración. No duplica automáticamente los mismos hooks en `.clinerules/hooks`, porque dos descubrimientos simultáneos producirían doble ejecución. La activación real queda pendiente del smoke test que hará el usuario en su instalación VS Code/Cline.
