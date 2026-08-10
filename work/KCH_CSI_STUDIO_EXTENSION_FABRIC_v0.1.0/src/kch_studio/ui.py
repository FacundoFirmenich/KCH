from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Any, Callable

from .advanced_runtime import KCHAdvancedRuntime
from .clipboard_hub import RegionSelector
from .constitutional import Actor
from .contracts import ArtifactKind, ArtifactSpec
from .extension import ExtensionFabric, RecommendationEngine, RuntimeInventory
from .installation import ConsentDecision, IsolatedInstaller
from .mcp_server import TOOLS, StudioMCP
from .permissions import OPERATIONS
from .response_modes import SCOPE_CONTEXT_KEYS, SCOPE_ORDER
from .studio import Studio

AUTHORITY_DEFAULT = "INSPECT,DESIGN,BUILD_STAGED,VALIDATE,RECOMMEND,REQUEST_INSTALL"


class KCHStudioApp(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        studio: Studio,
        *,
        advanced: KCHAdvancedRuntime | None = None,
        fabric: ExtensionFabric | None = None,
        installer: IsolatedInstaller | None = None,
        tool_call: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None,
        tool_descriptors: list[dict[str, Any]] | None = None,
    ):
        super().__init__(master, padding=6)
        self.studio = studio
        self.fabric = fabric or ExtensionFabric(studio.root / "extension_fabric")
        self.installer = installer or IsolatedInstaller(studio.root / "isolated_installs")
        self.advanced = advanced
        self.tool_call = tool_call
        self.tool_descriptors = list(tool_descriptors or [])
        self.pack(fill="both", expand=True)
        self._capsule_open = True
        self._build_style()
        self._build_capsule()
        self._build_workspace()
        self.refresh_sessions()
        self.draw_governance_graph()

    def _build_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Capsule.TFrame", background="#172033")
        style.configure(
            "Capsule.TLabel",
            background="#172033",
            foreground="#f4f7ff",
            font=("Segoe UI", 10, "bold"),
        )
        style.configure("Accent.TButton", font=("Segoe UI", 9, "bold"))

    def _build_capsule(self) -> None:
        self.capsule = ttk.Frame(self, style="Capsule.TFrame", padding=(10, 7))
        self.capsule.pack(fill="x", pady=(0, 6))
        ttk.Label(self.capsule, text="KCH · CSI Studio", style="Capsule.TLabel").pack(side="left")
        status = self.studio.status()
        text = f"HARNESS > AGENTS > RULES · {len(status['providers'])} generadores · instalación externa: NO"
        self.capsule_status = ttk.Label(self.capsule, text=text, style="Capsule.TLabel")
        self.capsule_status.pack(side="left", padx=18)
        ttk.Button(self.capsule, text="Ocultar/mostrar", command=self.toggle_capsule).pack(
            side="right"
        )

    def toggle_capsule(self) -> None:
        self._capsule_open = not self._capsule_open
        if self._capsule_open:
            self.capsule_status.pack(side="left", padx=18)
        else:
            self.capsule_status.pack_forget()

    def _build_workspace(self) -> None:
        vertical = ttk.Panedwindow(self, orient="vertical")
        vertical.pack(fill="both", expand=True)
        horizontal = ttk.Panedwindow(vertical, orient="horizontal")
        vertical.add(horizontal, weight=8)

        left = ttk.Frame(horizontal, padding=4)
        horizontal.add(left, weight=2)
        ttk.Label(left, text="Sesiones y artefactos").pack(anchor="w")
        self.session_tree = ttk.Treeview(
            left, columns=("state", "kind"), show="tree headings", selectmode="browse"
        )
        self.session_tree.heading("#0", text="Sesión")
        self.session_tree.heading("state", text="Estado")
        self.session_tree.heading("kind", text="Tipo")
        self.session_tree.column("#0", width=170)
        self.session_tree.column("state", width=135)
        self.session_tree.column("kind", width=100)
        self.session_tree.pack(fill="both", expand=True)
        self.session_tree.bind("<<TreeviewSelect>>", self.inspect_session)
        ttk.Button(left, text="Actualizar", command=self.refresh_sessions).pack(
            fill="x", pady=(4, 0)
        )

        center = ttk.Frame(horizontal, padding=4)
        horizontal.add(center, weight=6)
        self.notebook = ttk.Notebook(center)
        self.notebook.pack(fill="both", expand=True)
        self._build_guided_tab()
        self._build_graph_tab()
        self._build_extension_tab()
        self._build_install_tab()
        if self.advanced is not None:
            self._build_constitution_tab()
            self._build_runtime_tab()
            self._build_response_modes_tab()
            self._build_kwandata_tab()
            self._build_workbench_tab()
            self._build_clipboard_tab()
            self._build_voice_permissions_tab()
            if self.tool_call is not None and self.tool_descriptors:
                self._build_orchestration_console_tab()

        right = ttk.Frame(horizontal, padding=4)
        horizontal.add(right, weight=3)
        ttk.Label(right, text="Inspector transparente").pack(anchor="w")
        self.inspector = tk.Text(right, wrap="word", font=("Cascadia Mono", 9), undo=False)
        self.inspector.pack(fill="both", expand=True)

        console_frame = ttk.Frame(vertical, padding=4)
        vertical.add(console_frame, weight=2)
        ttk.Label(console_frame, text="Consola de evidencia").pack(anchor="w")
        self.console = tk.Text(
            console_frame,
            height=7,
            wrap="word",
            font=("Cascadia Mono", 9),
            background="#101726",
            foreground="#d8e1f0",
        )
        self.console.pack(fill="both", expand=True)

    @staticmethod
    def _safe_tool_template(descriptor: dict[str, Any]) -> dict[str, Any]:
        schema = descriptor.get("inputSchema", {})
        required = set(schema.get("required", []))
        result: dict[str, Any] = {}
        for name, value in schema.get("properties", {}).items():
            if name not in required:
                continue
            if name == "consent":
                result[name] = "NO"
            elif "enum" in value:
                result[name] = value["enum"][0]
            elif value.get("type") == "object":
                result[name] = {}
            elif value.get("type") == "array":
                result[name] = []
            elif value.get("type") == "boolean":
                result[name] = False
            elif value.get("type") == "integer":
                result[name] = int(value.get("minimum", 1))
            elif value.get("type") == "number":
                result[name] = float(value.get("minimum", 0.0))
            elif isinstance(value.get("type"), list) and "null" in value["type"]:
                result[name] = None
            else:
                result[name] = ""
        return result

    @staticmethod
    def _tool_category(name: str) -> str:
        prefixes = (
            "constitution",
            "programmed_policy",
            "proactive",
            "risk",
            "recovery",
            "persistence",
            "kwandata",
            "permission",
            "scheduler",
            "clipboard",
            "audio",
            "voice",
            "account",
            "diction",
            "checkpoint",
            "construct",
            "universal",
            "mis",
            "rgg",
            "kwanprompts",
            "sco",
            "phl",
            "workbench",
            "studio",
            "extension",
            "isolated",
            "kch",
        )
        return next((prefix for prefix in prefixes if name.startswith(prefix)), "other").upper()

    def _build_orchestration_console_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="Orquesta completa")
        ttk.Label(
            tab,
            text="Superficie íntegra Python/MCP: cada función conserva su gate, límites de autoridad y consentimiento. Las mutaciones cargan NO por defecto.",
            wraplength=1050,
        ).pack(anchor="w", pady=(0, 6))
        filter_frame = ttk.Frame(tab)
        filter_frame.pack(fill="x")
        ttk.Label(filter_frame, text="Buscar").pack(side="left")
        self.tool_filter = tk.StringVar()
        entry = ttk.Entry(filter_frame, textvariable=self.tool_filter)
        entry.pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(filter_frame, text="Filtrar", command=self.refresh_tool_catalog).pack(
            side="left"
        )
        ttk.Button(
            filter_frame,
            text="Mostrar todo",
            command=lambda: (self.tool_filter.set(""), self.refresh_tool_catalog()),
        ).pack(side="left", padx=(4, 0))

        body = ttk.Panedwindow(tab, orient="horizontal")
        body.pack(fill="both", expand=True, pady=(6, 0))
        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=3)
        body.add(right, weight=5)
        self.tool_tree = ttk.Treeview(
            left, columns=("access", "title"), show="tree headings", selectmode="browse"
        )
        self.tool_tree.heading("#0", text="Función")
        self.tool_tree.heading("access", text="Gate")
        self.tool_tree.heading("title", text="Propósito")
        self.tool_tree.column("#0", width=230)
        self.tool_tree.column("access", width=80)
        self.tool_tree.column("title", width=260)
        self.tool_tree.pack(fill="both", expand=True)
        self.tool_tree.bind("<<TreeviewSelect>>", self.inspect_tool)

        self.tool_title = ttk.Label(
            right, text="Selecciona una función", font=("Segoe UI", 11, "bold"), wraplength=700
        )
        self.tool_title.pack(anchor="w")
        self.tool_description = ttk.Label(right, text="", wraplength=700, justify="left")
        self.tool_description.pack(anchor="w", pady=(3, 7))
        ttk.Label(right, text="Argumentos JSON editables (plantilla segura y completa)").pack(
            anchor="w"
        )
        self.tool_arguments = tk.Text(
            right, height=12, wrap="none", font=("Cascadia Mono", 9), undo=True
        )
        self.tool_arguments.pack(fill="both", expand=True)
        buttons = ttk.Frame(right)
        buttons.pack(fill="x", pady=5)
        ttk.Button(
            buttons, text="Restaurar plantilla segura", command=self.reset_tool_template
        ).pack(side="left")
        ttk.Button(
            buttons,
            text="Ejecutar función seleccionada",
            style="Accent.TButton",
            command=self.execute_selected_tool,
        ).pack(side="right")
        ttk.Label(right, text="Resultado / recibo").pack(anchor="w")
        self.tool_result = tk.Text(right, height=10, wrap="word", font=("Cascadia Mono", 9))
        self.tool_result.pack(fill="both", expand=True)
        self._tool_by_name = {item["name"]: item for item in self.tool_descriptors}
        self.refresh_tool_catalog()

    def refresh_tool_catalog(self) -> None:
        query = self.tool_filter.get().strip().lower()
        self.tool_tree.delete(*self.tool_tree.get_children())
        parents: dict[str, str] = {}
        for descriptor in sorted(
            self.tool_descriptors,
            key=lambda item: (self._tool_category(item["name"]), item["name"]),
        ):
            haystack = " ".join(
                (descriptor["name"], descriptor.get("title", ""), descriptor.get("description", ""))
            ).lower()
            if query and query not in haystack:
                continue
            category = self._tool_category(descriptor["name"])
            if category not in parents:
                parents[category] = self.tool_tree.insert(
                    "", "end", text=category, values=("", ""), open=True
                )
            access = "LECTURA" if descriptor.get("readOnly") else "MUTACIÓN"
            self.tool_tree.insert(
                parents[category],
                "end",
                iid=f"tool::{descriptor['name']}",
                text=descriptor["name"],
                values=(access, descriptor.get("title", "")),
            )

    def inspect_tool(self, _event: Any = None) -> None:
        selected = self.tool_tree.selection()
        if not selected or not selected[0].startswith("tool::"):
            return
        name = selected[0].split("::", 1)[1]
        descriptor = self._tool_by_name[name]
        gate = "Sólo lectura" if descriptor.get("readOnly") else "Mutación gobernada"
        self.tool_title.configure(text=f"{descriptor.get('title', name)} · {gate}")
        self.tool_description.configure(text=descriptor.get("description", ""))
        self.reset_tool_template()
        self.show_inspector(descriptor)

    def reset_tool_template(self) -> None:
        selected = self.tool_tree.selection()
        if not selected or not selected[0].startswith("tool::"):
            return
        descriptor = self._tool_by_name[selected[0].split("::", 1)[1]]
        self.tool_arguments.delete("1.0", "end")
        self.tool_arguments.insert(
            "1.0", json.dumps(self._safe_tool_template(descriptor), ensure_ascii=False, indent=2)
        )

    def execute_selected_tool(self) -> None:
        selected = self.tool_tree.selection()
        if not selected or not selected[0].startswith("tool::"):
            messagebox.showinfo(
                "Orquesta completa", "Selecciona una función concreta.", parent=self
            )
            return
        name = selected[0].split("::", 1)[1]
        try:
            arguments = json.loads(self.tool_arguments.get("1.0", "end"))
            if not isinstance(arguments, dict):
                raise ValueError("los argumentos deben ser un objeto JSON")
            result = (
                self.tool_call(name, arguments)
                if self.tool_call is not None
                else {"state": "NO_TOOL_CALLER"}
            )
            self.tool_result.delete("1.0", "end")
            self.tool_result.insert(
                "1.0", json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)
            )
            self.log(f"Función orquestada: {name}", result)
        except Exception as exc:
            self.tool_result.delete("1.0", "end")
            self.tool_result.insert(
                "1.0", json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2)
            )
            self.log(f"Función fallida: {name}", {"error": str(exc)})

    def _build_guided_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Editor CSI guiado")
        fields = [
            ("Modo", "mode", "GUIDED_COMPLETE"),
            ("Nombre", "name", ""),
            ("Tipo", "kind", ArtifactKind.SKILL.value),
            ("Objetivo", "objective", ""),
            ("Jurisdicción", "jurisdiction", "KCH_PREINSTALL_STAGING_ONLY"),
            ("Entradas (coma)", "inputs", "request"),
            ("Salidas (coma)", "outputs", "receipt"),
            ("Autoridad máxima", "authority", AUTHORITY_DEFAULT),
        ]
        self.form_vars: dict[str, tk.StringVar] = {}
        for row, (label, key, default) in enumerate(fields):
            ttk.Label(tab, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
            variable = tk.StringVar(value=default)
            self.form_vars[key] = variable
            if key == "kind":
                widget = ttk.Combobox(
                    tab,
                    textvariable=variable,
                    values=[kind.value for kind in ArtifactKind],
                    state="readonly",
                )
            elif key == "mode":
                widget = ttk.Combobox(
                    tab,
                    textvariable=variable,
                    values=["GUIDED_COMPLETE", "ASSISTED", "EXPERT"],
                    state="readonly",
                )
            else:
                widget = ttk.Entry(tab, textvariable=variable)
            widget.grid(row=row, column=1, sticky="ew", pady=3)
        ttk.Label(tab, text="Metadatos JSON específicos del tipo").grid(
            row=len(fields), column=0, sticky="nw", pady=3
        )
        self.metadata_text = tk.Text(tab, height=9, font=("Cascadia Mono", 9))
        self.metadata_text.insert(
            "1.0",
            '{\n  "instructions": ["Inspeccionar la solicitud", "Validar la evidencia", "Emitir un recibo acotado"]\n}',
        )
        self.metadata_text.grid(row=len(fields), column=1, sticky="nsew", pady=3)
        buttons = ttk.Frame(tab)
        buttons.grid(row=len(fields) + 1, column=1, sticky="ew", pady=8)
        ttk.Button(buttons, text="Previsualizar especificación", command=self.preview_spec).pack(
            side="left"
        )
        ttk.Button(
            buttons,
            text="Generar · validar · sellar candidato",
            style="Accent.TButton",
            command=self.build_candidate,
        ).pack(side="right")
        tab.columnconfigure(1, weight=1)
        tab.rowconfigure(len(fields), weight=1)

    def _build_graph_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="Grafo de gobierno")
        self.graph_canvas = tk.Canvas(tab, background="#f5f7fb", highlightthickness=0)
        self.graph_canvas.pack(fill="both", expand=True)
        self.graph_canvas.bind("<Configure>", lambda _event: self.draw_governance_graph())

    def _build_extension_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="Extension Fabric")
        controls = ttk.Frame(tab)
        controls.pack(fill="x")
        self.provider_var = tk.StringVar(value="mcp-registry")
        ttk.Combobox(
            controls,
            textvariable=self.provider_var,
            values=sorted(self.fabric.providers),
            state="readonly",
            width=18,
        ).pack(side="left")
        self.query_var = tk.StringVar(value="filesystem")
        ttk.Entry(controls, textvariable=self.query_var).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(controls, text="Buscar", command=self.search_extensions).pack(side="left")
        ttk.Button(controls, text="Inventario local", command=self.show_inventory).pack(
            side="left", padx=(6, 0)
        )
        self.extension_tree = ttk.Treeview(
            tab, columns=("provider", "version", "decision"), show="tree headings"
        )
        self.extension_tree.heading("#0", text="Identificador")
        self.extension_tree.heading("provider", text="Fuente")
        self.extension_tree.heading("version", text="Versión")
        self.extension_tree.heading("decision", text="Adjudicación")
        self.extension_tree.pack(fill="both", expand=True, pady=(8, 0))
        self.extension_tree.bind("<<TreeviewSelect>>", self.inspect_extension)
        self.extension_records: dict[str, dict[str, Any]] = {}

    def _build_install_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Instalación aislada")
        ttk.Label(
            tab,
            text="Sólo perfiles desechables internos. Generar ≠ validar ≠ sellar ≠ instalar ≠ habilitar.",
            wraplength=700,
        ).pack(anchor="w")
        ttk.Button(
            tab, text="Planificar artefacto seleccionado", command=self.plan_selected_install
        ).pack(anchor="w", pady=8)
        self.install_text = tk.Text(tab, wrap="word", font=("Cascadia Mono", 9))
        self.install_text.pack(fill="both", expand=True)
        self.pending_plan = None
        self.pending_session: dict[str, Any] | None = None
        ttk.Button(
            tab, text="Ejecutar plan con consentimiento", command=self.execute_pending_install
        ).pack(anchor="e", pady=(8, 0))

    def _build_constitution_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="Constitución CSI")
        ttk.Label(
            tab,
            text="Gobierno inviolable por el modelo. Sólo una acción explícita del usuario promulga o modifica cajas.",
            wraplength=880,
        ).pack(anchor="w")
        body = ttk.Panedwindow(tab, orient="horizontal")
        body.pack(fill="both", expand=True, pady=(8, 0))
        left = ttk.Frame(body)
        body.add(left, weight=2)
        self.constitution_tree = ttk.Treeview(left, columns=("rank", "plane"), show="tree headings")
        self.constitution_tree.heading("#0", text="Caja constitucional")
        self.constitution_tree.heading("rank", text="Rango")
        self.constitution_tree.heading("plane", text="Plano")
        self.constitution_tree.pack(fill="both", expand=True)
        self.constitution_tree.bind("<<TreeviewSelect>>", self.select_constitution_box)
        actions = ttk.Frame(left)
        actions.pack(fill="x", pady=(5, 0))
        ttk.Button(actions, text="Nueva caja", command=self.add_constitution_box).pack(side="left")
        ttk.Button(actions, text="Actualizar", command=self.refresh_constitution).pack(side="right")
        right = ttk.Frame(body)
        body.add(right, weight=5)
        ttk.Label(right, text="Contenido — cada edición queda custodiada automáticamente").pack(
            anchor="w"
        )
        self.constitution_editor = tk.Text(right, wrap="word", undo=True, font=("Segoe UI", 11))
        self.constitution_editor.pack(fill="both", expand=True)
        self.constitution_editor.bind("<KeyRelease>", self.autosave_constitution_box)
        self._loading_constitution = False
        self.refresh_constitution()

    def refresh_constitution(self) -> None:
        if self.advanced is None:
            return
        state = self.advanced.constitution.state()
        self.constitution_tree.delete(*self.constitution_tree.get_children())
        by_parent: dict[str | None, list[dict[str, Any]]] = {}
        for box in state["boxes"]:
            by_parent.setdefault(box.get("parent_box_id"), []).append(box)

        def add(parent: str, parent_id: str | None) -> None:
            for box in sorted(
                by_parent.get(parent_id, []), key=lambda item: (item["rank"], item["box_id"])
            ):
                label = box["content"].replace("\n", " ")[:54] or "[caja vacía]"
                self.constitution_tree.insert(
                    parent,
                    "end",
                    iid=box["box_id"],
                    text=label,
                    values=(box["rank"], box["plane_id"]),
                    open=True,
                )
                add(box["box_id"], box["box_id"])

        add("", None)

    def select_constitution_box(self, _event: Any = None) -> None:
        if self.advanced is None or not self.constitution_tree.selection():
            return
        box_id = self.constitution_tree.selection()[0]
        box = next(
            item for item in self.advanced.constitution.state()["boxes"] if item["box_id"] == box_id
        )
        self._loading_constitution = True
        self.constitution_editor.delete("1.0", "end")
        self.constitution_editor.insert("1.0", box["content"])
        self._loading_constitution = False

    def autosave_constitution_box(self, _event: Any = None) -> None:
        if (
            self.advanced is None
            or self._loading_constitution
            or not self.constitution_tree.selection()
        ):
            return
        box_id = self.constitution_tree.selection()[0]
        content = self.constitution_editor.get("1.0", "end-1c")
        observed = next(
            item["content"]
            for item in self.advanced.constitution.state()["boxes"]
            if item["box_id"] == box_id
        )
        if content == observed:
            return
        receipt = self.advanced.constitution.update_box(box_id, content, actor=Actor.USER)
        self.advanced.launcher.publish(
            {
                "type": "box.edited",
                "authority": "USER",
                "box_id": box_id,
                "revision": receipt["state"]["revision"],
            }
        )
        self.constitution_tree.item(box_id, text=content.replace("\n", " ")[:54] or "[caja vacía]")

    def add_constitution_box(self) -> None:
        if self.advanced is None:
            return
        parent = (
            self.constitution_tree.selection()[0] if self.constitution_tree.selection() else None
        )
        result = self.advanced.constitution.add_box(parent_box_id=parent, actor=Actor.USER)
        self.refresh_constitution()
        self.constitution_tree.selection_set(result["box_id"])
        self.select_constitution_box()
        self.constitution_editor.focus_set()

    def _build_runtime_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="Runtime y modos")
        controls = ttk.Frame(tab)
        controls.pack(fill="x")
        self.policy_enabled = tk.BooleanVar()
        self.policy_announce = tk.BooleanVar()
        ttk.Checkbutton(
            controls,
            text="Programador/lanzador proactivo activo",
            variable=self.policy_enabled,
            command=self.save_policy_preferences,
        ).pack(side="left")
        ttk.Checkbutton(
            controls,
            text="Aviso en cada arranque",
            variable=self.policy_announce,
            command=self.save_policy_preferences,
        ).pack(side="left", padx=12)
        ttk.Button(controls, text="Actualizar estado", command=self.refresh_runtime).pack(
            side="right"
        )
        checkpoint = ttk.Frame(tab)
        checkpoint.pack(fill="x", pady=8)
        ttk.Button(checkpoint, text="Estimar checkpoint", command=self.estimate_checkpoint).pack(
            side="left"
        )
        ttk.Button(
            checkpoint,
            text="Crear persistencia estructurada",
            command=self.create_structured_checkpoint,
        ).pack(side="left", padx=6)
        ttk.Button(checkpoint, text="Checkpoint full…", command=self.create_full_checkpoint).pack(
            side="left"
        )
        ttk.Label(
            checkpoint, text="Checkpoint full: sólo tras aviso de tamaño y confirmación explícita."
        ).pack(side="left", padx=10)
        construct = ttk.LabelFrame(tab, text="CONSTRUCT — sucesor versionado", padding=5)
        construct.pack(fill="x", pady=(0, 8))
        self.construct_session_id: str | None = None
        ttk.Button(construct, text="Iniciar", command=self.start_construct).pack(side="left")
        ttk.Button(construct, text="Editar candidato", command=self.open_construct_editor).pack(
            side="left", padx=4
        )
        ttk.Button(construct, text="Validar", command=self.validate_construct).pack(side="left")
        ttk.Button(
            construct, text="Promover próximo arranque", command=self.promote_construct
        ).pack(side="left", padx=4)
        ttk.Button(construct, text="Rollback puntero", command=self.rollback_construct).pack(
            side="left"
        )
        self.construct_label = ttk.Label(construct, text="sin sesión activa")
        self.construct_label.pack(side="right")
        self.runtime_text = tk.Text(tab, wrap="word", font=("Cascadia Mono", 9))
        self.runtime_text.pack(fill="both", expand=True)
        self.refresh_runtime()

    def refresh_runtime(self) -> None:
        if self.advanced is None:
            return
        state = self.advanced.policy.state()
        self.policy_enabled.set(state["enabled"])
        self.policy_announce.set(state["announce_on_session_start"])
        self.runtime_text.delete("1.0", "end")
        self.runtime_text.insert(
            "1.0", json.dumps(self.advanced.status(), ensure_ascii=False, sort_keys=True, indent=2)
        )

    def save_policy_preferences(self) -> None:
        if self.advanced is None:
            return
        self.advanced.policy.set_preferences(
            enabled=self.policy_enabled.get(),
            announce_on_session_start=self.policy_announce.get(),
            actor=Actor.USER,
        )
        self.log("Preferencias proactivas promulgadas por el usuario y versionadas.")

    def _build_response_modes_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="Modos de respuesta")
        ttk.Label(
            tab,
            text=(
                "Controla sólo la contestación redactada del chat. Los outputs no se recortan "
                "ni consumen el presupuesto visual. La ficha técnica se guarda en Markdown y "
                "no se ofrece: únicamente se informa su ruta en una línea final."
            ),
            wraplength=1150,
            justify="left",
        ).pack(fill="x", pady=(0, 8))

        binding = ttk.LabelFrame(tab, text="Perfil efectivo por alcance", padding=6)
        binding.pack(fill="x")
        self.response_scope_type = tk.StringVar(value="GLOBAL")
        self.response_scope_key = tk.StringVar(value="*")
        self.response_profile_id = tk.StringVar(value="builtin.explicativo")
        ttk.Label(binding, text="Alcance").grid(row=0, column=0, sticky="w")
        scope_combo = ttk.Combobox(
            binding,
            textvariable=self.response_scope_type,
            values=list(SCOPE_ORDER),
            state="readonly",
            width=14,
        )
        scope_combo.grid(row=0, column=1, sticky="ew", padx=4)
        scope_combo.bind("<<ComboboxSelected>>", lambda _e: self._response_scope_changed())
        ttk.Label(binding, text="Clave exacta").grid(row=0, column=2, sticky="w")
        ttk.Entry(binding, textvariable=self.response_scope_key, width=30).grid(
            row=0, column=3, sticky="ew", padx=4
        )
        ttk.Label(binding, text="Perfil").grid(row=0, column=4, sticky="w")
        self.response_profile_combo = ttk.Combobox(
            binding, textvariable=self.response_profile_id, state="readonly", width=28
        )
        self.response_profile_combo.grid(row=0, column=5, sticky="ew", padx=4)
        ttk.Button(binding, text="Vincular", command=self.bind_response_mode).grid(
            row=0, column=6, padx=3
        )
        ttk.Button(binding, text="Heredar", command=self.clear_response_mode_scope).grid(
            row=0, column=7, padx=3
        )
        ttk.Button(binding, text="Resolver", command=self.resolve_response_mode).grid(
            row=0, column=8, padx=3
        )
        binding.columnconfigure(3, weight=1)
        binding.columnconfigure(5, weight=1)

        editor = ttk.LabelFrame(tab, text="Perfil custom persistente", padding=6)
        editor.pack(fill="both", expand=True, pady=8)
        form = ttk.Frame(editor)
        form.pack(fill="x")
        self.response_custom_id = tk.StringVar(value="custom.mi-perfil")
        self.response_custom_name = tk.StringVar(value="Mi perfil")
        self.response_custom_base = tk.StringVar(value="builtin.explicativo")
        for column, (label, variable) in enumerate(
            (
                ("ID custom", self.response_custom_id),
                ("Nombre", self.response_custom_name),
                ("Base", self.response_custom_base),
            )
        ):
            ttk.Label(form, text=label).grid(row=0, column=column * 2, sticky="w")
            if label == "Base":
                self.response_base_combo = ttk.Combobox(
                    form, textvariable=variable, state="readonly", width=28
                )
                widget: tk.Widget = self.response_base_combo
            else:
                widget = ttk.Entry(form, textvariable=variable, width=30)
            widget.grid(row=0, column=column * 2 + 1, sticky="ew", padx=(4, 10))
            form.columnconfigure(column * 2 + 1, weight=1)
        ttk.Label(editor, text="Overrides JSON — campos no indicados se heredan de la base").pack(
            anchor="w", pady=(7, 2)
        )
        self.response_custom_config = tk.Text(
            editor, height=12, wrap="none", undo=True, font=("Cascadia Mono", 9)
        )
        self.response_custom_config.pack(fill="both", expand=True)
        self.response_custom_config.insert("1.0", "{}")
        buttons = ttk.Frame(editor)
        buttons.pack(fill="x", pady=(5, 0))
        ttk.Button(buttons, text="Guardar perfil", command=self.save_custom_response_profile).pack(
            side="left"
        )
        ttk.Button(buttons, text="Cargar seleccionado", command=self.load_response_profile).pack(
            side="left", padx=4
        )
        ttk.Button(buttons, text="Archivar custom", command=self.archive_response_profile).pack(
            side="left"
        )
        ttk.Button(buttons, text="Actualizar", command=self.refresh_response_modes).pack(
            side="right"
        )
        self.response_mode_result = tk.Text(tab, height=10, wrap="word", font=("Cascadia Mono", 9))
        self.response_mode_result.pack(fill="both", expand=True)
        self.refresh_response_modes()

    def _response_scope_changed(self) -> None:
        if self.response_scope_type.get() == "GLOBAL":
            self.response_scope_key.set("*")
        elif self.response_scope_key.get() == "*":
            self.response_scope_key.set("")

    def _response_context(self) -> dict[str, str]:
        scope_type = self.response_scope_type.get()
        if scope_type == "GLOBAL":
            return {}
        key = self.response_scope_key.get().strip()
        if not key:
            raise ValueError("La clave exacta del alcance es obligatoria.")
        return {SCOPE_CONTEXT_KEYS[scope_type]: key}

    def refresh_response_modes(self) -> None:
        if self.advanced is None:
            return
        profiles = self.advanced.response_modes.profiles()
        identifiers = [item["profile_id"] for item in profiles]
        self.response_profile_combo.configure(values=identifiers)
        self.response_base_combo.configure(values=identifiers)
        if self.response_profile_id.get() not in identifiers:
            self.response_profile_id.set("builtin.explicativo")
        if self.response_custom_base.get() not in identifiers:
            self.response_custom_base.set("builtin.explicativo")
        self.resolve_response_mode()

    def resolve_response_mode(self) -> None:
        if self.advanced is None:
            return
        try:
            value = self.advanced.response_modes.compile_contract(self._response_context())
        except Exception as exc:
            messagebox.showerror("Modos de respuesta", str(exc), parent=self)
            return
        self.response_profile_id.set(value["resolution"]["profile"]["profile_id"])
        self.response_mode_result.delete("1.0", "end")
        self.response_mode_result.insert(
            "1.0", json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
        )

    def bind_response_mode(self) -> None:
        if self.advanced is None:
            return
        try:
            value = self.advanced.response_modes.set_scope(
                self.response_scope_type.get(),
                self.response_scope_key.get(),
                self.response_profile_id.get(),
            )
        except Exception as exc:
            messagebox.showerror("Modos de respuesta", str(exc), parent=self)
            return
        self.log("Perfil de respuesta vinculado por el usuario.", value)
        self.resolve_response_mode()

    def clear_response_mode_scope(self) -> None:
        if self.advanced is None:
            return
        try:
            value = self.advanced.response_modes.clear_scope(
                self.response_scope_type.get(), self.response_scope_key.get()
            )
        except Exception as exc:
            messagebox.showerror("Modos de respuesta", str(exc), parent=self)
            return
        self.log("Vínculo de respuesta eliminado; vuelve a regir la herencia.", value)
        self.resolve_response_mode()

    def save_custom_response_profile(self) -> None:
        if self.advanced is None:
            return
        try:
            overrides = json.loads(self.response_custom_config.get("1.0", "end"))
            value = self.advanced.response_modes.upsert_profile(
                {
                    "profile_id": self.response_custom_id.get(),
                    "name": self.response_custom_name.get(),
                    "base_profile_id": self.response_custom_base.get(),
                    "config": overrides,
                }
            )
        except Exception as exc:
            messagebox.showerror("Perfil custom", str(exc), parent=self)
            return
        self.response_profile_id.set(value["profile"]["profile_id"])
        self.log("Perfil custom de respuesta guardado y versionado.", value)
        self.refresh_response_modes()

    def load_response_profile(self) -> None:
        if self.advanced is None:
            return
        profile_id = self.response_profile_id.get()
        profile = next(
            item for item in self.advanced.response_modes.profiles() if item["profile_id"] == profile_id
        )
        if profile["built_in"]:
            self.response_custom_id.set("custom." + profile_id.split(".", 1)[1])
            self.response_custom_name.set(profile["name"] + " custom")
            self.response_custom_base.set(profile_id)
            config: dict[str, Any] = {}
        else:
            self.response_custom_id.set(profile_id)
            self.response_custom_name.set(profile["name"])
            self.response_custom_base.set(profile["base_profile_id"] or "builtin.explicativo")
            config = profile["config"]
        self.response_custom_config.delete("1.0", "end")
        self.response_custom_config.insert(
            "1.0", json.dumps(config, ensure_ascii=False, sort_keys=True, indent=2)
        )

    def archive_response_profile(self) -> None:
        if self.advanced is None:
            return
        try:
            value = self.advanced.response_modes.archive_profile(self.response_profile_id.get())
        except Exception as exc:
            messagebox.showerror("Archivar perfil", str(exc), parent=self)
            return
        self.log("Perfil custom archivado sin borrar su trazabilidad.", value)
        self.response_profile_id.set("builtin.explicativo")
        self.refresh_response_modes()

    def estimate_checkpoint(self) -> None:
        if self.advanced is None:
            return
        value = self.advanced.checkpoints.estimate()
        self.show_inspector(value)
        self.log("Estimación de checkpoint: no se creó ningún archivo full.", value)

    def create_structured_checkpoint(self) -> None:
        if self.advanced is None:
            return
        label = (
            simpledialog.askstring(
                "Persistencia estructurada", "Etiqueta del checkpoint:", parent=self
            )
            or "checkpoint-ui"
        )
        value = self.advanced.checkpoints.create_structured(label, actor=Actor.USER)
        self.show_inspector(value)
        self.log("Checkpoint estructurado deduplicado creado.", value)

    def create_full_checkpoint(self) -> None:
        if self.advanced is None:
            return
        label = (
            simpledialog.askstring("Checkpoint full", "Etiqueta del checkpoint full:", parent=self)
            or "full-ui"
        )
        plan = self.advanced.checkpoints.full_plan(label)
        warning = (
            f"Este checkpoint puede ocupar una barbaridad de disco.\n\n"
            f"Archivos: {plan['file_count']}\nBytes lógicos actuales: {plan['logical_bytes']:,}\n"
            f"Peor caso estimado: {plan['full_checkpoint_worst_case_bytes']:,} bytes\n\n"
            "¿Confirmas expresamente su creación ahora?"
        )
        confirmed = messagebox.askyesno("Confirmación de checkpoint full", warning, parent=self)
        value = self.advanced.checkpoints.create_full(
            plan["plan_id"], confirm_large_checkpoint=confirmed, actor=Actor.USER
        )
        self.show_inspector(value)
        self.log("Resultado del checkpoint full.", value)

    def start_construct(self) -> None:
        if self.advanced is None:
            return
        objective = simpledialog.askstring(
            "CONSTRUCT", "Objetivo de la nueva versión sucesora:", parent=self
        )
        if not objective:
            return
        value = self.advanced.construct.start(objective, actor=Actor.USER)
        self.construct_session_id = value["session_id"]
        self.construct_label.configure(text=self.construct_session_id[-16:])
        self.show_inspector(value)
        self.log(
            "CONSTRUCT iniciado con backup exacto de la estable; runtime activo intacto.", value
        )

    def open_construct_editor(self) -> None:
        if self.advanced is None or self.construct_session_id is None:
            messagebox.showinfo("CONSTRUCT", "Primero inicia una sesión CONSTRUCT.", parent=self)
            return
        dialog = tk.Toplevel(self)
        dialog.title("Editor de candidato CONSTRUCT")
        dialog.geometry("900x650")
        dialog.transient(self.winfo_toplevel())
        frame = ttk.Frame(dialog, padding=8)
        frame.pack(fill="both", expand=True)
        path_var = tk.StringVar(value="")
        ttk.Label(frame, text="Ruta relativa dentro del candidato").pack(anchor="w")
        ttk.Entry(frame, textvariable=path_var).pack(fill="x", pady=(0, 6))
        editor = tk.Text(frame, wrap="none", undo=True, font=("Cascadia Mono", 10))
        editor.pack(fill="both", expand=True)

        def save() -> None:
            try:
                proposal = {
                    "writes_files": True,
                    "path": path_var.get(),
                    "construct_session": self.construct_session_id,
                }
                advice = self.advanced.risk.assess(proposal)
                value = self.advanced.construct.write_file(
                    self.construct_session_id,
                    path_var.get(),
                    editor.get("1.0", "end-1c"),
                    actor=Actor.USER,
                )
                self.log(
                    "Archivo escrito sólo en el candidato CONSTRUCT.",
                    {"risk_advice": advice, "write": value},
                )
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("CONSTRUCT", str(exc), parent=dialog)

        ttk.Button(frame, text="Guardar en candidato con preimagen", command=save).pack(
            anchor="e", pady=(6, 0)
        )

    def validate_construct(self) -> None:
        if self.advanced is None or self.construct_session_id is None:
            messagebox.showinfo("CONSTRUCT", "No hay sesión CONSTRUCT activa.", parent=self)
            return
        value = self.advanced.construct.validate(self.construct_session_id, actor=Actor.USER)
        self.show_inspector(value)
        self.log("Gate del candidato CONSTRUCT ejecutado.", value)

    def promote_construct(self) -> None:
        if self.advanced is None or self.construct_session_id is None:
            messagebox.showinfo("CONSTRUCT", "No hay sesión CONSTRUCT activa.", parent=self)
            return
        if not messagebox.askyesno(
            "Promoción CONSTRUCT",
            "¿Promover este candidato validado sólo para el próximo arranque?",
            parent=self,
        ):
            return
        value = self.advanced.construct.promote_for_next_start(
            self.construct_session_id, actor=Actor.USER
        )
        self.show_inspector(value)
        self.log("Sucesor promovido para el próximo arranque; runtime actual intacto.", value)

    def rollback_construct(self) -> None:
        if self.advanced is None:
            return
        value = self.advanced.construct.rollback_pointer(actor=Actor.USER)
        self.show_inspector(value)
        self.log("Puntero del próximo arranque revertido.", value)

    def _build_kwandata_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="KwanData")
        ingest = ttk.Frame(tab)
        ingest.pack(fill="x")
        self.kwandata_source = tk.StringVar()
        ttk.Entry(ingest, textvariable=self.kwandata_source).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(ingest, text="Elegir fuente", command=self.choose_kwandata_source).pack(
            side="left", padx=5
        )
        ttk.Button(ingest, text="Estructurar", command=self.ingest_kwandata).pack(side="left")
        query = ttk.Frame(tab)
        query.pack(fill="x", pady=8)
        self.kwandata_query_var = tk.StringVar()
        ttk.Entry(query, textvariable=self.kwandata_query_var).pack(
            side="left", fill="x", expand=True
        )
        ttk.Button(query, text="Consultar", command=self.query_kwandata).pack(
            side="left", padx=(5, 0)
        )
        self.kwandata_text = tk.Text(tab, wrap="word", font=("Cascadia Mono", 9))
        self.kwandata_text.pack(fill="both", expand=True)

    def choose_kwandata_source(self) -> None:
        path = filedialog.askopenfilename(parent=self)
        if path:
            self.kwandata_source.set(path)

    def ingest_kwandata(self) -> None:
        if self.advanced is None:
            return
        try:
            value = self.advanced.kwandata.ingest(self.kwandata_source.get())
            self.kwandata_text.delete("1.0", "end")
            self.kwandata_text.insert("1.0", json.dumps(value, ensure_ascii=False, indent=2))
            self.log("Fuente incorporada a KwanData con custodia exacta.", value)
        except Exception as exc:
            messagebox.showerror("KwanData", str(exc), parent=self)

    def query_kwandata(self) -> None:
        if self.advanced is None:
            return
        value = self.advanced.kwandata.query(self.kwandata_query_var.get())
        self.kwandata_text.delete("1.0", "end")
        self.kwandata_text.insert("1.0", json.dumps(value, ensure_ascii=False, indent=2))

    def _build_workbench_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="Trabajo y aprendizaje")
        ttk.Label(
            tab,
            text=(
                "Archivo superficial, aprendizaje trazable y continuidad: conserva crudo + "
                "normalizado, genera protocolos fechados y skills en STAGED_UNEVALUATED, y "
                "nunca instala, activa ni copia secretos automáticamente."
            ),
            wraplength=1050,
            justify="left",
        ).pack(anchor="w")

        controls = ttk.Frame(tab)
        controls.pack(fill="x", pady=6)
        self.workbench_status_label = ttk.Label(controls, text="Estado: cargando…")
        self.workbench_status_label.pack(side="left", fill="x", expand=True)
        ttk.Button(controls, text="Actualizar", command=self.refresh_workbench).pack(side="right")
        ttk.Button(
            controls, text="Mantenimiento ahora", command=self.run_workbench_maintenance
        ).pack(side="right", padx=5)

        capture = ttk.LabelFrame(tab, text="Incorporar trabajo exacto", padding=5)
        capture.pack(fill="x")
        self.workbench_capture = tk.Text(capture, height=4, wrap="word", undo=True)
        self.workbench_capture.pack(fill="x", expand=True)
        capture_buttons = ttk.Frame(capture)
        capture_buttons.pack(fill="x", pady=(4, 0))
        ttk.Button(capture_buttons, text="Guardar texto", command=self.ingest_workbench_text).pack(
            side="left"
        )
        ttk.Button(
            capture_buttons, text="Importar archivo", command=self.ingest_workbench_file
        ).pack(side="left", padx=5)
        ttk.Button(capture_buttons, text="Nuevo grupo", command=self.create_workbench_group).pack(
            side="right"
        )

        body = ttk.Panedwindow(tab, orient="horizontal")
        body.pack(fill="both", expand=True, pady=(6, 0))
        archive_frame = ttk.LabelFrame(body, text="Grupos y subgrupos", padding=4)
        graph_frame = ttk.LabelFrame(
            body, text="Grafo multidimensional · clic para abrir", padding=4
        )
        artifact_frame = ttk.LabelFrame(body, text="Aprendizajes y artefactos", padding=4)
        body.add(archive_frame, weight=2)
        body.add(graph_frame, weight=5)
        body.add(artifact_frame, weight=3)

        self.workbench_archive_tree = ttk.Treeview(
            archive_frame, columns=("kind", "rank"), show="tree headings", selectmode="browse"
        )
        self.workbench_archive_tree.heading("#0", text="Grupo / miembro")
        self.workbench_archive_tree.heading("kind", text="Tipo")
        self.workbench_archive_tree.heading("rank", text="Rango")
        self.workbench_archive_tree.column("#0", width=190)
        self.workbench_archive_tree.column("kind", width=90)
        self.workbench_archive_tree.column("rank", width=45)
        self.workbench_archive_tree.pack(fill="both", expand=True)
        self.workbench_archive_tree.bind("<<TreeviewSelect>>", self.inspect_workbench_tree)

        self.workbench_graph_canvas = tk.Canvas(
            graph_frame, background="#f5f7fb", highlightthickness=0
        )
        self.workbench_graph_canvas.pack(fill="both", expand=True)
        self.workbench_graph_canvas.bind("<Configure>", lambda _event: self.draw_workbench_graph())

        self.workbench_artifact_tree = ttk.Treeview(
            artifact_frame, columns=("state",), show="tree headings", selectmode="browse"
        )
        self.workbench_artifact_tree.heading("#0", text="Elemento")
        self.workbench_artifact_tree.heading("state", text="Estado")
        self.workbench_artifact_tree.column("#0", width=220)
        self.workbench_artifact_tree.column("state", width=135)
        self.workbench_artifact_tree.pack(fill="both", expand=True)
        self.workbench_artifact_tree.bind("<<TreeviewSelect>>", self.inspect_workbench_tree)
        self._workbench_graph_cache: dict[str, Any] = {"nodes": [], "edges": []}
        self.after_idle(self.refresh_workbench)

    def _workbench_call(self, name: str, arguments: dict[str, Any]) -> Any:
        if self.tool_call is not None:
            value = self.tool_call(name, arguments)
            if isinstance(value, dict) and "structuredContent" in value:
                return value["structuredContent"]
            return value
        if self.advanced is None:
            raise RuntimeError("workbench runtime unavailable")
        return self.advanced.handlers[name](arguments)

    def refresh_workbench(self) -> None:
        if self.advanced is None:
            return
        status = self._workbench_call("workbench_status", {})
        tree = self._workbench_call("workbench_archive_tree", {})
        graph = self._workbench_call("workbench_graph", {})
        lessons = self._workbench_call("workbench_lessons_list", {})
        protocols = self._workbench_call("workbench_protocols_list", {})
        skills = self._workbench_call("workbench_skills_list", {})
        budget = status["budget"]["aggregate"]
        self.workbench_status_label.configure(
            text=(
                f"Fuentes {status['sources']} · aprendizajes {status['lessons']} · "
                f"protocolos {status['protocols']} · skills {status['skills']} · "
                f"presupuesto {budget['state']} / {budget['cadence_level']} · "
                f"integridad {status['integrity']['gate']}"
            )
        )

        self.workbench_archive_tree.delete(*self.workbench_archive_tree.get_children())
        groups = {item["group_id"]: item for item in tree["groups"]}
        pending = set(groups)
        while pending:
            progressed = False
            for group_id in sorted(pending, key=lambda value: (groups[value]["rank"], value)):
                group = groups[group_id]
                parent = group["parent_group_id"] or ""
                if parent and not self.workbench_archive_tree.exists(parent):
                    continue
                self.workbench_archive_tree.insert(
                    parent,
                    "end",
                    iid=group_id,
                    text=group["title"],
                    values=(group["group_kind"], group["rank"]),
                    open=not bool(group["archived"]),
                )
                pending.remove(group_id)
                progressed = True
                break
            if not progressed:
                break
        for member in tree["members"]:
            iid = f"member::{member['group_id']}::{member['item_type']}::{member['item_id']}"
            self.workbench_archive_tree.insert(
                member["group_id"],
                "end",
                iid=iid,
                text=member["item_id"],
                values=(member["item_type"], member["rank"]),
            )

        self.workbench_artifact_tree.delete(*self.workbench_artifact_tree.get_children())
        buckets = {}
        for label in ("LECCIONES", "PROTOCOLOS", "SKILLS"):
            buckets[label] = self.workbench_artifact_tree.insert(
                "", "end", text=label, values=("",), open=True
            )
        for item in lessons:
            self.workbench_artifact_tree.insert(
                buckets["LECCIONES"],
                "end",
                iid=f"node::{item['lesson_id']}",
                text=item["statement"][:72],
                values=(item["confidence_state"],),
            )
        for item in protocols:
            self.workbench_artifact_tree.insert(
                buckets["PROTOCOLOS"],
                "end",
                iid=f"node::{item['protocol_id']}",
                text=item["title"],
                values=(item["status"],),
            )
        for item in skills:
            self.workbench_artifact_tree.insert(
                buckets["SKILLS"],
                "end",
                iid=f"node::{item['skill_id']}",
                text=item["skill_name"],
                values=(item["status"],),
            )
        self._workbench_graph_cache = graph
        self.draw_workbench_graph()

    def draw_workbench_graph(self) -> None:
        canvas = getattr(self, "workbench_graph_canvas", None)
        if canvas is None:
            return
        canvas.delete("all")
        graph = self._workbench_graph_cache
        nodes = graph.get("nodes", [])[:90]
        if not nodes:
            canvas.create_text(
                max(canvas.winfo_width(), 500) / 2,
                120,
                text="El grafo aparecerá al incorporar fuentes, grupos y aprendizajes.",
                fill="#52627e",
            )
            return
        width = max(canvas.winfo_width(), 640)
        height = max(canvas.winfo_height(), 420)
        columns = {
            "GROUP": 0,
            "WORKSPACE": 0,
            "SESSION": 0,
            "SOURCE": 1,
            "LESSON": 2,
            "PROTOCOL": 3,
            "SKILL": 4,
        }
        grouped: dict[int, list[dict[str, Any]]] = {}
        for node in nodes:
            grouped.setdefault(columns.get(node["type"], 2), []).append(node)
        positions: dict[str, tuple[float, float]] = {}
        for column, values in grouped.items():
            x = 55 + column * max(115, (width - 110) / 4)
            spacing = max(34, (height - 50) / max(1, len(values)))
            for index, node in enumerate(values):
                positions[node["id"]] = (x, 30 + index * spacing)
        for edge in graph.get("edges", []):
            if edge["source"] in positions and edge["target"] in positions:
                x1, y1 = positions[edge["source"]]
                x2, y2 = positions[edge["target"]]
                canvas.create_line(x1, y1, x2, y2, fill="#9aa8bd", arrow="last")
        colors = {
            "GROUP": "#172033",
            "SOURCE": "#1f6f78",
            "LESSON": "#8b5e34",
            "PROTOCOL": "#5b4b8a",
            "SKILL": "#356b3f",
            "WORKSPACE": "#394b68",
            "SESSION": "#394b68",
        }
        for node in nodes:
            x, y = positions[node["id"]]
            tag = f"wbnode::{node['id']}"
            canvas.create_oval(
                x - 8,
                y - 8,
                x + 8,
                y + 8,
                fill=colors.get(node["type"], "#60708f"),
                outline="white",
                tags=(tag,),
            )
            canvas.create_text(
                x,
                y + 14,
                text=str(node["label"])[:24],
                width=100,
                fill="#27364e",
                font=("Segoe UI", 7),
                tags=(tag,),
            )
            canvas.tag_bind(
                tag, "<Button-1>", lambda _event, n=node["id"]: self.open_workbench_node(n)
            )
        if len(graph.get("nodes", [])) > len(nodes):
            canvas.create_text(
                width - 8,
                height - 8,
                anchor="se",
                text=f"Vista limitada a {len(nodes)} nodos; el grafo completo sigue accesible por herramienta.",
                fill="#7c4d22",
            )

    def open_workbench_node(self, node_id: str) -> None:
        self.show_inspector(
            self._workbench_call("workbench_graph_resolve_node", {"node_id": node_id})
        )

    def inspect_workbench_tree(self, event: Any = None) -> None:
        tree = event.widget if event is not None else None
        if tree is None:
            return
        selected = tree.selection()
        if not selected:
            return
        iid = selected[0]
        if iid.startswith("node::"):
            self.open_workbench_node(iid.split("::", 1)[1])
        elif iid.startswith("member::"):
            self.open_workbench_node(iid.rsplit("::", 1)[1])
        elif iid.startswith("GROUP-"):
            self.open_workbench_node(iid)

    def ingest_workbench_text(self) -> None:
        text = self.workbench_capture.get("1.0", "end-1c")
        if not text.strip():
            messagebox.showinfo(
                "Trabajo y aprendizaje", "La caja de texto está vacía.", parent=self
            )
            return
        title = simpledialog.askstring("Título", "Título de esta evidencia", parent=self)
        if not title:
            return
        value = self._workbench_call(
            "workbench_ingest",
            {
                "source_kind": "CHAT",
                "title": title,
                "raw_text": text,
                "provenance": {"capture_surface": "KCH_UI"},
                "consent": "YES",
            },
        )
        self.workbench_capture.delete("1.0", "end")
        self.log(
            "Trabajo incorporado; protocolos y skills sólo se preparan con evidencia suficiente.",
            value,
        )
        self.refresh_workbench()

    def ingest_workbench_file(self) -> None:
        path = filedialog.askopenfilename(parent=self)
        if not path:
            return
        value = self._workbench_call(
            "workbench_ingest",
            {
                "source_kind": "FILE",
                "title": Path(path).name,
                "source_path": path,
                "provenance": {"capture_surface": "KCH_UI_FILE_PICKER"},
                "consent": "YES",
            },
        )
        self.log("Archivo incorporado con capa cruda, normalizada y hash.", value)
        self.refresh_workbench()

    def create_workbench_group(self) -> None:
        title = simpledialog.askstring("Nuevo grupo", "Nombre del grupo", parent=self)
        if not title:
            return
        parent = simpledialog.askstring(
            "Grupo padre", "ID del grupo padre", initialvalue="GROUP-ROOT", parent=self
        )
        if not parent:
            return
        value = self._workbench_call(
            "workbench_archive_group_create",
            {
                "title": title,
                "group_kind": "USER_DEFINED",
                "parent_group_id": parent,
                "consent": "YES",
            },
        )
        self.log("Grupo archivístico creado sin fusionar ni borrar elementos.", value)
        self.refresh_workbench()

    def run_workbench_maintenance(self) -> None:
        value = self._workbench_call(
            "workbench_maintenance_run", {"trigger": "USER_UI", "force": True}
        )
        self.log("Mantenimiento de aprendizaje y continuidad completado.", value)
        self.refresh_workbench()

    def _build_clipboard_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="Superportapapeles")
        ttk.Label(
            tab,
            text="Historial local, post-its versionados y captura rectangular. Los secretos no se persisten automáticamente.",
        ).pack(anchor="w")
        self.clipboard_editor = tk.Text(tab, height=10, wrap="word")
        self.clipboard_editor.pack(fill="both", expand=True, pady=6)
        actions = ttk.Frame(tab)
        actions.pack(fill="x")
        ttk.Button(actions, text="Guardar clip de texto", command=self.capture_clip_text).pack(
            side="left"
        )
        ttk.Button(actions, text="Crear post-it", command=self.create_postit).pack(
            side="left", padx=5
        )
        ttk.Button(
            actions, text="Seleccionar rectángulo de pantalla", command=self.select_screen_region
        ).pack(side="left")
        ttk.Button(
            actions,
            text="Estado",
            command=lambda: self.show_inspector(
                self.advanced.clipboard.status() if self.advanced else {}
            ),
        ).pack(side="right")

    def capture_clip_text(self) -> None:
        if self.advanced is None:
            return
        value = self.advanced.clipboard.capture(
            self.clipboard_editor.get("1.0", "end-1c"),
            kind="TEXT",
            media_type="text/plain; charset=utf-8",
        )
        self.log("Clip capturado localmente.", value)

    def create_postit(self) -> None:
        if self.advanced is None:
            return
        value = self.advanced.clipboard.create_postit(
            body=self.clipboard_editor.get("1.0", "end-1c")
        )
        self.log("Post-it persistente y versionado creado.", value)

    def select_screen_region(self) -> None:
        if self.advanced is None:
            return

        def captured(bbox: tuple[int, int, int, int]) -> None:
            try:
                self.log(
                    "Región capturada como imagen y clip.",
                    self.advanced.clipboard.capture_region(bbox),
                )
            except Exception as exc:
                messagebox.showerror("Captura de pantalla", str(exc), parent=self)

        RegionSelector(self, captured)

    def _build_voice_permissions_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="Voz, permisos y cuentas")
        ttk.Label(
            tab,
            text="El micrófono nunca se activa durante la instalación ni al abrir KCH; requiere una acción explícita y mantiene indicador visible.",
            wraplength=900,
        ).pack(anchor="w")
        audio = ttk.Frame(tab)
        audio.pack(fill="x", pady=8)
        ttk.Button(audio, text="Importar audio y transcribir", command=self.import_audio).pack(
            side="left"
        )
        ttk.Button(audio, text="Iniciar monitor", command=self.start_audio_monitor).pack(
            side="left", padx=5
        )
        ttk.Button(audio, text="Detener monitor", command=self.stop_audio_monitor).pack(side="left")
        ttk.Button(audio, text="Estado de voz", command=self.refresh_voice_permissions).pack(
            side="right"
        )
        account = ttk.LabelFrame(tab, text="Permiso temporal de cuenta", padding=7)
        account.pack(fill="x")
        self.account_provider = tk.StringVar(value="GITHUB")
        self.account_scopes = tk.StringVar(value="repo:read")
        self.account_purpose = tk.StringVar(value="operación puntual autorizada")
        self.account_duration = tk.StringVar(value="PUNCTUAL")
        ttk.Combobox(
            account,
            textvariable=self.account_provider,
            values=["SSH", "GITHUB", "GOOGLE_DRIVE", "COLAB", "KAGGLE", "GENERIC_OAUTH"],
            state="readonly",
            width=18,
        ).grid(row=0, column=0, padx=3)
        ttk.Entry(account, textvariable=self.account_scopes, width=28).grid(row=0, column=1, padx=3)
        ttk.Entry(account, textvariable=self.account_purpose, width=42).grid(
            row=0, column=2, padx=3
        )
        ttk.Combobox(
            account,
            textvariable=self.account_duration,
            values=["PUNCTUAL", "DAILY", "WEEKLY", "MONTHLY", "QUARTERLY"],
            state="readonly",
            width=12,
        ).grid(row=0, column=3, padx=3)
        ttk.Button(
            account, text="Crear lease finito", command=self.request_account_permission
        ).grid(row=0, column=4, padx=3)
        scheduler = ttk.LabelFrame(tab, text="Agenda y scheduler", padding=7)
        scheduler.pack(fill="x", pady=(7, 0))
        self.schedule_name = tk.StringVar(value="Aviso KCH")
        self.schedule_kind = tk.StringVar(value="INTERVAL")
        self.schedule_expression = tk.StringVar(value="3600")
        self.schedule_event = tk.StringVar(value="user.reminder")
        ttk.Entry(scheduler, textvariable=self.schedule_name, width=24).grid(
            row=0, column=0, padx=3
        )
        ttk.Combobox(
            scheduler,
            textvariable=self.schedule_kind,
            values=["ONCE", "INTERVAL", "CRON"],
            state="readonly",
            width=10,
        ).grid(row=0, column=1, padx=3)
        ttk.Entry(scheduler, textvariable=self.schedule_expression, width=28).grid(
            row=0, column=2, padx=3
        )
        ttk.Entry(scheduler, textvariable=self.schedule_event, width=24).grid(
            row=0, column=3, padx=3
        )
        ttk.Button(scheduler, text="Programar", command=self.create_schedule).grid(
            row=0, column=4, padx=3
        )
        permission = ttk.LabelFrame(
            tab, text="Regla de permiso promulgada por el usuario", padding=7
        )
        permission.pack(fill="x", pady=(7, 0))
        self.permission_actor = tk.StringVar(value="MODEL")
        self.permission_resource = tk.StringVar(value="file://external/*")
        self.permission_operation = tk.StringVar(value="READ")
        self.permission_effect = tk.StringVar(value="ALLOW")
        ttk.Entry(permission, textvariable=self.permission_actor, width=16).grid(
            row=0, column=0, padx=3
        )
        ttk.Entry(permission, textvariable=self.permission_resource, width=38).grid(
            row=0, column=1, padx=3
        )
        ttk.Combobox(
            permission,
            textvariable=self.permission_operation,
            values=sorted(OPERATIONS),
            state="readonly",
            width=18,
        ).grid(row=0, column=2, padx=3)
        ttk.Combobox(
            permission,
            textvariable=self.permission_effect,
            values=["ALLOW", "DENY", "WARN"],
            state="readonly",
            width=9,
        ).grid(row=0, column=3, padx=3)
        ttk.Button(permission, text="Promulgar", command=self.grant_permission).grid(
            row=0, column=4, padx=3
        )
        self.voice_permissions_text = tk.Text(tab, wrap="word", font=("Cascadia Mono", 9))
        self.voice_permissions_text.pack(fill="both", expand=True, pady=(8, 0))
        self.refresh_voice_permissions()

    def import_audio(self) -> None:
        if self.advanced is None:
            return
        path = filedialog.askopenfilename(
            parent=self, filetypes=[("Audio", "*.wav *.mp3 *.m4a *.flac"), ("Todos", "*.*")]
        )
        if not path:
            return
        value = self.advanced.audio.ingest_and_transcribe(
            path, culture="es-ES", consent_basis="USER_SELECTED_AUDIO"
        )
        self.show_inspector(value)
        self.refresh_voice_permissions()

    def start_audio_monitor(self) -> None:
        if self.advanced is None:
            return
        if not messagebox.askyesno(
            "Monitor de audio",
            "¿Activar el micrófono local en modo brainstorming del usuario con indicador visible?",
            parent=self,
        ):
            return
        value = self.advanced.audio.start_monitor(
            mode="BRAINSTORM_USER_ONLY", consent_basis="USER_EXPLICIT_UI_ACTION", culture="es-ES"
        )
        self.log("Resultado de activación del monitor de audio.", value)
        self.refresh_voice_permissions()

    def stop_audio_monitor(self) -> None:
        if self.advanced is not None:
            self.advanced.audio.stop_monitor()
            self.refresh_voice_permissions()

    def request_account_permission(self) -> None:
        if self.advanced is None:
            return
        request = self.advanced.account_broker.request(
            provider=self.account_provider.get(),
            scopes=[item.strip() for item in self.account_scopes.get().split(",") if item.strip()],
            purpose=self.account_purpose.get(),
        )
        lease = self.advanced.account_broker.approve(
            request["request_id"], duration_class=self.account_duration.get()
        )
        value = {"request": request, "finite_lease": lease, "authentication_launched": False}
        self.show_inspector(value)
        self.log("Lease finito creado; la autenticación todavía no fue lanzada.", value)
        self.refresh_voice_permissions()

    def create_schedule(self) -> None:
        if self.advanced is None:
            return
        value = self.advanced.scheduler.create_schedule(
            name=self.schedule_name.get(),
            kind=self.schedule_kind.get(),
            expression=self.schedule_expression.get(),
            event={"type": self.schedule_event.get(), "authority": "USER_SCHEDULE"},
            created_by="USER",
        )
        self.show_inspector(value)
        self.log("Tarea programada persistente creada.", value)
        self.refresh_voice_permissions()

    def grant_permission(self) -> None:
        if self.advanced is None:
            return
        value = self.advanced.permissions.grant(
            actor_pattern=self.permission_actor.get(),
            resource_pattern=self.permission_resource.get(),
            operation_pattern=self.permission_operation.get(),
            effect=self.permission_effect.get(),
            priority=5000,
            rationale="Regla promulgada explícitamente desde la UI KCH",
            enacting_actor=Actor.USER,
        )
        self.show_inspector(value)
        self.log("Regla de permiso promulgada por el usuario.", value)
        self.refresh_voice_permissions()

    def refresh_voice_permissions(self) -> None:
        if self.advanced is None:
            return
        value = {
            "audio": self.advanced.audio.status(),
            "permissions": self.advanced.permissions.status(),
            "accounts": self.advanced.account_broker.status(),
        }
        self.voice_permissions_text.delete("1.0", "end")
        self.voice_permissions_text.insert(
            "1.0", json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
        )

    def log(self, message: str, evidence: Any | None = None) -> None:
        self.console.insert("end", message.rstrip() + "\n")
        if evidence is not None:
            self.console.insert(
                "end", json.dumps(evidence, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
            )
        self.console.see("end")

    def form_spec(self) -> ArtifactSpec:
        values = {key: variable.get().strip() for key, variable in self.form_vars.items()}
        metadata = json.loads(self.metadata_text.get("1.0", "end").strip() or "{}")

        def split(value: str) -> tuple[str, ...]:
            return tuple(item.strip() for item in value.split(",") if item.strip())

        return ArtifactSpec(
            name=values["name"],
            kind=ArtifactKind(values["kind"]),
            objective=values["objective"],
            jurisdiction=values["jurisdiction"],
            inputs=split(values["inputs"]),
            outputs=split(values["outputs"]),
            authority_ceiling=frozenset(split(values["authority"])),
            host_targets=tuple(metadata.pop("host_targets", [])),
            metadata=metadata,
        )

    def preview_spec(self) -> None:
        try:
            spec = self.form_spec()
            self.show_inspector(spec.to_dict())
            self.log("Especificación válida; todavía no se ha generado ningún archivo.")
        except Exception as exc:
            messagebox.showerror("Especificación inválida", str(exc), parent=self)

    def build_candidate(self) -> None:
        try:
            result = self.studio.build_and_seal(self.form_spec())
            self.refresh_sessions()
            self.show_inspector(result)
            self.log(f"Candidato terminado en estado {result['state']}", result.get("seal_body"))
        except Exception as exc:
            self.log("Fallo de construcción preservado", {"error": str(exc)})
            messagebox.showerror("Construcción detenida por gate", str(exc), parent=self)

    def refresh_sessions(self) -> None:
        self.session_tree.delete(*self.session_tree.get_children())
        for session in self.studio.store.list_sessions():
            full = self.studio.store.get(session["session_id"])
            self.session_tree.insert(
                "",
                "end",
                iid=session["session_id"],
                text=session["session_id"][-12:],
                values=(session["state"], full["spec"]["kind"]),
            )

    def inspect_session(self, _event: Any = None) -> None:
        selected = self.session_tree.selection()
        if selected:
            self.show_inspector(self.studio.store.get(selected[0]))

    def draw_governance_graph(self) -> None:
        canvas = getattr(self, "graph_canvas", None)
        if canvas is None:
            return
        canvas.delete("all")
        width = max(canvas.winfo_width(), 800)
        centers = {
            "HARNESS": (width / 2, 60),
            "AGENTS": (width / 2, 180),
            "RULES": (width / 2, 340),
        }
        for first, second in (("HARNESS", "AGENTS"), ("AGENTS", "RULES")):
            x1, y1 = centers[first]
            x2, y2 = centers[second]
            canvas.create_line(x1, y1 + 30, x2, y2 - 30, arrow="last", width=2, fill="#60708f")
        for label, (x, y) in centers.items():
            canvas.create_rectangle(
                x - 135, y - 30, x + 135, y + 30, fill="#172033", outline="#30486f", width=2
            )
            canvas.create_text(x, y, text=label, fill="white", font=("Segoe UI", 12, "bold"))
        canvas.create_text(
            width / 2,
            430,
            text="Las capas inferiores especializan o restringen; nunca amplían autoridad.",
            fill="#2f3d58",
            font=("Segoe UI", 10),
        )

    def search_extensions(self) -> None:
        try:
            records = self.fabric.search(self.provider_var.get(), self.query_var.get(), 12)
            inventory = RuntimeInventory().collect()
            available = [
                name for name, item in inventory["commands"].items() if item["state"] == "AVAILABLE"
            ]
            adjudicated = RecommendationEngine().evaluate(
                records, objective=self.query_var.get(), available_runtimes=available
            )
            self.extension_tree.delete(*self.extension_tree.get_children())
            self.extension_records.clear()
            for index, item in enumerate(adjudicated):
                record = item["record"]
                iid = f"ext-{index}"
                self.extension_records[iid] = item
                self.extension_tree.insert(
                    "",
                    "end",
                    iid=iid,
                    text=record["identifier"],
                    values=(record["provider"], record.get("version"), item["decision"]),
                )
            self.log(f"Búsqueda completada: {len(adjudicated)} resultados; sin instalación.")
        except Exception as exc:
            self.log("Búsqueda no completada", {"error": str(exc)})
            messagebox.showerror("Extension Fabric", str(exc), parent=self)

    def show_inventory(self) -> None:
        inventory = RuntimeInventory().collect()
        self.show_inspector(inventory)
        self.log("Inventario local de sólo lectura actualizado.")

    def inspect_extension(self, _event: Any = None) -> None:
        selected = self.extension_tree.selection()
        if selected and selected[0] in self.extension_records:
            self.show_inspector(self.extension_records[selected[0]])

    def show_inspector(self, value: Any) -> None:
        self.inspector.delete("1.0", "end")
        self.inspector.insert(
            "1.0", json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)
        )

    def plan_selected_install(self) -> None:
        selected = self.session_tree.selection()
        if not selected:
            messagebox.showinfo(
                "Instalación aislada", "Selecciona una sesión sellada.", parent=self
            )
            return
        session = self.studio.store.get(selected[0])
        if session["state"] != "SEALED_CANDIDATE":
            messagebox.showwarning(
                "Instalación aislada", "La sesión debe estar en SEALED_CANDIDATE.", parent=self
            )
            return
        plan = self.installer.plan(
            session["artifact_root"],
            artifact_kind=session["spec"]["kind"],
            target_name=f"{session['spec']['name']}-{selected[0][-8:]}",
        )
        self.pending_plan = plan
        self.pending_session = session
        self.install_text.delete("1.0", "end")
        self.install_text.insert(
            "1.0", json.dumps(plan.to_dict(), ensure_ascii=False, sort_keys=True, indent=2)
        )
        self.log("Plan aislado creado. Aún no se ha instalado nada.")

    def ask_consent(self) -> ConsentDecision | None:
        dialog = tk.Toplevel(self)
        dialog.title("Consentimiento gobernado KCH")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ttk.Label(
            dialog,
            text="¿Ejecutar esta instalación sólo dentro del perfil desechable KCH?",
            padding=12,
            wraplength=500,
        ).pack()
        choice: list[ConsentDecision] = []
        options = [
            ("Sí", ConsentDecision.YES),
            ("No", ConsentDecision.NO),
            ("Nunca en esta sesión", ConsentDecision.NEVER_THIS_SESSION),
            ("Siempre en esta sesión", ConsentDecision.ALWAYS_THIS_SESSION),
        ]
        frame = ttk.Frame(dialog, padding=10)
        frame.pack(fill="x")
        for label, decision in options:
            ttk.Button(
                frame,
                text=label,
                command=lambda value=decision: (choice.append(value), dialog.destroy()),
            ).pack(side="left", padx=4)
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
        self.wait_window(dialog)
        return choice[0] if choice else None

    def execute_pending_install(self) -> None:
        if self.pending_plan is None:
            messagebox.showinfo("Instalación aislada", "Primero crea un plan.", parent=self)
            return
        decision = self.ask_consent()
        if decision is None:
            return
        try:
            receipt = self.installer.execute(self.pending_plan, decision)
            if receipt["state"] == "INSTALLED_ISOLATED_DISABLED":
                receipt["verification"] = self.installer.verify(receipt)
            self.install_text.delete("1.0", "end")
            self.install_text.insert(
                "1.0", json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2)
            )
            self.log(f"Instalación gobernada: {receipt['state']}", receipt)
        except Exception as exc:
            self.log("Instalación aislada fallida", {"error": str(exc)})
            messagebox.showerror("Instalación aislada", str(exc), parent=self)


def launch(root: str | Path, *, smoke: bool = False) -> dict[str, Any] | None:
    tk_root = tk.Tk()
    tk_root.title("KCH CSI Studio · Extension Fabric")
    tk_root.geometry("1380x860")
    server = StudioMCP(root)
    studio = server.studio
    app = KCHStudioApp(
        tk_root,
        studio,
        advanced=server.advanced,
        fabric=server.fabric,
        installer=server.installer,
        tool_call=server.call,
        tool_descriptors=TOOLS,
    )
    if smoke:
        tk_root.withdraw()
        tk_root.update_idletasks()
        tk_root.update()
        result = {
            "passed": True,
            "tk_version": tk.TkVersion,
            "providers": len(studio.providers.describe()),
            "tabs": app.notebook.index("end"),
        }
        server.advanced.close()
        tk_root.destroy()
        return result

    def close() -> None:
        server.advanced.close()
        tk_root.destroy()

    tk_root.protocol("WM_DELETE_WINDOW", close)
    tk_root.mainloop()
    return None
