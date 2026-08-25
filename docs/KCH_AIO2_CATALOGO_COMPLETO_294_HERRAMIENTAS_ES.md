# Catálogo completo de herramientas KCH AIO2 / Super MCP

Este catálogo se genera mediante `tools/list` sobre el entrypoint federado ejecutable `kch-super-mcp-studio` (`serverInfo.name = kch-super-mcp`). Combina KwanCode Harness con Studio 0.3.16. No es una lista manual ni prospectiva. La presencia de una herramienta expresa capacidad; no concede por sí misma permiso, soporte, autoridad, ejecución ni entrenamiento.

- Total federado observado: **294**.
- Sólo lectura según anotación MCP: **154**.
- Con potencial de mutación gobernada: **140**.

## ACCOUNT — 7

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `account_auth_launch` | Mutación gobernada | Launch a terminal-first interactive authentication flow, with browser fallback only when required. |
| `account_broker_status` | Lectura | Inspect providers, finite duration classes and local/remote revocation limits. |
| `account_expire_due` | Mutación gobernada | Remove validated disposable local profiles for leases whose finite interval has ended. |
| `account_lease_approve` | Mutación gobernada | User-approve one pending request for a punctual, daily, weekly, monthly, quarterly or custom finite interval. |
| `account_lease_get` | Lectura | Read one finite lease without exposing secrets. |
| `account_permission_request` | Mutación gobernada | Create a terminal-first, finite-duration account permission request; does not approve or authenticate. |
| `account_use_authorize` | Mutación gobernada | Consume one authorized finite lease use and return its bounded receipt. |

## AIKIDO — 2

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `aikido_catalog` | Lectura | List prehashed adverse-to-capability transformations and their non-promoted status. |
| `aikido_transform` | Mutación gobernada | Synthesize a positive capability, dated protocol, skill and operator candidate, OBL/PHL envelope and regression contract from one prehashed incident; never auto-promotes it. |

## AUDIO — 5

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `audio_backends` | Lectura | Inspect local transcription, monitoring and speech backends without recording. |
| `audio_ingest_transcribe` | Mutación gobernada | Custody an authorized audio clip and transcribe with an available local backend. |
| `audio_monitor_start` | Mutación gobernada | Start visible microphone monitoring under an explicit consent basis and third-party notice contract. |
| `audio_monitor_stop` | Mutación gobernada | Stop microphone monitoring and seal the local monitor session. |
| `audio_status` | Lectura | Inspect transcription, microphone and TTS backends without activating the microphone. |

## CHECKPOINT — 9

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `checkpoint_diff_current` | Lectura | Compute missing, extra and changed files without restoring anything. |
| `checkpoint_estimate` | Lectura | Calculate exact current logical bytes and warn before any full checkpoint. |
| `checkpoint_full_create` | Mutación gobernada | Create the warned large ZIP checkpoint only after a prior plan and explicit size confirmation. |
| `checkpoint_full_plan` | Mutación gobernada | Create a warning-bearing plan; it does not create the large full checkpoint. |
| `checkpoint_manifest_get` | Lectura | Read and verify one structured checkpoint manifest. |
| `checkpoint_restore_new_root` | Mutación gobernada | Reconstruct exact bytes only into a new or empty destination and verify every hash. |
| `checkpoint_status` | Lectura | Inspect structured and full checkpoint coverage without creating a checkpoint. |
| `checkpoint_structured_create` | Mutación gobernada | Create an exact content-addressed incremental checkpoint with bidirectional traceability. |
| `checkpoint_trace_file` | Lectura | Read the presence and exact hash of one path across structured checkpoints. |

## CLIPBOARD — 13

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `clipboard_capture_text` | Mutación gobernada | Capture explicit text into the local clipboard history with secret detection. |
| `clipboard_explanation_context` | Lectura | Return one user-selected clipboard item for ad hoc explanation. |
| `clipboard_monitor_start` | Mutación gobernada | Start bounded polling of system clipboard text under the current persistence policy. |
| `clipboard_monitor_stop` | Mutación gobernada | Stop system clipboard polling without deleting captured history. |
| `clipboard_pin` | Mutación gobernada | Persist exact bytes for one previously captured clipboard item. |
| `clipboard_poll_once` | Mutación gobernada | Read and adjudicate the current system clipboard text once under the persistence policy. |
| `clipboard_postit_create` | Mutación gobernada | Create a versioned post-it from text or a clipboard item. |
| `clipboard_postit_edit` | Mutación gobernada | Autosave a post-it revision. |
| `clipboard_postit_get` | Lectura | Read one persistent post-it, tags, links and revision. |
| `clipboard_postit_link` | Mutación gobernada | Connect a post-it to any declared KCH entity by a user-defined relation. |
| `clipboard_region_capture` | Mutación gobernada | Capture a user-declared rectangle as persistent PNG and optionally copy it to the system clipboard. |
| `clipboard_search` | Lectura | Search non-secret previews and post-it text. |
| `clipboard_status` | Lectura | Inspect clipboard monitor, persistent items, and post-it database. |

## COMMITMENT — 6

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `commitment_monitor_check` | Mutación gobernada | Reconcile process identity, logs, artifacts and terminal receipt now; terminal alerting is exactly once and never relaunches the process. |
| `commitment_monitor_evidence` | Mutación gobernada | Return a canonically sealed evidence receipt with process identity, terminal status, exit code and hashed log metadata. |
| `commitment_monitor_launch` | Mutación gobernada | Launch a shell-free argv through a dedicated worker that owns stdout, stderr and a canonically sealed terminal receipt. Secret-like environment overrides are rejected. |
| `commitment_monitor_register` | Mutación gobernada | Persist an external PID, its OS creation identity, logs, artifacts and optional terminal receipt. Artifact presence alone never proves exit success. |
| `commitment_monitor_status` | Lectura | Inspect background monitoring, reconciliation errors and all terminal states without promoting them into general execution claims. |
| `commitment_monitor_wait_terminal` | Mutación gobernada | Follow the same registered execution until terminal evidence or a bounded wait timeout. Timeout keeps the commitment active and never kills or relaunches it. |

## CONSTITUTION — 8

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `constitution_box_add` | Mutación gobernada | User-enact a ranked and optionally nested constitutional box. |
| `constitution_box_set_active` | Mutación gobernada | User-activate or deactivate one constitutional box without deleting its history. |
| `constitution_box_update` | Mutación gobernada | User-update the exact content of an existing constitutional box. |
| `constitution_boxes_connect` | Mutación gobernada | User-enact a typed, optionally directed relation between constitutional boxes. |
| `constitution_effective` | Lectura | Compile active constitutional boxes in rank order without changing them. |
| `constitution_plane_add` | Mutación gobernada | User-enact a ranked horizontal, vertical, diagonal or freeform constitutional plane. |
| `constitution_propose` | Mutación gobernada | Store a model proposal separately; it does not enact or alter constitutional authority. |
| `constitution_state` | Lectura | Read the ranked, nested, connected user constitution. Models cannot mutate it. |

## CONSTRUCT — 7

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `construct_file_write` | Mutación gobernada | Write only inside a versioned candidate while preserving any preimage. A matching constitutional lock requires an exact one-shot authorization id. |
| `construct_file_write_propose` | Mutación gobernada | Compute the exact candidate preimage, proposed hash and recovery-bound change request without modifying candidate bytes. Only a trusted local user gesture may authorize it. |
| `construct_promote_next_start` | Mutación gobernada | Promote only a validated candidate through the next-start pointer. |
| `construct_rollback_pointer` | Mutación gobernada | Restore the previous stable pointer for the next start; current runtime bytes remain untouched. |
| `construct_session_get` | Lectura | Read candidate state, changes, validation and stable-backup reference. |
| `construct_start` | Mutación gobernada | Copy the stable KCH into a versioned candidate after creating an exact stable backup. |
| `construct_validate` | Mutación gobernada | Compile and test a candidate without modifying active runtime bytes. |

## CONTINUITY — 8

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `continuity_action_preflight` | Mutación gobernada | Fail closed on stale, non-material, mission-drifting, uncustodied, incompletely-read or recurrently unsafe work. |
| `continuity_harm_record` | Mutación gobernada | Append exact user-reported harm without inferring a medical diagnosis or rewriting historical evidence. |
| `continuity_integrity_verify` | Lectura | Verify the complete hash chain of continuity, burden and Aikido events. |
| `continuity_mission_set` | Mutación gobernada | Freeze the user-authorized governing objective and its authority source. |
| `continuity_protocol_register` | Mutación gobernada | Register a prehashed, explicitly verified historical protocol for mandatory reuse. |
| `continuity_protocol_resolve` | Lectura | Find matching verified protocols before fragments or replacement designs are allowed. |
| `continuity_reading_adjudicate` | Mutación gobernada | Forbid a complete-reading claim unless pagination reached EOF and every material truncation was recovered. |
| `continuity_status` | Lectura | Verify mission continuity, recurrent-failure controls and the append-only harm ledger. |

## CONTINUOUS — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `continuous_period_ledger_compile` | Lectura | Require every minimum period in the target interval and type it as OBSERVED, NO_EVENT or NOT_ESTIMABLE; block compressed calendars. |

## DICTION — 4

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `diction_correction_record` | Mutación gobernada | Record a transcription correction as PHL-authorized but untrained future-only feedback. |
| `diction_obl_add` | Mutación gobernada | User-add canonical diction variants to onboarding learning. |
| `diction_resolve` | Mutación gobernada | Preserve raw text and compute an auditable normalized overlay. |
| `diction_status` | Lectura | Inspect OBL lexicon, resolution and PHL-shadow correction counts. |

## DIRECT — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `direct_consent_status` | Lectura | Inspect per-action session consent without granting authority. |

## EVIDENCE — 2

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `evidence_closure_materialize` | Lectura | Mechanically project complete-reading and terminal-monitor evidence into a final task receipt while retaining every original sealed payload. Manual hash, line, span and exit-code transcription is forbidden. |
| `evidence_closure_verify` | Lectura | Regenerate a task closure from its retained source envelope and reject any altered, compacted or manually retranscribed representation even when it was resealed. |

## EXTENSION — 4

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `extension_inventory` | Lectura | Read runtime and host availability without reading secrets. |
| `extension_recommend` | Lectura | Evaluate independent recommendation lanes without a global winner score. |
| `extension_resolve` | Lectura | Resolve one exact provider identifier to current metadata; this does not download or install it. |
| `extension_search` | Lectura | Search a declared provider; search does not download or install. |

## FULL — 3

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `full_read_batch` | Lectura | Generate one machine-owned ordered inventory with two-read receipts and optional exact source-span evidence. No agent-authored hash transcription is required. |
| `full_read_file` | Lectura | Read every byte twice, transport the complete UTF-8 text when it fits the declared bound, and return a verifiable receipt. External paths require explicit permission; fragments never satisfy the claim. |
| `full_read_verify_batch` | Lectura | Re-read every source file and reject a canonically self-consistent batch whose hashes, content, order, ordinals or exact-span evidence were corrupted after tool execution. |

## ISOLATED — 4

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `isolated_install_execute` | Mutación gobernada | Execute only within the disposable KCH sandbox and only with one of the four explicit consent choices. |
| `isolated_install_plan` | Lectura | Create a reviewable install and rollback plan; does not execute it. |
| `isolated_install_rollback` | Mutación gobernada | Remove the exact disposable target described by a receipt. |
| `isolated_install_verify` | Lectura | Verify the isolated target against its receipt without changing it. |

## KCH — 3

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch_mode_status` | Lectura | Inspect the three canonical modes and the successor-only CONSTRUCT pointer. |
| `kch_next_status` | Lectura | Aggregate constitutional, launcher, recovery, data, permission, persistence, account, clipboard, audio, scheduler and MIS state. |
| `kch_preflight` | Lectura | Return one canonical gate over compiled governance, full strategic surface, launcher coverage, and PHL state. Use this instead of probing internal runtime classes. |

## KCH.COMPONENT.STATUS — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.component.status` | Lectura | Probe installed sovereign component distributions without invoking mutations. |

## KCH.CONTROL.R01 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R01` | Lectura | Bloqueo del objetivo gobernante. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R02 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R02` | Lectura | Firewall entre proyectos. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R03 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R03` | Lectura | Compilador de autorizaci�n. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R04 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R04` | Lectura | KCH aplicado al propio agente. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R05 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R05` | Lectura | Recibo previo de coste y alcance. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R06 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R06` | Lectura | Presupuesto de tokens y fan-out. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R07 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R07` | Lectura | Probe barato obligatorio. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R08 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R08` | Lectura | Parada por irrelevancia. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R09 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R09` | Lectura | Firewall ciencia-producto. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R10 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R10` | Lectura | Mapa directo-transferible-no aplicable. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R11 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R11` | Lectura | Auditor del significado de avance. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R12 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R12` | Lectura | Ledger de coste de oportunidad. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R13 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R13` | Lectura | Control de comunicaci�n completa. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R14 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R14` | Lectura | Firewall de readiness comercial. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R15 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R15` | Lectura | Enlace claim-fuente-ejecuci�n-jurisdicci�n. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R16 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R16` | Lectura | Registro can�nico de nombre y genealog�a. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R17 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R17` | Lectura | Ledger de �ltimas correcciones del usuario. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R18 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R18` | Lectura | Detector de contaminaci�n entre tareas. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R19 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R19` | Lectura | Validador de handoff m�nimo y suficiente. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R20 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R20` | Lectura | Limitador de proliferaci�n documental. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R21 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R21` | Lectura | Extractor de valor de resultados adversos. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R22 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R22` | Lectura | Ledger de reparaci�n. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R23 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R23` | Lectura | Interrupci�n humana prioritaria. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R24 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R24` | Lectura | Auditor de divergencia decisi�n-evidencia. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R25 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R25` | Lectura | Canonicalizador de roles de evidencia. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R26 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R26` | Lectura | Veto de m�tricas degeneradas. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R27 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R27` | Lectura | Control de completitud de transporte y fallos unitarios. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.CONTROL.R28 — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.control.R28` | Lectura | Degradaci�n autom�tica de autoridad cuando se pierde evidencia. Returns a signed-by-content governance receipt; never creates authority. |

## KCH.KWANPROMPTS.PROBE — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.kwanprompts.probe` | Lectura | Probe KwanPrompts package availability only. |

## KCH.MIS.CERTIFICATE.VERIFY — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.mis.certificate.verify` | Lectura | Verify the sealed MIS v0.3.1 historical integration certificate; creates no KCH authority. |

## KCH.OBL — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.obl_phl.probe` | Lectura | Probe OBL/PHL learning package availability only. |

## KCH.PHL.PROJECTION — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.phl.projection` | Lectura | Read and verify the effectively integrated PHL/KCH state projection. |

## KCH.RGG.PROBE — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.rgg.probe` | Lectura | Probe Rigor Gradient Governor package availability only. |

## KCH.SCO.PROJECTION — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.sco.projection` | Lectura | Read and verify an SCO graph projection while preserving chat sovereignty. |

## KCH.SUPER.ACTION.AUTHORIZE — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.super.action.authorize` | Mutación gobernada | Authorize only evidence-complete read-only proposals; mutating execution remains unavailable. |

## KCH.SUPER.ACTION.EXECUTE — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.super.action.execute` | Mutación gobernada | Execute a one-use authorized read-only federated route. Mutating routes are prohibited in KCH 0.11. |

## KCH.SUPER.ACTION.PROPOSE — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.super.action.propose` | Mutación gobernada | Record a governed action proposal; proposal is not authorization. |

## KCH.SUPER.AUDIT.EXPORT — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.super.audit.export` | Lectura | Export the append-only KCH 0.11 event chain and content hash. |

## KCH.SUPER.CONTEXT.COMPILE — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.super.context.compile` | Lectura | Evaluate an explicit subset of R01-R28 and compose their receipts without creating authority. |

## KCH.SUPER.CONTROLS — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.super.controls` | Lectura | Return the exact catalog of 28 reflexive controls and evidence ceiling. |

## KCH.SUPER.EVIDENCE.ADMIT — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.super.evidence.admit` | Mutación gobernada | Admit one preregistered evidence record with explicit role, provenance and jurisdiction. |

## KCH.SUPER.OUTCOME.REGISTER — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.super.outcome.register` | Mutación gobernada | Register an outcome, including adverse results, without rewriting historical evidence. |

## KCH.SUPER.PRECOMMIT.VERIFY — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.super.precommit.verify` | Mutación gobernada | Verify objective, jurisdiction, evidence, artifact identity and external observer before shadow precommit. |

## KCH.SUPER.REGISTRY — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.super.registry` | Lectura | Return the canonical KCH 0.11 federated registry without merging service authority. |

## KCH.SUPER.REGISTRY.EVIDENCE.AUDIT — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.super.registry.evidence.audit` | Lectura | Rehash the portable evidence copies referenced by the registry. |

## KCH.SUPER.ROLLBACK — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.super.rollback` | Mutación gobernada | Append an immutable compensating rollback record; it never rewrites history or silently mutates files. |

## KCH.SUPER.SESSION.OPEN — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.super.session.open` | Mutación gobernada | Open a governed session and issue one-use objective-bound capabilities. |

## KCH.SUPER.STATUS — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kch.super.status` | Lectura | Return KCH 0.11 runtime, profile, ledger, component and claim-boundary status. |

## KWANDATA — 7

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kwandata_ingest` | Mutación gobernada | Ingest an authorized local file with exact source custody and deterministic structuring. |
| `kwandata_program_create` | Mutación gobernada | Create a deterministic user-programmable structuring and tagging program. |
| `kwandata_query` | Lectura | Query structured records and tags. |
| `kwandata_status` | Lectura | Inspect source, record, tag, supertag, program and layer counts. |
| `kwandata_supertag_create` | Mutación gobernada | Create a ranked semantic relation from one supertag to declared child tags. |
| `kwandata_watch_add` | Mutación gobernada | Register an authorized finite local root for proactive deterministic ingestion. |
| `kwandata_watch_scan` | Mutación gobernada | Scan one registered root and ingest observed files with exact byte custody. |

## KWANPROMPTS — 6

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `kwanprompts_adjudicate` | Mutación gobernada | Run KwanPrompts message-boundary adjudication. |
| `kwanprompts_ingest` | Mutación gobernada | Persist a KwanPrompts message record without granting authority. |
| `kwanprompts_inspect` | Lectura | Read one KwanPrompts message and its provenance. |
| `kwanprompts_kwandocs_envelope` | Lectura | Build a provenance-preserving thread envelope for KwanDocs. |
| `kwanprompts_status` | Lectura | Inspect the persistent message-governance service. |
| `kwanprompts_verify` | Lectura | Verify the complete KwanPrompts ledger. |

## LOCK — 8

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `lock_authorization_status` | Lectura | Inspect whether one proposal remains pending, is authorized once, or has already consumed its exact capability. |
| `lock_authorized_execute` | Mutación gobernada | Consume one trusted one-shot authorization only when the tool name and complete arguments are byte-for-byte canonically equivalent to the approved proposal. |
| `lock_change_propose` | Mutación gobernada | Register the exact resource, operation, hashes, rationale, impact, dependencies and recovery plan. This never authorizes or executes the change. |
| `lock_drift_verify` | Lectura | Rehash exact locked files and detect external unmediated changes without claiming that KCH prevented writes outside its control. |
| `lock_governor_status` | Lectura | Inspect optional lock enforcement, exact one-shot authority, coverage boundaries and hash-chain integrity without changing policy. |
| `lock_list` | Lectura | List active or historical object and tool locks without granting mutation authority. |
| `lock_pending_proposals` | Lectura | Read every exact change request awaiting a trusted local user gesture, including rationale, impact, dependencies and recovery plan. |
| `lock_tool_call_propose` | Mutación gobernada | Mechanically bind one mutating tool name and its complete arguments to a change proposal; a model may propose but cannot authorize it. |

## MIS — 23

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `mis_atom_register` | Mutación gobernada | Register a user-authored semantic atom without changing frozen MIS bytes. |
| `mis_atom_resolve` | Lectura | Resolve a language skin to one stable semantic atom. |
| `mis_atoms_list` | Lectura | List canonical and user-declared semantic atoms as compositional CSI material. |
| `mis_certificate_export` | Mutación gobernada | Write one verified exact MIS certificate to the governed local export area without promoting its claim ceiling. |
| `mis_certificate_verify_full` | Lectura | Verify the packaged historical certificate or a supplied MIS certificate. |
| `mis_csi_lowering` | Lectura | Read and verify the bounded four-instruction CSI lowering with its operational limitation. |
| `mis_decision_register_phl` | Mutación gobernada | Convert a verified exact MIS certificate into a reviewable decision and register it without training. |
| `mis_describe` | Lectura | Describe the full bounded MIS v0.3.1 mathematical service. |
| `mis_dynamic_csi_lowering` | Lectura | Lower any verified MIS certificate to a compositional CSI program with no authority transfer. |
| `mis_exact_decide` | Lectura | Compute a rational Bayesian loss decision for declared inputs; creates no execution authority. |
| `mis_full_status` | Lectura | Distinguish real MIS mathematics from the formerly amputated KCH 0.11 surface. |
| `mis_historical_audit` | Lectura | Recompute the exact 480-record/60-ledger bounded historical audit. |
| `mis_integrity_verify` | Lectura | Verify the MIS event chain, certificates, prospective ledgers and reviewable-decision projections. |
| `mis_kwandata_archive` | Mutación gobernada | Export exact certificate bytes and ingest them into KwanData with provenance. |
| `mis_rgg_adjudicate` | Lectura | Apply an explicit RGG action request to a verified MIS certificate while retaining both boundaries. |
| `mis_sco_issue_review` | Mutación gobernada | Build and issue a bounded MIS review work order to an independent SCO node. |
| `mis_sco_work_order_template` | Lectura | Build a bounded no-dispatch SCO review work order for one verified MIS certificate. |
| `mis_studies_list` | Lectura | List persistent prospective MIS studies. |
| `mis_study_close` | Mutación gobernada | Close a prospective study only when no outcome is pending. |
| `mis_study_create` | Mutación gobernada | Create an empty future-only exact Bayesian study; no outcome or empirical value is invented. |
| `mis_study_freeze` | Mutación gobernada | Freeze the pre-outcome prior and exact decision certificate. |
| `mis_study_observe` | Mutación gobernada | Record a source-hashed outcome only after its decision freeze. |
| `mis_study_projection` | Lectura | Inspect freezes, outcomes, next prior and local claim ceiling. |

## PERMISSION — 4

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `permission_check` | Mutación gobernada | Evaluate and record one actor/resource/operation decision. |
| `permission_grant` | Mutación gobernada | User-enact one scoped, ranked and optionally expiring permission rule. |
| `permission_revoke` | Mutación gobernada | User-disable one permission rule while retaining its history and receipt. |
| `permission_status` | Lectura | Inspect governed capability domains and receipt counts. |

## PERSISTENCE — 8

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `persistence_chat_create` | Mutación gobernada | Create a KCH chat record with explicit platform and capture mode. |
| `persistence_chat_get` | Lectura | Read chat identity, capture mode, completeness ceiling and turn count. |
| `persistence_chat_verify` | Lectura | Verify the complete local turn hash chain without asserting external transport completeness. |
| `persistence_page_mark` | Mutación gobernada | Record a hash-bearing page receipt; caller EOF remains unverified until an authenticated connector exists. |
| `persistence_status` | Lectura | Inspect exact KCH/SCO custody coverage and external-host transport limits. |
| `persistence_superchat_create` | Mutación gobernada | Orchestrate existing chats without merging their context or identity. |
| `persistence_superchat_get` | Lectura | Read one no-merge superchat membership manifest. |
| `persistence_turn_append` | Mutación gobernada | Append exact JSON payload to a chat hash chain. |

## PHL — 7

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `phl_decision_register` | Mutación gobernada | Register a conformant decision in both effective and learning ledgers; this does not train PHL. |
| `phl_decisions_list` | Lectura | List reviewable decisions without starting a PHL session. |
| `phl_packet_compile` | Mutación gobernada | Compile a future-only packet; activation remains prohibited pending replay and user approval. |
| `phl_score` | Mutación gobernada | Record an exact 000..100 user-authored score as future-only feedback. |
| `phl_session_close` | Mutación gobernada | Close both linked ledgers and release the ordinary-work mutation lock. |
| `phl_session_start` | Mutación gobernada | Start linked effective and learning PHL sessions under one of the four explicit consent choices. |
| `phl_status` | Lectura | Inspect the authorized but possibly untrained PHL capability and both linked ledgers. |

## PLAN — 2

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `plan_build_execute` | Mutación gobernada | Execute a previously persisted plan inside the KCH runtime with original-byte custody. |
| `plan_build_plan` | Mutación gobernada | Persist a reviewable ingest/transform/restore plan without executing it. |

## PROACTIVE — 7

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `proactive_event_publish` | Mutación gobernada | Queue an event for background governed dispatch. |
| `proactive_launcher_manifest` | Lectura | Read every registered capability and its declared side-effect class. |
| `proactive_launcher_run_once` | Mutación gobernada | Claim and dispatch at most one queued event through governed handlers. |
| `proactive_launcher_start` | Mutación gobernada | Start the governed background dispatcher for this runtime. |
| `proactive_launcher_status` | Lectura | Inspect background state, capability coverage, and blind spots. |
| `proactive_launcher_stop` | Mutación gobernada | Stop the governed background dispatcher for this runtime. |
| `proactive_launcher_wait` | Lectura | Read the bounded result of one event without creating another event. |

## PROGRAMMED — 5

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `programmed_policy_evaluate` | Lectura | Evaluate every applicable programmed rule; does not execute it. |
| `programmed_policy_preferences_set` | Mutación gobernada | User-enable or disable the proactive program and its startup announcement. |
| `programmed_policy_replace` | Mutación gobernada | User-replace the complete versioned proactive if/then/else policy. |
| `programmed_policy_rule_add` | Mutación gobernada | User-add one validated proactive rule to the current policy. |
| `programmed_policy_status` | Lectura | Inspect direct if/then/else rules and startup-announcement preference. |

## RECOVERY — 7

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `recovery_alert_record` | Mutación gobernada | Persist a warning or overridden-warning receipt for later diagnosis and rescue. |
| `recovery_checkpoint` | Mutación gobernada | Persist an optional event payload and snapshot all current master-vault assets. |
| `recovery_export_latest` | Mutación gobernada | Export exact current bytes under an explicitly selected safe root and relative path. |
| `recovery_latest` | Lectura | Read one exact recovery asset revision with binary content encoded as base64. |
| `recovery_restore_revision` | Mutación gobernada | Append a selected historic revision as the new current revision; history is retained. |
| `recovery_revision` | Lectura | Read one numbered recovery revision with binary content encoded as base64. |
| `recovery_verify` | Lectura | Verify append-only master recovery chains. |

## REMOTE — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `remote_transport_preflight` | Lectura | Block empty, shell-mutated, stale-marker or hash-mismatched remote wrappers before any process starts. |

## RESPONSE — 13

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `response_authority_adjudicate` | Mutación gobernada | Fail closed when structured response claims violate active semantic authority, conflate experiments, promote scope, add off-mission classifications or promise unregistered monitoring. |
| `response_authority_register` | Mutación gobernada | Freeze an explicit mission, terminology, provenance, jurisdiction, experiment-boundary or rejected-frame constraint with its authority source. |
| `response_authority_status` | Lectura | Inspect active response constraints, hash-chain integrity and the explicit host-interposition evidence boundary. |
| `response_execution_register` | Mutación gobernada | Persist the technical execution record separately as Markdown; it is never offered or substituted for the substantive answer. |
| `response_mode_contract` | Lectura | Compile the exact host instruction for authored chat text; outputs remain outside this policy. |
| `response_mode_integrity` | Lectura | Verify canonical presets, foreign keys and the response-policy audit hash chain. |
| `response_mode_profile_archive` | Mutación gobernada | Archive an unbound custom profile; canonical presets cannot be altered or archived. |
| `response_mode_profile_upsert` | Mutación gobernada | Create or revise a persistent custom response profile derived from a canonical or custom base. |
| `response_mode_profiles_list` | Lectura | List canonical and user-defined chat-response profiles. |
| `response_mode_resolve` | Lectura | Resolve the effective response profile by message, session, task, SCO, workspace and global precedence. |
| `response_mode_scope_clear` | Mutación gobernada | Clear one exact response-profile binding and restore inheritance from the next broader scope. |
| `response_mode_scope_set` | Mutación gobernada | Bind a response profile to global, workspace, SCO, task, session or message scope. |
| `response_mode_status` | Lectura | Inspect the three canonical chat-response presets, scope precedence, invariants and integrity without affecting outputs. |

## RGG — 5

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `rgg_adjudicate_action` | Lectura | Separate action permission from claim ceiling under an explicit RGG profile. |
| `rgg_audit_review` | Lectura | Audit fact, claim and action judgments without erasing adverse evidence. |
| `rgg_resolve_profile` | Lectura | Resolve purpose, audience and risk into a bounded RGG profile. |
| `rgg_status` | Lectura | Inspect all packaged rigor profiles and the shadow-only authority boundary. |
| `rgg_transition_plan` | Lectura | Plan a rigor-regime transition while preserving frozen parents. |

## RISK — 2

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `risk_assess` | Lectura | Warn about dependency, history, authority, external-write, and lossy-conversion risk; does not censor. |
| `risk_override_record` | Mutación gobernada | Record warnings and a recovery snapshot for an explicitly user-authorized proposal; this tool does not execute the proposal itself. |

## SCHEDULER — 8

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `scheduler_agenda_create` | Mutación gobernada | Create an independently named agenda with an IANA timezone. |
| `scheduler_create` | Mutación gobernada | Create a persisted schedule that publishes events to the proactive launcher. |
| `scheduler_get` | Lectura | Read one schedule, its event payload and current enabled state. |
| `scheduler_run_due` | Mutación gobernada | Publish all currently due occurrences exactly once through the proactive launcher. |
| `scheduler_set_enabled` | Mutación gobernada | User-enable or disable one persisted schedule without deleting it. |
| `scheduler_start` | Mutación gobernada | Start the governed background schedule loop. |
| `scheduler_status` | Lectura | Inspect agendas, active one-shot/interval/cron schedules, and occurrence history. |
| `scheduler_stop` | Mutación gobernada | Stop the governed background schedule loop. |

## SCO — 12

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `sco_add_edge` | Mutación gobernada | Connect two independent chats through an explicit disclosure contract. |
| `sco_add_node` | Mutación gobernada | Add a native Codex, Cline, Cowork, OpenCode, ChatGPT or custom node without copying its memory. |
| `sco_create` | Mutación gobernada | Create a full SCO record under optimistic concurrency. |
| `sco_declare_conflict` | Mutación gobernada | Register irreducible divergence between node receipts. |
| `sco_dispatch_envelopes` | Lectura | Build bounded per-node dispatch envelopes; a host bridge must transmit them. |
| `sco_export_bundle` | Lectura | Export a context-separated orchestration bundle. |
| `sco_graph_diagnostics` | Lectura | Inspect cycles, reachability and orchestration consistency. |
| `sco_ingest_receipt` | Mutación gobernada | Ingest a bounded node receipt while preserving failures, abstentions and limitations. |
| `sco_issue_work_order` | Mutación gobernada | Issue a bounded subsistemic work order with no implicit authority transfer. |
| `sco_retire_node` | Mutación gobernada | Retire a node while preserving ledger history. |
| `sco_schedule` | Lectura | Compute dependency-ready work orders without dispatching external chats. |
| `sco_status` | Lectura | Inspect SCO projections and integrity without merging member context. |

## SOURCE — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `source_fitness_adjudicate` | Lectura | Block training when time-window scope, continuous coverage, observed support or jurisdiction support is insufficient. |

## STUDIO — 6

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `studio_build_and_seal` | Mutación gobernada | Run the complete create, generate, validate and seal pipeline; no installation or enablement authority is created. |
| `studio_create_session` | Mutación gobernada | Validate and persist a governed artifact specification. |
| `studio_generate` | Mutación gobernada | Generate only inside KCH staging; does not install or enable. |
| `studio_seal` | Mutación gobernada | Seal a validated candidate without installation authority. |
| `studio_status` | Lectura | Inspect Studio, governance, providers, and sessions without changing state. |
| `studio_validate` | Mutación gobernada | Run provider, custody, and ledger validation. |

## TEMPORAL — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `temporal_scale_compile` | Lectura | Keep timestamp resolution, prediction horizon, event count, minimum period and update cadence distinct; enforce minimum complete period to minimum complete period. |

## UNIVERSAL — 3

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `universal_asset_ingest` | Mutación gobernada | Custody exact original bytes and create a readable TXT projection when deterministically supported. |
| `universal_asset_restore` | Mutación gobernada | Restore exact original bytes of one universal asset to a safe relative runtime target. |
| `universal_asset_transform` | Mutación gobernada | Create a declared derivative while retaining exact original-byte recovery. |

## VOICE — 1

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `voice_notify` | Mutación gobernada | Preserve a KCH message transcript and synthesize it locally when available. |

## WORKBENCH — 21

| Herramienta | Clase | Descripción contractual |
|---|---|---|
| `workbench_archive_attach` | Mutación gobernada | Attach a source, protocol, skill, handoff or external reference to a ranked group. |
| `workbench_archive_group_create` | Mutación gobernada | Create one ranked group or subgroup without deleting or merging its members. |
| `workbench_archive_group_set_archived` | Mutación gobernada | Change only the archive visibility state; no member or artifact is deleted. |
| `workbench_archive_tree` | Lectura | Return all groups and ranked members with no deletion or merge. |
| `workbench_budget_account_configure` | Mutación gobernada | Declare a token, currency or percentage budget and its telemetry source without inferring limits or prices. |
| `workbench_budget_policy_set` | Mutación gobernada | Replace the complete user-controlled cadence policy after exact schema validation. |
| `workbench_budget_sample_record` | Mutación gobernada | Record explicit use or availability with a source receipt; never infer account prices. |
| `workbench_budget_status` | Lectura | Return exact source-derived availability or NOT_ESTIMABLE when live evidence is absent. |
| `workbench_graph` | Lectura | Return clickable nodes and provenance, archive, workspace, session, domain and artifact edges. |
| `workbench_graph_connect` | Mutación gobernada | Add an explicit typed, multidimensional relationship without conflating node authority. |
| `workbench_graph_resolve_node` | Lectura | Resolve one clicked node to its exact local record or declared dimension. |
| `workbench_handoffs_list` | Lectura | List local continuity packets; task creation and predecessor archival remain host-connector actions. |
| `workbench_ingest` | Mutación gobernada | Preserve raw and normalized layers, redact secrets, detect evidence candidates, and run governed maintenance. |
| `workbench_integrity_verify` | Lectura | Verify raw and normalized bytes, protocols, staged skill manifests and the event hash chain. |
| `workbench_kwandata_envelope` | Lectura | Describe a structured-data bridge without executing ingestion or transferring authority. |
| `workbench_kwandocs_envelope` | Lectura | Describe a canonical-evidence bridge without executing ingestion or transferring authority. |
| `workbench_lessons_list` | Lectura | List evidence-linked candidates by scope or domain; lexical detection is not promoted to truth. |
| `workbench_maintenance_run` | Mutación gobernada | Apply the configured evidence and weekly-budget cadence; may stage local protocols, skills, checkpoints requests and handoff packets. |
| `workbench_protocols_list` | Lectura | List evidence-derived, pre-hashed protocols without installing anything. |
| `workbench_skills_list` | Lectura | List generated skill candidates and their unevaluated, uninstalled and inactive lifecycle state. |
| `workbench_status` | Lectura | Inspect automatic learning, protocols, staged skills, archives, graph, weekly budget and integrity. |

