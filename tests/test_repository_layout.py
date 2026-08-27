# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

"""Repository-root cleanliness invariants."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COPYRIGHT_TAG = "SPDX-FileCopyright" + "Text:"
LICENSE_TAG = "SPDX-License-" + "Identifier:"


def _spdx_header_precedes_content(text: str) -> bool:
    lines = text.removeprefix("\ufeff").splitlines()
    tag_index = next(
        (
            index
            for index, line in enumerate(lines)
            if COPYRIGHT_TAG in line or LICENSE_TAG in line
        ),
        None,
    )
    if tag_index is None:
        return True

    leading_lines = [line.strip() for line in lines[:tag_index] if line.strip()]
    if leading_lines and (
        leading_lines[0].startswith("#!")
        or leading_lines[0].startswith("<?xml")
        or leading_lines[0].lower().startswith("<!doctype")
        or leading_lines[0] == "---"
    ):
        leading_lines.pop(0)
    if leading_lines and leading_lines[0] in {"<!--", "/*"}:
        leading_lines.pop(0)
    return not leading_lines


def test_local_prism_directory_contains_only_runtime_state() -> None:
    prism_state = ROOT / ".prism"
    if prism_state.exists():
        assert {path.name for path in prism_state.iterdir()} <= {"kbs.yaml", "runs"}


def test_canonical_examples_have_a_language_boundary() -> None:
    assert (ROOT / "examples" / "language").is_dir()


def test_shared_vscode_configuration_is_not_ignored() -> None:
    ignore_rules = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".vscode/" not in ignore_rules
    settings = (ROOT / ".vscode" / "settings.json").read_text(encoding="utf-8")
    assert '"prismSolver.logging.includePayloads": false' in settings


def test_inline_spdx_headers_precede_file_content() -> None:
    tracked_files = (
        subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
        .stdout.decode()
        .split("\0")
    )
    misplaced_headers = []
    for relative_path in tracked_files:
        path = ROOT / relative_path
        if not relative_path or not path.is_file():
            continue
        contents = path.read_bytes()
        if b"SPDX-" not in contents:
            continue
        text = contents.decode("utf-8", errors="replace")
        if not _spdx_header_precedes_content(text):
            misplaced_headers.append(relative_path)

    assert not misplaced_headers, "SPDX header is not at the top of:\n" + "\n".join(
        misplaced_headers
    )
