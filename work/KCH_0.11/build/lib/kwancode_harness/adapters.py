from __future__ import annotations

import importlib
import importlib.metadata
import json
import os
from pathlib import Path
from typing import Any, Callable


class FederationAdapters:
    """Read-only integration boundary for sovereign KCH services."""

    PACKAGES = {
        "PHL_EFFECTIVE_INTEGRATION": "kch-phl-effective-integration",
        "SCO": "kch-superchats-orchestrators",
        "MIS_ADAPTER": "kch-mis-v03-integration",
        "MIS_BACKEND": "mis-qualitative-bayes",
        "OBL_PHL": "kch-obl-phl-learning-system",
        "RGG": "kch-rigor-gradient-governor",
        "KWANPROMPTS": "kwanprompts",
    }

    def __init__(self, bundle_root: str | Path | None = None):
        self.bundle_root = Path(bundle_root or os.environ.get("KCH_011_BUNDLE_ROOT", ".")).resolve()

    def component_status(self) -> dict[str, Any]:
        rows = []
        for component, distribution in self.PACKAGES.items():
            try:
                version = importlib.metadata.version(distribution)
                state = "AVAILABLE"
            except importlib.metadata.PackageNotFoundError:
                version, state = None, "UNAVAILABLE"
            rows.append({"component": component, "distribution": distribution, "version": version, "state": state})
        return {
            "schema": "kch.component-status.v0.11.0",
            "release": "KCH 0.11",
            "components": rows,
            "available": sum(row["state"] == "AVAILABLE" for row in rows),
            "unavailable": sum(row["state"] == "UNAVAILABLE" for row in rows),
            "authority_created": False,
        }

    def _path(self, env: str, relative: str) -> Path:
        return Path(os.environ.get(env, str(self.bundle_root / relative))).resolve()

    def phl_projection(self) -> dict[str, Any]:
        path = self._path("KCH_011_PHL_STATE", "evidence/KCH_CURRENT_INTEGRATION_STATE_v0.6.0.sqlite3")
        if not path.is_file():
            return {"state": "UNAVAILABLE", "reason": "PHL_STATE_UNAVAILABLE", "path": str(path)}
        try:
            service = importlib.import_module("kch_phl_integration").EffectiveIntegrationService(path)
            return {"state": "AVAILABLE", "path": str(path), "projection": service.projection(), "integrity": service.verify(), "authority_created": False}
        except (ImportError, AttributeError) as exc:
            return {"state": "UNAVAILABLE", "reason": "PHL_ADAPTER_UNAVAILABLE", "detail": type(exc).__name__, "path": str(path)}

    def sco_projection(self, sco_id: str | None = None) -> dict[str, Any]:
        path = self._path("KCH_011_SCO_STATE", "evidence/KCH_PRE2G_SCO_v0.1.0.sqlite3")
        if not path.is_file():
            return {"state": "UNAVAILABLE", "reason": "SCO_STATE_UNAVAILABLE", "path": str(path)}
        try:
            service = importlib.import_module("kch_sco").SCOService(path)
            return {"state": "AVAILABLE", "path": str(path), "projection": service.projection(sco_id), "integrity": service.verify(), "live_cross_provider_dispatch": False, "authority_created": False}
        except (ImportError, AttributeError) as exc:
            return {"state": "UNAVAILABLE", "reason": "SCO_ADAPTER_UNAVAILABLE", "detail": type(exc).__name__, "path": str(path)}

    def mis_certificate_verify(self) -> dict[str, Any]:
        path = self._path("KCH_011_MIS_CERTIFICATE", "evidence/KCH_MIS_V03_HISTORICAL_CERTIFICATE_v0.1.0.json")
        if not path.is_file():
            return {"state": "UNAVAILABLE", "reason": "MIS_CERTIFICATE_UNAVAILABLE", "path": str(path)}
        try:
            certificate = json.loads(path.read_text(encoding="utf-8-sig"))
            verifier: Callable[[dict[str, Any]], dict[str, Any]] = importlib.import_module("kch_mis_v03_integration").verify_historical_certificate
            result = verifier(certificate)
            return {"state": "AVAILABLE", "path": str(path), "verification": result, "authority_created": False, "automatic_promotion": False}
        except (ImportError, AttributeError) as exc:
            return {"state": "UNAVAILABLE", "reason": "MIS_ADAPTER_UNAVAILABLE", "detail": type(exc).__name__, "path": str(path)}

    def probe_module(self, component: str) -> dict[str, Any]:
        modules = {"KWANPROMPTS": "kwanprompts", "RGG": "kch_rigor_governor", "OBL_PHL": "kch_learning"}
        if component not in modules:
            raise ValueError("unsupported component probe")
        try:
            module = importlib.import_module(modules[component])
            return {"component": component, "state": "AVAILABLE", "module": modules[component], "origin": str(getattr(module, "__file__", "")), "authority_created": False}
        except ImportError:
            return {"component": component, "state": "UNAVAILABLE", "module": modules[component], "authority_created": False}
