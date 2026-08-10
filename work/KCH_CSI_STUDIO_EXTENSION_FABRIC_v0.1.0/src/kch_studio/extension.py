from __future__ import annotations

import hashlib
import json
import platform
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

USER_AGENT = "KCH-Extension-Fabric/0.1.0 (+local-governed-discovery)"


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class ExtensionRecord:
    provider: str
    identifier: str
    version: str | None
    summary: str
    license: str | None
    homepage: str | None
    repository: str | None
    published_at: str | None
    runtimes: tuple[str, ...]
    source_url: str
    provenance: str
    security_evidence: dict[str, Any] = field(default_factory=dict)
    raw_evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["runtimes"] = list(self.runtimes)
        return value


class HttpCache:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def get_json(self, url: str, *, timeout: int = 15) -> tuple[Any, dict[str, Any]]:
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()
        body_path = self.root / f"{key}.json"
        meta_path = self.root / f"{key}.meta.json"
        headers = {"Accept": "application/json", "User-Agent": USER_AGENT}
        if meta_path.is_file():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if meta.get("etag"):
                headers["If-None-Match"] = str(meta["etag"])
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                value = json.loads(raw.decode("utf-8"))
                body_path.write_bytes(raw)
                meta = {
                    "url": url,
                    "fetched_at": utc_now(),
                    "etag": response.headers.get("ETag"),
                    "last_modified": response.headers.get("Last-Modified"),
                    "status": response.status,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "cache_hit": False,
                }
                meta_path.write_text(
                    json.dumps(meta, sort_keys=True, indent=2) + "\n", encoding="utf-8"
                )
                return value, meta
        except urllib.error.HTTPError as exc:
            if exc.code == 304 and body_path.is_file() and meta_path.is_file():
                value = json.loads(body_path.read_text(encoding="utf-8"))
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                meta["cache_hit"] = True
                meta["revalidated_at"] = utc_now()
                return value, meta
            raise


class DiscoveryProvider:
    provider_id = "base"
    capabilities: frozenset[str] = frozenset()

    def search(self, query: str, limit: int = 10) -> list[ExtensionRecord]:
        raise NotImplementedError(f"UNAVAILABLE_PROVIDER_CAPABILITY:{self.provider_id}:search")

    def resolve(self, identifier: str) -> ExtensionRecord:
        raise NotImplementedError(f"UNAVAILABLE_PROVIDER_CAPABILITY:{self.provider_id}:resolve")

    def describe(self) -> dict[str, Any]:
        return {"provider": self.provider_id, "capabilities": sorted(self.capabilities)}


class PyPIProvider(DiscoveryProvider):
    provider_id = "pypi"
    capabilities = frozenset({"resolve", "inspect", "security_evidence", "exact_search"})

    def __init__(self, cache: HttpCache):
        self.cache = cache

    def resolve(self, identifier: str) -> ExtensionRecord:
        name = urllib.parse.quote(identifier, safe="")
        value, meta = self.cache.get_json(f"https://pypi.org/pypi/{name}/json")
        info = value.get("info", {})
        vulnerabilities = value.get("vulnerabilities")
        project_urls = info.get("project_urls") or {}
        repository = (
            project_urls.get("Source") or project_urls.get("Repository") or project_urls.get("Code")
        )
        return ExtensionRecord(
            provider=self.provider_id,
            identifier=str(info.get("name") or identifier),
            version=info.get("version"),
            summary=str(info.get("summary") or ""),
            license=info.get("license_expression") or info.get("license"),
            homepage=info.get("home_page") or project_urls.get("Homepage"),
            repository=repository,
            published_at=max(
                (item.get("upload_time_iso_8601") or "" for item in value.get("urls", [])),
                default="",
            )
            or None,
            runtimes=(f"python{sys.version_info.major}.{sys.version_info.minor}",),
            source_url=f"https://pypi.org/project/{urllib.parse.quote(str(info.get('name') or identifier))}/",
            provenance="PYPI_JSON_API",
            security_evidence={
                "known_vulnerabilities": vulnerabilities
                if isinstance(vulnerabilities, list)
                else None,
                "status": "OBSERVED" if isinstance(vulnerabilities, list) else "NOT_ESTIMABLE",
            },
            raw_evidence={
                "requires_python": info.get("requires_python"),
                "yanked": info.get("yanked"),
                "cache": meta,
            },
        )

    def search(self, query: str, limit: int = 10) -> list[ExtensionRecord]:
        # PyPI's supported JSON API resolves project names; it is not a general ranking API.
        # This method therefore exposes exact-name search semantics instead of scraping HTML.
        try:
            return [self.resolve(query)]
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return []
            raise


class NpmProvider(DiscoveryProvider):
    provider_id = "npm"
    capabilities = frozenset({"search", "resolve", "inspect"})

    def __init__(self, cache: HttpCache):
        self.cache = cache

    def resolve(self, identifier: str) -> ExtensionRecord:
        encoded = urllib.parse.quote(identifier, safe="@")
        value, meta = self.cache.get_json(f"https://registry.npmjs.org/{encoded}/latest")
        repository = value.get("repository")
        if isinstance(repository, dict):
            repository = repository.get("url")
        engines = value.get("engines") or {}
        return ExtensionRecord(
            provider=self.provider_id,
            identifier=str(value.get("name") or identifier),
            version=value.get("version"),
            summary=str(value.get("description") or ""),
            license=value.get("license") if isinstance(value.get("license"), str) else None,
            homepage=value.get("homepage"),
            repository=repository,
            published_at=None,
            runtimes=(f"node:{engines.get('node')}",) if engines.get("node") else ("node",),
            source_url=f"https://www.npmjs.com/package/{identifier}",
            provenance="NPM_REGISTRY_LATEST_DOCUMENT",
            security_evidence={
                "status": "NOT_ESTIMABLE",
                "reason": "npm package metadata is not an audit result",
            },
            raw_evidence={"engines": engines, "dist": value.get("dist", {}), "cache": meta},
        )

    def search(self, query: str, limit: int = 10) -> list[ExtensionRecord]:
        npm = shutil.which("npm")
        if not npm:
            raise RuntimeError("UNAVAILABLE_PROVIDER_RUNTIME:npm")
        result = subprocess.run(
            [npm, "search", "--json", f"--searchlimit={int(limit)}", query],
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(f"npm search failed: {result.stderr.strip()}")
        values = json.loads(result.stdout or "[]")
        records: list[ExtensionRecord] = []
        for value in values[:limit]:
            links = value.get("links") or {}
            records.append(
                ExtensionRecord(
                    provider=self.provider_id,
                    identifier=str(value.get("name") or ""),
                    version=value.get("version"),
                    summary=str(value.get("description") or ""),
                    license=None,
                    homepage=links.get("homepage") or links.get("npm"),
                    repository=links.get("repository"),
                    published_at=value.get("date"),
                    runtimes=("node",),
                    source_url=links.get("npm")
                    or f"https://www.npmjs.com/package/{value.get('name')}",
                    provenance="NPM_CLI_SEARCH_JSON",
                    security_evidence={"status": "NOT_ESTIMABLE"},
                    raw_evidence={
                        "publisher": value.get("publisher"),
                        "maintainers": value.get("maintainers"),
                    },
                )
            )
        return records


class MCPRegistryProvider(DiscoveryProvider):
    provider_id = "mcp-registry"
    capabilities = frozenset({"search", "resolve", "inspect"})

    def __init__(self, cache: HttpCache):
        self.cache = cache

    @staticmethod
    def _record(value: dict[str, Any], meta: dict[str, Any]) -> ExtensionRecord:
        server = value.get("server") if isinstance(value.get("server"), dict) else value
        name = str(server.get("name") or server.get("id") or "")
        packages = server.get("packages") or []
        runtimes = tuple(
            sorted(
                {
                    str(item.get("registryType") or item.get("registry_type"))
                    for item in packages
                    if isinstance(item, dict)
                }
            )
        )
        repository = server.get("repository")
        if isinstance(repository, dict):
            repository = repository.get("url")
        return ExtensionRecord(
            provider="mcp-registry",
            identifier=name,
            version=server.get("version"),
            summary=str(server.get("description") or ""),
            license=None,
            homepage=server.get("websiteUrl") or server.get("website_url"),
            repository=repository,
            published_at=value.get("meta", {}).get("updatedAt")
            if isinstance(value.get("meta"), dict)
            else None,
            runtimes=runtimes,
            source_url=f"https://registry.modelcontextprotocol.io/v0.1/servers/{urllib.parse.quote(name, safe='')}",
            provenance="OFFICIAL_MCP_REGISTRY_API",
            security_evidence={
                "status": "NOT_ESTIMABLE",
                "reason": "registry inclusion is not a security audit",
            },
            raw_evidence={
                "packages": packages,
                "remotes": server.get("remotes", []),
                "cache": meta,
            },
        )

    def search(self, query: str, limit: int = 10) -> list[ExtensionRecord]:
        url = "https://registry.modelcontextprotocol.io/v0.1/servers?" + urllib.parse.urlencode(
            {"search": query, "version": "latest", "limit": int(limit)}
        )
        value, meta = self.cache.get_json(url)
        servers = value.get("servers") or value.get("data") or []
        return [self._record(item, meta) for item in servers[:limit]]

    def resolve(self, identifier: str) -> ExtensionRecord:
        url = f"https://registry.modelcontextprotocol.io/v0.1/servers/{urllib.parse.quote(identifier, safe='')}"
        value, meta = self.cache.get_json(url)
        return self._record(value, meta)


class OpenVSXProvider(DiscoveryProvider):
    provider_id = "open-vsx"
    capabilities = frozenset({"search", "resolve", "inspect"})

    def __init__(self, cache: HttpCache):
        self.cache = cache

    def search(self, query: str, limit: int = 10) -> list[ExtensionRecord]:
        url = "https://open-vsx.org/api/-/search?" + urllib.parse.urlencode(
            {"query": query, "size": int(limit)}
        )
        value, meta = self.cache.get_json(url)
        records: list[ExtensionRecord] = []
        for item in (value.get("extensions") or [])[:limit]:
            namespace = item.get("namespace")
            name = item.get("name")
            identifier = f"{namespace}.{name}"
            records.append(
                ExtensionRecord(
                    provider=self.provider_id,
                    identifier=identifier,
                    version=item.get("version"),
                    summary=str(item.get("description") or ""),
                    license=item.get("license"),
                    homepage=item.get("homepage"),
                    repository=item.get("repository"),
                    published_at=item.get("timestamp"),
                    runtimes=("vscode-compatible",),
                    source_url=f"https://open-vsx.org/extension/{namespace}/{name}",
                    provenance="OPEN_VSX_PUBLIC_REGISTRY_API",
                    security_evidence={"status": "NOT_ESTIMABLE"},
                    raw_evidence={"download_count": item.get("downloadCount"), "cache": meta},
                )
            )
        return records

    def resolve(self, identifier: str) -> ExtensionRecord:
        if "." not in identifier:
            raise ValueError("Open VSX identifiers use namespace.name")
        namespace, name = identifier.split(".", 1)
        value, meta = self.cache.get_json(
            f"https://open-vsx.org/api/{urllib.parse.quote(namespace)}/{urllib.parse.quote(name)}/latest"
        )
        return ExtensionRecord(
            provider=self.provider_id,
            identifier=identifier,
            version=value.get("version"),
            summary=str(value.get("description") or ""),
            license=value.get("license"),
            homepage=value.get("homepage"),
            repository=value.get("repository"),
            published_at=value.get("timestamp"),
            runtimes=("vscode-compatible",),
            source_url=f"https://open-vsx.org/extension/{namespace}/{name}",
            provenance="OPEN_VSX_PUBLIC_REGISTRY_API",
            security_evidence={"status": "NOT_ESTIMABLE"},
            raw_evidence={"cache": meta},
        )


class RuntimeInventory:
    def collect(self) -> dict[str, Any]:
        commands = {
            name: shutil.which(name)
            for name in (
                "python",
                "node",
                "npm",
                "npx",
                "code",
                "codex",
                "cline",
                "opencode",
                "opencode2",
                "git",
            )
        }
        versions: dict[str, dict[str, Any]] = {}
        for name, path in commands.items():
            if not path:
                versions[name] = {"state": "UNAVAILABLE", "path": None, "version": None}
                continue
            try:
                result = subprocess.run(
                    [path, "--version"], text=True, capture_output=True, timeout=10, check=False
                )
                versions[name] = {
                    "state": "AVAILABLE" if result.returncode == 0 else "UNAVAILABLE_EXECUTION",
                    "path": path,
                    "version": (result.stdout or result.stderr).strip().splitlines()[:3],
                    "returncode": result.returncode,
                }
            except (OSError, subprocess.SubprocessError) as exc:
                versions[name] = {
                    "state": "UNAVAILABLE_EXECUTION",
                    "path": path,
                    "version": None,
                    "error": str(exc),
                }
        extensions: list[str] = []
        code = commands.get("code")
        if code:
            try:
                result = subprocess.run(
                    [code, "--list-extensions", "--show-versions"],
                    text=True,
                    capture_output=True,
                    timeout=20,
                    check=False,
                )
                if result.returncode == 0:
                    extensions = sorted(
                        line.strip() for line in result.stdout.splitlines() if line.strip()
                    )
            except (OSError, subprocess.SubprocessError):
                pass
        home = Path.home()
        config_candidates = {
            "codex": [home / ".codex" / "config.toml"],
            "cline": [home / ".cline" / "data" / "settings" / "cline_mcp_settings.json"],
            "opencode": [
                home / ".config" / "opencode" / "opencode.json",
                home / ".config" / "opencode" / "opencode.jsonc",
            ],
        }
        configs = {
            host: [
                {
                    "path": str(path),
                    "exists": path.is_file(),
                    "bytes": path.stat().st_size if path.is_file() else None,
                }
                for path in paths
            ]
            for host, paths in config_candidates.items()
        }
        return {
            "schema": "kch.extension-runtime-inventory.v0.1.0",
            "collected_at": utc_now(),
            "platform": {
                "system": platform.system(),
                "release": platform.release(),
                "machine": platform.machine(),
            },
            "python": {"version": sys.version, "executable": sys.executable, "prefix": sys.prefix},
            "commands": versions,
            "vscode_extensions": extensions,
            "config_presence": configs,
            "secrets_read": False,
            "state_changed": False,
        }


class ExtensionFabric:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        cache = HttpCache(self.root / "cache")
        providers: list[DiscoveryProvider] = [
            PyPIProvider(cache),
            NpmProvider(cache),
            MCPRegistryProvider(cache),
            OpenVSXProvider(cache),
        ]
        self.providers = {provider.provider_id: provider for provider in providers}

    def describe(self) -> dict[str, Any]:
        return {
            "schema": "kch.extension-fabric-providers.v0.1.0",
            "providers": [provider.describe() for provider in self.providers.values()],
            "vscode_marketplace": {
                "capabilities": ["local_inventory", "workspace_recommendation"],
                "public_search": "UNAVAILABLE_PROVIDER_SUPPORTED_PUBLIC_API",
            },
            "additional_planned_ecosystems": [
                "conda",
                "oci",
                "winget",
                "homebrew",
                "apt",
                "crates",
                "go",
                "nuget",
                "maven",
            ],
        }

    def search(self, provider: str, query: str, limit: int = 10) -> list[dict[str, Any]]:
        if provider not in self.providers:
            raise KeyError(f"UNAVAILABLE_PROVIDER:{provider}")
        if not query.strip():
            raise ValueError("query cannot be empty")
        return [
            record.to_dict() for record in self.providers[provider].search(query.strip(), limit)
        ]

    def resolve(self, provider: str, identifier: str) -> dict[str, Any]:
        if provider not in self.providers:
            raise KeyError(f"UNAVAILABLE_PROVIDER:{provider}")
        return self.providers[provider].resolve(identifier).to_dict()


def _tokens(value: str) -> set[str]:
    return {
        item
        for item in re.findall(r"[a-z0-9]{3,}", value.lower())
        if item not in {"the", "and", "for", "with"}
    }


class RecommendationEngine:
    """Multi-lane adjudication. It deliberately emits no global scalar score."""

    APPROVED_LICENSES = frozenset(
        {"mit", "apache-2.0", "apache 2.0", "bsd-2-clause", "bsd-3-clause", "isc", "mpl-2.0"}
    )

    def evaluate(
        self,
        records: Iterable[dict[str, Any]],
        *,
        objective: str,
        available_runtimes: Iterable[str],
    ) -> list[dict[str, Any]]:
        objective_tokens = _tokens(objective)
        runtimes = {item.lower() for item in available_runtimes}
        results: list[dict[str, Any]] = []
        for record in records:
            record_tokens = _tokens(
                " ".join([str(record.get("identifier", "")), str(record.get("summary", ""))])
            )
            overlap = len(objective_tokens & record_tokens)
            fit = (
                None
                if not objective_tokens
                else min(1.0, overlap / max(1, min(4, len(objective_tokens))))
            )
            required = {str(item).lower() for item in record.get("runtimes", [])}
            compatibility: float | None
            if not required:
                compatibility = None
            elif any(
                any(
                    runtime.startswith(prefix)
                    or prefix.startswith(runtime)
                    or prefix in runtime
                    or runtime in prefix
                    for runtime in runtimes
                )
                for prefix in required
            ):
                compatibility = 1.0
            else:
                compatibility = 0.0
            license_value = str(record.get("license") or "").strip().lower()
            license_lane = (
                None
                if not license_value
                else (1.0 if license_value in self.APPROVED_LICENSES else 0.5)
            )
            provenance = 1.0 if record.get("source_url") and record.get("provenance") else None
            maintenance = 1.0 if record.get("version") else None
            reproducibility = 1.0 if record.get("version") else 0.0
            security_status = (record.get("security_evidence") or {}).get("status")
            security = None if security_status in {None, "NOT_ESTIMABLE"} else 1.0
            lanes = {
                "objective_fit": fit,
                "host_runtime_compatibility": compatibility,
                "authority_permissions": 1.0,
                "provenance": provenance,
                "maintenance": maintenance,
                "security": security,
                "license": license_lane,
                "cost_network": 0.5,
                "reproducibility_lock_rollback": reproducibility,
                "popularity_secondary": None,
            }
            if compatibility == 0.0:
                decision = "INCOMPATIBLE"
            elif provenance is None or compatibility is None:
                decision = "NOT_ESTIMABLE"
            elif fit is not None and fit >= 0.5 and license_lane == 1.0 and maintenance == 1.0:
                decision = "RECOMMEND"
            else:
                decision = "CONSIDER"
            results.append(
                {
                    "record": record,
                    "decision": decision,
                    "lanes": lanes,
                    "global_score": None,
                    "authority_created": False,
                    "installation_authorized": False,
                }
            )
        return results
