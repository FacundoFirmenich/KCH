from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from scripts.extract_and_install import extract_exact, safe_member


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
