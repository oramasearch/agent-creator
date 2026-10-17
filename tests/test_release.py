"""The version in pyproject.toml has release notes, and the release index lists them."""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def project_version() -> str:
    # package = false: nothing is installed, so pyproject.toml is the one source of the version.
    with (ROOT / "pyproject.toml").open("rb") as file:
        return tomllib.load(file)["project"]["version"]


def test_release_notes_exist_for_project_version():
    version = project_version()
    notes = ROOT / "docs" / "releases" / f"v{version}.md"
    assert notes.is_file(), f"no release notes at {notes.relative_to(ROOT)}"

    heading = next(line for line in notes.read_text().splitlines() if line.startswith("# "))
    assert f"v{version}" in heading, f"the first heading does not name v{version}: {heading}"

    index = (ROOT / "docs" / "releases" / "README.md").read_text()
    assert f"[v{version}](v{version}.md)" in index, f"docs/releases/README.md does not list v{version}"
