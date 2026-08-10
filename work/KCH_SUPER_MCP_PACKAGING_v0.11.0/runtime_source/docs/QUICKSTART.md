# Inicio rápido

1. Requiere Python 3.11 o posterior.
2. Ejecute `python -X utf8 launcher/doctor.py --output runtime/doctor_result.json`.
3. Exija `PASS`.
4. Ejecute `python -X utf8 launcher/generate_client_configs.py --output-dir generated_configs`.
5. Fusione la configuración del cliente elegido; no sobrescriba otros servidores.
6. Reinicie el cliente e invoque primero `kch.super.status`.

Antes de fusionarlas puede validar que las tres configuraciones arrancan el mismo servidor y conservan estados separados:

```powershell
python -X utf8 launcher/validate_client_configs.py --config-dir generated_configs
```

Este gate usa los campos de configuración, pero no suplanta una invocación real desde el host Cline/Codex/VS Code.

La configuración se entrega en perfil `agent-shadow`, con mutación prohibida y aprobaciones automáticas vacías/prompt. PHL real no se ejecuta.

Para exportar esquemas exactos de la interfaz viva:

```powershell
python -X utf8 launcher/export_interface.py
```

La documentación explicativa completa está en `docs/full` dentro de este paquete y también se distribuye como ZIP documental separado.
