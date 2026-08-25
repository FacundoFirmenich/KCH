from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from scripts import extract_and_install as extractor_module
from scripts.build_portable_release import EXCLUDES

from scripts.extract_and_install import extract_exact, safe_member
from scripts.portable_bootstrap import (
    HOST_ADAPTER_FILENAMES,
    collect_host_adapters,
    render_codex_config,
)
from scripts.post_install_gate import resolve_runtime
from kch_studio.generators import resolve_system_skill_root


def test_system_creator_roots_follow_codex_home_and_explicit_override(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    codex_home = tmp_path / "portable-codex"
    override = tmp_path / "explicit-plugin-creator"
    monkeypatch.setenv("CODEX_HOME", str(codex_home))
    monkeypatch.delenv("KCH_SKILL_CREATOR_ROOT", raising=False)
    monkeypatch.setenv("KCH_PLUGIN_CREATOR_ROOT", str(override))

    assert resolve_system_skill_root("skill-creator", "KCH_SKILL_CREATOR_ROOT") == (
        codex_home / "skills" / ".system" / "skill-creator"
    ).resolve()
    assert resolve_system_skill_root("plugin-creator", "KCH_PLUGIN_CREATOR_ROOT") == (
        override.resolve()
    )


def test_short_extractor_preserves_bytes_and_rejects_nonempty_target(tmp_path: Path) -> None:
    archive = tmp_path / "candidate.zip"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr("KCH_0.11_PRE2G_R6/README.txt", b"exact bytes\n")
        stream.writestr("KCH_0.11_PRE2G_R6/deep/data.json", b"{}\n")
    target = tmp_path / "short"
    receipt = extract_exact(archive, target)
    assert receipt["file_count"] == 2
    assert (Path(receipt["package"]) / "README.txt").read_bytes() == b"exact bytes\n"
    with pytest.raises(ValueError, match="new or empty"):
        extract_exact(archive, target)


def test_short_extractor_uses_bounded_temporary_prefix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive = tmp_path / "long-name-candidate.zip"
    destination_name = ("x" * 120) + ".md"
    with zipfile.ZipFile(archive, "w") as stream:
        stream.writestr(f"KCH_0.11.34_PRE2G_R34/evidence/{destination_name}", b"bounded\n")

    observed_prefixes: list[str] = []
    real_mkstemp = extractor_module.tempfile.mkstemp

    def capture_mkstemp(*args: object, **kwargs: object) -> tuple[int, str]:
        observed_prefixes.append(str(kwargs["prefix"]))
        return real_mkstemp(*args, **kwargs)

    monkeypatch.setattr(extractor_module.tempfile, "mkstemp", capture_mkstemp)
    receipt = extract_exact(archive, tmp_path / "bounded")

    assert receipt["file_count"] == 1
    assert observed_prefixes == [".kch-part-"]
    assert destination_name not in observed_prefixes[0]

def test_short_extractor_rejects_zip_slip(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unsafe ZIP member"):
        safe_member(tmp_path, "../escape.txt")
    with pytest.raises(ValueError, match="unsafe ZIP member"):
        safe_member(tmp_path, "/absolute.txt")


def test_portable_receipt_enumerates_every_host_adapter_format(tmp_path: Path) -> None:
    adapters = tmp_path / "adapters_runtime"
    adapters.mkdir()
    for name in HOST_ADAPTER_FILENAMES:
        (adapters / name).write_text("generated\n", encoding="utf-8")

    observed = collect_host_adapters(adapters)

    assert [Path(path).name for path in observed] == list(HOST_ADAPTER_FILENAMES)
    assert "codex.config.toml" in observed[3]
    assert "AGENTS_KCH.md" in observed[0]


def test_portable_receipt_fails_closed_when_adapter_is_missing(tmp_path: Path) -> None:
    adapters = tmp_path / "adapters_runtime"
    adapters.mkdir()
    for name in HOST_ADAPTER_FILENAMES[1:]:
        (adapters / name).write_text("generated\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="AGENTS_KCH.md"):
        collect_host_adapters(adapters)


def test_codex_adapter_binds_all_canonical_roots_to_both_servers() -> None:
    environment = {
        "PYTHONUTF8": "1",
        "KCH_STUDIO_RUNTIME": r"D:\runtime\state",
        "KCH_MIS_ROOT": r"D:\package\mis",
        "KCH_CONSTRUCT_STABLE_ROOT": r"D:\package\source\kch-studio",
        "KCH_STORAGE_POLICY": "CLOUD_FIRST_LOCAL_MINIMAL",
    }
    rendered = render_codex_config(
        preflight_command=r"D:\runtime\kch-preflight.exe",
        bootstrap_command=r"D:\runtime\kch-bootstrap.exe",
        environment=environment,
    )

    for variable in environment:
        assert rendered.count(f"{variable} = ") == 2
    assert "[mcp_servers.kch_0_11_preflight.env]" in rendered
    assert "[mcp_servers.kch_0_11_bootstrap.env]" in rendered


def test_codex_adapter_fails_closed_on_incomplete_environment() -> None:
    with pytest.raises(ValueError, match="KCH_MIS_ROOT"):
        render_codex_config(
            preflight_command="preflight",
            bootstrap_command="bootstrap",
            environment={"KCH_STUDIO_RUNTIME": "state"},
        )


def test_post_install_gate_recovers_runtime_from_bootstrap_paths(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.delenv("KCH_RUNTIME_ROOT", raising=False)
    monkeypatch.delenv("KCH_PORTABLE_RUNTIME", raising=False)
    package = tmp_path / "package"
    package.mkdir()
    expected = tmp_path / "short-runtime"
    (package / "runtime_paths.cmd").write_text(
        f'@echo off\nset "KCH_RUNTIME_ROOT={expected}"\n', encoding="utf-8"
    )

    assert resolve_runtime(package) == expected.resolve()


def test_portable_release_excludes_installed_runtime_tree() -> None:
    assert "runtime" in EXCLUDES


def test_portable_contract_is_mcp_only() -> None:
    assert "msp.json" not in HOST_ADAPTER_FILENAMES
    assert not any("msp" in name.casefold() for name in HOST_ADAPTER_FILENAMES)
    assert {
        "cline_mcp_settings.json",
        "codex.config.toml",
        "vscode.mcp.json",
    } <= set(HOST_ADAPTER_FILENAMES)
