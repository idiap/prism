# SPDX-FileCopyrightText: © 2026 Idiap Research Institute <contact@idiap.ch>
# SPDX-FileContributor: Danilo Gusicuma <danilo.gusicuma@idiap.ch>
#
# SPDX-License-Identifier: MIT

import json
from pathlib import Path

from prism.tooling.cli import app
from typer.testing import CliRunner

RUNNER = CliRunner()


def _invoke_json(*args: str, expected_exit_code: int = 0) -> dict:
    result = RUNNER.invoke(app, list(args))
    assert result.exit_code == expected_exit_code, result.stdout
    return json.loads(result.stdout)


def test_cli_build_skill_emits_a_checked_typed_module(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "review"
    source.mkdir()
    skill = source / "SKILL.md"
    skill.write_text(
        "---\nname: review\ndescription: Review a supplied repository\n---\n"
        "Review the supplied repository.\n",
        encoding="utf-8",
    )
    contracts = tmp_path / "contracts.prism"
    contracts.write_text("type ReviewTask:\n    request: String\n", encoding="utf-8")
    output = tmp_path / "review_skill"

    monkeypatch.chdir(tmp_path)
    payload = _invoke_json(
        "build",
        "skill",
        str(source),
        "--contract",
        "contracts.ReviewTask",
        "--out",
        str(output),
    )

    assert payload["status"] == "built"
    assert payload["type"] == "Skill[ReviewTask]"
    assert output.with_suffix(".prism").is_file()


def test_cli_discovers_generated_project_for_absolute_source_path(
    tmp_path: Path, monkeypatch
) -> None:
    project = tmp_path / "projects" / "artifact_acceptance_loop" / "prism_project"
    project.mkdir(parents=True)
    (project / "runtime.json").write_text(
        '{"handler": "fake", "workspace": "."}\n', encoding="utf-8"
    )
    (project / "artifact_acceptance_loop.prism").write_text(
        "type ArtifactAcceptanceCase:\n    name: String\n", encoding="utf-8"
    )
    reasoning = project / "reasoning.prism"
    reasoning.write_text(
        "from artifact_acceptance_loop import ArtifactAcceptanceCase\n",
        encoding="utf-8",
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.delenv("PRISM_PROJECT_ROOT", raising=False)
    monkeypatch.chdir(outside)

    payload = _invoke_json("check", str(reasoning))

    assert payload["status"] == "ok"
    assert "ArtifactAcceptanceCase" in payload["declarations"]
