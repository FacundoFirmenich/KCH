from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from scripts.extract_and_install import extract_exact, safe_member
from scripts.portable_bootstrap import (
    HOST_ADAPTER_FILENAMES,
    collect_host_adapters,
    render_codex_config,
)
from scripts.post_install_gate import resolve_runtime


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
