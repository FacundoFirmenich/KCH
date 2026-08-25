from __future__ import annotations

from typing import Any

from .integration import KCHInstructionGovernance


def create_integrated_runtime(
    runtime_class: Any,
    *,
    runtime_root: str,
    governance_root: str,
    stable_root: str | None = None,
) -> tuple[Any, KCHInstructionGovernance, dict[str, Any]]:
    """Construct KCH and IGE in the only safe ordering supported by R21."""

    governance = KCHInstructionGovernance(governance_root)
    composition = composition_arguments(governance)
    runtime = runtime_class(
        runtime_root,
        extra_handlers=composition["extra_handlers"],
        extra_tools=composition["extra_tools"],
        stable_root=stable_root,
    )
    receipt = {
        **{key: value for key, value in composition.items() if key not in {"extra_handlers", "extra_tools"}},
        "runtime_class": f"{runtime_class.__module__}.{runtime_class.__qualname__}",
        "candidate_handler_count": len(composition["extra_handlers"]),
        "runtime_constructed": True,
        "runtime_closed": False,
        "host_interposition_established": False,
        "reason_host_interposition_unestablished": (
            "local runtime composition is not a trusted native host lifecycle receipt"
        ),
    }
    return runtime, governance, receipt


def composition_arguments(governance: KCHInstructionGovernance) -> dict[str, Any]:
    """Return the exact pre-start arguments accepted by ``KCHAdvancedRuntime``.

    KCH must receive these handlers through ``extra_handlers`` and
    ``extra_tools`` during construction, before PHL dispatch and constitutional
    lock wrappers are compiled.  Post-start mutation would create an ungoverned
    bypass and is therefore not supported.
    """

    handlers = governance.handlers()
    descriptors = governance.tool_descriptors()
    return {
        "schema": "kch.ige.runtime-bridge-receipt.v0.3.0",
        "extra_handlers": handlers,
        "extra_tools": descriptors,
        "handler_names": sorted(handlers),
        "descriptor_names": sorted(item["name"] for item in descriptors),
        "composition_phase": "KCH_ADVANCED_RUNTIME_PRE_START",
        "post_start_binding_supported": False,
        "phl_dispatch_wrapping_required": True,
        "constitutional_lock_wrapping_required_for_mutations": True,
        "host_interposition_established": False,
        "stable_patch_required_for_startup_order": True,
        "mcp_used": False,
        "authority_created": False,
    }


def bind_instruction_governance(
    runtime: Any,
    governance: KCHInstructionGovernance,
) -> dict[str, Any]:
    """Reject unsafe post-start binding and explain the supported route."""

    if hasattr(runtime, "phl_catalog_receipt") or hasattr(runtime, "_mutating_tool_names"):
        raise RuntimeError(
            "post-start binding is prohibited: pass composition_arguments(...) as "
            "extra_handlers/extra_tools to KCHAdvancedRuntime during construction"
        )
    handlers = governance.handlers()
    overlap = set(runtime.handlers) & set(handlers)
    if overlap:
        raise ValueError(f"instruction-governance handler collision: {sorted(overlap)}")
    raise RuntimeError(
        "post-start binding is intentionally unsupported even for an unstarted stub; "
        "use composition_arguments(...)"
    )
